#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.rag.chunking import build_chunks
from app.rag.parsing import diagnose_parsing, get_document_stats, parse_document


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose backend parsing quality.")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()

    stats = get_document_stats(args.path)
    blocks = parse_document(args.path)
    chunks = build_chunks(blocks)
    diagnosis = diagnose_parsing(
        blocks,
        file_name=args.path.name,
        source_type=args.path.suffix.lstrip(".").lower(),
        total_pages=stats.get("total_pages", 0),
        total_slides=stats.get("total_slides", 0),
        chunk_count=len(chunks),
    )
    payload = {
        "stats": stats,
        "diagnosis": diagnosis.to_dict(),
        "blocks": len(blocks),
        "chunks": len(chunks),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
