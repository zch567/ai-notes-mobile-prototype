from __future__ import annotations

import re
from typing import Any

from .text_utils import compact, normalize_learning_text


TECHNICAL_TERMS = [
    "DMA",
    "CPU",
    "I/O",
    "IO",
    "主存",
    "总线",
    "接口",
    "寄存器",
    "中断",
    "控制逻辑",
    "数据传送",
]

POLITICS_TERMS = [
    "国家",
    "民族",
    "道路",
    "精神",
    "力量",
    "自信",
    "青少年",
    "中国特色社会主义",
    "法治",
    "责任",
    "理想",
    "道德",
    "传统文化",
    "社会实践",
    "使命感",
    "国家利益",
]

EXAM_TERMS = [
    "唯物论",
    "物质",
    "意识",
    "运动",
    "静止",
    "原理",
    "方法论",
    "考点",
    "真题",
    "易混",
]

ENUMERATION_TERMS = ["种", "类", "阶段", "步骤", "方面", "表现", "原因", "方式", "功能", "组成", "类型", "包括"]
PROCESS_TERMS = ["过程", "流程", "步骤", "阶段", "预处理", "后处理", "申请", "请求", "结束", "并行工作"]
COMPONENT_TERMS = ["接口", "部件", "组成", "结构", "寄存器", "机构", "控制逻辑", "控制电路"]
COMPARISON_TERMS = ["比较", "区别", "差异", "vs", "VS", "对比", "辨析"]
ACTION_TERMS = ["如何", "怎样", "怎么做", "助力", "行动", "做法", "要求", "落实", "应该"]
REASON_TERMS = ["原因", "为什么", "依据", "底气"]
PRINCIPLE_TERMS = ["原理", "方法论", "关系"]


def infer_learning_profile(
    title: str,
    summary: str = "",
    key_points: list[str] | None = None,
    content: str = "",
) -> dict[str, Any]:
    points = [str(item) for item in key_points or [] if str(item).strip()]
    title_text = normalize_learning_text(title)
    probe = normalize_learning_text(" ".join([title_text, summary, content, *points]))
    material = infer_material(probe)
    labels = numbered_labels(points)
    roles: set[str] = set()
    subtype = ""

    if labels and (len(labels) >= 2 or has_any(title_text, ENUMERATION_TERMS)):
        roles.add("enumeration")
    if (
        has_any(title_text, PROCESS_TERMS)
        or (material == "technical" and has_any(probe, ["预处理", "后处理", "传送结束"]))
        or (material == "technical" and has_any(title_text, ["申请", "请求", "响应", "条件"]))
    ):
        roles.add("process")
    if material == "technical" and (has_any(title_text, COMPONENT_TERMS) or has_any(probe, ["字计数器", "缓冲", "地址寄存器", "控制逻辑"])):
        roles.add("component")
    if material == "technical" and has_any(probe, ["主存周期", "总线控制权", "交替访问", "停止 CPU", "停止CPU", "暂停访问", "分周期", "周期挪用", "周期窃取"]):
        roles.add("transfer_method")
    if has_any(title_text, COMPARISON_TERMS):
        roles.add("comparison")
    if has_any(title_text, ACTION_TERMS):
        roles.add("action")
    if has_any(title_text, REASON_TERMS):
        roles.add("reason")
    if has_any(title_text, ["表现", "特点", "体现"]):
        roles.add("manifestation")
    if has_any(title_text, PRINCIPLE_TERMS):
        roles.add("principle")
    if has_any(title_text, ["高频", "考点", "清单", "总结"]):
        roles.add("checklist")
    if has_any(title_text, ["易混", "辨析", " vs ", " VS "]):
        roles.add("contrast")

    if "component" in roles:
        subtype = component_subtype(probe)
    if "transfer_method" in roles:
        subtype = transfer_method_subtype(probe) or subtype
    if "process" in roles:
        process_kind = process_subtype(probe)
        if has_any(title_text, ["申请", "请求", "响应", "条件"]):
            process_kind = "request_arbitration"
        elif "后处理" in title_text:
            process_kind = "post_process"
        elif "并行工作" in title_text:
            process_kind = "parallel_execution"
        elif has_any(title_text, ["过程", "流程"]) and has_any(probe, ["预处理", "数据传送", "后处理"]):
            process_kind = "three_phase_process"
        if process_kind and (subtype in {"", "component", "control_logic"} or has_any(title_text, ["申请", "请求", "响应", "条件", "后处理", "并行工作"])):
            subtype = process_kind

    return {
        "material": material,
        "roles": roles,
        "subtype": subtype,
        "numberedLabels": labels,
        "probe": probe,
    }


def infer_material(probe: str) -> str:
    if has_any(probe, TECHNICAL_TERMS):
        return "technical"
    if has_any(probe, POLITICS_TERMS):
        return "politics"
    if has_any(probe, EXAM_TERMS):
        return "exam"
    return "general"


def has_any(text: str, tokens: list[str] | tuple[str, ...] | set[str]) -> bool:
    return any(token and token in text for token in tokens)


def leading_number(value: str) -> str:
    match = re.match(r"^\s*(?:[（(](\d+)[）)]|([①②③④⑤⑥⑦⑧⑨⑩])|(\d+)[.、])", str(value))
    return next((group for group in match.groups() if group), "") if match else ""


def strip_leading_number(value: str) -> str:
    return re.sub(r"^\s*(?:[（(]\d+[）)]|[①②③④⑤⑥⑦⑧⑨⑩]|\d+[.、])\s*", "", str(value)).strip()


def point_label(point: str) -> str:
    text = normalize_learning_text(str(point)).strip(" ；;。")
    number = leading_number(text)
    body = strip_leading_number(text)
    if "：" in body and len(body) > 28:
        head, tail = body.split("：", 1)
        body = head if 2 <= len(head) <= 18 else tail
    for sep in ["，", "；", "。"]:
        if sep in body and len(body) > 28:
            body = body.split(sep, 1)[0]
    label = compact(body, 32)
    return f"{numbered_prefix(number)}{label}" if number else label


def numbered_labels(points: list[str]) -> list[str]:
    labels: list[str] = []
    for point in points:
        if leading_number(point):
            label = point_label(point)
            if label:
                labels.append(label)
    return labels


def numbered_prefix(number: str) -> str:
    if number in "①②③④⑤⑥⑦⑧⑨⑩":
        return number
    if number:
        return f"({number}) "
    return ""


def component_subtype(probe: str) -> str:
    if "中断机构" in probe or ("中断请求" in probe and "后处理" in probe):
        return "completion_notifier"
    if has_any(probe, ["选择型", "多路型", "连接方式", "公共请求线", "独立请求线", "链式查询", "字节交叉"]):
        return "connection_type"
    if "功能" in probe:
        return "interface_function"
    if "数据缓冲寄存器" in probe or ("缓冲" in probe and ("字节" in probe or "字装配" in probe)):
        return "data_buffer"
    if "字计数器" in probe or "传送长度" in probe:
        return "counter"
    if "主存地址寄存器" in probe or "地址寄存器" in probe:
        return "address_register"
    if "控制逻辑" in probe or "控制电路" in probe:
        return "control_logic"
    if has_any(probe, ["逻辑部件", "组成", "部件包括", "结构包括"]):
        return "component_group"
    return "component"


def transfer_method_subtype(probe: str) -> str:
    if "周期挪用" in probe or "周期窃取" in probe or ("主存周期" in probe and "总线控制权" in probe):
        return "cycle_stealing"
    if "交替访问" in probe or "分周期" in probe or ("C1" in probe and "C2" in probe):
        return "interleaved_access"
    if "停止" in probe and ("访问主存" in probe or "CPU" in probe):
        return "exclusive_access"
    if "暂停访问" in probe or "独占主存" in probe:
        return "exclusive_access"
    return ""


def process_subtype(probe: str) -> str:
    if has_any(probe, ["并行工作", "继续执行主程序"]):
        return "parallel_execution"
    if has_any(probe, ["预处理", "数据传送", "后处理"]):
        return "three_phase_process"
    if has_any(probe, ["申请", "请求", "响应", "排队", "优先级"]):
        return "request_arbitration"
    if "后处理" in probe:
        return "post_process"
    return ""
