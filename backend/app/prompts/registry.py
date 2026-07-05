from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..bootstrap import WORKSPACE_ROOT


PREFERRED_WEEK2_PROMPT_NAME = "\u667a\u5e8f\u77e5\u8bc6\u52a9\u624bprompt week 2.md"
PREFERRED_WEEK2_PROMPT_PATH = WORKSPACE_ROOT.parent.parent / "prompt" / PREFERRED_WEEK2_PROMPT_NAME


FALLBACK_PROMPTS: dict[str, str] = {
    "M2": (
        "You are module M2_topic_summary. Read the provided chunks and return only JSON "
        "with: meta, topic, summary, keywords, learning_scene, core_points, "
        "missing_information. Do not invent facts outside the chunks. "
        "Output all user-facing text in Simplified Chinese."
    ),
    "M3": (
        "You are module M3_structured_notes. Return only JSON with: meta, notes, "
        "global_summary, possible_risks. Use the semantic note contract exactly. "
        "Each note must use note_id, title, content, summary, keyPoints, examples, "
        "relations, blocks, level, note_type, source_refs, children. "
        "Each outline block should include structuredItems: [{text, children}]. "
        "Extract knowledge points dynamically from each section; do not force a fixed "
        "number of bullets. Merge line continuations, colon-completion fragments, "
        "and definitions for the same concept. Represent total-branch structures such "
        "as problems, effects, features, contents, and capabilities as one parent "
        "item with children instead of many top-level bullets. Keep low-value examples "
        "like model-name lists in examples, not as knowledge points. Drop contextless "
        "fragments such as isolated pronouns, empty input labels, or half examples. "
        "Do not paste raw chunks as the main note unless inside an evidence block. "
        "Output all note titles and content in Simplified Chinese."
    ),
    "M4": (
        "You are module M4_mindmap. Return only JSON with: meta and mindmap. "
        "The mindmap must use graph form: mindmap.nodes and mindmap.edges. "
        "Each node must include id, label, detail, related_note_id, source_refs. "
        "Each edge must include from, to, type, label, reason, confidence, source_refs. "
        "Allowed edge types are: hierarchy, prerequisite, component, mechanism, "
        "training-flow, evolution, application, contrast, evidence, solution. "
        "Do not create a flat star where every note connects directly to root. "
        "Group concepts into logical modules and connect modules by dependency, "
        "composition, mechanism, workflow, evolution, contrast, evidence, or solution "
        "relations when supported by notes. Preserve related_note_id and source_refs "
        "when available. Output all labels, details, reasons, and edge labels in "
        "Simplified Chinese."
    ),
    "M6": (
        "You are module M6_review_generation. Return only JSON with: meta and review. "
        "Generate review questions, weak points, recommendations, and link each "
        "question to related_note_id when possible. "
        "Output questions, answers, explanations, and recommendations in Simplified Chinese."
    ),
    "M7": (
        "You are module M7_note_chat. Answer the user question only from the provided "
        "notes, mindmap, citations, and retrieved sources. Return only JSON with: "
        "meta, answer, used_citations, related_notes, is_fully_supported_by_sources, "
        "unsupported_parts, follow_up_suggestions. Answer in Simplified Chinese."
    ),
}


@dataclass(frozen=True)
class PromptRegistry:
    prompts: dict[str, str]
    source: str

    @classmethod
    def load_default(cls) -> "PromptRegistry":
        prompt_dir = WORKSPACE_ROOT / "prompt"
        for path in _candidate_prompt_files(prompt_dir):
            raw_prompts = extract_module_prompts(path)
            if raw_prompts:
                runtime_prompts = build_runtime_prompts(raw_prompts)
                merged = {**FALLBACK_PROMPTS, **runtime_prompts}
                return cls(prompts=merged, source=str(path))
        return cls(prompts=dict(FALLBACK_PROMPTS), source="fallback-builtins")

    def get(self, module: str) -> str:
        key = module.upper()
        if key not in self.prompts:
            raise KeyError(f"Prompt module not registered: {module}")
        return self.prompts[key]



def extract_module_prompts(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig")
    prompts = _extract_markdown_module_prompts(text)
    if not prompts:
        prompts = _extract_legacy_prompt_blocks(text)
    security = _extract_security_rules(text)
    if security:
        prompts["SECURITY"] = security
    return prompts


def build_runtime_prompts(raw: dict[str, str]) -> dict[str, str]:
    security = raw.get("SECURITY", "")
    modules = {key: value for key, value in raw.items() if key != "SECURITY"}
    return _map_prompt_modules(modules, security)


def _extract_markdown_module_prompts(text: str) -> dict[str, str]:
    matches = re.finditer(
        r"\*\*[^\n]*(M\d)[^\n]*\*\*.*?\*\*Prompt\*\*\s*(.*?)(?=\n---|\Z)",
        text,
        flags=re.S,
    )
    prompts: dict[str, str] = {}
    for match in matches:
        module = match.group(1).upper()
        prompt = match.group(2).strip()
        if module and prompt:
            prompts[module] = prompt
    return prompts


def _extract_legacy_prompt_blocks(text: str) -> dict[str, str]:
    heading_pattern = re.compile(r"^###\s*(?:\*\*)?\s*[^\n]*?(M\d)\s*[?:?]?[^\n]*(?:\*\*)?\s*$", re.M)
    matches = list(heading_pattern.finditer(text))
    prompts: dict[str, str] = {}
    for index, match in enumerate(matches):
        module = match.group(1).upper()
        block_start = match.end()
        block_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[block_start:block_end].strip()
        prompt_marker = re.search(r"^\*\*Prompt\*\*\s*$", block, flags=re.M | re.I)
        if prompt_marker:
            block = block[prompt_marker.end():].strip()
        if not block or "not involve LLM" in block.lower():
            continue
        prompts[module] = block
    return prompts


def _extract_security_rules(text: str) -> str:
    match = re.search("(?:" + _zh([0x5b89,0x5168,0x89c4,0x5219]) + r"|security rules?).*", text, flags=re.S | re.I)
    if not match:
        return ""
    return match.group(0).strip()


def _map_prompt_modules(raw: dict[str, str], security: str = "") -> dict[str, str]:
    prompts: dict[str, str] = {}

    def with_contract(module: str, body: str) -> str:
        additions = {
            "M2": FALLBACK_PROMPTS["M2"],
            "M3": FALLBACK_PROMPTS["M3"],
            "M4": FALLBACK_PROMPTS["M4"],
            "M6": FALLBACK_PROMPTS["M6"],
            "M7": FALLBACK_PROMPTS["M7"],
        }
        parts = [body.strip(), additions.get(module, "").strip()]
        if security:
            parts.append(security)
        return "\n\n".join(part for part in parts if part)

    # Week 2 names M1 as topic/summary. Current backend names that runtime module M2.
    if raw.get("M1"):
        prompts["M2"] = with_contract("M2", raw["M1"])
    elif raw.get("M2"):
        prompts["M2"] = with_contract("M2", raw["M2"])

    # Current M3 performs structured-note generation and normalization; combine Week 2 M2 and M3 when available.
    note_parts = [raw.get("M2", ""), raw.get("M3", "")]
    note_prompt = "\n\n".join(part.strip() for part in note_parts if part and part.strip())
    if note_prompt:
        prompts["M3"] = with_contract("M3", note_prompt)

    if raw.get("M4"):
        prompts["M4"] = with_contract("M4", raw["M4"])
    if raw.get("M6"):
        # Week 2 M7 is assessment/advice. Current review module can consume those requirements as part of review output.
        body = "\n\n".join(part for part in [raw.get("M6", ""), raw.get("M7", "")] if part)
        prompts["M6"] = with_contract("M6", body)
    if raw.get("M8"):
        prompts["M7"] = with_contract("M7", raw["M8"])
    elif raw.get("M7"):
        prompts["M7"] = with_contract("M7", raw["M7"])
    return prompts


def _candidate_prompt_files(prompt_dir: Path) -> list[Path]:
    roots = []
    for root in [prompt_dir, WORKSPACE_ROOT.parent.parent / "prompt", WORKSPACE_ROOT.parent / "prompt"]:
        if root.exists() and root not in roots:
            roots.append(root)
    files: list[Path] = []
    for root in roots:
        files.extend(sorted(root.glob("*.md")))
    exact_path = PREFERRED_WEEK2_PROMPT_PATH.resolve()
    exact = [
        path
        for path in files
        if path.resolve() == exact_path
    ]
    same_name = [
        path
        for path in files
        if path.name == PREFERRED_WEEK2_PROMPT_NAME and path not in exact
    ]
    preferred = [
        path
        for path in files
        if ("week 2" in path.name.lower() or "week2" in path.name.lower()) and path not in exact and path not in same_name
    ]
    secondary = [
        path
        for path in files
        if ("week 1" in path.name.lower() or "week1" in path.name.lower()) and path not in preferred
    ]
    return exact + same_name + preferred + secondary + [
        path
        for path in files
        if path not in exact and path not in same_name and path not in preferred and path not in secondary
    ]


def _zh(codepoints: list[int]) -> str:
    return "".join(chr(code) for code in codepoints)
