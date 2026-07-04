from app.rag.learning_notes import enrich_learning_notes
from app.rag.schemas import SourceChunk


def chunk() -> SourceChunk:
    return SourceChunk(
        id="c1",
        sourceId="doc",
        title="Transformer",
        heading="Transformer structure",
        text=(
            "二、Transformer的整体结构\n"
            "Transformer采用Encoder-Decoder架构。\n"
            "整体模型由两部分组成：\n"
            "Encoder（编码器）\n"
            "Decoder（解码器）\n"
            "编码器负责理解输入内容。\n"
            "解码器负责根据编码结果生成输出内容。\n"
            "例如：\n"
            "I love machine learning. -> 我喜欢机器学习。\n"
            "Transformer中的输入首先会经过Embedding层转换成向量表示。"
        ),
        sourceType="docx",
        fileName="Transformer介绍.docx",
        chunkIndex=1,
        sourceRef="para_12_38",
    )


def test_enrich_learning_notes_adds_outline_blocks_and_source_refs():
    source = chunk()
    notes = [
        {
            "id": "note-1",
            "title": "Transformer的整体结构",
            "content": "Transformer采用Encoder-Decoder架构。",
            "source_refs": ["c1"],
            "citationIds": [],
        }
    ]

    enriched = enrich_learning_notes(notes, [source])
    note = enriched[0]

    assert note["summary"]
    assert "Encoder" in " ".join(note["keyPoints"])
    assert note["sourceRefs"] == ["c1"]
    assert note["source_refs"] == ["c1"]
    assert note["blocks"][0]["type"] == "summary"
    assert any(block["type"] == "outline" for block in note["blocks"])
    assert any(item["target"] == "Encoder" for item in note["relations"])
    assert any(example["type"] in {"example", "formula-or-mapping"} for example in note["examples"])


def test_learning_notes_separate_summary_content_and_key_points():
    source = SourceChunk(
        id="dma-c1",
        sourceId="dma",
        title="DMA方式",
        heading="DMA 与主存交换数据的三种方式",
        text=(
            "DMA 与主存交换数据的三种方式\n"
            "(1) 停止 CPU 访问主存\n"
            "(2) 周期挪用（或周期窃取）\n"
            "(3) DMA 与 CPU 交替访问\n"
        ),
        sourceType="pdf",
        fileName="dma.pdf",
        chunkIndex=1,
        sourceRef="page_1",
    )
    note = enrich_learning_notes(
        [{"id": "note-1", "title": "DMA 与主存交换数据的三种方式", "content": "", "source_refs": ["dma-c1"], "citationIds": []}],
        [source],
    )[0]

    assert "主要包括" not in note["summary"]
    assert "结构拆解" not in note["content"]
    assert note["summary"] != "；".join(note["keyPoints"])
    assert any(block["type"] == "outline" for block in note["blocks"])


def test_learning_notes_filter_broken_outline_fragments():
    source = SourceChunk(
        id="dma-c2",
        sourceId="dma",
        title="DMA接口",
        heading="DMA接口功能",
        text=(
            "DMA接口功能\n"
            "DMA接口和主存之间存在直接数据通路，主存和\n"
            "服务，省去了保护和恢复现场。\n"
            "负责管理 DMA的数据传送过程，由控制电\n"
            "路、时序电路、及命令状态控制寄存器组成。\n"
        ),
        sourceType="pdf",
        fileName="dma.pdf",
        chunkIndex=2,
        sourceRef="page_2",
    )
    note = enrich_learning_notes(
        [{"id": "note-2", "title": "DMA接口功能", "content": "", "source_refs": ["dma-c2"], "citationIds": []}],
        [source],
    )[0]
    joined = "；".join(note["keyPoints"])

    assert "主存和；服务" not in note["content"]
    assert "控制电；路" not in joined
    assert "服务，省去了保护和恢复现场" not in note["keyPoints"]


def test_learning_notes_drop_incomplete_sentence_tail_from_outline():
    source = SourceChunk(
        id="dma-c3",
        sourceId="dma",
        title="DMA方式",
        heading="DMA访问主存",
        text=(
            "DMA访存时，CPU 处于不工作状态或保持状态。\n"
            "由于外设准备数据间隔远大于主存存取周期，未\n"
            "充分发挥主存的利用率。\n"
        ),
        sourceType="pdf",
        fileName="dma.pdf",
        chunkIndex=3,
        sourceRef="page_3",
    )
    note = enrich_learning_notes(
        [{"id": "note-3", "title": "DMA访问主存", "content": "", "source_refs": ["dma-c3"], "citationIds": []}],
        [source],
    )[0]

    assert "未" not in note["keyPoints"]


def test_parent_summary_uses_learning_relation_not_system_template():
    parent = SourceChunk(
        id="dma-parent",
        sourceId="dma",
        title="DMA",
        heading="DMA 与主存交换数据的三种方式",
        text="DMA 与主存交换数据的三种方式",
        sourceType="pdf",
        fileName="dma.pdf",
        chunkIndex=1,
        sourceRef="page_1",
    )
    child = SourceChunk(
        id="dma-child",
        sourceId="dma",
        title="DMA",
        heading="(2) 周期挪用（或周期窃取）",
        text="周期挪用通过占用一个或几个主存周期完成 I/O 数据传送。",
        sourceType="pdf",
        fileName="dma.pdf",
        chunkIndex=2,
        sourceRef="page_2",
    )
    notes = [
        {"id": "note-1", "title": "DMA 与主存交换数据的三种方式", "content": "", "source_refs": ["dma-parent"], "citationIds": []},
        {"id": "note-2", "title": "(2) 周期挪用（或周期窃取）", "content": "", "parentId": "note-1", "source_refs": ["dma-child"], "citationIds": []},
    ]

    enriched = enrich_learning_notes(notes, [parent, child])
    parent_note = enriched[0]

    assert "子模块构成" not in parent_note["summary"]
    assert "需要结合原文判断" in parent_note["summary"]
    assert "之间的作用和边界" not in parent_note["summary"]



def test_learning_notes_merge_short_fragments_and_skip_minor_examples():
    source = SourceChunk(
        id="c2",
        sourceId="doc",
        title="Self Attention",
        heading="Self Attention",
        text=(
            "\u4e94\u3001\u81ea\u6ce8\u610f\u529b\u673a\u5236\uff08Self-Attention\uff09\n"
            "\u6a21\u578b\u9700\u8981\u5224\u65ad\uff1a\n"
            "it\n"
            "\u6307\u4ee3\u8c01\u3002\n"
            "\u901a\u8fc7\u81ea\u6ce8\u610f\u529b\u673a\u5236\uff0c\n"
            "it\n"
            "\u53ef\u4ee5\u5173\u6ce8\uff1a\n"
            "animal\n"
            "\u4ece\u800c\u83b7\u5f97\u6b63\u786e\u8bed\u4e49\u3002\n"
        ),
        sourceType="docx",
        fileName="Transformer\u4ecb\u7ecd.docx",
        chunkIndex=2,
        sourceRef="para_58_94",
    )
    notes = [{"id": "note-2", "title": "\u81ea\u6ce8\u610f\u529b\u673a\u5236", "content": "", "source_refs": ["c2"], "citationIds": []}]

    note = enrich_learning_notes(notes, [source])[0]
    outline = next(block for block in note["blocks"] if block["type"] == "outline")["items"]

    joined = " ".join(outline)
    assert not any(item == "it" or item == "animal" or item == "\u6307\u4ee3\u8c01\u3002" for item in outline)
    assert "\u6a21\u578b\u9700\u8981\u5224\u65ad" not in joined
    assert "animal" not in joined


def test_learning_notes_keep_llm_series_as_example_not_outline_points():
    source = SourceChunk(
        id="c3",
        sourceId="doc",
        title="LLM",
        heading="LLM",
        text=(
            "\u5f53\u524d\u4e3b\u6d41\u5927\u8bed\u8a00\u6a21\u578b\u57fa\u672c\u5efa\u7acb\u5728Transformer\u67b6\u6784\u4e4b\u4e0a\u3002\n"
            "\u4f8b\u5982\uff1a\n"
            "GPT\u7cfb\u5217\n"
            "Gemini\u7cfb\u5217\n"
            "Claude\u7cfb\u5217\n"
            "DeepSeek\u7cfb\u5217\n"
            "Qwen\u7cfb\u5217\n"
            "\u8fd9\u4e9b\u6a21\u578b\u901a\u5e38\u5305\u542b\uff1a\n"
            "\u6570\u5341\u4ebf\u81f3\u6570\u4e07\u4ebf\u53c2\u6570\uff1b\n"
            "\u6d77\u91cf\u4e92\u8054\u7f51\u6570\u636e\u8bad\u7ec3\uff1b\n"
        ),
        sourceType="docx",
        fileName="Transformer\u4ecb\u7ecd.docx",
        chunkIndex=3,
        sourceRef="para_216_235",
    )
    notes = [{"id": "note-3", "title": "\u5927\u8bed\u8a00\u6a21\u578b", "content": "", "source_refs": ["c3"], "citationIds": []}]

    note = enrich_learning_notes(notes, [source])[0]
    outline = next(block for block in note["blocks"] if block["type"] == "outline")["items"]
    joined = " ".join(outline)

    assert "GPT\u7cfb\u5217" not in outline
    assert "Gemini\u7cfb\u5217" not in outline
    assert "Claude\u7cfb\u5217" not in outline
    assert "\u5f53\u524d\u4e3b\u6d41\u5927\u8bed\u8a00\u6a21\u578b" in joined
    assert any("\u8fd9\u4e9b\u6a21\u578b\u901a\u5e38\u5305\u542b" in item for item in outline)


def test_learning_notes_group_problem_and_effect_lists_as_nested_structure():
    source = SourceChunk(
        id="c4",
        sourceId="doc",
        title="RNN limits",
        heading="RNN limits",
        text=(
            "\u8fd9\u4e9b\u6a21\u578b\u5728\u673a\u5668\u7ffb\u8bd1\u3001\u6587\u672c\u5206\u7c7b\u548c\u8bed\u97f3\u8bc6\u522b\u7b49\u4efb\u52a1\u4e2d\u53d6\u5f97\u4e86\u5e7f\u6cdb\u5e94\u7528\u3002\u7136\u800c\uff0c\u7531\u4e8eRNN\u9700\u8981\u6309\u7167\u65f6\u95f4\u987a\u5e8f\u9010\u6b65\u5904\u7406\u8f93\u5165\u5e8f\u5217\uff0c\u56e0\u6b64\u5b58\u5728\u4ee5\u4e0b\u95ee\u9898\uff1a\n"
            "\u96be\u4ee5\u5e76\u884c\u8ba1\u7b97\n"
            "\u957f\u8ddd\u79bb\u4f9d\u8d56\u5efa\u6a21\u80fd\u529b\u6709\u9650\n"
            "\u8bad\u7ec3\u6548\u7387\u8f83\u4f4e\n"
            "\u5e8f\u5217\u8f83\u957f\u65f6\u5bb9\u6613\u51fa\u73b0\u68af\u5ea6\u6d88\u5931\u6216\u68af\u5ea6\u7206\u70b8\u3002\n"
        ),
        sourceType="docx",
        fileName="Transformer.docx",
        chunkIndex=4,
        sourceRef="p4",
    )
    note = enrich_learning_notes([{"id": "note-4", "title": "RNN", "content": "", "source_refs": ["c4"], "citationIds": []}], [source])[0]
    outline = next(block for block in note["blocks"] if block["type"] == "outline")

    assert len([item for item in outline["items"] if "RNN" in item]) == 1
    grouped = next(item for item in outline["structuredItems"] if "RNN" in item["text"])
    assert len(grouped["children"]) >= 3
    assert "\u96be\u4ee5\u5e76\u884c\u8ba1\u7b97" in grouped["children"]


def test_learning_notes_merge_embedding_definition():
    source = SourceChunk(
        id="c5",
        sourceId="doc",
        title="Embedding",
        heading="Embedding",
        text=(
            "\u8ba1\u7b97\u673a\u65e0\u6cd5\u76f4\u63a5\u5904\u7406\u6587\u672c\uff0c\u56e0\u6b64\u9996\u5148\u9700\u8981\u5c06\u5355\u8bcd\u8f6c\u6362\u4e3a\u5411\u91cf\u3002\n"
            "\u8fd9\u79cd\u5411\u91cf\u8868\u793a\u79f0\u4e3aEmbedding\u3002\n"
        ),
        sourceType="docx",
        fileName="Transformer.docx",
        chunkIndex=5,
        sourceRef="p5",
    )
    note = enrich_learning_notes([{"id": "note-5", "title": "Embedding", "content": "", "source_refs": ["c5"], "citationIds": []}], [source])[0]
    outline = next(block for block in note["blocks"] if block["type"] == "outline")["items"]

    assert len(outline) == 1
    assert "Embedding" in outline[0]


def test_learning_notes_merge_decoder_prediction_sentence():
    source = SourceChunk(
        id="c6",
        sourceId="doc",
        title="Masked Attention",
        heading="Masked Attention",
        text=(
            "Decoder\u5728\u751f\u6210\u6587\u672c\u65f6\u4e0d\u80fd\u63d0\u524d\u770b\u5230\u672a\u6765\u4fe1\u606f\u3002\n"
            "\u5f53\u9884\u6d4b\uff1a\n"
            "love\n"
            "\u65f6\uff0c\n"
            "\u4e0d\u80fd\u63d0\u524d\u77e5\u9053\uff1a\n"
            "AI\n"
        ),
        sourceType="docx",
        fileName="Transformer.docx",
        chunkIndex=6,
        sourceRef="p6",
    )
    note = enrich_learning_notes([{"id": "note-6", "title": "Masked", "content": "", "source_refs": ["c6"], "citationIds": []}], [source])[0]
    outline = next(block for block in note["blocks"] if block["type"] == "outline")["items"]
    joined = " ".join(outline)

    assert "\uff1bAI" not in joined
    assert "love" not in joined and "AI" not in joined


def test_learning_notes_keep_low_value_capability_list_nested():
    source = SourceChunk(
        id="c7",
        sourceId="doc",
        title="LLM capabilities",
        heading="LLM capabilities",
        text=(
            "\u5176\u80fd\u529b\u5305\u62ec\uff1a\n"
            "\u6587\u672c\u751f\u6210\n"
            "\u4ee3\u7801\u751f\u6210\n"
            "\u6587\u6863\u603b\u7ed3\n"
            "\u591a\u8f6e\u5bf9\u8bdd\n"
            "\u77e5\u8bc6\u95ee\u7b54\n"
            "Agent\u4efb\u52a1\u6267\u884c\u3002\n"
        ),
        sourceType="docx",
        fileName="Transformer.docx",
        chunkIndex=7,
        sourceRef="p7",
    )
    note = enrich_learning_notes([{"id": "note-7", "title": "LLM", "content": "", "source_refs": ["c7"], "citationIds": []}], [source])[0]
    outline = next(block for block in note["blocks"] if block["type"] == "outline")
    assert outline["items"] == ["\u5176\u80fd\u529b\u5305\u62ec"]
    assert len(outline["structuredItems"][0]["children"]) >= 5




def test_learning_notes_drop_empty_translation_input_fragment():
    source = SourceChunk(
        id="c8",
        sourceId="doc",
        title="Architecture",
        heading="Architecture",
        text=(
            "Transformer\u91c7\u7528Encoder-Decoder\u67b6\u6784\u3002\n"
            "\u5728\u673a\u5668\u7ffb\u8bd1\u4efb\u52a1\u4e2d\uff1a\n"
            "\u8f93\u5165\uff1a\n"
            "I love machine learning.\n"
            "\u7ecf\u8fc7Encoder\u7f16\u7801\u540e\u5f62\u6210\u8bed\u4e49\u8868\u793a\u3002\n"
            "Decoder\u6839\u636e\u8bed\u4e49\u8868\u793a\u751f\u6210\uff1a\u6211\u559c\u6b22\u673a\u5668\u5b66\u4e60\u3002\n"
        ),
        sourceType="docx",
        fileName="Transformer.docx",
        chunkIndex=8,
        sourceRef="p8",
    )
    note = enrich_learning_notes([{"id": "note-8", "title": "Architecture", "content": "", "source_refs": ["c8"], "citationIds": []}], [source])[0]
    outline = next(block for block in note["blocks"] if block["type"] == "outline")["items"]
    joined = " ".join(outline)

    assert "\u8f93\u5165\uff1a\u7ecf\u8fc7Encoder" not in joined
    assert "I love machine learning" not in joined
    assert "Decoder\u6839\u636e" in joined


def test_learning_notes_keep_all_total_branch_children_until_next_sentence():
    source = SourceChunk(
        id="c9",
        sourceId="doc",
        title="LLM",
        heading="LLM",
        text=(
            "\u8fd9\u4e9b\u6a21\u578b\u901a\u5e38\u5305\u542b\uff1a\n"
            "\u6570\u5341\u4ebf\u81f3\u6570\u4e07\u4ebf\u53c2\u6570\n"
            "\u6d77\u91cf\u4e92\u8054\u7f51\u6570\u636e\u8bad\u7ec3\n"
            "\u6307\u4ee4\u5fae\u8c03\n"
            "\u5f3a\u5316\u5b66\u4e60\u4f18\u5316\u3002\n"
            "\u5176\u80fd\u529b\u5305\u62ec\uff1a\n"
            "\u6587\u672c\u751f\u6210\n"
            "\u4ee3\u7801\u751f\u6210\n"
            "\u6587\u6863\u603b\u7ed3\n"
            "\u591a\u8f6e\u5bf9\u8bdd\n"
            "\u77e5\u8bc6\u95ee\u7b54\n"
            "Agent\u4efb\u52a1\u6267\u884c\u3002\n"
        ),
        sourceType="docx",
        fileName="Transformer.docx",
        chunkIndex=9,
        sourceRef="p9",
    )
    note = enrich_learning_notes([{"id": "note-9", "title": "LLM", "content": "", "source_refs": ["c9"], "citationIds": []}], [source])[0]
    structured = next(block for block in note["blocks"] if block["type"] == "outline")["structuredItems"]

    assert len(structured) == 2
    assert all(item["children"] for item in structured)
    assert "\u77e5\u8bc6\u95ee\u7b54" in structured[1]["children"]
    assert "Agent\u4efb\u52a1\u6267\u884c\u3002" in structured[1]["children"]

def test_result_builder_selects_until_main_content_coverage():
    from app.rag.result_builder import _representative_chunks

    chunks = [
        SourceChunk(
            id=f"c{index}",
            sourceId="doc",
            title=f"chunk {index}",
            heading=f"Section {index}",
            text=("important concept " + str(index) + " ") * 8,
            sourceType="text",
            fileName="sample.md",
            chunkIndex=index,
            sourceRef=f"para_{index}",
        )
        for index in range(1, 15)
    ]

    selected = _representative_chunks(chunks, min_notes=4, max_notes=20, keyword_coverage=0.8)

    assert len(selected) > 4
    assert selected[-1].chunkIndex > 4






def test_learning_notes_remove_background_filler_and_complete_rnn_problem_list():
    source = SourceChunk(
        id="c10",
        sourceId="doc",
        title="RNN limits",
        heading="RNN limits",
        text=(
            "\u8fd9\u4e9b\u6a21\u578b\u5728\u673a\u5668\u7ffb\u8bd1\u3001\u6587\u672c\u5206\u7c7b\u548c\u8bed\u97f3\u8bc6\u522b\u7b49\u4efb\u52a1\u4e2d\u53d6\u5f97\u4e86\u5e7f\u6cdb\u5e94\u7528\u3002\u7136\u800c\uff0c\u7531\u4e8eRNN\u9700\u8981\u6309\u7167\u65f6\u95f4\u987a\u5e8f\u9010\u6b65\u5904\u7406\u8f93\u5165\u5e8f\u5217\uff0c\u56e0\u6b64\u5b58\u5728\u4ee5\u4e0b\u95ee\u9898\uff1a\n"
            "\u96be\u4ee5\u5e76\u884c\u8ba1\u7b97\n"
            "\u957f\u8ddd\u79bb\u4f9d\u8d56\u5efa\u6a21\u80fd\u529b\u6709\u9650\n"
            "\u8bad\u7ec3\u6548\u7387\u8f83\u4f4e\n"
            "\u5e8f\u5217\u8f83\u957f\u65f6\u5bb9\u6613\u51fa\u73b0\u68af\u5ea6\u6d88\u5931\u6216\u68af\u5ea6\u7206\u70b8\u3002\n"
            "Transformer\u5f7b\u5e95\u629b\u5f03\u5faa\u73af\u7ed3\u6784\uff0c\u4ec5\u4f9d\u8d56\u6ce8\u610f\u529b\u673a\u5236\u8fdb\u884c\u5e8f\u5217\u5efa\u6a21\uff0c\u5927\u5e45\u63d0\u5347\u4e86\u8bad\u7ec3\u6548\u7387\u548c\u6a21\u578b\u6027\u80fd\u3002\n"
        ),
        sourceType="docx",
        fileName="Transformer.docx",
        chunkIndex=10,
        sourceRef="p10",
    )
    note = enrich_learning_notes([
        {"id": "note-10", "title": "\u4f20\u7edf\u5e8f\u5217\u5efa\u6a21\u6a21\u578b\u7684\u7f3a\u9677", "content": "", "source_refs": ["c10"], "citationIds": []}
    ], [source])[0]
    outline = next(block for block in note["blocks"] if block["type"] == "outline")
    joined = " ".join(outline["items"])

    assert "\u5e7f\u6cdb\u5e94\u7528" not in joined
    assert "Transformer\u5f7b\u5e95\u629b\u5f03\u5faa\u73af\u7ed3\u6784" not in joined
    grouped = next(item for item in outline["structuredItems"] if "RNN" in item["text"])
    assert "\u96be\u4ee5\u5e76\u884c\u8ba1\u7b97" in grouped["children"]
    assert "\u957f\u8ddd\u79bb\u4f9d\u8d56\u5efa\u6a21\u80fd\u529b\u6709\u9650" in grouped["children"]
    assert "\u5e8f\u5217\u8f83\u957f\u65f6\u5bb9\u6613\u51fa\u73b0\u68af\u5ea6\u6d88\u5931\u6216\u68af\u5ea6\u7206\u70b8\u3002" in grouped["children"]


def test_learning_notes_split_decoder_example_from_original_transformer_depth():
    source = SourceChunk(
        id="c11",
        sourceId="doc",
        title="Architecture",
        heading="Architecture",
        text=(
            "Transformer\u91c7\u7528Encoder-Decoder\u67b6\u6784\u3002\n"
            "\u6574\u4f53\u6a21\u578b\u7531\u4e24\u90e8\u5206\u7ec4\u6210\uff1a\n"
            "Encoder\uff08\u7f16\u7801\u5668\uff09\n"
            "Decoder\uff08\u89e3\u7801\u5668\uff09\n"
            "\u7f16\u7801\u5668\u8d1f\u8d23\u7406\u89e3\u8f93\u5165\u5185\u5bb9\u3002\n"
            "\u89e3\u7801\u5668\u8d1f\u8d23\u6839\u636e\u7f16\u7801\u7ed3\u679c\u751f\u6210\u8f93\u51fa\u5185\u5bb9\u3002\n"
            "Decoder\u6839\u636e\u8bed\u4e49\u8868\u793a\u751f\u6210\uff1a\u6211\u559c\u6b22\u673a\u5668\u5b66\u4e60\u3002\uff1b\u539f\u59cbTransformer\u6a21\u578b\u5305\u542b\uff1b6\u5c42Encoder\uff1b6\u5c42Decoder\n"
            "\u6bcf\u5c42\u7ed3\u6784\u57fa\u672c\u76f8\u540c\u3002\n"
        ),
        sourceType="docx",
        fileName="Transformer.docx",
        chunkIndex=11,
        sourceRef="p11",
    )
    note = enrich_learning_notes([
        {"id": "note-11", "title": "Transformer\u7684\u6574\u4f53\u67b6\u6784", "content": "", "source_refs": ["c11"], "citationIds": []}
    ], [source])[0]
    outline = next(block for block in note["blocks"] if block["type"] == "outline")
    items = outline["structuredItems"]
    joined = " ".join(outline["items"])

    assert "\u6bcf\u5c42\u7ed3\u6784\u57fa\u672c\u76f8\u540c" not in joined
    assert not any("Decoder\u6839\u636e\u8bed\u4e49\u8868\u793a\u751f\u6210" in item["text"] and "6\u5c42Encoder" in item["text"] for item in items)
    assert any("Decoder\u6839\u636e\u8bed\u4e49\u8868\u793a\u751f\u6210" in item["text"] for item in items)
    assert any("\u539f\u59cbTransformer\u7684\u5806\u53e0\u7ed3\u6784" in item["text"] for item in items)


def test_learning_notes_merge_pdf_hard_line_breaks_and_filter_duplicate_title():
    source = SourceChunk(
        id="c12",
        sourceId="doc",
        title="DMA",
        heading="周期挪用（或周期窃取）",
        text=(
            "周期挪用（或周期窃取）\n"
            "这种方式既实现了I/O传送，又提高了CPU对主\n"
            "存的利用率，使用广泛\n"
            "I/O设备每挪用一个主存周期都要申请总线控\n"
            "制权、建立总线控制权、归还总线控制权，尽\n"
            "管传送一个字对主存只要一个存取周期，但\n"
        ),
        sourceType="pdf",
        fileName="sample.pdf",
        chunkIndex=12,
        sourceRef="page_12",
    )
    note = enrich_learning_notes(
        [{"id": "note-12", "title": "周期挪用（或周期窃取）", "content": "", "source_refs": ["c12"], "citationIds": []}],
        [source],
    )[0]

    outline = next(block for block in note["blocks"] if block["type"] == "outline")["items"]
    joined = " ".join([note["summary"], *outline])

    assert "主存的利用率" in joined
    assert "总线控制权" in joined
    assert "尽管" in joined
    assert not note["summary"].startswith("周期挪用（或周期窃取）主要包括周期挪用（或周期窃取）")
    assert "存的利用率，使用广泛" not in outline


def test_learning_notes_drop_ppt_template_noise_from_outline():
    source = SourceChunk(
        id="c13",
        sourceId="doc",
        title="China Dream",
        heading="第四单元 和谐与梦想",
        text=(
            "第四单元 和谐与梦想\n"
            "第八课 中国人中国梦\n"
            "第2框 共圆中国梦\n"
            "第一PPT模板网-WWW.1PPT.COM\n"
            "怎样实现中国梦？\n"
            "必须走中国道路，即中国特色社会主义道路。\n"
        ),
        sourceType="pptx",
        fileName="sample.pptx",
        chunkIndex=13,
        sourceRef="slide_1",
    )
    note = enrich_learning_notes(
        [{"id": "note-13", "title": "第四单元 和谐与梦想", "content": "", "source_refs": ["c13"], "citationIds": []}],
        [source],
    )[0]

    outline = next(block for block in note["blocks"] if block["type"] == "outline")["items"]
    joined = " ".join([note["summary"], *outline, note["content"]])

    assert "1PPT" not in joined
    assert "PPT模板" not in joined
    assert any("怎样实现中国梦" in item or "中国特色社会主义道路" in item for item in outline)


def test_result_builder_filters_ppt_activities_and_keeps_core_notes():
    from app.rag.result_builder import build_agent_result

    chunks = [
        SourceChunk(
            id="ppt-1",
            sourceId="ppt",
            title="共圆中国梦",
            heading="通过本节课学习，增强对实现中国梦的自信心",
            text="通过本节课学习，增强对实现中国梦的自信心。\n了解自信中国人的特点和自信的源泉。",
            sourceType="pptx",
            fileName="共圆中国梦.pptx",
            chunkIndex=1,
            sourceRef="slide_2",
            slide=2,
        ),
        SourceChunk(
            id="ppt-2",
            sourceId="ppt",
            title="共圆中国梦",
            heading="每个人都有自己的梦想，采访身边的人",
            text="每个人都有自己的梦想，采访身边的人，记录他们的中国梦。\n想一想：他们实现梦想需要哪些条件？",
            sourceType="pptx",
            fileName="共圆中国梦.pptx",
            chunkIndex=2,
            sourceRef="slide_3",
            slide=3,
        ),
        SourceChunk(
            id="ppt-3",
            sourceId="ppt",
            title="共圆中国梦",
            heading="1.怎样实现中国梦？（国家层面）",
            text="1.怎样实现中国梦？（国家层面）\n①要坚持党的领导，贯彻五大发展理念。\n②必须走中国道路，即中国特色社会主义道路。\n③必须弘扬中国精神。\n④要凝聚中国力量。",
            sourceType="pptx",
            fileName="共圆中国梦.pptx",
            chunkIndex=3,
            sourceRef="slide_6",
            slide=6,
        ),
        SourceChunk(
            id="ppt-4",
            sourceId="ppt",
            title="共圆中国梦",
            heading="①树立崇高远大理想，努力学习科学文化知识，不断提高自身素质",
            text="①树立崇高远大理想，努力学习科学文化知识，不断提高自身素质。\n②弘扬民族精神和时代精神。\n③从点滴做起，积极承担责任。\n2.为了实现中国梦，作为新时代的青少年应该怎么做？",
            sourceType="pptx",
            fileName="共圆中国梦.pptx",
            chunkIndex=4,
            sourceRef="slide_7",
            slide=7,
        ),
    ]

    result = build_agent_result(chunks)
    titles = [note["title"] for note in result["notes"]]
    joined = " ".join(titles)

    assert not any("通过本节课学习" in title for title in titles)
    assert not any("采访身边的人" in title for title in titles)
    assert any("怎样实现中国梦" in title for title in titles), titles
    assert "青少年如何助力实现中国梦" in joined
    assert all(note.get("content") for note in result["notes"])
    assert result["_meta"]["contentQuality"]["metrics"]["activityNoteRate"] == 0
    assert result["_meta"]["contentQuality"]["metrics"]["emptyContentRate"] == 0
    assert all(note.get("sourceExcerpts") for note in result["notes"])


def test_content_quality_blocks_visible_broken_fragments_and_weak_excerpts():
    from app.rag.content_quality import assess_content_quality

    result = {
        "notes": [
            {
                "id": "note-1",
                "title": "DMA 接口组成 线",
                "summary": "核心是理解核心概念与关键要点",
                "content": "DMA传送速 率高，总线",
                "keyPoints": ["控制电；路", "字装配 /、拆卸硬件"],
                "citationIds": ["c1"],
                "sourceExcerpts": [],
            }
        ]
    }

    quality = assess_content_quality(result)

    assert not quality["passed"]
    assert "broken-fragment-present" in quality["failedChecks"]
    assert "low-info-summary-high" in quality["failedChecks"]
    assert quality["metrics"]["citationDisplayCoverage"] == 0


def test_learning_notes_filter_recent_dma_residual_fragments():
    source = SourceChunk(
        id="dma-c14",
        sourceId="dma",
        title="DMA接口",
        heading="DMA接口组成",
        text=(
            "DMA 接口组成 线\n"
            "DMA传送速 率高，总线\n"
            "起总线竞争\n"
            "CPU在一个工作周期内访\n"
            "问一次存储器即可不需要 申请建立和归还 总线的使用权\n"
            "数据缓冲寄存器BR主要暂存每次传送的数据。\n"
        ),
        sourceType="pdf",
        fileName="dma.pdf",
        chunkIndex=14,
        sourceRef="page_14",
    )
    note = enrich_learning_notes(
        [{"id": "note-14", "title": "DMA接口组成", "content": "", "source_refs": ["dma-c14"], "citationIds": []}],
        [source],
    )[0]
    joined = " ".join([note["summary"], note["content"], *note["keyPoints"]])

    assert "DMA 接口组成 线" not in joined
    assert "DMA传送速 率高" not in joined
    assert "起总线竞争" not in joined
    assert "CPU在一个工作周期内访" not in joined
    assert "数据缓冲寄存器BR" in joined


def test_result_builder_keeps_how_to_confident_chinese_as_top_level():
    from app.rag.result_builder import _reconstruct_note_hierarchy

    notes = [
        {"id": "note-1", "title": "自信中国人的表现", "content": "自信中国人对国家有认同。"},
        {"id": "note-2", "title": "自信中国人的表现：对国家有认同", "content": "对国家有认同是表现之一。"},
        {"id": "note-3", "title": "如何做自信中国人", "content": "要培育理性平和、不卑不亢、开放包容的心态。"},
    ]

    rebuilt = _reconstruct_note_hierarchy(notes)
    by_title = {note["title"]: note for note in rebuilt}

    assert by_title["自信中国人的表现：对国家有认同"]["parentId"] == "note-1"
    assert by_title["如何做自信中国人"]["level"] == 1
    assert by_title["如何做自信中国人"]["parentId"] is None


def test_result_builder_filters_diagram_fragments_from_dma_notes():
    from app.rag.result_builder import build_agent_result

    chunks = [
        SourceChunk(
            id="diagram-1",
            sourceId="dma",
            title="DMA",
            heading="DMA接口（page_16）",
            text="设备\n控制逻\n中断\nDMA接口\n主存\n+1\n数据线\n",
            sourceType="pdf",
            fileName="dma.pdf",
            chunkIndex=1,
            sourceRef="page_16",
            page=16,
        ),
        SourceChunk(
            id="select-1",
            sourceId="dma",
            title="DMA",
            heading="选择型 在 物理上 连接 多个 设备",
            text=(
                "选择型 在 物理上 连接 多个 设备\n"
                "在 逻辑上 只允许连接 一个 设备\n"
                "预处理时，将所选设备的设备号送入设备地址 寄\n"
                "存器。\n"
                "选择型DMA接口适用于数据传输率很高的 I/O 设备。\n"
            ),
            sourceType="pdf",
            fileName="dma.pdf",
            chunkIndex=2,
            sourceRef="page_20",
            page=20,
        ),
    ]

    result = build_agent_result(chunks)
    joined = " ".join(
        [
            *(note["title"] for note in result["notes"]),
            *(point for note in result["notes"] for point in note.get("keyPoints", [])),
            *(note.get("content", "") for note in result["notes"]),
        ]
    )

    assert "DMA接口（page_16）" not in joined
    assert "控制逻" not in joined
    assert "+1" not in joined
    assert "理时，将所选设备" not in joined
    assert any("选择型" in note["title"] for note in result["notes"])
    assert result["_meta"]["contentQuality"]["metrics"]["fragmentTitleRate"] == 0


def test_content_quality_flags_fragment_title_and_diagram_points():
    from app.rag.content_quality import assess_content_quality

    quality = assess_content_quality(
        {
            "notes": [
                {
                    "id": "note-x",
                    "title": "理时，将所选设备的设备号送入设备地址 寄",
                    "summary": "选择型 DMA 接口说明设备连接方式。",
                    "content": "在 逻辑上 只允许连接 一个 设备 设备地址寄存器",
                    "keyPoints": ["控制逻", "+1", "数据线"],
                    "sourceExcerpts": [{"quote": "选择型DMA接口适用于数据传输率很高的 I/O 设备。"}],
                }
            ]
        }
    )

    assert not quality["passed"]
    assert "fragment-title-present" in quality["failedChecks"]
    assert "visual-label-point-high" in quality["failedChecks"]


def test_learning_content_uses_study_explanation_not_raw_excerpt():
    source = SourceChunk(
        id="dma-study",
        sourceId="dma",
        title="DMA",
        heading="DMA 数据传送过程",
        text="DMA 数据传送过程\n包含预处理、数据传送、后处理 3个阶段\nCPU用几条输入输出指令为DMA接口预置信\n",
        sourceType="pdf",
        fileName="dma.pdf",
        chunkIndex=30,
        sourceRef="page_30",
    )
    note = enrich_learning_notes(
        [{"id": "note-study", "title": "DMA 数据传送过程", "content": "", "source_refs": ["dma-study"], "citationIds": []}],
        [source],
    )[0]

    assert "预处理、数据传送、后处理三步" in note["content"]
    assert "预置信" not in note["content"]


def test_content_quality_flags_learning_value_gaps():
    from app.rag.content_quality import assess_content_quality

    result = {
        "notes": [
            {
                "id": "note-weak",
                "title": "DMA 数据传送过程",
                "summary": "DMA 数据传送过程包含预处理、数据传送、后处理。",
                "content": "包含预处理、数据传送、后处理 3个阶段 CPU用几条输入输出指令为DMA接口预置信",
                "keyPoints": ["CPU用几条输入输出指令为DMA接口预置信"],
                "sourceExcerpts": [{"quote": "无关内容"}],
            }
        ]
    }

    quality = assess_content_quality(result)

    assert not quality["passed"]
    assert "truncated-sentence-high" in quality["failedChecks"]
    assert "weak-explanation-high" in quality["failedChecks"]


def test_content_quality_blocks_template_learning_text_and_semantic_repetition():
    from app.rag.content_quality import assess_content_quality

    title = "\u4e3a\u4ec0\u4e48\u4e2d\u56fd\u68a6\u80fd\u591f\u5b9e\u73b0"
    content = (
        "\u5b66\u4e60\u65f6\u5148\u7406\u89e3\u4e3a\u4ec0\u4e48\u4e2d\u56fd\u68a6\u80fd\u591f\u5b9e\u73b0\u7684\u6838\u5fc3\u542b\u4e49\uff0c"
        "\u518d\u56f4\u7ed5\u66f4\u63a5\u8fd1\u76ee\u6807\u3001\u66f4\u6709\u4fe1\u5fc3\u68b3\u7406\u4f5c\u7528\u3001\u6761\u4ef6\u548c\u6613\u6df7\u70b9\u3002"
    )
    quality = assess_content_quality(
        {
            "notes": [
                {
                    "id": "note-template",
                    "title": title,
                    "summary": title + "\u5305\u542b\u66f4\u63a5\u8fd1\u76ee\u6807\u548c\u66f4\u6709\u4fe1\u5fc3\u3002",
                    "content": content,
                    "keyPoints": [
                        "\u66f4\u63a5\u8fd1\u4e2d\u534e\u6c11\u65cf\u4f1f\u5927\u590d\u5174\u7684\u76ee\u6807",
                        "\u66f4\u6709\u4fe1\u5fc3\u3001\u6709\u80fd\u529b\u5b9e\u73b0\u8fd9\u4e2a\u76ee\u6807",
                    ],
                    "sourceExcerpts": [{"quote": "\u6211\u4eec\u6bd4\u5386\u53f2\u4e0a\u4efb\u4f55\u65f6\u671f\u90fd\u66f4\u63a5\u8fd1\u4e2d\u534e\u6c11\u65cf\u4f1f\u5927\u590d\u5174\u7684\u76ee\u6807\u3002"}],
                }
            ]
        }
    )

    assert not quality["passed"]
    assert "template-content-present" in quality["failedChecks"]
    assert "weak-teaching-value-high" in quality["failedChecks"]


def test_result_builder_merges_dependent_detail_notes_and_rewrites_roles():
    from app.rag.result_builder import _semantic_note_contract

    notes = [
        {
            "id": "note-1",
            "title": "周期挪用（或周期窃取）",
            "summary": "周期挪用说明这种方式既实现了I/O传送，又提高了CPU对主存的利用率。",
            "content": "学习时先理解周期挪用的核心含义，再围绕总线控制权梳理作用、条件和易混点。",
            "keyPoints": ["每次传送要申请和归还总线控制权"],
            "sourceRefs": ["c1"],
        },
        {
            "id": "note-2",
            "title": "周期挪用的适用性说明",
            "summary": "周期挪用适合 I/O设备读写周期大于主存周期的情况。",
            "content": "学习时先理解这种方式的核心含义，再围绕适用条件梳理作用、条件和易混点。",
            "keyPoints": ["适合外设读写周期大于主存周期的场景"],
            "parentId": "note-1",
            "sourceRefs": ["c2"],
        },
    ]

    result = _semantic_note_contract(notes)

    assert len(result) == 1
    note = result[0]
    assert "学习时先理解" not in note["content"]
    assert "梳理作用、条件和易混点" not in note["content"]
    assert "适合外设读写周期大于主存周期的场景" in note["keyPoints"]
    assert note["sourceRefs"] == ["c1", "c2"]


def test_result_builder_splits_first_numbered_item_from_enumeration_parent():
    from app.rag.result_builder import _semantic_note_contract

    notes = [
        {
            "id": "note-1",
            "title": "\u67d0\u4e3b\u9898\u7684\u4e09\u79cd\u65b9\u5f0f",
            "summary": "\u5305\u542b\u4e09\u79cd\u65b9\u5f0f\u3002",
            "content": "\u8fd9\u662f\u603b\u8d77\u5185\u5bb9\u3002",
            "keyPoints": ["(1) \u7b2c\u4e00\u79cd\u65b9\u5f0f", "\u7b2c\u4e00\u79cd\u65b9\u5f0f\u7684\u9002\u7528\u6761\u4ef6"],
            "sourceRefs": ["c1"],
        },
        {
            "id": "note-2",
            "title": "(2) \u7b2c\u4e8c\u79cd\u65b9\u5f0f",
            "summary": "\u7b2c\u4e8c\u79cd\u65b9\u5f0f\u8bf4\u660e\u3002",
            "content": "\u5b50\u9879\u5185\u5bb9\u3002",
            "keyPoints": ["\u7b2c\u4e8c\u79cd\u65b9\u5f0f\u8981\u70b9"],
            "level": 2,
            "parentId": "note-1",
            "sourceRefs": ["c2"],
        },
        {
            "id": "note-3",
            "title": "(3) \u7b2c\u4e09\u79cd\u65b9\u5f0f",
            "summary": "\u7b2c\u4e09\u79cd\u65b9\u5f0f\u8bf4\u660e\u3002",
            "content": "\u5b50\u9879\u5185\u5bb9\u3002",
            "keyPoints": ["\u7b2c\u4e09\u79cd\u65b9\u5f0f\u8981\u70b9"],
            "level": 2,
            "parentId": "note-1",
            "sourceRefs": ["c3"],
        },
    ]

    result = _semantic_note_contract(notes)
    parent = result[0]
    children = [note for note in result if note.get("parentId") == parent["id"]]

    assert len(children) == 3
    assert children[0]["title"].startswith("(1)")
    assert "(1)" in parent["keyPoints"][0]
    assert "\u7b2c\u4e00\u79cd\u65b9\u5f0f\u7684\u9002\u7528\u6761\u4ef6" not in parent["keyPoints"]
    assert "\u5e76\u5217\u5185\u5bb9" in parent["summary"]
    assert "\u603b\u8d77\u6a21\u5757" not in parent["summary"]
    assert "\u4e0d\u5e94\u627f\u8f7d" not in parent["content"]
    assert "\u7ed3\u6784\u603b\u89c8" not in parent["content"]


def test_result_builder_keeps_six_numbered_action_points():
    from app.rag.result_builder import _semantic_note_contract

    notes = [
        {
            "id": "note-1",
            "title": "青少年如何助力实现中国梦",
            "summary": "青少年应从理想、学习、责任、实践、道德和法治等方面行动。",
            "content": "这部分是个人层面的行动要求，答题时可从多个角度组织。",
            "keyPoints": [
                "①树立崇高远大理想，努力学习科学文化知识，不断提高自身素质",
                "②弘扬民族精神和时代精神，继承和弘扬中华优秀传统文化",
                "③从点滴做起，养成亲社会行为，积极承担责任",
                "④积极参与社会实践，培养创新能力和实践能力",
                "⑤加强思想道德修养，自强不息、艰苦奋斗",
                "⑥增强法治观念，尊法学法守法用法，依法规范自身行为，依法维护国家利益",
            ],
            "sourceRefs": ["ppt-7"],
        }
    ]

    result = _semantic_note_contract(notes)
    points = result[0]["keyPoints"]

    assert len(points) == 6
    assert any("增强法治观念" in point for point in points)


def test_result_builder_orders_parent_before_colon_child_and_drops_repeated_numbered_heading():
    from app.rag.result_builder import _semantic_note_contract

    notes = [
        {
            "id": "note-1",
            "title": "自信中国人的表现：对国家有认同",
            "summary": "自信中国人对国家有认同。",
            "content": "表现类题要把态度和行动分开。",
            "keyPoints": [
                "①自信的中国人对国家有认同",
                "以天下为己任的使命感",
                "能够自觉维护国家利益和国家尊严，自觉维护祖国统一和领土完整",
            ],
            "level": 2,
            "parentId": "note-2",
            "sourceRefs": ["ppt-12"],
        },
        {
            "id": "note-2",
            "title": "自信中国人的表现",
            "summary": "自信中国人主要体现在国家认同、文化底气和发展信心。",
            "content": "表现类题要把态度和行动分开。",
            "keyPoints": [
                "①自信的中国人对国家有认同",
                "②自信的中国人对文化有底气",
                "③自信的中国人对发展有信心",
            ],
            "level": 1,
            "parentId": None,
            "sourceRefs": ["ppt-14"],
        },
    ]

    result = _semantic_note_contract(notes)
    titles = [note["title"] for note in result]
    parent = next(note for note in result if note["title"] == "自信中国人的表现")
    child = next(note for note in result if note["title"] == "自信中国人的表现：对国家有认同")

    assert titles.index("自信中国人的表现") < titles.index("自信中国人的表现：对国家有认同")
    assert child["parentId"] == parent["id"]
    assert not any(point.startswith("①") for point in child["keyPoints"])
    assert "以天下为己任的使命感" in child["keyPoints"]


def test_result_builder_rewrites_mismatched_dma_component_summary_and_keypoints():
    from app.rag.result_builder import _semantic_note_contract

    notes = [
        {
            "id": "note-8",
            "title": "DMA 中断机构",
            "summary": "字计数器溢出，表示一批数据传送完毕，通过说明中断机构向CPU提出中断请求 ，请CPU做DMA操作的后处理，以报告一批数据传送结束。",
            "content": "这类接口结构应按职责记忆：地址类部件负责定位，计数类部件负责长度，缓冲类部件暂存数据，控制逻辑负责协调请求、响应和结束通知。",
            "keyPoints": ["中断机构向CPU提出中断请求 ，请CPU做DMA操作的后处理，以报告一批数据传送结束"],
            "sourceRefs": ["dma-c8"],
            "source_refs": ["dma-c8"],
        },
        {
            "id": "note-9",
            "title": "DMA 数据传送过程",
            "summary": "DMA 数据传送过程包含✓ 预处理之后：当 I/O设备准备好发送的数据、CPU继续执行主程序、校验送入主存的数据是否正确等内容，重点是理解流程顺序和关键操作。",
            "content": "这类技术流程应按触发条件、执行动作、结束信号三步学习。",
            "keyPoints": [
                "✓ 预处理之后：当 I/O设备准备好发送的数据",
                "（对应输入情况 ），或者上次接收的数据已",
                "经处理完毕（对应输出情况），便通过DMA",
            ],
            "sourceRefs": ["dma-c9"],
            "source_refs": ["dma-c9"],
        },
    ]

    result = _semantic_note_contract(notes)
    by_title = {note["title"]: note for note in result}
    interrupt = by_title["DMA 中断机构"]
    process = by_title["DMA 数据传送过程"]

    assert "字计数器溢出" not in interrupt["summary"]
    assert "通过说明" not in interrupt["summary"]
    assert "地址类部件负责定位" not in interrupt["content"]
    assert "一批数据传送结束后发出中断请求" in interrupt["keyPoints"]
    joined_process = " ".join([process["summary"], process["content"], *process["keyPoints"]])
    assert "✓ 预处理之后" not in joined_process
    assert "对应输入情况" not in joined_process
    assert "经处理完毕" not in joined_process


def test_content_quality_blocks_component_mismatch_and_transition_fragments():
    from app.rag.content_quality import assess_content_quality

    quality = assess_content_quality(
        {
            "notes": [
                {
                    "id": "note-8",
                    "title": "DMA 中断机构",
                    "summary": "字计数器溢出，表示一批数据传送完毕，通过说明中断机构向CPU提出中断请求。",
                    "content": "这类接口结构应按职责记忆：地址类部件负责定位，计数类部件负责长度，缓冲类部件暂存数据。",
                    "keyPoints": ["✓ 预处理之后：当 I/O设备准备好发送的数据"],
                    "sourceExcerpts": [{"quote": "中断机构向CPU提出中断请求，请CPU做DMA操作的后处理。"}],
                }
            ]
        }
    )

    assert not quality["passed"]
    assert "title-summary-mismatch-present" in quality["failedChecks"]
    assert "generic-template-mismatch-present" in quality["failedChecks"]
    assert "transition-fragment-present" in quality["failedChecks"]


def test_learning_units_filter_transition_fragments_before_keypoints():
    source = SourceChunk(
        id="dma-process",
        sourceId="dma",
        title="DMA",
        heading="DMA 数据传送申请条件",
        text=(
            "DMA 数据传送申请条件\n"
            "✓ 预处理之后：当 I/O设备准备好发送的数据\n"
            "（对应输入情况 ），或者上次接收的数据已\n"
            "经处理完毕（对应输出情况），便通过DMA\n"
            "多个 DMA 请求由硬件排队决定优先级。\n"
        ),
        sourceType="pdf",
        fileName="dma.pdf",
        chunkIndex=31,
        sourceRef="page_31",
    )

    note = enrich_learning_notes(
        [{"id": "note-process", "title": "DMA 数据传送申请条件", "content": "", "source_refs": ["dma-process"], "citationIds": []}],
        [source],
    )[0]
    joined = " ".join([note["summary"], note["content"], *note["keyPoints"]])

    assert "✓ 预处理之后" not in joined
    assert "对应输入情况" not in joined
    assert "经处理完毕" not in joined
    assert "多个 DMA 请求由硬件排队决定优先级" in joined


def test_result_builder_recovers_interrupt_note_from_preposition_hard_break():
    from app.rag.result_builder import build_agent_result

    source = SourceChunk(
        id="dma-interrupt",
        sourceId="dma",
        title="DMA",
        heading="字计数器溢出，表示一批数据传送完毕，通过",
        text=(
            "字计数器溢出，表示一批数据传送完毕，通过\n"
            "中断机构向CPU提出中断请求，请CPU做DMA操作的后处理，以报告一批数据传送结束。\n"
        ),
        sourceType="pdf",
        fileName="dma.pdf",
        chunkIndex=32,
        sourceRef="page_32",
    )

    result = build_agent_result([source])
    joined = " ".join([note["title"] for note in result["notes"]])
    note = result["notes"][0]

    assert "DMA 中断机构" in joined
    assert "字计数器溢出，表示一批数据传送完毕，通过" not in note["title"]
    assert "一批数据传送结束后发出中断请求" in " ".join(note["keyPoints"])


def test_visual_label_detector_does_not_reject_meaningful_dma_request_sentence():
    from app.rag.content_quality import is_visual_label
    from app.rag.learning_units import is_visual_label_line

    assert not is_visual_label("设备就绪后提出 DMA 请求")
    assert not is_visual_label_line("设备就绪后提出 DMA 请求")
    assert is_visual_label("DMA请求")
    assert is_visual_label_line("DMA请求")


def test_text_cleaning_keeps_normal_enumeration_punctuation():
    from app.rag.text_utils import normalize_learning_text

    text = "DMA 与主存交换数据可分为停止 CPU 访问、周期挪用和交替访问三种方式。"

    assert "访问、周期挪用" in normalize_learning_text(text)


def test_result_builder_rewrites_generic_ppt_action_question_without_sample_title():
    from app.rag.result_builder import build_agent_result

    source = SourceChunk(
        id="ppt-generic-action",
        sourceId="ppt",
        title="校园行动",
        heading="①节约水电，减少浪费",
        text=(
            "①节约水电，减少浪费。\n"
            "②参与校园志愿服务。\n"
            "为了绿色校园，作为高中生应该怎么做？"
        ),
        sourceType="pptx",
        fileName="校园行动.pptx",
        chunkIndex=1,
        sourceRef="slide_1",
        slide=1,
    )

    result = build_agent_result([source])
    titles = " ".join(note["title"] for note in result["notes"])

    assert "高中生如何助力绿色校园" in titles


def test_result_builder_uses_completion_notifier_profile_without_dma_title():
    from app.rag.result_builder import _semantic_note_contract

    notes = [
        {
            "id": "note-1",
            "title": "传送完成中断机构",
            "summary": "字计数器溢出，表示一批数据传送完毕，通过说明中断机构向CPU提出中断请求。",
            "content": "这类接口结构应按职责记忆。",
            "keyPoints": ["中断机构向CPU提出中断请求，请CPU做后处理"],
            "sourceRefs": ["c1"],
        }
    ]

    result = _semantic_note_contract(notes)
    note = result[0]

    assert "字计数器溢出" not in note["summary"]
    assert "一批数据传送结束后发出中断请求" in note["keyPoints"]
    assert "地址类部件负责定位" not in note["content"]
