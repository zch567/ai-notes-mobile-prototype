from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_rag_grounding_audit_script_outputs_report(tmp_path: Path):
    input_file = tmp_path / "sample.md"
    input_file.write_text("# RAG\n\nRAG uses retrieval evidence to ground generated notes and citations.", encoding="utf-8")
    out_dir = tmp_path / "audit"

    completed = subprocess.run(
        [sys.executable, "scripts/rag_grounding_audit.py", "--input", str(input_file), "--out", str(out_dir), "--strict"],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    report = json.loads((out_dir / "rag_grounding_audit.json").read_text(encoding="utf-8"))

    assert Path(payload["json"]).exists()
    assert (out_dir / "rag_grounding_audit.md").exists()
    assert report["summary"]["total"] == 1
    assert report["summary"]["blockingFailureCount"] == 0
    assert report["cases"][0]["groundingPerf"]["corpusHash"]
