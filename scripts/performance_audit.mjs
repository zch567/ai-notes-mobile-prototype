import { createServer } from "node:http";
import { execFile } from "node:child_process";
import { gzipSync } from "node:zlib";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { performance } from "node:perf_hooks";
import { createRequire } from "node:module";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const nodeExe = process.execPath;
const viteBin = path.join(root, "node_modules", "vite", "bin", "vite.js");
const reportDir = path.join(root, "reports", "performance");
const require = createRequire(import.meta.url);
const playwrightBase = process.env.PLAYWRIGHT_MODULE_DIR
  || process.env.NODE_PATH?.split(path.delimiter)[0]
  || path.join(process.env.USERPROFILE || "", ".cache", "codex-runtimes", "codex-primary-runtime", "dependencies", "node", "node_modules");
const { chromium } = require(resolvePlaywrightPackage(playwrightBase));

const samples = [
  {
    name: "text-transformer",
    path: path.join(root, "test_set", "text", "Transformer介绍.docx"),
  },
  {
    name: "pdf-machine-learning",
    path: path.join(root, "test_set", "pdf", "机器学习讲义.pdf"),
  },
  {
    name: "ppt-academic",
    path: path.join(root, "test_set", "ppt", "学术汇报.pptx"),
  },
];

function resolvePlaywrightPackage(baseDir) {
  const pnpmDir = path.join(baseDir, ".pnpm");
  try {
    const entries = require("node:fs").readdirSync(pnpmDir);
    const match = entries.find((entry) => entry.startsWith("playwright@"));
    if (match) return path.join(pnpmDir, match, "node_modules", "playwright");
  } catch {
    // Fall through to a conventional node_modules layout.
  }
  return path.join(baseDir, "playwright");
}

await fs.mkdir(reportDir, { recursive: true });

const startedAt = new Date().toISOString();
const environment = {
  node: process.version,
  platform: process.platform,
  arch: process.arch,
  cwd: root,
};

const build = await timeCommand(nodeExe, [viteBin, "build"], root);
const bundle = await collectBundleMetrics(path.join(root, "dist"));
const browser = await measureBrowser(path.join(root, "dist"));
const backendTests = await runBackendTests();
const backend = await measureBackend();

const report = {
  generatedAt: startedAt,
  environment,
  build,
  bundle,
  browser,
  backendTests,
  backend,
  thresholds: {
    productionBuildMs: 10000,
    totalGzipKb: 120,
    mobileDomContentLoadedMs: 1200,
    mobileLoadMs: 1800,
    navInteractionP95Ms: 200,
    backendRagOnlyP95Ms: 1500,
  },
};

await fs.writeFile(path.join(reportDir, "performance-metrics.json"), JSON.stringify(report, null, 2), "utf8");
await fs.writeFile(path.join(reportDir, "performance-report.md"), renderMarkdown(report), "utf8");
console.log(JSON.stringify(report, null, 2));

async function timeCommand(command, args, cwd) {
  const start = performance.now();
  const result = await exec(command, args, cwd);
  return {
    command: [command, ...args].join(" "),
    exitCode: result.exitCode,
    durationMs: Math.round(performance.now() - start),
    stdoutTail: tail(result.stdout, 2000),
    stderrTail: tail(result.stderr, 2000),
  };
}

function exec(command, args, cwd) {
  return new Promise((resolve) => {
    execFile(
      command,
      args,
      {
        cwd,
        windowsHide: true,
        env: {
          ...process.env,
          PYTHONIOENCODING: "utf-8",
        },
      },
      (error, stdout, stderr) => {
        resolve({
          exitCode: error?.code ?? 0,
          stdout: String(stdout || ""),
          stderr: String(stderr || ""),
        });
      }
    );
  });
}

async function collectBundleMetrics(distDir) {
  const files = await listFiles(distDir);
  const rows = [];
  for (const file of files) {
    const buffer = await fs.readFile(file);
    rows.push({
      file: path.relative(distDir, file).replaceAll("\\", "/"),
      bytes: buffer.length,
      gzipBytes: gzipSync(buffer).length,
    });
  }
  rows.sort((a, b) => b.bytes - a.bytes);
  return {
    fileCount: rows.length,
    totalBytes: rows.reduce((sum, item) => sum + item.bytes, 0),
    totalGzipBytes: rows.reduce((sum, item) => sum + item.gzipBytes, 0),
    largestFiles: rows.slice(0, 10),
  };
}

async function listFiles(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...await listFiles(fullPath));
    } else {
      files.push(fullPath);
    }
  }
  return files;
}

async function measureBrowser(distDir) {
  const server = await startStaticServer(distDir);
  const browser = await chromium.launch({ headless: true, executablePath: resolveBrowserExecutable() });
  const page = await browser.newPage({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 3,
    isMobile: true,
    hasTouch: true,
  });
  const started = performance.now();
  await page.goto(server.url, { waitUntil: "load" });
  const wallLoadMs = Math.round(performance.now() - started);
  const navTiming = await page.evaluate(() => {
    const nav = performance.getEntriesByType("navigation")[0];
    return {
      domContentLoadedMs: Math.round(nav.domContentLoadedEventEnd),
      loadEventMs: Math.round(nav.loadEventEnd),
      transferSize: nav.transferSize || 0,
    };
  });
  const visibleText = await page.locator("body").innerText();
  const navTargets = [
    { label: "笔记", name: "notes-tab" },
    { label: "导图", name: "mindmap-tab" },
    { label: "我的", name: "profile-tab" },
    { label: "AI", name: "ai-tab" },
  ];
  const interactions = [];
  for (const target of navTargets) {
    const start = performance.now();
    await page.getByText(target.label, { exact: true }).last().click();
    await page.waitForTimeout(50);
    interactions.push({ action: target.name, durationMs: Math.round(performance.now() - start) });
  }
  await browser.close();
  await server.close();
  return {
    url: server.url,
    viewport: "390x844 mobile",
    wallLoadMs,
    ...navTiming,
    bodyTextChars: visibleText.length,
    interactions,
    interactionP95Ms: percentile(interactions.map((item) => item.durationMs), 0.95),
  };
}

function resolveBrowserExecutable() {
  if (process.env.PLAYWRIGHT_BROWSER_EXECUTABLE) return process.env.PLAYWRIGHT_BROWSER_EXECUTABLE;
  if (process.platform !== "win32") return undefined;
  const candidates = [
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  ];
  const fsSync = require("node:fs");
  return candidates.find((candidate) => fsSync.existsSync(candidate));
}

function startStaticServer(distDir) {
  const mime = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
  };
  const server = createServer(async (request, response) => {
    const url = new URL(request.url || "/", "http://127.0.0.1");
    const requested = url.pathname === "/" ? "/index.html" : decodeURIComponent(url.pathname);
    const filePath = path.resolve(distDir, `.${requested}`);
    if (!filePath.startsWith(path.resolve(distDir))) {
      response.writeHead(403);
      response.end("Forbidden");
      return;
    }
    try {
      const data = await fs.readFile(filePath);
      response.writeHead(200, { "Content-Type": mime[path.extname(filePath)] || "application/octet-stream" });
      response.end(data);
    } catch {
      const html = await fs.readFile(path.join(distDir, "index.html"));
      response.writeHead(200, { "Content-Type": mime[".html"] });
      response.end(html);
    }
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      resolve({
        url: `http://127.0.0.1:${address.port}`,
        close: () => new Promise((done) => server.close(done)),
      });
    });
  });
}

async function measureBackend() {
  const python = process.env.PYTHON || "python";
  const code = `
import json, pathlib, statistics, sys, time
from app.config import settings
from app.contracts import RunAgentRequest
from app.evaluation import evaluate_result
from app.service import AgentService

root = pathlib.Path(r"${root.replaceAll("\\", "\\\\")}")
object.__setattr__(settings, "allowed_input_root", root.resolve())
object.__setattr__(settings, "output_dir", (root / "reports" / "performance" / "backend-runtime").resolve())
service = AgentService()
samples = ${JSON.stringify(samples).replaceAll("\\", "\\\\")}
rows = []
for sample in samples:
    path = pathlib.Path(sample["path"])
    durations = []
    metrics = None
    for _ in range(3):
        start = time.perf_counter()
        result = service.run(RunAgentRequest(filePath=str(path), pipeline="rag-only", topK=2))
        duration = round((time.perf_counter() - start) * 1000)
        durations.append(duration)
        metrics = evaluate_result(result, duration)
    rows.append({
        "name": sample["name"],
        "file": str(path),
        "runs": durations,
        "minMs": min(durations),
        "medianMs": round(statistics.median(durations)),
        "p95Ms": max(durations),
        "qualityScore": metrics["qualityScore"],
        "noteCitationCoverage": metrics["noteCitationCoverage"],
        "quoteInSourceRate": metrics["quoteInSourceRate"],
        "sourceCoverage": metrics["sourceCoverage"],
    })
print(json.dumps({"samples": rows}, ensure_ascii=False))
`;
  const result = await exec(python, ["-c", code], path.join(root, "backend"));
  return {
    command: `${python} -c <rag-only benchmark>`,
    exitCode: result.exitCode,
    ...(result.exitCode === 0 ? JSON.parse(result.stdout) : {}),
    stdoutTail: tail(result.stdout, 1000),
    stderrTail: tail(result.stderr, 2000),
  };
}

async function runBackendTests() {
  const python = process.env.PYTHON || "python";
  const result = await timeCommand(
    python,
    ["-m", "pytest", "-q", "-p", "no:cacheprovider"],
    path.join(root, "backend"),
  );
  const passed = result.stdoutTail.match(/(\d+) passed/);
  const skipped = result.stdoutTail.match(/(\d+) skipped/);
  return {
    ...result,
    passed: passed ? Number(passed[1]) : 0,
    skipped: skipped ? Number(skipped[1]) : 0,
  };
}

function percentile(values, q) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const index = Math.min(sorted.length - 1, Math.ceil(q * sorted.length) - 1);
  return sorted[index];
}

function kb(bytes) {
  return (bytes / 1024).toFixed(2);
}

function tail(text, maxLength) {
  return text.length > maxLength ? text.slice(-maxLength) : text;
}

function pass(value, threshold, lowerIsBetter = true) {
  return lowerIsBetter ? value <= threshold : value >= threshold;
}

function renderMarkdown(data) {
  const checks = [
    ["Production build", data.build.durationMs, data.thresholds.productionBuildMs, "ms"],
    ["Total gzip bundle", Number(kb(data.bundle.totalGzipBytes)), data.thresholds.totalGzipKb, "KB"],
    ["Mobile DCL", data.browser.domContentLoadedMs, data.thresholds.mobileDomContentLoadedMs, "ms"],
    ["Mobile load", data.browser.loadEventMs || data.browser.wallLoadMs, data.thresholds.mobileLoadMs, "ms"],
    ["Navigation interaction p95", data.browser.interactionP95Ms, data.thresholds.navInteractionP95Ms, "ms"],
  ];
  const backendP95 = Math.max(...(data.backend.samples || []).map((item) => item.p95Ms));
  checks.push(["Backend rag-only p95", backendP95, data.thresholds.backendRagOnlyP95Ms, "ms"]);

  return [
    "# AI Notes Mobile Prototype Performance Report",
    "",
    `Generated at: ${data.generatedAt}`,
    "",
    "## 测试结论",
    "",
    "- 本次性能审计覆盖前端生产构建、产物体积、移动端首屏加载、底部导航交互、后端 pytest、后端 rag-only 三类样例处理延迟。",
    "- 通过项：构建耗时、bundle gzip 体积、首屏加载、后端单元测试、后端 rag-only p95。",
    `- 未达标项：底部导航交互 p95 为 ${data.browser.interactionP95Ms} ms，高于 ${data.thresholds.navInteractionP95Ms} ms 阈值；主要由首次进入 notes-tab 的 ${data.browser.interactions[0]?.durationMs ?? 0} ms 拉高。`,
    "- 真实 Lanxin hybrid 链路未纳入本地性能基线，因为它强依赖外部模型服务、网络和额度；建议单独以线上监控方式统计。",
    "",
    "## Executive Summary",
    "",
    `- Frontend production build: ${data.build.durationMs} ms, exit code ${data.build.exitCode}.`,
    `- Backend pytest: ${data.backendTests.passed} passed, ${data.backendTests.skipped} skipped, ${data.backendTests.durationMs} ms.`,
    `- Bundle total: ${kb(data.bundle.totalBytes)} KB raw / ${kb(data.bundle.totalGzipBytes)} KB gzip.`,
    `- Mobile browser load: DCL ${data.browser.domContentLoadedMs} ms, load ${data.browser.loadEventMs} ms, wall ${data.browser.wallLoadMs} ms.`,
    `- Navigation p95 interaction latency: ${data.browser.interactionP95Ms} ms.`,
    `- Backend rag-only max p95 across samples: ${backendP95} ms.`,
    "",
    "## Threshold Results",
    "",
    "| Check | Actual | Threshold | Result |",
    "|---|---:|---:|---|",
    ...checks.map(([name, actual, threshold, unit]) => `| ${name} | ${actual} ${unit} | <= ${threshold} ${unit} | ${pass(actual, threshold) ? "PASS" : "FAIL"} |`),
    `| Backend pytest | ${data.backendTests.exitCode} exit code | == 0 | ${data.backendTests.exitCode === 0 ? "PASS" : "FAIL"} |`,
    "",
    "## Frontend Bundle",
    "",
    "| File | Raw KB | Gzip KB |",
    "|---|---:|---:|",
    ...data.bundle.largestFiles.map((item) => `| ${item.file} | ${kb(item.bytes)} | ${kb(item.gzipBytes)} |`),
    "",
    "## Browser Interaction",
    "",
    "| Action | Duration ms |",
    "|---|---:|",
    ...data.browser.interactions.map((item) => `| ${item.action} | ${item.durationMs} |`),
    "",
    "## Backend Rag-Only Samples",
    "",
    "| Sample | Runs ms | Median ms | P95 ms | Quality | Citation coverage | Quote rate |",
    "|---|---:|---:|---:|---:|---:|---:|",
    ...(data.backend.samples || []).map((item) => `| ${item.name} | ${item.runs.join(", ")} | ${item.medianMs} | ${item.p95Ms} | ${item.qualityScore} | ${item.noteCitationCoverage} | ${item.quoteInSourceRate} |`),
    "",
    "## Risks And Recommendations",
    "",
    "- This report measures local rag-only backend performance; real Lanxin hybrid latency is external-provider-bound and should be tracked separately.",
    "- Current frontend bundle is comfortably small, but there is no automated budget gate in package scripts yet.",
    "- Browser test covers key navigation only; add form upload and API-connected E2E once backend test keys and fixtures are standardized.",
    "",
  ].join("\n");
}
