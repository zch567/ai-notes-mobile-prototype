from pathlib import Path

from app.agents.orchestrator import (
    build_agent_result_from_modules,
    convert_mindmap,
    normalize_chunks_for_prompt,
)
from app.prompts.registry import PromptRegistry, extract_module_prompts
from app.rag.grounding import ground_result
from app.rag.schemas import SourceChunk


def chunk() -> SourceChunk:
    return SourceChunk(
        id="sample-doc-c0001",
        sourceId="sample-doc",
        title="RAG",
        text="RAG uses retrieval results to constrain generation and provide grounded citations.",
        sourceType="text",
        fileName="sample.md",
        chunkIndex=1,
        sourceRef="para_1",
        heading="RAG",
        paragraphStart=1,
        paragraphEnd=1,
    )


def test_prompt_registry_extracts_week_modules():
    registry = PromptRegistry.load_default()

    assert {"M2", "M3", "M4", "M6", "M7"} <= set(registry.prompts)
    assert registry.get("M2")


def test_extract_module_prompts_from_minimal_file(tmp_path: Path):
    prompt = tmp_path / "prompt.md"
    prompt.write_text(
        "**模块 M2：主题识别**\n\n**Prompt**\n\nReturn M2 JSON.\n\n---\n"
        "**模块 M3：笔记生成**\n\n**Prompt**\n\nReturn M3 JSON.\n",
        encoding="utf-8",
    )

    prompts = extract_module_prompts(prompt)

    assert prompts["M2"] == "Return M2 JSON."
    assert prompts["M3"] == "Return M3 JSON."


def test_prompt_chunk_normalization_keeps_source_id():
    normalized = normalize_chunks_for_prompt([chunk()])

    assert normalized[0]["source_id"] == "sample-doc-c0001"
    assert normalized[0]["heading"] == "RAG"


def test_mindmap_converter_handles_tree_and_frontend_nodes():
    notes = [{"id": "n1", "title": "RAG", "content": "Retrieval grounded generation.", "citationIds": []}]
    tree = {
        "root": {
            "node_id": "m0",
            "title": "RAG",
            "children": [{"node_id": "m1", "title": "Grounding", "related_note_id": "n1", "children": []}],
        }
    }
    frontend = {"nodes": [{"id": "x1", "label": "RAG"}], "edges": []}

    tree_result = convert_mindmap(tree, "RAG", notes)
    frontend_result = convert_mindmap(frontend, "RAG", notes)

    assert tree_result["nodes"][1]["relatedNoteId"] == "n1"
    assert tree_result["edges"][0] == {
        "from": "m0",
        "to": "m1",
        "type": "hierarchy",
        "label": "归属",
        "reason": "Tree parent-child relation returned by M4.",
        "confidence": 0.72,
        "source_refs": [],
    }
    assert frontend_result["nodes"][0]["id"] == "x1"


def test_modular_outputs_are_grounded_into_agent_contract():
    source_chunk = chunk()
    outputs = {
        "M2": {
            "topic": "RAG",
            "summary": "RAG grounds generated answers in retrieved sources.",
            "keywords": ["RAG", "retrieval"],
            "core_points": [{"point_id": "p1", "title": "Grounding", "brief": "Use retrieval.", "source_refs": [source_chunk.id]}],
        },
        "M3": {
            "notes": [
                {
                    "note_id": "n1",
                    "title": "Grounding",
                    "content": "RAG uses retrieval results to constrain generation.",
                    "level": 1,
                    "source_refs": [source_chunk.id],
                    "children": [],
                }
            ]
        },
        "M4": {"mindmap": {"root": {"node_id": "m0", "title": "RAG", "children": []}}},
        "M6": {
            "review": {
                "questions": [
                    {
                        "question_id": "q1",
                        "question": "How does RAG constrain generation?",
                        "answer": "By using retrieval results.",
                        "related_note_id": "n1",
                    }
                ]
            }
        },
    }

    draft = build_agent_result_from_modules(outputs, [source_chunk], input_path=None, prompt_source="test")
    grounded = ground_result(draft, [source_chunk], top_k=1)

    assert grounded["notes"][0]["citationIds"] == [source_chunk.id]
    assert grounded["review"]["questions"][0]["citationIds"] == [source_chunk.id]
    assert grounded["citations"][0]["noteId"] == "n1"
