#!/usr/bin/env python3
"""
痛点信号搜索关键词 v1.0
三层信号：L1找而不得 → L2抱怨缺失 → L3凑合着用
搜到的文本丢给 llm_intent_classifier.py 做最终判断
"""
import re

# ═══ L1: 找而不得（99%是真需求真空）═══
L1_CN = [
    "找不到", "找了好久", "找了半天", "搜不到", "搜了好久",
    "一直没有找到", "找遍了", "翻遍了",
    "求一个", "求个", "跪求", "哪位有", "谁有",
    "推荐一个", "推荐个好用的", "有推荐的",
    "有没有工具", "有没有软件", "有没有网站",
    "市面上有没有", "市面上有什么",
    "就没有一个", "怎么就没人做", "为什么没人做",
    "谁做过", "有大佬做过吗", "有没有大佬做过",
]

L1_EN = [
    "any tool that can", "any tool for", "anyone know a tool",
    "looking for a tool", "is there a tool", "is there a website",
    "can't find a tool", "no tool for", "wish there was a tool",
    "need a simple tool", "someone should build",
    "why isn't there a", "recommend a tool",
    "does anyone know of", "trying to find a tool",
]

# ═══ L2: 抱怨缺失 / 跨领域缺口 ═══
L2_CN = [
    "就没有", "怎么就没", "居然没有", "竟然没人做",
    "难道就没有", "可惜没有", "唯一缺的",
    "就是不能", "唯一的缺憾", "最大痛点", "就差一个",
    "希望有人能做", "希望有人开发", "坐等大佬",
    "能不能把", "有没有办法把", "有没有什么办法",
    "在线等一个", "等一个工具",
]

L2_EN = [
    "wish i had a", "i wish there was", "if only there was",
    "why can't i just", "why do i have to",
    "it would be nice if", "someone please make",
    "the one thing missing", "all i need is",
    "i just want a simple", "i just need a quick",
]

# ═══ L3: 凑合着用 / 潜在需求 ═══
L3_CN = [
    "我现在用的是", "现在只能手动", "每次都要手动",
    "每次都得", "每次都要打开", "每次得",
    "太麻烦了每次", "每次还要", "还得手动",
    "能不能自动", "能不能一键", "有没有快捷方式",
    "有没有更快的方法", "能不能简化",
    "用Excel手动", "用记事本手动", "用计算器手动",
]

L3_EN = [
    "currently using", "right now i have to",
    "i currently", "every time i need",
    "it's so annoying to", "takes forever to",
    "there must be a better way", "there's got to be",
    "surely there's a", "has anyone automated",
]

# ═══ 正则模式（兜底捕获）═══
PAIN_PATTERNS = [
    r'(找|搜|寻).*(了.*(半天|好久|一天|几年)|遍了)',
    r'(怎么|到底).*(没有|没人做|就没人)',
    r'(有没有|谁有).*(工具|软件|网站|脚本|App).*(推荐|好用)',
    r'求(一个|个).*(工具|软件|脚本)',
    r'i\s+wish\s+(there|i|someone|somebody)',
    r'(looking|searching).*(tool|website|app|script)',
]

# ═══ 全量集合 ═══
ALL_PAIN_KEYWORDS = L1_CN + L1_EN + L2_CN + L2_EN + L3_CN + L3_EN
L1_ALL = L1_CN + L1_EN


def detect_pain_signal(text: str) -> dict:
    """
    检测文本是否包含痛点信号，返回信号等级和匹配词
    """
    tl = text.lower()
    result = {"has_signal": False, "level": 0, "matched": []}

    for kw in L1_ALL:
        if kw.lower() in tl:
            result["has_signal"] = True
            result["level"] = 1
            result["matched"].append(kw)

    if not result["has_signal"]:
        for kw in L2_CN + L2_EN:
            if kw.lower() in tl:
                result["has_signal"] = True
                result["level"] = 2
                result["matched"].append(kw)
                break

    if not result["has_signal"]:
        for kw in L3_CN + L3_EN:
            if kw.lower() in tl:
                result["has_signal"] = True
                result["level"] = 3
                result["matched"].append(kw)
                break

    if not result["has_signal"]:
        for pattern in PAIN_PATTERNS:
            if re.search(pattern, tl):
                result["has_signal"] = True
                result["level"] = 2
                result["matched"].append(f"regex:{pattern}")
                break

    return result
