from app.rag.llm_polish import apply_polish_result
from app.rag.schemas import SourceChunk


def source_chunk(chunk_id: str = "c1") -> SourceChunk:
    return SourceChunk(
        id=chunk_id,
        sourceId="doc",
        title="DMA",
        heading="DMA",
        text="DMA 通过直接数据通路传送数据，减少 CPU 现场保护和恢复开销。",
        sourceType="pdf",
        fileName="dma.pdf",
        chunkIndex=1,
        sourceRef="page_1",
    )


def test_llm_polish_updates_text_but_preserves_source_refs_and_clears_citations():
    result = {
        "notes": [
            {
                "id": "note-1",
                "title": "DMA 和程序中断两种方式的数据通路",
                "summary": "DMA 和程序中断两种方式的数据通路主要包括 DMA 直接通路等内容。",
                "content": "重复内容",
                "keyPoints": ["DMA 直接通路"],
                "sourceRefs": ["c1"],
                "source_refs": ["c1"],
                "citationIds": ["old-citation"],
                "blocks": [],
            }
        ],
        "mindMap": {"nodes": [{"id": "mind-note-1", "relatedNoteId": "note-1"}], "edges": []},
        "review": {"questions": [{"id": "q1", "relatedNoteId": "note-1", "answer": "", "citationIds": ["old"]}]},
    }
    patch = {
        "notes": [
            {
                "id": "note-1",
                "title": "DMA 数据通路",
                "summary": "DMA 通过直接通路减少 CPU 参与数据搬运的开销。",
                "content": "适合高速设备与主存之间的批量数据交换。",
                "keyPoints": ["建立 DMA 接口与主存的直接数据通路", "减少 CPU 保护和恢复现场的开销"],
                "sourceRefs": ["c1"],
            }
        ]
    }

    polished = apply_polish_result(result, patch, [source_chunk()])
    note = polished["notes"][0]

    assert note["title"] == "DMA 数据通路"
    assert note["sourceRefs"] == ["c1"]
    assert note["source_refs"] == ["c1"]
    assert note["citationIds"] == []
    assert [block["type"] for block in note["blocks"]] == ["summary", "outline", "explanation"]
    assert polished["_meta"]["llmPolish"]["preservedSourceRefs"] is True
    assert polished["review"]["questions"][0]["citationIds"] == []


def test_llm_polish_rejects_new_source_refs_from_model():
    result = {
        "notes": [
            {
                "id": "note-1",
                "title": "旧标题",
                "summary": "旧概要",
                "content": "旧内容",
                "keyPoints": [],
                "sourceRefs": ["c1"],
                "source_refs": ["c1"],
                "citationIds": [],
            }
        ]
    }
    patch = {
        "notes": [
            {
                "id": "note-1",
                "title": "不应应用的新标题",
                "summary": "不应应用的新概要",
                "sourceRefs": ["c2"],
            }
        ]
    }

    polished = apply_polish_result(result, patch, [source_chunk("c1")])

    assert polished["notes"][0]["title"] == "旧标题"
    assert "_meta" not in polished
