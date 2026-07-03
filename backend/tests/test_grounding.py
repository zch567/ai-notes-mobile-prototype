from app.rag.grounding import build_grounding_query, clear_grounding_cache, ground_result, validate_result
from app.rag.schemas import SourceChunk


def make_chunk(index: int, text: str, *, heading: str = "", source_ref: str | None = None) -> SourceChunk:
    return SourceChunk(
        id=f"c{index}",
        sourceId="doc",
        title=heading or f"chunk {index}",
        text=text,
        sourceType="text",
        fileName="sample.md",
        chunkIndex=index,
        sourceRef=source_ref or f"para_{index}",
        heading=heading,
        keywords=["grounding", "evidence"] if index == 2 else [],
    )


def base_result(note: dict) -> dict:
    return {
        "id": "r1",
        "topic": "RAG",
        "summary": "summary",
        "agentStages": [],
        "sources": [],
        "notes": [note],
        "citations": [],
        "mindMap": {"nodes": [], "edges": []},
        "review": {"questions": []},
    }


def test_build_grounding_query_uses_note_structure_and_source_heading():
    chunks = [make_chunk(1, "RAG grounding evidence text", heading="Grounding Section")]
    note = {
        "id": "n1",
        "title": "Grounding",
        "summary": "Connect notes to evidence.",
        "keyPoints": ["citation", "source"],
        "blocks": [{"type": "evidence", "items": ["quote must exist"]}],
        "source_refs": ["c1"],
    }

    query = build_grounding_query(note, chunks)

    assert "title" in query["querySources"]
    assert "summary" in query["querySources"]
    assert "keyPoints" in query["querySources"]
    assert "sourceHeading" in query["querySources"]
    assert "Grounding Section" in query["rawQuery"]


def test_ground_result_prefers_explicit_source_and_adds_support_trace():
    chunks = [
        make_chunk(1, "Unrelated overview text."),
        make_chunk(2, "Grounding citations connect generated notes to source evidence.", heading="Grounding", source_ref="sec-ground"),
    ]
    note = {
        "id": "n1",
        "title": "Grounding citations",
        "content": "Grounding citations connect generated notes to source evidence.",
        "source_refs": ["c2"],
    }

    grounded = ground_result(base_result(note), chunks, top_k=1)
    out_note = grounded["notes"][0]

    assert out_note["citationIds"] == ["c2"]
    assert out_note["groundingTrace"]["selectionReasons"] == ["explicit-high-support"]
    assert out_note["support"]["score"] > 0
    assert grounded["citations"][0]["support"]["quoteExistsInSource"] is True
    assert grounded["citationDiagnostics"]["quoteInSourceRate"] == 1


def test_low_support_note_is_marked_and_diagnostics_reported():
    chunks = [make_chunk(1, "RAG uses retrieval evidence to ground generated notes.")]
    note = {
        "id": "n1",
        "title": "Quantum biology",
        "content": "This document proves a claim about unrelated quantum biology and cell mutation.",
    }

    grounded = ground_result(base_result(note), chunks, top_k=1)
    out_note = grounded["notes"][0]
    diagnostics = validate_result(grounded, chunks)

    assert out_note["support"]["level"] in {"low", "unsupported"}
    assert "low_note_source_support" in out_note.get("quality_issues", [])
    assert diagnostics["lowSupportNoteRate"] == 1
    assert "averageNoteSupportScore" in diagnostics


def test_grounding_reports_perf_diagnostics():
    chunks = [make_chunk(1, "Grounding citations connect notes to source evidence.", heading="Grounding")]
    note = {"id": "n1", "title": "Grounding citations", "content": "Grounding citations connect notes to source evidence."}

    grounded = ground_result(base_result(note), chunks, top_k=1)
    perf = grounded["citationDiagnostics"]["groundingPerf"]

    assert perf["chunkCount"] == 1
    assert perf["noteCount"] == 1
    assert perf["retrievalCalls"] == 1
    assert len(perf["corpusHash"]) == 40
    assert perf["elapsedMs"] >= 0


def test_grounding_reuses_retriever_cache_for_same_corpus():
    clear_grounding_cache()
    chunks = [make_chunk(1, "Grounding citations connect notes to source evidence.", heading="Grounding")]
    note = {"id": "n1", "title": "Grounding citations", "content": "Grounding citations connect notes to source evidence."}

    first = ground_result(base_result(note), chunks, top_k=1)
    second = ground_result(base_result(note), chunks, top_k=1)

    assert first["citationDiagnostics"]["groundingPerf"]["retrieverCacheHit"] is False
    assert second["citationDiagnostics"]["groundingPerf"]["retrieverCacheHit"] is True
    assert second["citationDiagnostics"]["groundingPerf"]["retrieverCacheSize"] == 1
