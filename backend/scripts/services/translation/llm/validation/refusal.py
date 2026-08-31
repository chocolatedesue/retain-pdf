"""模型拒答检测。

当翻译上游（尤其是网页代理类 provider）返回的是拒答/免责声明而不是译文时，
这里的启发式把它识别出来，交由上层校验错误 → plain-text 重试链路处理。
匹配在去空白后做子串判断：真实论文正文几乎不可能包含这些短语，误伤可忽略。
"""

from __future__ import annotations

import re

_REFUSAL_PATTERNS = (
    # 中文拒答 / 免责声明
    "我只是一个文本",
    "我只是个文本",
    "我只是一个AI",
    "我只是个AI",
    "我是一名AI助手",
    "我是一个AI助手",
    "作为一个人工智能",
    "作为AI助手",
    "无法帮到你",
    "没法帮到你",
    "无法协助",
    "不能协助",
    "违反我的使用政策",
    "违反了使用政策",
    # 英文拒答 / 免责声明
    "I'mjustatext",
    "Iamjustatext",
    "Icannotassist",
    "Ican'tassist",
    "Ican'thelpwith",
    "Icannothelpwith",
    "AsanAIlanguagemodel",
    "AsanAIassistant",
    "I'munabletohelp",
    "Iamunabletohelp",
)

_WHITESPACE_RE = re.compile(r"\s+")


def looks_like_model_refusal(text: str) -> bool:
    """判断译文是否疑似模型拒答/免责声明，而不是对原文的翻译。"""
    if not text:
        return False
    normalized = _WHITESPACE_RE.sub("", text)
    if not normalized:
        return False
    return any(pattern in normalized for pattern in _REFUSAL_PATTERNS)


__all__ = ["looks_like_model_refusal"]
