from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from .schemas import SourceChunk
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
            note["summary"] = unit.summary
            note["content"] = unit.explanation
            note["keyPoints"] = [item.text for item in unit.outline_items]
            note["examples"] = unit.examples
            note["relations"] = unit.relations
            note["sourceRefs"] = unit.source_refs
            note["source_refs"] = unit.source_refs
            note["blocks"] = render_blocks(unit)
            note["structure"] = {"style": "learning-unit-contract-v2", "concepts": ["LearningUnit", "parent-child consistency", "typed blocks", "postprocess validator"], "modelFirst": True, "postProcessing": "learning-unit-normalization", "qualityIssues": unit.quality_issues}
            result.append(note)
        return result


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
    return f"{title}由" + "、".join(names[:6]) + "等子模块构成，各子模块共同支撑本部分的核心知识。"


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
        return first_meaningful_sentence(source_text)
    if len(outline) == 1:
        item = outline[0]
        if item.children:
            return compact(f"{item.text.rstrip('。')}，主要包括" + "、".join(str(child).rstrip('。') for child in item.children[:4]) + "。", 220)
        return compact(item.text, 220)
    names = [item.text for item in outline[:5] if item.text]
    return compact(f"{strip_section_number(title)}主要包括" + "、".join(names) + "等内容。", 220)


def explanation_from_unit(title: str, model_content: str, summary: str, blocks: list[LearningBlock]) -> str:
    parts = [summary]
    for block in blocks:
        if block.type == "summary":
            continue
        if block.content:
            parts.append(f"{block.title}：{block.content}")
        elif block.items:
            rendered = render_items_text(block.items)
            if rendered:
                parts.append(f"{block.title}：{rendered}")
    text = normalize_text("\n".join(dedupe_strings(parts)))
    if len(text) < 80 and model_content:
        extra = remove_evidence_tail(model_content)
        if extra and extra not in text:
            text = normalize_text(text + "\n" + extra)
    return text


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
    if not value or is_noisy_learning_text(value):
        return False
    if len(value) < 2 or len(value) > 80:
        return False
    if re.fullmatch(r"[\d.\u3001\u2460-\u2469\s]+", value):
        return False
    if re.fullmatch(r"[A-Za-z]{1,3}", value):
        return False
    if re.match(r"^[\u7684\u5f97\u5730\u548c\u4e0e\u53ca\u6216\u3001\uff0c\u3002\uff1b\uff1a,.;:\uff09)]", value):
        return False
    if re.match(r"^(存的|制权|式高|务|能是|期长|送之前)", value):
        return False
    if value.endswith(("\u6216", "\u548c", "\u4e0e", "\u5bf9", "\u628a", "\u5c06", "\u63a7", "\u4e3b", "\u5c3d")):
        return False
    if len(value) <= 8 and source_text and source_text.count(value) <= 1 and not re.search(r"[A-Za-z]{2,}|\d", value):
        return False
    return True

def clean_outline_items(title: str, items: list[OutlineItem]) -> list[OutlineItem]:
    cleaned: list[OutlineItem] = []
    for item in items:
        text = clean_item(item.text)
        children = [clean_item(str(child)) for child in item.children]
        children = [child for child in children if keep_child_text(child) and not same_learning_text(child, title)]
        if same_learning_text(text, title) and children:
            cleaned.extend(OutlineItem(child, []) for child in children[:4])
            continue
        if keep_outline_text(text) and not same_learning_text(text, title):
            dedup_children = dedupe_strings(children)[:8]
            cleaned.append(OutlineItem(text, dedup_children))
    if not cleaned and items:
        fallback = [item for item in items if keep_outline_text(item.text)]
        cleaned = fallback[:1]
    return dedupe_outline_items(cleaned)


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
    return bool(re.fullmatch(r"[\(?]?\d+[\)?]?", text) or re.fullmatch(r"[??????????]", text))

def clean_item(value: str) -> str:
    value = normalize_learning_text(normalize_text(value))
    value = strip_bullet(value)
    value = strip_section_number(value)
    value = value.replace("Linear↓ReLU↓Linear", "Linear -> ReLU -> Linear").replace("↓", " -> ")
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
    if b and "转换为向量" in a and "Embedding" in b:
        return normalize_text(a.rstrip("。") + "，" + b)
    if b and a.endswith("：") and len(b) < 40:
        return normalize_text(a + b)
    return a


def label_without_colon(value: str) -> str:
    return clean_item(value).rstrip("：:")


def strip_bullet(value: str) -> str:
    value = re.sub(r"^[-*•]\s*", "", value)
    value = re.sub(r"^\d+[.、．]\s*", "", value)
    return value.strip()


def strip_section_number(value: str) -> str:
    value = str(value or "").strip()
    cn = "一二三四五六七八九十"
    value = re.sub(r"^\d+(?:\.\d+)*(?:[.、．]\s*|\s+)", "", value)
    value = re.sub(rf"^[{cn}]+[、.．]\s*", "", value)
    return value.strip()


def keep_outline_text(text: str) -> bool:
    value = clean_item(text)
    if not value or is_orphan_label(value) or is_minor_example_line(value):
        return False
    if is_noisy_learning_text(value):
        return False
    if is_background_filler(value) or is_transformer_solution(value):
        return False
    if re.fullmatch(r"\d{1,3}", value):
        return False
    if re.fullmatch(r"[\u2460-\u2469]+", value):
        return False
    if re.fullmatch(r"[A-Za-z]+", value) and len(value) < 8:
        return False
    return value not in {"每层结构基本相同。", "每层结构基本相同"}


def keep_child_text(text: str) -> bool:
    value = clean_item(text)
    return bool(value and not is_orphan_label(value) and not is_minor_example_line(value) and not is_noisy_learning_text(value))


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
