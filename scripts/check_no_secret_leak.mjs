import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const defaultSecretPath = "D:\\AIGC\\api";
const secretPath = process.env.BACKEND_SECRETS_FILE || defaultSecretPath;
const targets = process.argv.slice(2).map((item) => path.resolve(root, item));

if (targets.length === 0) {
  targets.push(path.join(root, "dist"), path.join(root, "dist-webview"));
}

const forbiddenBasenames = new Set([".env", "api"]);
const forbiddenRelativePaths = new Set([
  "backend/.env",
  "backend/api",
  ".env",
  "api",
]);

const skipDirs = new Set([
  ".git",
  "node_modules",
  ".pytest_cache",
  ".venv",
  "venv",
  "runtime",
  "reports",
  "evaluation_outputs",
]);

const secrets = await loadSecrets(secretPath);
const findings = [];

for (const target of targets) {
  if (!(await exists(target))) {
    continue;
  }
  await scanPath(target, target);
}

if (findings.length > 0) {
  console.error("[secret-check] Potential secret leak detected:");
  for (const finding of findings) {
    console.error(`- ${finding.reason}: ${finding.file}`);
  }
  process.exit(1);
}

console.log(`[secret-check] OK. Scanned ${targets.length} target(s); no API key material or local secret files found.`);

async function loadSecrets(file) {
  const values = new Set();
  if (await exists(file)) {
    const content = await fs.readFile(file, "utf8");
    for (const rawLine of content.split(/\r?\n/)) {
      const line = rawLine.trim();
      if (!line || line.startsWith("#")) continue;
      const value = line.includes("=") ? line.split("=").slice(1).join("=").trim() : line;
      const cleaned = value.replace(/^['"]|['"]$/g, "");
      if (cleaned.length >= 8) values.add(cleaned);
    }
  }
  for (const name of ["LANXIN_API_KEY"]) {
    const value = process.env[name];
    if (value && value.length >= 8) values.add(value);
  }
  return [...values];
}

async function scanPath(current, targetRoot) {
  const stat = await fs.stat(current);
  const relative = normalizeRelative(path.relative(targetRoot, current));
  const rootRelative = normalizeRelative(path.relative(root, current));

  if (stat.isDirectory()) {
    if (skipDirs.has(path.basename(current))) return;
    for (const entry of await fs.readdir(current)) {
      await scanPath(path.join(current, entry), targetRoot);
    }
    return;
  }

  if (!stat.isFile()) return;

  const basename = path.basename(current);
  if (forbiddenBasenames.has(basename) || forbiddenRelativePaths.has(relative) || forbiddenRelativePaths.has(rootRelative)) {
    findings.push({ reason: "local secret file included", file: current });
    return;
  }

  if (stat.size > 10 * 1024 * 1024) return;
  const buffer = await fs.readFile(current);
  if (buffer.includes(0)) return;
  const text = buffer.toString("utf8");
  for (const secret of secrets) {
    if (secret && text.includes(secret)) {
      findings.push({ reason: "API key material included", file: current });
      return;
    }
  }
}

async function exists(file) {
  try {
    await fs.access(file);
    return true;
  } catch {
    return false;
  }
}

function normalizeRelative(value) {
  return value.replaceAll(path.sep, "/");
}
