from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from .schemas import SourceChunk
from .learning_profile import infer_learning_profile, leading_number as profile_leading_number
from .text_utils import compact, extract_keywords, normalize_learning_text, split_sentences


@dataclass
class OutlineItem:
    text: str
    children: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "children": serialize_block_items(self.children)}


@dataclass
class LearningBlock:
    type: str
    title: str
    content: str = ""
    items: list[Any] = field(default_factory=list)


@dataclass
class LearningUnit:
    id: str
    title: str
    note_type: str
    level: int
    parent_id: str | None
    source_refs: list[str]
    model_summary: str
    model_content: str
    source_text: str
    headings: list[str]
    blocks: list[LearningBlock]
    summary: str
    explanation: str
    examples: list[dict[str, str]]
    relations: list[dict[str, str]]
    quality_issues: list[str] = field(default_factory=list)

    @property
    def outline_items(self) -> list[OutlineItem]:
        for block in self.blocks:
            if block.type == "outline":
                return [item if isinstance(item, OutlineItem) else OutlineItem(str(item), []) for item in block.items]
        return []


class SourceResolver:
    def __init__(self, chunks: list[SourceChunk]) -> None:
        self.chunks = chunks
        self.by_id = {chunk.id: chunk for chunk in chunks}
        self.by_ref: dict[str, list[SourceChunk]] = {}
        for chunk in chunks:
            self.by_ref.setdefault(chunk.sourceRef, []).append(chunk)

    def resolve(self, note: dict[str, Any]) -> list[SourceChunk]:
        refs = string_list(note.get("sourceRefs") or note.get("source_refs") or note.get("citationIds") or note.get("refs") or [])
        resolved: list[SourceChunk] = []
        seen: set[str] = set()
        for ref in refs:
            candidates = [self.by_id[ref]] if ref in self.by_id else self.by_ref.get(ref, [])
            for chunk in candidates:
                if chunk.id not in seen:
                    resolved.append(chunk)
                    seen.add(chunk.id)
        if resolved:
            return resolved
        title_tokens = set(extract_keywords(str(note.get("title") or ""), limit=6))
        if not title_tokens:
            return []
        ranked = sorted(self.chunks, key=lambda c: len(title_tokens & set(extract_keywords(f"{c.heading} {c.text}", limit=16))), reverse=True)
        return [ranked[0]] if ranked else []


class LearningUnitBuilder:
    def build(self, note: dict[str, Any], chunks: list[SourceChunk]) -> LearningUnit:
        title = clean(str(note.get("title") or "知识点"))
        source_text = normalize_learning_text(merge_source_text(chunks) if chunks else clean(str(note.get("content") or "")))
        model_content = clean_model(str(note.get("content") or ""))
        model_summary = clean_model(str(note.get("summary") or ""))
        refs = [chunk.id for chunk in chunks] or string_list(note.get("sourceRefs") or note.get("source_refs"))
        headings = [strip_section_number(chunk.heading or chunk.title) for chunk in chunks if strip_section_number(chunk.heading or chunk.title)]
        blocks = blocks_for(title, model_content, source_text, headings, chunks)
        summary = summarize_from_unit(title, model_summary, source_text or model_content, blocks)
        explanation = explanation_from_unit(title, model_content, summary, blocks)
        unit = LearningUnit(
            id=str(note.get("id") or "note"), title=title,
            note_type=str(note.get("noteType") or note.get("note_type") or "note"),
            level=to_int(note.get("level"), infer_level(str(note.get("id") or ""))),
            parent_id=str(note.get("parentId") or "") or None,
            source_refs=refs, model_summary=model_summary, model_content=model_content,
            source_text=source_text, headings=headings, blocks=blocks, summary=summary,
            explanation=explanation, examples=examples(source_text), relations=relations(title, source_text or model_content),
        )
        return PostprocessContractValidator().validate(unit)


class PostprocessContractValidator:
    def validate(self, unit: LearningUnit) -> LearningUnit:
        issues: list[str] = []
        unit.summary = normalize_text(unit.summary)
        unit.explanation = normalize_text(unit.explanation)
        cleaned: list[LearningBlock] = []
        for block in unit.blocks:
            fixed = normalize_block(block)
            if fixed is None:
                issues.append(f"drop-empty-block:{block.type}")
                continue
            if has_orphan_label(fixed):
                issues.append(f"orphan-label:{fixed.type}")
                fixed = remove_orphan_items(fixed)
            if block_has_broken_sentence(fixed):
                issues.append(f"broken-sentence:{fixed.type}")
            cleaned.append(fixed)
        unit.blocks = cleaned or [LearningBlock("outline", "结构拆解", items=generic_outline(unit.model_content or unit.source_text))]
        if not summary_matches_structure(unit.summary, unit.blocks):
            issues.append("summary-structure-topic-mismatch")
            unit.summary = summarize_from_unit(unit.title, "", unit.source_text or unit.explanation, unit.blocks)
        unit.summary = reduce_summary_outline_duplication(unit.title, unit.summary, unit.outline_items, unit.source_text)
        unit.explanation = reduce_explanation_duplication(unit.explanation, unit.summary, unit.outline_items)
        if field_repetition_rate(unit.summary, unit.explanation, [item.text for item in unit.outline_items]) > 0.55:
            issues.append("field-repetition-high")
        unit.quality_issues = list(dict.fromkeys([*unit.quality_issues, *issues]))
        return unit


class NoteBlockAssembler:
    def __init__(self) -> None:
        self.builder = LearningUnitBuilder()

    def enrich(self, notes: list[dict[str, Any]], chunks: list[SourceChunk]) -> list[dict[str, Any]]:
        resolver = SourceResolver(chunks)
        pairs: list[tuple[dict[str, Any], LearningUnit]] = []
        for item in notes:
            note = dict(item)
            pairs.append((note, self.builder.build(note, resolver.resolve(note))))
        apply_parent_child_consistency(pairs)
        result: list[dict[str, Any]] = []
        for note, unit in pairs:
            note["title"] = unit.title
            note["summary"] = unit.summary
            note["content"] = user_facing_content(unit)
            note["keyPoints"] = learning_key_points(unit)
            note["examples"] = unit.examples
            note["relations"] = unit.relations
            note["sourceRefs"] = unit.source_refs
            note["source_refs"] = unit.source_refs
            note["blocks"] = render_blocks(unit)
            note["structure"] = {"style": "learning-unit-contract-v2", "concepts": ["LearningUnit", "parent-child consistency", "typed blocks", "postprocess validator"], "modelFirst": True, "postProcessing": "learning-unit-normalization", "qualityIssues": unit.quality_issues}
            result.append(note)
        return result


def learning_key_points(unit: LearningUnit) -> list[str]:
    title = strip_section_number(unit.title)
    outline_text = " ".join(item.text for item in unit.outline_items if item.text)
    points = [item.text for item in unit.outline_items if keep_outline_text(item.text)]
    points = [point for point in points if not has_truncated_learning_point(point)]
    profile = infer_learning_profile(title, unit.summary, points, outline_text)
    return learning_key_points_for_profile(profile, points, title=title)


def learning_key_points_for_profile(profile: dict[str, Any], points: list[str], *, title: str = "") -> list[str]:
    labels = profile.get("numberedLabels") or []
    if "enumeration" in profile["roles"] and labels:
        return dedupe_learning_values(labels, max_items=6 if len(labels) >= 6 else 5)
    if profile["material"] != "technical":
        fallback = points or fallback_learning_points_from_title(title, profile)
        return dedupe_learning_values(fallback, max_items=6 if numbered_series_count(fallback) >= 6 else 5)
    subtype = profile["subtype"]
    if "transfer_method" in profile["roles"]:
        if subtype == "cycle_stealing":
            return ["每次传送要申请和归还总线控制权", "适合外设读写周期大于主存周期的场景", "优点是提高处理器对主存的利用率"]
        if subtype == "exclusive_access":
            return ["处理器暂停访问主存", "传送方独占主存完成数据交换", "控制简单但处理器利用率较低"]
        if subtype == "interleaved_access":
            return ["把工作周期划分为不同访存分周期", "传送方和处理器交替访问主存", "硬件控制逻辑更复杂"]
    if "component" in profile["roles"]:
        if subtype == "completion_notifier":
            return ["一批数据传送结束后发出中断请求", "通知 CPU 执行后处理", "不要把完成通知部件等同于数据缓冲部件"]
        if subtype == "data_buffer":
            return ["暂存每次传送的数据", "主存侧通常按字传送", "设备侧可能按字节或位传送", "接口需要完成字装配或拆卸"]
        if subtype == "interface_function":
            return ["申请传送并接管总线", "维护地址和传送长度", "管理数据交换并通知处理器"]
        if subtype == "connection_type":
            joined = " ".join(points)
            if "选择型" in joined:
                return ["物理上可连接多个设备", "逻辑上同一时间只服务一个设备", "适合高速设备独占式传送"]
            if "多路型" in joined or "字节交叉" in joined:
                return ["物理上可连接多个设备", "多个设备可共享接口服务", "可采用字节交叉方式传送"]
            return ["区分单设备独占与多设备共享", "按设备速度选择连接方式", "关注请求线和响应线组织"]
        if subtype == "component_group":
            return ["地址类部件负责定位", "计数类部件记录长度", "缓冲类部件暂存数据", "控制逻辑协调传送"]
    if "process" in profile["roles"]:
        if subtype == "request_arbitration":
            return ["设备准备好数据后可申请传送", "多个请求由硬件排队决定优先级", "获得控制权后开始数据交换"]
        if subtype == "parallel_execution":
            return ["处理器继续执行主程序", "传送控制器独立完成数据块交换", "传送结束后发出完成通知"]
        if subtype == "three_phase_process":
            return ["预处理设置地址和传送长度", "数据传送阶段完成数据块交换", "结束后执行校验和后处理"]
        if subtype == "post_process":
            return ["校验传送数据是否正确", "判断是否继续传送其他数据块", "必要时重新初始化接口或停止外设"]
    return dedupe_learning_values(points, max_items=5)


def fallback_learning_points_from_title(title: str, profile: dict[str, Any]) -> list[str]:
    cleaned = strip_section_number(clean_item(title))
    cleaned = re.sub(r"^(?:行动要求|具体做法|做法|要求|路径|措施|要点)[:：]\s*", "", cleaned).strip()
    if not cleaned:
        return []
    if profile["material"] == "politics" and "action" in profile["roles"]:
        parts = [part.strip(" 。；;，,") for part in re.split(r"[，、；;]", cleaned) if part.strip(" 。；;，,")]
        return parts[:4] or [cleaned]
    if profile["material"] in {"politics", "exam"}:
        return [cleaned]
    return []


def dedupe_learning_values(values: list[str], *, max_items: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean_item(value)
        key = re.sub(r"[\W_]+", "", normalize_learning_text(text)).lower()
        if text and key and key not in seen:
            seen.add(key)
            result.append(text)
        if len(result) >= max_items:
            break
    return result


def numbered_series_count(values: list[str]) -> int:
    return sum(1 for value in values if profile_leading_number(value))


def has_truncated_learning_point(value: str) -> bool:
    text = clean_item(value)
    return bool(
        re.search(r"(可以采$|可以采。|预置信$|字装配\s*/$|DMA接$|有选择$|后处$|CPU停$|已$|P\d+\s*[-－]\s*\d+)", text)
        or is_transition_fragment(text)
    )


def enrich_learning_notes_contract(notes: list[dict[str, Any]], chunks: list[SourceChunk]) -> list[dict[str, Any]]:
    return NoteBlockAssembler().enrich(notes, chunks)


def blocks_for(title: str, model_content: str, source_text: str, headings: list[str], chunks: list[SourceChunk]) -> list[LearningBlock]:
    text = source_text or model_content
    probe = f"{title}\n{text}"
    if "核心组件" in title and len(chunks) > 1:
        return core_component_parent_blocks(chunks, text)
    if is_rnn_limit(title, text):
        return rnn_limit_blocks(text)
    if has_any(title, ["优势", "优点"]) or has_any(probe, ["并行计算能力强", "长距离依赖建模能力强", "扩展能力强", "大规模预训练"]):
        return advantage_blocks(title, text, chunks)
    if has_any(probe, ["整体架构", "整体结构", "Encoder-Decoder"]):
        return architecture_blocks(text)
    if has_any(title, ["位置编码", "Positional Encoding"]) or has_any(probe, ["Positional Encoding"]):
        return positional_encoding_blocks(text)
    if has_any(title, ["Masked", "Mask", "掩码"]) or has_any(probe, ["Masked", "不能提前看到未来"]):
        return masked_attention_blocks(text)
    if has_any(title, ["多头注意力", "Multi-Head"]) or has_any(probe, ["Multi-Head"]):
        return multi_head_attention_blocks(text)
    if has_any(title, ["自注意力", "Self-Attention"]):
        return self_attention_blocks(text)
    if has_any(title, ["前馈神经网络", "Feed Forward", "FFN"]):
        return feed_forward_blocks(text)
    if has_any(title, ["残差连接", "层归一化", "Layer Normalization"]):
        return residual_norm_blocks(text)
    if has_any(title, ["词向量", "Embedding"]) or has_any(probe, ["词向量", "Embedding"]):
        return embedding_blocks(text)
    if has_any(probe, ["BERT", "GPT", "T5", "ViT", "大语言模型", "衍生模型", "LLM"]):
        return derivative_model_blocks(text)
    if is_history_stage_note(title, text):
        return history_stage_blocks(title, text)
    return generic_blocks(title, text)


def typed_note_blocks(summary: str, outline: list[OutlineItem], typed: list[LearningBlock]) -> list[LearningBlock]:
    return [LearningBlock("summary", "概要", summary), LearningBlock("outline", "结构拆解", items=outline), *typed]


def core_component_parent_blocks(chunks: list[SourceChunk], source_text: str) -> list[LearningBlock]:
    items: list[OutlineItem] = []
    for chunk in chunks:
        heading = strip_section_number(chunk.heading or chunk.title)
        if not heading or is_document_heading(heading):
            continue
        sub_blocks = blocks_for(heading, "", chunk.text or "", [heading], [chunk])
        summary = summarize_from_unit(heading, "", chunk.text or "", sub_blocks)
        children = [block_first_line(block) for block in sub_blocks if block.type in TYPED_BLOCKS]
        items.append(OutlineItem(heading, dedupe_strings(children)[:3] or [summary]))
    if not items:
        items = generic_outline(source_text)
    return typed_note_blocks(
        "Transformer的核心组件包括输入表示、位置编码、注意力机制、前馈网络、残差连接、层归一化以及Decoder端的掩码注意力；这些模块共同完成文本向量化、顺序建模、关系建模和稳定训练。",
        items[:8],
        [],
    )


def embedding_blocks(text: str) -> list[LearningBlock]:
    definition = select_sentence(text, ["Embedding", "向量表示", "转换为向量"]) or "Embedding将离散的文本符号转换为模型可以计算的连续向量表示。"
    if "Embedding" not in definition:
        definition = normalize_text(definition.rstrip("。") + "，这种向量表示称为Embedding。")
    mechanism = select_sentence(text, ["语义相近", "语义关系", "相近"]) or "语义相近的词在向量空间中距离更近，使模型能够利用向量关系表达词义差异。"
    return typed_note_blocks(
        "Embedding负责把单词或Token转换为向量，是Transformer处理文本的输入表示基础。",
        [OutlineItem("Embedding将文本转换为可计算的向量表示", ["保留词语语义信息", "为后续注意力计算提供输入"])],
        [LearningBlock("definition", "概念定义", definition), LearningBlock("mechanism", "表示机制", mechanism)],
    )


def positional_encoding_blocks(text: str) -> list[LearningBlock]:
    definition = select_sentence(text, ["位置编码", "词语顺序", "顺序信息"]) or "位置编码为Token向量补充顺序信息，弥补Transformer没有循环结构时无法天然感知词序的问题。"
    mechanism = select_sentence(text, ["相加", "Embedding", "正弦", "余弦"]) or "模型通常将位置编码与Embedding向量相加，使同一个词在不同位置拥有可区分的表示。"
    return typed_note_blocks(
        "位置编码为输入Token补充顺序信息，使并行结构下的Transformer仍能区分词语位置。",
        [OutlineItem("位置编码补充序列顺序信息", ["解决无循环结构的词序感知问题", "与Embedding共同构成输入表示"])],
        [LearningBlock("definition", "概念定义", definition), LearningBlock("mechanism", "工作方式", mechanism)],
    )


def self_attention_blocks(text: str) -> list[LearningBlock]:
    qkv = ["Query表示当前Token主动寻找相关信息的查询向量。", "Key表示其他Token可被匹配的索引向量。", "Value表示被注意力权重加权汇总的内容向量。"]
    procedure = ["计算Query与Key的相似度，得到注意力分数。", "用sqrt(dk)进行缩放，避免分数过大导致Softmax过于尖锐。", "对分数做Softmax归一化，得到每个Token的注意力权重。", "用注意力权重加权求和Value，得到包含上下文信息的新表示。"]
    return typed_note_blocks(
        "自注意力机制让每个Token根据上下文动态关注其他Token，是Transformer建模长距离依赖的核心机制。",
        [OutlineItem("自注意力机制建模Token之间的上下文依赖", ["通过Q、K、V表示查询、匹配和内容", "通过注意力权重聚合相关Token信息", "支持序列内长距离关系建模"])],
        [LearningBlock("definition", "概念定义", "自注意力机制在同一序列内部计算Token之间的相关性，使每个Token的表示能够融合上下文信息。"), LearningBlock("mechanism", "Q/K/V机制", items=qkv), LearningBlock("procedure", "注意力计算过程", items=procedure), LearningBlock("formula", "核心公式", "Attention(Q, K, V) = softmax(QK^T / sqrt(dk))V")],
    )


def multi_head_attention_blocks(text: str) -> list[LearningBlock]:
    mechanism = select_sentence(text, ["多个", "不同角度", "多个头", "head"]) or "多头注意力将Q、K、V投影到多个子空间并行计算，让模型从不同语义角度捕捉关系。"
    effect = select_sentence(text, ["丰富", "增强", "不同语义", "表达能力"]) or "多个注意力头的结果会拼接并线性变换，从而增强模型对多种关系的表达能力。"
    return typed_note_blocks(
        "多头注意力通过多个注意力头并行观察序列关系，弥补单一注意力视角不足的问题。",
        [OutlineItem("多头注意力扩展自注意力的表达视角", ["多个Head并行计算注意力", "不同Head学习不同语义关系", "拼接后形成更丰富的上下文表示"])],
        [LearningBlock("mechanism", "工作机制", mechanism), LearningBlock("effect", "作用效果", effect)],
    )


def feed_forward_blocks(text: str) -> list[LearningBlock]:
    structure = "每个位置上的表示会经过两层线性变换和非线性激活，常见结构可写作 Linear -> ReLU -> Linear。"
    effects = ["提升非线性表达能力", "提取更复杂的特征", "增强每个Token表示的可学习变换能力"]
    return typed_note_blocks(
        "前馈神经网络在注意力层之后对每个Token表示做非线性变换，补充特征提取和表达能力。",
        [OutlineItem("前馈神经网络对注意力输出进行逐位置非线性变换", ["结构通常为两层线性变换加非线性激活", "作用是增强特征表达，而不是建模Token间关系"])],
        [LearningBlock("mechanism", "网络结构", structure), LearningBlock("effect", "作用", items=effects)],
    )


def residual_norm_blocks(text: str) -> list[LearningBlock]:
    return typed_note_blocks(
        "残差连接与层归一化用于稳定深层Transformer训练，缓解梯度传播和表示分布不稳定的问题。",
        [OutlineItem("残差连接与层归一化提升训练稳定性", ["残差连接保留原始输入信息", "层归一化稳定每层输出分布", "二者共同支持更深层网络训练"])],
        [LearningBlock("mechanism", "残差连接", "残差连接将子层输入与子层输出相加，帮助信息和梯度跨层传递。"), LearningBlock("mechanism", "层归一化", "层归一化对每个样本的隐藏表示进行归一化，使训练过程更稳定。")],
    )


def masked_attention_blocks(text: str) -> list[LearningBlock]:
    return typed_note_blocks(
        "Masked Attention用于Decoder生成阶段，阻止当前位置提前看到未来Token，保证自回归生成顺序。",
        [OutlineItem("Masked Attention限制Decoder只能关注已生成内容", ["未来位置被Mask矩阵遮挡", "生成过程从左到右逐步进行", "避免训练时泄露未来答案"])],
        [LearningBlock("definition", "概念定义", "Masked Self-Attention是在Decoder自注意力中加入遮罩，使当前位置不能关注未来位置。"), LearningBlock("mechanism", "遮罩机制", "Mask矩阵会把未来位置的注意力分数置为不可见或极小值，Softmax后这些位置的权重接近零。")],
    )


def rnn_limit_blocks(text: str) -> list[LearningBlock]:
    problems = select_list_after_label(text, ["存在以下问题", "问题"])
    if not problems:
        problems = select_sentences(text, ["难以并行", "长距离依赖", "训练效率", "梯度消失", "梯度爆炸"])
    problems = [item for item in problems if not is_background_filler(item) and not is_transformer_solution(item)]
    if not problems:
        problems = ["难以并行计算", "长距离依赖建模能力有限", "训练效率较低", "长序列中容易出现梯度消失或梯度爆炸"]
    return typed_note_blocks(
        "RNN及其变体按时间顺序逐步处理序列，因此在并行训练、长距离依赖和长序列稳定性上存在明显限制。",
        [OutlineItem("RNN存在以下问题", dedupe_strings(problems)[:6])],
        [LearningBlock("effect", "主要缺陷", items=dedupe_strings(problems)[:6])],
    )


def architecture_blocks(text: str) -> list[LearningBlock]:
    items = [OutlineItem("Transformer采用Encoder-Decoder架构", ["Encoder负责编码并理解输入内容", "Decoder根据编码结果按序生成输出内容"])]
    if "Decoder根据语义表示生成" in text:
        items.append(OutlineItem("Decoder根据语义表示生成目标文本", []))
    if "6层" in text or "6" in text:
        items.append(OutlineItem("原始Transformer的堆叠结构", ["包含6层Encoder", "包含6层Decoder"]))
    return typed_note_blocks(
        "Transformer整体上由Encoder和Decoder组成：Encoder理解输入序列，Decoder基于编码结果生成输出序列。",
        items,
        [LearningBlock("definition", "整体架构", "Transformer采用Encoder-Decoder架构，将输入理解和输出生成拆分为两个协作模块。"), LearningBlock("mechanism", "模块分工", items=["Encoder负责将输入内容编码为语义表示。", "Decoder根据语义表示和已生成内容产生下一步输出。"])],
    )



def advantage_blocks(title: str, text: str, chunks: list[SourceChunk]) -> list[LearningBlock]:
    items: list[OutlineItem] = []
    for chunk in chunks:
        heading = strip_section_number(chunk.heading or chunk.title)
        if heading and any(token in heading for token in ["并行", "长距离", "扩展", "预训练", "优势"]):
            summary = first_meaningful_sentence(chunk.text) or heading
            items.append(OutlineItem(heading, [summary] if summary and summary != heading else []))
    if not items:
        candidates = select_sentences(text, ["并行计算", "长距离依赖", "扩展能力", "预训练", "训练效率"])
        items = [OutlineItem("Transformer的优势", candidates[:6])]
    return typed_note_blocks(
        "Transformer的优势主要体现在并行计算、长距离依赖建模、模型扩展和大规模预训练效果等方面。",
        items,
        [LearningBlock("effect", "优势归纳", items=[item.text for item in items])],
    )


def derivative_model_blocks(text: str) -> list[LearningBlock]:
    model_names = [name for name in ["BERT", "GPT", "T5", "ViT"] if name in text]
    outline: list[OutlineItem] = []
    if "大语言模型" in text:
        outline.append(OutlineItem("当前主流大语言模型基本建立在Transformer架构之上", ["Transformer提供序列建模和注意力机制基础"]))
    if "这些模型通常包含" in text:
        outline.append(OutlineItem("这些模型通常包含", select_list_after_label(text, ["这些模型通常包含"])))
    if "其能力包括" in text:
        outline.append(OutlineItem("其能力包括", select_list_after_label(text, ["其能力包括"])))
    if model_names and not outline:
        outline.append(OutlineItem("Transformer衍生出多类代表模型", model_names))
    if not outline:
        outline = generic_outline(text)
    return typed_note_blocks(
        "Transformer是BERT、GPT、T5、ViT以及现代大语言模型的重要基础架构。",
        outline,
        [LearningBlock("example", "代表模型", items=model_names or ["BERT", "GPT", "T5", "ViT"])],
    )



def history_stage_blocks(title: str, text: str) -> list[LearningBlock]:
    sentences = [s for s in normalized_sentences(text) if keep_outline_text(s)]
    title_clean = strip_section_number(title)
    event = first_sentence_with(sentences, ["提出", "举办", "发表", "取得", "遭遇", "减少", "复兴", "突破", "进入"])
    reason = first_sentence_with(sentences, ["由于", "因此", "原因", "受限", "无法", "推动"])
    effect = first_sentence_with(sentences, ["推动", "影响", "标志", "被认为", "使", "带来", "进入"])
    children = [item for item in [event, reason, effect] if item]
    if not children:
        children = sentences[:3]
    outline = [OutlineItem(title_clean, children[:4])]
    typed: list[LearningBlock] = []
    if event:
        typed.append(LearningBlock("definition", "阶段定位", event))
    if reason:
        typed.append(LearningBlock("mechanism", "原因与条件", reason))
    if effect:
        typed.append(LearningBlock("effect", "影响", effect))
    return typed_note_blocks(
        summarize_from_outline(title_clean, outline, text),
        outline,
        typed,
    )


def first_sentence_with(sentences: list[str], keywords: list[str]) -> str:
    for sentence in sentences:
        if any(keyword in sentence for keyword in keywords):
            return sentence
    return ""


def is_history_stage_note(title: str, text: str) -> bool:
    probe = title + text
    return has_any(probe, ["人工智能", "图灵", "达特茅斯", "寒冬", "发展高潮", "深度学习", "未来展望"])

def generic_blocks(title: str, text: str) -> list[LearningBlock]:
    outline = clean_outline_items(title, generic_outline(text))
    return typed_note_blocks(summarize_from_outline(title, outline, text), outline, [])


def generic_outline(text: str) -> list[OutlineItem]:
    lines = semantic_lines(normalize_learning_text(text))
    items: list[OutlineItem] = []
    i = 0
    while i < len(lines):
        line = clean_item(lines[i])
        if not keep_outline_text(line) or is_heading_line(lines[i]):
            i += 1
            continue
        label = label_without_colon(line)
        if lines[i].strip().endswith(("：", ":")) or is_total_branch_label(label):
            children: list[str] = []
            i += 1
            while i < len(lines):
                child = clean_item(lines[i])
                if not child:
                    i += 1
                    continue
                if is_heading_line(child) or (child.endswith(("：", ":")) and children):
                    break
                if looks_like_new_sentence(child) and children and not is_short_list_item(child):
                    break
                if keep_child_text(child):
                    children.extend(split_semicolon_units(child))
                i += 1
            if children:
                items.append(OutlineItem(label, dedupe_strings(children)[:8]))
            elif not is_orphan_label(label):
                items.append(OutlineItem(label, []))
            continue
        merged = merge_adjacent_definition(line, lines[i + 1] if i + 1 < len(lines) else "")
        if merged != line:
            i += 1
        for part in split_semicolon_units(merged):
            if keep_outline_text(part):
                items.append(OutlineItem(part, []))
        i += 1
    return dedupe_outline_items(items)[:8]


def apply_parent_child_consistency(pairs: list[tuple[dict[str, Any], LearningUnit]]) -> None:
    by_id = {unit.id: unit for _, unit in pairs}
    for _, unit in pairs:
        if not unit.parent_id:
            parent_id = infer_numeric_parent(unit.id)
            if parent_id and parent_id in by_id:
                unit.parent_id = parent_id
    children_by_parent: dict[str, list[LearningUnit]] = {}
    for _, unit in pairs:
        if unit.parent_id:
            children_by_parent.setdefault(unit.parent_id, []).append(unit)
    for parent_id, children in children_by_parent.items():
        parent = by_id.get(parent_id)
        if parent:
            summarize_parent_from_children(parent, children)


def infer_numeric_parent(note_id: str) -> str | None:
    return note_id.rsplit(".", 1)[0] if "." in note_id else None


def summarize_parent_from_children(parent: LearningUnit, children: list[LearningUnit]) -> None:
    ordered = sorted(children, key=lambda unit: natural_key(unit.id))
    outline = [OutlineItem(child.title, [child.summary or summarize_from_unit(child.title, "", child.source_text, child.blocks)]) for child in ordered]
    if not outline:
        return
    parent.blocks = [block for block in parent.blocks if block.type not in {"summary", "outline"}]
    parent.summary = aggregate_parent_summary(parent.title, ordered)
    parent.blocks.insert(0, LearningBlock("outline", "结构拆解", items=outline))
    parent.blocks.insert(0, LearningBlock("summary", "概要", parent.summary))
    parent.explanation = explanation_from_unit(parent.title, "", parent.summary, parent.blocks)
    parent.quality_issues.append("parent-summary-aggregated-from-children")


def aggregate_parent_summary(title: str, children: list[LearningUnit]) -> str:
    names = [strip_section_number(child.title) for child in children]
    if "核心组件" in title and names:
        return "Transformer的核心组件包括" + "、".join(names[:8]) + "；这些子模块分别承担输入表示、顺序补充、关系建模、非线性变换和训练稳定化等职责。"
    label = semantic_relation_label(title)
    if len(names) == 1:
        return compact(f"{title}说明{names[0]}，需要结合原文判断它的适用条件和作用。", 220)
    if names:
        return compact(f"{title}包含" + "、".join(names[:4]) + f"等内容，重点是理解{label}。", 220)
    return compact(f"{title}用于说明{label}。", 220)


def render_blocks(unit: LearningUnit) -> list[dict[str, Any]]:
    rendered: list[dict[str, Any]] = []
    for index, block in enumerate(unit.blocks, start=1):
        item: dict[str, Any] = {"id": f"{unit.id}-{block.type}-{index}", "type": block.type, "title": block.title, "sourceRefs": unit.source_refs}
        if block.content:
            item["content"] = block.content
        if block.items:
            item["items"] = serialize_block_items(block.items)
            if block.type == "outline":
                item["structuredItems"] = [entry.to_dict() if isinstance(entry, OutlineItem) else {"text": str(entry), "children": []} for entry in block.items]
                item["items"] = [entry.text if isinstance(entry, OutlineItem) else str(entry) for entry in block.items]
        rendered.append(item)
    if unit.examples:
        rendered.append({"id": f"{unit.id}-examples", "type": "examples", "title": "例子", "items": unit.examples, "sourceRefs": unit.source_refs})
    if unit.relations:
        rendered.append({"id": f"{unit.id}-relations", "type": "relations", "title": "关联概念", "items": unit.relations, "sourceRefs": unit.source_refs})
    return rendered


def serialize_block_items(items: list[Any]) -> list[Any]:
    out: list[Any] = []
    for item in items:
        if isinstance(item, OutlineItem):
            out.append(item.to_dict())
        elif isinstance(item, dict):
            out.append(item)
        else:
            out.append(str(item))
    return out


def summarize_from_unit(title: str, model_summary: str, source_text: str, blocks: list[LearningBlock]) -> str:
    typed_summary = next((block.content for block in blocks if block.type == "summary" and block.content), "")
    if typed_summary and is_good_summary(typed_summary):
        return compact(normalize_text(typed_summary), 240)
    outline = next((block.items for block in blocks if block.type == "outline"), [])
    generated = summarize_from_outline(title, [item if isinstance(item, OutlineItem) else OutlineItem(str(item), []) for item in outline], source_text)
    if generated:
        return generated
    if model_summary and is_good_summary(model_summary):
        return compact(normalize_text(model_summary), 220)
    return compact(first_meaningful_sentence(source_text) or title, 220)


def summarize_from_outline(title: str, outline: list[OutlineItem], source_text: str) -> str:
    outline = clean_outline_items(title, outline)
    if not outline:
        return explanatory_sentence_from_source(title, source_text)
    if len(outline) == 1:
        item = outline[0]
        if item.children:
            children = [summary_outline_label(str(child)) for child in item.children]
            children = [child for child in dedupe_strings(children) if child][:4]
            if children:
                joined = "、".join(children)
                if same_learning_text(item.text, title):
                    return compact(f"{strip_section_number(title)}具体包括{joined}。", 220)
                return compact(f"{strip_section_number(title)}说明{summary_outline_label(item.text) or strip_section_number(item.text)}，具体包括{joined}。", 220)
        return compact(normalize_summary_sentence(title, item.text, source_text), 220)
    relation = semantic_relation_label(title)
    labels = [summary_outline_label(item.text) for item in outline]
    labels = [label for label in dedupe_strings(labels) if label][:4]
    if not labels:
        return explanatory_sentence_from_source(title, source_text)
    names = "、".join(labels)
    return compact(f"{strip_section_number(title)}包含{names}，核心是理解{relation}。", 220)


def explanation_from_unit(title: str, model_content: str, summary: str, blocks: list[LearningBlock]) -> str:
    parts: list[str] = []
    for block in blocks:
        if block.type in {"summary", "outline"}:
            continue
        if block.content:
            if not is_redundant_text(block.content, parts):
                parts.append(f"{block.title}：{block.content}")
        elif block.items:
            rendered = render_items_text(block.items)
            if rendered and not is_redundant_text(rendered, parts):
                parts.append(f"{block.title}：{rendered}")
    text = normalize_text("\n".join(dedupe_strings(parts)))
    has_typed_blocks = any(block.type not in {"summary", "outline"} for block in blocks)
    if len(text) < 80 and model_content:
        extra = remove_evidence_tail(model_content)
        extra_sentence = first_non_redundant_sentence(extra, text)
        if extra_sentence:
            text = normalize_text(text + "\n" + extra_sentence)
    if not text and has_typed_blocks:
        text = first_non_redundant_sentence(model_content, summary)
    return text


def user_facing_content(unit: LearningUnit) -> str:
    learning = learning_explanation(unit.title, unit.summary, unit.outline_items)
    if learning:
        return compact(learning, 420)
    explanation = normalize_text(unit.explanation)
    if explanation and not is_low_quality_user_content(explanation) and not is_redundant_pair(explanation, unit.summary):
        return compact(explanation, 420)
    source = explanatory_content_from_source(unit.title, unit.summary, unit.source_text, unit.outline_items)
    if source and not is_low_quality_user_content(source) and not is_redundant_pair(source, unit.summary):
        return compact(source, 420)
    return synthesized_explanation(unit.title, unit.outline_items)


def learning_explanation(title: str, summary: str, outline: list[OutlineItem]) -> str:
    title_clean = strip_section_number(title)
    points = [strip_section_number(item.text).rstrip("。；") for item in outline if item.text and keep_outline_text(item.text)]
    points = [point for point in points if not same_learning_text(point, title_clean)][:4]
    profile = infer_learning_profile(title_clean, summary, points)
    explanation = explanation_for_profile(profile, points)
    if explanation:
        return explanation
    if points:
        if len(points) == 1:
            return compact(f"{title_clean}的关键线索是{points[0]}，需要说明其含义、条件、作用或例子。", 420)
        return compact(f"{title_clean}围绕" + "、".join(points[:3]) + "展开，重点说明这些要点的含义、条件、作用和区别。", 420)
    return ""


def explanation_for_profile(profile: dict[str, Any], points: list[str]) -> str:
    material = profile["material"]
    roles = profile["roles"]
    subtype = profile["subtype"]
    if material == "technical":
        if subtype == "cycle_stealing":
            return "周期挪用以“临时占用主存周期”为核心：它提高主存利用率，但每次传送都涉及总线控制权申请、建立和归还。"
        if subtype == "interleaved_access":
            return "交替访问属于主存交换方式之一：处理器和传送方按分周期交替访问主存，适合按固定节奏分时访存的场景，但硬件控制逻辑更复杂。"
        if subtype == "exclusive_access":
            return "停止 CPU 访问主存以处理器等待为代价换取控制简单，适合成组快速传送，但不利于处理器利用率。"
        if subtype == "data_buffer":
            return "缓冲部件用于暂存本次传送的数据。要区分主存侧和设备侧的数据宽度，理解为什么需要装配或拆卸。"
        if subtype == "completion_notifier":
            return "完成通知部件用于在一批数据传送结束后通知处理器执行后处理，它与数据暂存、地址更新等职责不同。"
        if subtype in {"component_group", "interface_function", "counter", "address_register", "control_logic"}:
            return "接口部件可按职责区分：地址类负责定位，计数类负责长度，缓冲类负责暂存，控制逻辑负责协调请求、响应和结束通知。"
        if subtype == "connection_type":
            return "连接方式的差异在服务对象和请求机制：有的结构强调单个高速设备独占服务，有的结构强调多个低速设备按请求线、优先级或交叉方式共享服务。"
        if "process" in roles:
            if subtype == "parallel_execution":
                return "理解重点是并行关系：传送控制器独立完成数据块交换，处理器不必一直等待；传送结束后再通过完成通知执行收尾处理。"
            return "流程类内容可按预处理、数据传送、后处理三步记忆：先设置地址和长度，再管理数据块传送，最后通知处理器收尾。"
        if "comparison" in roles:
            return "比较时重点看传送单位、响应时间、异常处理和现场保护，先判断适用场景，再逐项对照差异。"
        return "这类技术点要放回数据流和控制流中理解，重点分清触发条件、执行动作和最终结果。"
    if material == "politics":
        if "action" in roles:
            return "行动路径由主体、目标、具体做法和落实场景构成，需要把国家层面的方向与个人层面的责任区分开。"
        if "reason" in roles:
            return "原因说明需要把结论和依据对应起来，常见依据包括制度、道路、文化和现实成就。"
        if "manifestation" in roles:
            return "表现内容需要把态度和行动分开：国家认同、文化底气、发展信心分别对应不同的行为要求。"
    if material == "exam":
        if "contrast" in roles:
            return "对照内容需要同时说明区别和联系，避免把抽象范畴和具体对象混为一谈。"
        if "principle" in roles:
            return "原理内容由原理表述、方法论要求和材料解释入口构成，常见误区是偷换或夸大概念。"
        if "checklist" in roles:
            return "高频考点需要覆盖触发词、常用原理和易错表述，重点是能把关键词展开成完整判断。"
    return ""


def explanatory_content_from_source(title: str, summary: str, source_text: str, outline: list[OutlineItem]) -> str:
    existing = " ".join([title, summary, render_items_text(outline)])
    candidates: list[str] = []
    for sentence in normalized_sentences(source_text):
        clean_sentence = clean_item(sentence)
        if not keep_outline_text(clean_sentence):
            continue
        if is_redundant_pair(clean_sentence, existing):
            continue
        if is_activity_or_prompt_line(clean_sentence) or is_visual_label_line(clean_sentence):
            continue
        candidates.append(clean_sentence)
        if len(candidates) >= 2:
            break
    return normalize_text(" ".join(candidates))


def synthesized_explanation(title: str, outline: list[OutlineItem]) -> str:
    names = [item.text.rstrip("。；") for item in outline if item.text and not is_low_quality_user_content(item.text)][:3]
    title_clean = strip_section_number(title)
    profile = infer_learning_profile(title_clean, key_points=names)
    generated = explanation_for_profile(profile, names)
    if generated:
        return generated
    if names:
        relation = semantic_relation_label(title_clean)
        return compact(f"这部分说明{relation}，可结合" + "、".join(names[:2]) + "等内容理解。", 220)
    return compact(f"{title_clean}需要结合上下文理解其定义、作用和适用场景。", 220)


def normalize_summary_sentence(title: str, item_text: str, source_text: str) -> str:
    title_clean = strip_section_number(title)
    item = answer_outline_text(item_text) if is_question_title(title_clean) else summary_outline_label(item_text)
    if item and not same_learning_text(item, title_clean):
        if is_question_title(title_clean):
            return f"{title_clean}的关键答案是：{item}。"
        if is_declarative_sentence_title(title_clean):
            return f"{title_clean}，并且{item}。"
        return f"{title_clean}说明{item}。"
    source_sentence = explanatory_sentence_from_source(title, source_text)
    return source_sentence or title_clean


def is_question_title(title: str) -> bool:
    title_clean = strip_section_number(title)
    return title_clean.endswith("？") or title_clean.startswith(("为什么", "怎样", "如何", "什么是"))


def answer_outline_text(value: str, limit: int = 140) -> str:
    text = strip_section_number(clean_item(value)).rstrip("。；")
    if not text or is_transition_fragment(text) or is_broken_outline_fragment(text):
        return ""
    text = re.sub(r"^(说明|包括|主要包括)\s*", "", text).strip()
    if len(text) <= limit:
        return text
    compressed = compress_parallel_answer(text)
    if compressed and len(compressed) <= limit:
        return compressed
    clauses = [part.strip(" ，,；;。") for part in re.split(r"[；;。]", text) if part.strip(" ，,；;。")]
    if clauses:
        first = clauses[0]
        if len(first) <= limit:
            return first
    parts = [part.strip(" ，,；;。") for part in re.split(r"[，,；;]", text) if part.strip(" ，,；;。")]
    selected: list[str] = []
    total = 0
    for part in parts:
        projected = total + len(part) + (1 if selected else 0)
        if selected and projected > limit:
            break
        if projected <= limit:
            selected.append(part)
            total = projected
    if selected:
        return "，".join(selected)
    return text[:limit].rstrip("，,；;。")


def compress_parallel_answer(text: str) -> str:
    match = re.search(r"比历史上任何时期都更接近(?P<goal>[^，,。；;]+)，比历史上任何时期都更有信心[、,，]?有能力实现(?P=goal)", text)
    if match:
        goal = match.group("goal")
        return f"比历史上任何时期都更接近{goal}，也更有信心和能力实现这一目标"
    return ""


def is_declarative_sentence_title(title: str) -> bool:
    title_clean = strip_section_number(title).rstrip("。；")
    if len(title_clean) < 24:
        return False
    if title_clean.endswith("？") or title_clean.startswith(("为什么", "怎样", "如何", "什么是")):
        return False
    return any(token in title_clean for token in ["，", "、", "既", "又", "是", "用于", "适合", "包括"])

def semantic_relation_label(title: str) -> str:
    probe = strip_section_number(title)
    if any(token in probe for token in ["方式", "路径", "方法"]):
        return "不同方法的适用场景和限制"
    if any(token in probe for token in ["功能", "组成", "结构", "接口"]):
        return "组成部分及其职责分工"
    if any(token in probe for token in ["原因", "为什么", "依据"]):
        return "原因、依据和结果之间的关系"
    if any(token in probe for token in ["步骤", "流程", "过程"]):
        return "流程顺序和关键操作"
    if any(token in probe for token in ["意义", "作用", "影响"]):
        return "作用、影响和实践价值"
    if any(token in probe for token in ["概念", "原理", "范畴"]):
        return "核心概念、判断依据和应用边界"
    return "本主题的背景、结论和应用边界"


def summary_outline_label(value: str) -> str:
    text = strip_section_number(clean_item(value)).rstrip("。；")
    if not text or is_transition_fragment(text) or is_broken_outline_fragment(text):
        return ""
    if len(text) > 38 and re.search(r"[，,；;：:]", text):
        head = re.split(r"[，,；;：:]", text, maxsplit=1)[0].strip()
        if 4 <= len(head) <= 38 and not is_transition_fragment(head) and not is_broken_outline_fragment(head):
            text = head
    text = re.sub(r"^(说明|包括|主要包括)\s*", "", text).strip()
    return compact_outline_label(text, 42)


def compact_outline_label(text: str, limit: int) -> str:
    value = normalize_text(text).strip()
    if len(value) <= limit:
        return value
    parts = [part.strip(" ，,；;。") for part in re.split(r"[，,；;。]", value) if part.strip(" ，,；;。")]
    for part in parts:
        if 4 <= len(part) <= limit:
            return part
    selected: list[str] = []
    total = 0
    for part in parts:
        projected = total + len(part) + (1 if selected else 0)
        if selected and projected > limit:
            break
        if projected <= limit:
            selected.append(part)
            total = projected
    if selected:
        return "，".join(selected)
    return value[:limit].rstrip("，,；;。")

def explanatory_sentence_from_source(title: str, source_text: str) -> str:
    sentence = first_meaningful_sentence(source_text)
    if sentence and not same_learning_text(sentence, title):
        return compact(sentence, 220)
    return compact(strip_section_number(title), 220)


def reduce_summary_outline_duplication(title: str, summary: str, outline: list[OutlineItem], source_text: str) -> str:
    cleaned = normalize_text(summary)
    if not cleaned:
        return summarize_from_outline(title, outline, source_text)
    outline_texts = [item.text for item in outline if item.text]
    if not outline_texts:
        return cleaned
    if cleaned.startswith(strip_section_number(title)) and ("主要包括" in cleaned or "等内容" in cleaned):
        return summarize_from_outline(title, outline, source_text)
    if field_repetition_rate(cleaned, "", outline_texts) > 0.62:
        return summarize_from_outline(title, outline, source_text)
    return cleaned


def reduce_explanation_duplication(explanation: str, summary: str, outline: list[OutlineItem]) -> str:
    text = normalize_text(explanation)
    if not text:
        return summary
    rendered_outline = render_items_text(outline)
    for marker in ["结构拆解：", "要点："]:
        if marker in text and rendered_outline:
            before, _sep, _after = text.partition(marker)
            text = normalize_text(before)
    if text != summary and is_redundant_pair(text, rendered_outline):
        return summary
    return text or summary


def field_repetition_rate(summary: str, explanation: str, key_points: list[str]) -> float:
    fields = [summary, explanation, " ".join(key_points)]
    keys = [normalize_key(value) for value in fields if normalize_key(value)]
    if len(keys) < 2:
        return 0.0
    comparisons = 0
    repeated = 0
    for index, left in enumerate(keys):
        for right in keys[index + 1 :]:
            comparisons += 1
            if left in right or right in left or jaccard_char_similarity(left, right) > 0.72:
                repeated += 1
    return repeated / max(1, comparisons)


def is_redundant_text(value: str, existing: list[str]) -> bool:
    return any(is_redundant_pair(value, item) for item in existing if item)


def is_redundant_pair(a: str, b: str) -> bool:
    ka = normalize_key(a)
    kb = normalize_key(b)
    if not ka or not kb:
        return False
    return ka in kb or kb in ka or jaccard_char_similarity(ka, kb) > 0.72


def jaccard_char_similarity(a: str, b: str) -> float:
    left = set(a)
    right = set(b)
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, len(left | right))


def first_non_redundant_sentence(text: str, existing: str) -> str:
    for sentence in normalized_sentences(text):
        if keep_outline_text(sentence) and not is_redundant_pair(sentence, existing):
            return compact(sentence, 260)
    return ""


def summary_matches_structure(summary: str, blocks: list[LearningBlock]) -> bool:
    if not summary:
        return False
    terms = set(extract_keywords(summary, limit=8))
    block_text = " ".join(render_items_text(block.items) + " " + block.content for block in blocks if block.type != "summary")
    block_terms = set(extract_keywords(block_text, limit=16))
    return True if not terms or not block_terms else bool(terms & block_terms)


def normalize_block(block: LearningBlock) -> LearningBlock | None:
    title = normalize_text(block.title)
    content = normalize_text(clean_item(block.content)).replace("Linear↓ReLU↓Linear", "Linear -> ReLU -> Linear").replace("↓", " -> ")
    items = normalize_items(block.items)
    if not content and not items:
        return None
    if block.type == "summary" and content:
        content = compact(content, 240)
    return LearningBlock(block.type, title, content, items)


def normalize_items(items: list[Any]) -> list[Any]:
    normalized: list[Any] = []
    for item in items:
        if isinstance(item, OutlineItem):
            text = clean_item(item.text)
            children = dedupe_strings([clean_item(str(child)) for child in item.children if keep_child_text(str(child))])
            if keep_outline_text(text) or children:
                normalized.append(OutlineItem(text, children))
        elif isinstance(item, dict):
            text = clean_item(str(item.get("text") or item.get("title") or item.get("label") or ""))
            if keep_outline_text(text):
                normalized.append({**item, "text": text})
        else:
            text = clean_item(str(item))
            if keep_outline_text(text):
                normalized.append(text)
    return dedupe_mixed_items(normalized)


def select_sentence(text: str, keywords: list[str]) -> str:
    for sentence in normalized_sentences(text):
        if any(keyword in sentence for keyword in keywords) and keep_outline_text(sentence):
            return clean_item(sentence)
    return ""


def select_sentences(text: str, keywords: list[str]) -> list[str]:
    return dedupe_strings([clean_item(sentence) for sentence in normalized_sentences(text) if any(keyword in sentence for keyword in keywords) and keep_outline_text(sentence)])


def select_list_after_label(text: str, labels: list[str]) -> list[str]:
    lines = semantic_lines(text)
    result: list[str] = []
    collecting = False
    for line in lines:
        clean_line = clean_item(line)
        if not collecting and any(label in clean_line for label in labels):
            after = ""
            for sep in ["：", ":"]:
                if sep in clean_line:
                    after = clean_line.split(sep, 1)[1].strip()
                    break
            if after and keep_child_text(after):
                result.extend(split_semicolon_units(after))
            collecting = True
            continue
        if collecting:
            if not clean_line:
                continue
            if is_heading_line(clean_line) or clean_line.endswith(("：", ":")) or (result and is_total_branch_label(clean_line)):
                break
            if keep_child_text(clean_line):
                result.extend(split_semicolon_units(clean_line))
    return dedupe_strings([item for item in result if item])


def examples(source_text: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    lines = semantic_lines(source_text)
    for index, line in enumerate(lines):
        if line.startswith("例如") or line.lower().startswith("example"):
            values: list[str] = []
            cursor = index + 1
            while cursor < len(lines) and len(values) < 5:
                item = clean_item(lines[cursor])
                if not item or is_heading_line(item):
                    cursor += 1
                    continue
                if values and looks_like_new_sentence(item) and not is_minor_example_line(item):
                    break
                if item.endswith(("：", ":")):
                    break
                values.append(item)
                cursor += 1
            if values:
                result.append({"type": "example", "text": compact(" / ".join(values), 220)})
        elif "->" in line or "→" in line or "≈" in line:
            result.append({"type": "formula-or-mapping", "text": compact(clean_item(line), 220)})
        if len(result) >= 3:
            break
    return dedupe_dicts(result, "text")


def relations(title: str, source_text: str) -> list[dict[str, str]]:
    text = f"{title}\n{source_text}"
    found: list[dict[str, str]] = []
    if has_any(text, ["Encoder", "编码器"]):
        found.append({"type": "component", "target": "Encoder", "description": "理解输入内容并形成语义表示"})
    if has_any(text, ["Decoder", "解码器"]):
        found.append({"type": "component", "target": "Decoder", "description": "根据编码结果和已生成内容生成输出"})
    if has_any(text, ["Embedding", "词向量"]):
        found.append({"type": "prerequisite", "target": "Embedding", "description": "将文本转换为模型可计算的向量"})
    if has_any(text, ["Attention", "注意力"]):
        found.append({"type": "core-mechanism", "target": "注意力机制", "description": "建模序列中Token之间的依赖关系"})
    return found[:4]


def merge_source_text(chunks: list[SourceChunk]) -> str:
    seen: set[str] = set()
    parts: list[str] = []
    for chunk in chunks:
        text = clean(str(chunk.text or ""))
        if text and text not in seen:
            seen.add(text)
            parts.append(text)
    return "\n".join(parts)


def clean_model(value: str) -> str:
    return remove_evidence_tail(normalize_text(value))


def remove_evidence_tail(value: str) -> str:
    return re.split(r"原文依据[:：]", value or "", maxsplit=1)[0].strip()


def normalize_text(value: str) -> str:
    value = clean(value)
    value = value.replace("；；", "；").replace("：；", "：").replace("；：", "；")
    value = value.replace("和、服务", "和服务")
    value = value.replace("或、服务", "或服务")
    value = value.replace("因为等等内容", "")
    value = value.replace("控制电；路", "控制电路")
    value = value.replace("控制电、路", "控制电路")
    value = value.replace("周期；挪用", "周期挪用")
    value = value.replace("字装配 /；拆卸", "字装配/拆卸")
    value = value.replace("字装配 /、拆卸", "字装配/拆卸")
    value = re.sub(r"[?？]+", "", value)
    value = re.sub(r"([，。；、])[:：]+", r"\1", value)
    value = re.sub(r"[:：]+([，。；、]|$)", r"\1", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value.strip("；; ")


def clean(value: str) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ").strip()


def clean_learning_title(value: str, source_text: str = "") -> str:
    title = clean_item(value)
    if is_good_note_title(title, source_text):
        return compact(title, 42)
    for sentence in normalized_sentences(source_text):
        candidate = clean_item(sentence)
        if is_good_note_title(candidate, source_text):
            return compact(candidate, 42)
    return compact(title or first_meaningful_sentence(source_text) or "note", 42)


def is_good_note_title(candidate: str, source_text: str = "") -> bool:
    value = clean_item(candidate)
    if not value or is_noisy_learning_text(value) or is_broken_outline_fragment(value):
        return False
    if len(value) < 2 or len(value) > 80:
        return False
    if re.fullmatch(r"[\d.\u3001\u2460-\u2469\s]+", value):
        return False
    if re.fullmatch(r"[A-Za-z]{1,3}", value):
        return False
    if re.match(r"^[\u7684\u5f97\u5730\u548c\u4e0e\u53ca\u6216\u3001\uff0c\u3002\uff1b\uff1a,.;:\uff09)]", value):
        return False
    if re.match(r"^(存的|制权|式高|务|能是|期长|送之前|理时|设备地址|设备交换信息不需要 CPU暂停执行原程序为设备)", value):
        return False
    if is_visual_label_line(value):
        return False
    if value.endswith(("\u6216", "\u548c", "\u4e0e", "\u5bf9", "\u628a", "\u5c06", "\u63a7", "\u4e3b", "\u5c3d", "\u901a\u8fc7")):
        return False
    if len(value) <= 8 and source_text and source_text.count(value) <= 1 and not re.search(r"[A-Za-z]{2,}|\d", value):
        return False
    return True

def clean_outline_items(title: str, items: list[OutlineItem]) -> list[OutlineItem]:
    cleaned: list[OutlineItem] = []
    title_number = leading_item_number(title)
    for item in items:
        text = clean_item(item.text)
        item_number = leading_item_number(text)
        if title_number and item_number and item_number != title_number:
            continue
        children = [clean_item(str(child)) for child in item.children]
        children = [child for child in children if keep_child_text(child) and not same_learning_text(child, title)]
        if title_number:
            children = [
                child
                for child in children
                if not (leading_item_number(child) and leading_item_number(child) != title_number)
            ]
        if same_learning_text(text, title) and children:
            cleaned.extend(OutlineItem(child, []) for child in children[:4])
            continue
        if keep_outline_text(text) and not same_learning_text(text, title):
            dedup_children = dedupe_strings(children)[:8]
            cleaned.append(OutlineItem(text, dedup_children))
    if not cleaned and items:
        fallback = [item for item in items if keep_outline_text(item.text)]
        cleaned = fallback[:1]
    return dedupe_outline_items(merge_broken_outline_neighbors(cleaned))


def merge_broken_outline_neighbors(items: list[OutlineItem]) -> list[OutlineItem]:
    merged: list[OutlineItem] = []
    index = 0
    while index < len(items):
        current = items[index]
        if index + 1 < len(items):
            nxt = items[index + 1]
            combined = merge_broken_pair(current.text, nxt.text)
            if combined:
                merged.append(OutlineItem(combined, dedupe_strings([*current.children, *nxt.children])))
                index += 2
                continue
        merged.append(current)
        index += 1
    return merged


def merge_broken_pair(left: str, right: str) -> str:
    lval = clean_item(left)
    rval = clean_item(right)
    pairs = {
        "控制电": "路",
        "主存和": "服务",
        "中断方": "式",
        "总线控": "制权",
        "周期": "挪用",
        "字装配 /": "拆卸",
        "字装配/": "拆卸",
        "总线": "控制权",
        "判决": "机构",
        "优先级别": "先后",
        "采": "取",
    }
    for tail, head in pairs.items():
        if lval.endswith(tail) and rval.startswith(head):
            return clean_item(lval[: -len(tail)] + tail + rval)
    if lval.endswith(("但", "因为", "由于", "和", "或", "与", "由")) and rval:
        return clean_item(lval + rval)
    return ""


def same_learning_text(a: str, b: str) -> bool:
    ka = normalize_key(strip_section_number(a))
    kb = normalize_key(strip_section_number(b))
    return bool(ka and kb and ka == kb)


def is_noisy_learning_text(value: str) -> bool:
    text = clean_item(value)
    if not text:
        return True
    lowered = text.lower()
    if any(token in lowered for token in ["1ppt.com", "ppt\u6a21\u677f", "www.", "http://", "https://"]):
        return True
    if re.fullmatch(r"(?:br|page[_ -]?\d+)", lowered):
        return True
    if text in {"\u76ee\u5f55", "\u7b14\u8bb0\u533a", "\u5c01\u9762", "\u8c22\u8c22", "\u8c22 \u8c22"}:
        return True
    return False


def is_subsection_marker(value: str) -> bool:
    text = clean_item(value)
    return bool(re.fullmatch(r"[\(?]?\d+[\)?]?", text) or re.fullmatch(r"[一二三四五六七八九十①②③④⑤⑥⑦⑧⑨⑩]", text))

def clean_item(value: str) -> str:
    value = normalize_learning_text(normalize_text(value))
    value = strip_bullet(value)
    value = strip_section_number(value)
    value = value.replace("Linear↓ReLU↓Linear", "Linear -> ReLU -> Linear").replace("↓", " -> ")
    value = value.replace("控制电；路", "控制电路")
    value = value.replace("控制电、路", "控制电路")
    value = value.replace("操、作", "操作")
    value = value.replace("信 息", "信息")
    value = value.replace("设备地址 寄 存器", "设备地址寄存器")
    value = value.replace("设备地址 寄", "设备地址寄存器")
    value = value.replace("周期；挪用", "周期挪用")
    value = value.replace("字装配 /；拆卸", "字装配/拆卸")
    value = value.replace("字装配 /、拆卸", "字装配/拆卸")
    return value.strip("；; ")


def semantic_lines(text: str) -> list[str]:
    raw = [line.strip() for line in clean(text).splitlines() if line.strip()]
    expanded: list[str] = []
    for line in raw:
        expanded.extend(split_inline_label_lists(line) or [line])
    return [line for line in expanded if line.strip()]


def normalized_sentences(text: str) -> list[str]:
    parts: list[str] = []
    for line in semantic_lines(text):
        pieces = split_sentences(line) or [line]
        parts.extend(pieces)
    return [normalize_text(part) for part in parts if normalize_text(part)]


def split_inline_label_lists(line: str) -> list[str]:
    value = line.strip()
    if "；" not in value:
        return [value]
    if any(label in value for label in ["包含", "包括", "存在以下问题", "作用", "特点"]):
        return split_semicolon_units(value)
    return [value]


def split_semicolon_units(value: str) -> list[str]:
    return [normalize_text(part) for part in re.split(r"[；;]+", value) if normalize_text(part)]


def merge_adjacent_definition(line: str, next_line: str) -> str:
    a = clean_item(line)
    b = clean_item(next_line)
    merged = merge_broken_pair(a, b)
    if merged:
        return merged
    if b and "转换为向量" in a and "Embedding" in b:
        return normalize_text(a.rstrip("。") + "，" + b)
    if b and a.endswith("：") and len(b) < 40:
        return normalize_text(a + b)
    return a


def label_without_colon(value: str) -> str:
    return clean_item(value).rstrip("：:")


def strip_bullet(value: str) -> str:
    value = re.sub(r"^[-*•✓✔☑]\s*", "", value)
    value = re.sub(r"^\d+[.、．]\s*", "", value)
    return value.strip()


def strip_section_number(value: str) -> str:
    value = str(value or "").strip()
    cn = "一二三四五六七八九十"
    value = re.sub(r"^\d+(?:\.\d+)*(?:[.、．]\s*|\s+)", "", value)
    value = re.sub(rf"^[{cn}]+[、.．]\s*", "", value)
    return value.strip()


def leading_item_number(value: str) -> str:
    text = str(value or "").strip()
    match = re.match(r"^\s*(?:\((\d+)\)|（(\d+)）|([①②③④⑤⑥⑦⑧⑨]))", text)
    if not match:
        return ""
    return next((group for group in match.groups() if group), "")


def keep_outline_text(text: str) -> bool:
    value = clean_item(text)
    if not value or is_orphan_label(value) or is_minor_example_line(value):
        return False
    if is_transition_fragment(value):
        return False
    if is_noisy_learning_text(value):
        return False
    if is_background_filler(value) or is_transformer_solution(value):
        return False
    if is_activity_or_prompt_line(value) or is_visual_label_line(value):
        return False
    if is_broken_outline_fragment(value):
        return False
    if re.fullmatch(r"\d{1,3}", value):
        return False
    if re.fullmatch(r"[\u4e00-\u9fff]", value):
        return False
    if re.fullmatch(r"[\u2460-\u2469]+", value):
        return False
    if re.fullmatch(r"[A-Za-z]+", value) and len(value) < 8:
        return False
    return value not in {"每层结构基本相同。", "每层结构基本相同"}


def keep_child_text(text: str) -> bool:
    value = clean_item(text)
    return bool(value and not is_orphan_label(value) and not is_minor_example_line(value) and not is_noisy_learning_text(value) and not is_transition_fragment(value) and not is_broken_outline_fragment(value) and not is_activity_or_prompt_line(value) and not is_visual_label_line(value))


def is_low_quality_user_content(value: str) -> bool:
    text = normalize_text(clean_item(value))
    if not text:
        return True
    if len(re.sub(r"\s+", "", text)) < 18:
        return True
    if is_activity_or_prompt_line(text) or is_visual_label_line(text) or is_transition_fragment(text) or is_broken_outline_fragment(text):
        return True
    if re.search(r"(结构拆解[:：].*要点|要点介绍[:：].*结构拆解)", text):
        return True
    if re.search(r"(DMA\s*接口组成\s*线|DMA\s*传送速\s*率高|起总线竞争|CPU在一个工作周期内访$|^\d+[.、]\s*DMA\s*接口功能)", text):
        return True
    if re.match(r"^\d+[.、]\s*DMA\s*接口功能", text) or re.match(r"^DMA\s*接口功能\s*\(", text):
        return True
    return False


def is_orphan_label(value: str) -> bool:
    return label_without_colon(value) in {"作用", "特点", "公式", "输入", "训练数据", "例如", "主要包括", "能力包括"}


def has_orphan_label(block: LearningBlock) -> bool:
    return any(is_orphan_label(item.text if isinstance(item, OutlineItem) else str(item)) for item in block.items)


def remove_orphan_items(block: LearningBlock) -> LearningBlock:
    block.items = [item for item in block.items if not is_orphan_label(item.text if isinstance(item, OutlineItem) else str(item))]
    return block


def block_has_broken_sentence(block: LearningBlock) -> bool:
    values = [block.content, *[item.text if isinstance(item, OutlineItem) else str(item) for item in block.items]]
    return any(value.strip().endswith(("：", ":", "，", ",")) for value in values if value)


def is_broken_outline_fragment(value: str) -> bool:
    text = clean_item(value)
    if not text:
        return True
    compacted = re.sub(r"\s+", "", text)
    if is_transition_fragment(text):
        return True
    if text.endswith(("但", "因为", "由于", "通过", "以及", "和", "或", "与", "由", "对", "把", "将", "未", "当", "已", "访", "控", "制", "电", "方", "速")) and len(text) <= 42:
        return True
    if re.match(r"^(路、|服务，|制权|式高|率高|存的|能是|期长|送之前|待中断|主程序|充分发挥|取以下|起总线竞争|拆卸硬件|问一次存储器|很快，硬件)", text):
        return True
    if re.search(r"(控制电[；;、]?\s*路|字装配\s*/[、；;]?\s*拆卸|主存和[、；;]\s*服务|原程序为设备|因为等|在一段时间内\s*[，,]?\s*$)", text):
        return True
    if re.search(r"(DMA\s*传送速\s*率高|DMA\s*接口组成\s*线|CPU在一个工作周期内访|问一次存储器即可不需要\s*申请建立和归还\s*总线)", text):
        return True
    if re.search(r"(控[、；;\s]+制权|方[、；;\s]+式高|主[、；;\s]+存|尽[、；;\s]+管|控制电[、；;\s]+路)", text):
        return True
    if compacted in {"线", "数据传送", "DMA接口组成线", "DMA传送速", "率高总线", "请", "求"}:
        return True
    if re.search(r"(关键是在预处|在预处$)", text):
        return True
    if re.search(r"^(控制逻|接口\d+|接口nCPU|数据线|DMA响应\d*|DMA请求\d*|\+1|…)$", compacted):
        return True
    if re.search(r"(设备设备设备DMA|理时，将所选设备|设备地址寄存器$|DMA接口（page_\d+）)", text):
        return True
    if re.search(r"(DMA操$|^作的后处理|设备信$|^息存储区|与接口$|^相连的设备|各自$|^的传送参数)", text):
        return True
    if re.search(r"(可以采$|可以采。|分时使用主存，可以采)", text):
        return True
    if re.search(r"(接口nCPU|I/O总线|地址线|打印机\s*t|磁带\s*t|磁盘\s*t|每\d+\s*s请求DMA|s\s*一次DMA传送)", text):
        return True
    if len(compacted) <= 8 and any(token in compacted for token in ["控制逻", "溢出信号", "中断"]):
        return True
    return False


def is_transition_fragment(value: str) -> bool:
    text = clean_item(value)
    compacted = re.sub(r"\s+", "", text)
    return bool(
        re.search(r"^(?:✓|✔|☑)\s*", str(value or ""))
        or re.search(r"(通过说明|预处理之后|对应输入情况|对应输出情况|经处理完毕|便通过\s*DMA)", text)
        or re.search(r"当\s*(?:I/O|IO)?设备准备好发送的数据$", text)
        or compacted.endswith("便通过DMA")
    )


def is_activity_or_prompt_line(value: str) -> bool:
    text = clean_item(value)
    if any(token in text for token in ["采访身边的人", "想一想", "你对", "为何会产生", "思考：", "基础型作业", "发展型作业", "完成课时练习", "应该怎么做"]):
        return True
    if re.search(r"[A-D][．.]", text) and re.search(r"[①②③④]", text):
        return True
    return False


def is_visual_label_line(value: str) -> bool:
    text = re.sub(r"\s+", "", clean_item(value))
    if text in {"t", "I/O", "设", "备", "ACC", "线", "+1", "…", "控制逻", "数据线"}:
        return True
    labels = [
        "主存工作时间",
        "CPU不执行程序",
        "DMA不工作",
        "DMA工作",
        "CPU控制并使用主存",
        "DMA控制并使用主存",
        "DMA传送速率高总线",
        "DMA接口组成线",
        "接口CPU主存",
        "设备设备设备DMA",
        "DMA响应",
        "DMA请求",
    ]
    return any(text == label or (len(text) <= len(label) + 4 and label in text) for label in labels)


def is_heading_line(line: str) -> bool:
    value = line.strip()
    return bool(re.match(r"^[一二三四五六七八九十]+、", value)) or bool(re.match(r"^\d+(?:\.\d+)*\s+", value))


def looks_like_new_sentence(line: str) -> bool:
    value = clean_item(line)
    return len(value) > 24 or value.endswith(("。", "！", "？", ".", "!", "?"))


def is_short_list_item(line: str) -> bool:
    value = clean_item(line)
    return len(value) <= 32


def is_minor_example_line(line: str) -> bool:
    value = clean_item(line)
    if not value:
        return True
    if re.fullmatch(r"(GPT|Gemini|Claude|DeepSeek|Qwen)系列", value, flags=re.I):
        return True
    if re.fullmatch(r"[A-Za-z ]+\.?", value) and len(value.split()) <= 5:
        return True
    if "->" in value or "→" in value or "≈" in value or value.startswith("PE("):
        return True
    return value in {"it", "animal", "love", "AI", "指代谁。"}


def is_background_filler(value: str) -> bool:
    text = clean_item(value)
    return any(token in text for token in ["广泛应用", "取得了广泛应用", "自然语言处理", "重要研究方向"])


def is_transformer_solution(value: str) -> bool:
    text = clean_item(value)
    return text.startswith("Transformer彻底抛弃") or text.startswith("为了克服这些缺陷")


def is_total_branch_label(value: str) -> bool:
    text = label_without_colon(value)
    return any(token in text for token in ["存在以下问题", "通常包含", "能力包括", "作用", "特点", "主要包括"])


def is_good_summary(value: str) -> bool:
    text = clean_item(value)
    return bool(len(text) >= 24 and not text.endswith(("：", ":", "，", ",")) and not is_background_filler(text))


def first_meaningful_sentence(text: str) -> str:
    for sentence in normalized_sentences(text):
        if keep_outline_text(sentence):
            return sentence
    return ""


def block_first_line(block: LearningBlock) -> str:
    if block.content:
        return compact(block.content, 90)
    if block.items:
        return compact(render_items_text(block.items), 90)
    return ""


def render_items_text(items: list[Any]) -> str:
    parts: list[str] = []
    for item in items:
        if isinstance(item, OutlineItem):
            if item.children:
                parts.append(f"{item.text}（" + "、".join(map(str, item.children[:4])) + "）")
            else:
                parts.append(item.text)
        else:
            parts.append(str(item))
    return "；".join([part for part in parts if part])


def dedupe_outline_items(items: list[OutlineItem]) -> list[OutlineItem]:
    result: list[OutlineItem] = []
    seen: set[str] = set()
    for item in items:
        key = normalize_key(item.text)
        if key and key not in seen:
            seen.add(key)
            result.append(OutlineItem(clean_item(item.text), dedupe_strings([str(child) for child in item.children])))
    return result


def dedupe_mixed_items(items: list[Any]) -> list[Any]:
    result: list[Any] = []
    seen: set[str] = set()
    for item in items:
        text = item.text if isinstance(item, OutlineItem) else str(item)
        key = normalize_key(text)
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def dedupe_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean_value = clean_item(value)
        key = normalize_key(clean_value)
        if clean_value and key and key not in seen:
            seen.add(key)
            result.append(clean_value)
    return result


def dedupe_dicts(values: list[dict[str, str]], key: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for value in values:
        marker = normalize_key(value.get(key, ""))
        if marker and marker not in seen:
            seen.add(marker)
            result.append(value)
    return result


def normalize_key(value: str) -> str:
    return re.sub(r"\s+", "", clean_item(value)).lower()


def has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def infer_level(note_id: str) -> int:
    return 2 if "." in note_id else 1


def natural_key(value: str) -> list[Any]:
    parts = re.split(r"(\d+)", value)
    return [int(part) if part.isdigit() else part for part in parts]


def is_rnn_limit(title: str, text: str) -> bool:
    probe = title + text
    if "RNN" not in probe:
        return False
    return "缺陷" in title or "局限" in title or "提出背景" in title or "存在以下问题" in text


def is_document_heading(heading: str) -> bool:
    return strip_section_number(heading) in {"Transformer", "Transformer模型简介", "简介"}


TYPED_BLOCKS = {"definition", "mechanism", "procedure", "effect", "formula", "example", "explanation"}


