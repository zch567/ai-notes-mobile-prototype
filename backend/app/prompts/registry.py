from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..bootstrap import WORKSPACE_ROOT


FALLBACK_PROMPTS: dict[str, str] = {
    "M2": (
        "You are module M2_topic_summary. Read the provided chunks and return only JSON "
        "with: meta, topic, summary, keywords, learning_scene, core_points, "
        "missing_information. Do not invent facts outside the chunks."
    ),
    "M3": (
        "You are module M3_structured_notes. Return only JSON with: meta, notes, "
        "global_summary, possible_risks. Notes must use note_id, title, content, "
        "level, note_type, source_refs, children."
    ),
    "M4": (
        "You are module M4_mindmap. Return only JSON with: meta and mindmap.root. "
        "Build a compact tree from the provided notes and preserve related_note_id "
        "and source_refs when available."
    ),
    "M6": (
        "You are module M6_review_generation. Return only JSON with: meta and review. "
        "Generate review questions, weak points, recommendations, and link each "
        "question to related_note_id when possible."
    ),
    "M7": (
        "You are module M7_note_chat. Answer the user question only from the provided "
        "notes, mindmap, citations, and retrieved sources. Return only JSON with: "
        "meta, answer, used_citations, related_notes, is_fully_supported_by_sources, "
        "unsupported_parts, follow_up_suggestions."
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
            prompts = extract_module_prompts(path)
            if prompts:
                merged = {**FALLBACK_PROMPTS, **prompts}
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


def _candidate_prompt_files(prompt_dir: Path) -> list[Path]:
    if not prompt_dir.exists():
        return []
    files = sorted(prompt_dir.glob("*.md"))
    preferred = [
        path
        for path in files
        if "week 1" in path.name.lower() or "week1" in path.name.lower()
    ]
    return preferred + [path for path in files if path not in preferred]
