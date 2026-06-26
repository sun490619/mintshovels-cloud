#!/usr/bin/env python3
"""
MintShovels 雷达需求甄别过滤器 v4.0
=====================================
v4.0 核心升级：
  🔄 废除机械关键词黑名单 → 引入 intent_classifier 多维意图判定引擎
  🔄 "如何/怎么/为什么"不再一刀切拦截，由意图分类器综合评估
  🔄 错题本(bad_cases.json)反例沉淀 + 正面范本匹配
  🔄 多维打分：数据闭环/工具名词/正反案例/计算路径/语言质量

v3.0 保留:
  🔧 GitHub owner/repo 智能提取
  🔧 Show HN / Ask HN 前缀去噪

用法: from demand_filter import is_valid_demand, is_professional_tool_name
"""

import re
import os
import sys

# ── 引入意图分类器 ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    from intent_classifier import IntentClassifier
    _ic = IntentClassifier()
    INTENT_CLASSIFIER_AVAILABLE = True
except ImportError:
    INTENT_CLASSIFIER_AVAILABLE = False
    _ic = None


# ═══════════════════════════════════════════════════════════
# 🧹 名称预处理：去噪 + 智能提取
# ═══════════════════════════════════════════════════════════

def preprocess_name(name: str) -> str:
    """
    对工具名称做预处理清洗，返回更干净的核心名用于后续评估。
    """
    if not name:
        return name

    cleaned = name.strip()

    # ── 1. 去掉 HN 前缀 ──
    hn_prefixes = [
        r'^Show\s+HN\s*[:：]\s*',
        r'^Ask\s+HN\s*[:：]\s*',
        r'^Tell\s+HN\s*[:：]\s*',
    ]
    for pat in hn_prefixes:
        cleaned = re.sub(pat, '', cleaned, flags=re.IGNORECASE).strip()

    # ── 2. GitHub owner/repo 提取 ──
    github_match = re.match(
        r'^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)\s*[:：]\s*(.+)',
        cleaned
    )
    if github_match:
        repo_name = github_match.group(2)
        cleaned = repo_name

    # ── 3. 去掉 "Random " 前缀（交由意图分类器处理，只做预处理）──
    cleaned = re.sub(r'^Random\s+', '', cleaned, flags=re.IGNORECASE).strip()

    # ── 4. 去掉末尾 emoji + 多余空格 ──
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned


# ═══════════════════════════════════════════════════════════
# 🚫 硬核黑名单关键词（v2.0 保留项 — 明确非工具的绝对拦截）
# ═══════════════════════════════════════════════════════════

# v4.0: 大幅精简，只保留"绝对不可能成为工具"的内容
# 新闻/八卦/闲聊等现在交给意图分类器判断
HARD_BLOCK_KEYWORDS = [
    # ── 绝对非工具内容 ──
    "paper towels", "toilet paper", "bounty paper", "charmin",
    "tide pods", "laundry detergent", "dish soap",
    "family rolls", "regular rolls",
    "black friday", "cyber monday",
    "lorem ipsum",
]

HARD_BLOCK_PATTERNS = [
    # 商品规格公式
    r"\b(\d+)\s*(family|regular|mega|jumbo|double)\s*(rolls?|packs?)\s*=\s*\d+\s*(regular)?\s*(rolls?|packs?)",
    # 纯数字+单位商品
    r"^\d+\s*(rolls?|packs?|sheets?)\s*$",
]

# ═══════════════════════════════════════════════════════════
# ✅ 工具后缀白名单（精简）
# ═══════════════════════════════════════════════════════════

TOOL_SUFFIXES = [
    "generator", "converter", "checker", "calculator", "editor",
    "viewer", "formatter", "validator", "analyzer", "tracker",
    "downloader", "compressor", "encoder", "decoder", "scanner",
    "finder", "extractor", "monitor", "optimizer", "detector",
    "tester", "builder", "creator", "manager", "explorer",
    "debugger", "profiler", "inspector", "visualizer", "renderer",
    "splitter", "merger", "uploader", "scheduler", "notifier",
    "translator", "summarizer", "parser", "minifier", "beautifier",
    "tool", "utility", "helper", "assistant",
    "resolver", "cleaner", "linter", "mapper", "reducer",
]


# ═══════════════════════════════════════════════════════════
# v4.0 核心：意图驱动判定
# ═══════════════════════════════════════════════════════════

def is_professional_tool_name(name: str) -> bool:
    """
    v4.0: 意图分类器驱动的专业工具名判定

    不再靠关键词黑名单拦截，而是通过多维意图打分综合评估：
      - 数据闭环 (输入→输出)
      - 工具名词检测
      - 正面/反面案例相似度
      - 计算路径可行性
      - 语言质量

    返回 True = 合格工具名，False = 不合格
    """
    if not name or not isinstance(name, str):
        return False

    cleaned_name = preprocess_name(name)
    cleaned_lower = cleaned_name.lower()
    words = cleaned_lower.split()

    # ── 基础检查 ──
    if len(words) > 15:
        return False
    if len(cleaned_name) > 80:
        return False
    if len(words) < 1:
        return False

    # ── 绝对拦截 (商品规格类) ──
    for kw in HARD_BLOCK_KEYWORDS:
        if kw in cleaned_lower:
            return False

    for pattern in HARD_BLOCK_PATTERNS:
        if re.search(pattern, cleaned_lower):
            return False

    # ── 🤖 意图分类器判定 ──
    if INTENT_CLASSIFIER_AVAILABLE and _ic:
        result = _ic.classify(cleaned_name)
        if result["verdict"] in ("PASS", "WARN"):
            return True
        # BLOCK: 意图分类器判定为垃圾
        return False

    # ── 回退逻辑（意图分类器不可用时）──
    has_tool_suffix = any(s in cleaned_lower for s in TOOL_SUFFIXES)
    if has_tool_suffix:
        return True

    tech_pattern = (
        r"\b(AI|API|JSON|XML|CSV|PDF|HTML|CSS|SQL|URL|HTTP|REST|CRUD|"
        r"CLI|GUI|SDK|OCR|ML|NLP|3D|2D|RGB|HEX|UUID|SHA|MD5|AES|JWT|"
        r"OAuth|DNS|SSL|TLS|VPN|SSH|FTP|IP|TCP|UDP)\b"
    )
    if re.search(tech_pattern, cleaned_name):
        return True

    return False


def is_valid_demand(text: str) -> bool:
    """
    v4.0: 判断雷达抓取到的需求是否为有效需求

    短词模式 (≤3词): 直接走意图分类器
    长词模式 (>3词): 走 is_professional_tool_name → 意图分类器
    """
    if not text or not isinstance(text, str):
        return False

    cleaned = text.strip()
    if not cleaned or len(cleaned) < 2:
        return False

    words = cleaned.split()

    # 短词直接走意图分类器
    if len(words) <= 3 and INTENT_CLASSIFIER_AVAILABLE and _ic:
        name_lower = cleaned.lower()
        # 只有绝对非工具词才硬拦
        for kw in HARD_BLOCK_KEYWORDS:
            if kw in name_lower:
                return False
        for pattern in HARD_BLOCK_PATTERNS:
            if re.search(pattern, name_lower):
                return False
        result = _ic.classify(cleaned)
        return result["verdict"] in ("PASS", "WARN")

    return is_professional_tool_name(cleaned)


def filter_demand_list(items: list) -> tuple:
    """
    批量过滤需求列表
    """
    valid = []
    rejected = []
    for item in items:
        if is_valid_demand(str(item)):
            valid.append(item)
        else:
            rejected.append(item)
    return valid, rejected


def get_compliance_rate(tool_names: list) -> dict:
    """
    计算工具名称合规率
    """
    total = len(tool_names)
    invalid_samples = []

    for name in tool_names:
        if not is_professional_tool_name(name):
            invalid_samples.append(name)

    invalid = len(invalid_samples)
    valid = total - invalid
    rate = (valid / total * 100) if total > 0 else 100.0

    return {
        "total": total,
        "valid": valid,
        "invalid": invalid,
        "compliance_rate": round(rate, 1),
        "samples": invalid_samples[:10],
    }


# ═══════════════════════════════════════════════════════════
# 自检脚本
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    test_cases = [
        # ✅ 合格工具名
        ("AI Image Upscaler", True),
        ("PDF Converter", True),
        ("JSON Formatter", True),
        ("Crypto Price Tracker", True),
        ("Markdown Editor", True),
        ("URL Shortener", True),
        ("Password Generator", True),
        ("DNS Lookup Tool", True),
        ("SHA256 Hash Generator", True),

        # ✅ v4.0: 中文工具需求（现在应该通过）
        ("如何计算公积金贷款", True),
        ("怎么验证JSON格式", True),
        ("随机密码生成工具", True),
        ("BMI身体质量指数计算器", True),
        ("房贷月供计算器", True),
        ("单位换算器", True),
        ("图片压缩工具", True),
        ("小费分摊计算器 AA制", True),

        # 🚫 不合格（长句新闻/问题）
        ("Will the jetson nano 4gb be sufficient for our system?", False),
        ("How to move what's stored in the setup function?", False),
        ("Who here has worked with legacy? the longer you wait, the worse it gets", False),

        # 🚫 不合格（新闻/政治）
        ("Trump vents growing frustrations with reflecting-pool problems - wsj", False),
        ("Starmer is on the precipice as pressure builds for the uk leader to resign", False),

        # 🚫 不合格（娱乐/八卦）
        ("Netflix show tops charts for third week running", False),
        ("Celebrity divorce shocks fans worldwide", False),

        # 🚫 不合格（商品描述）
        ("Bounty paper towels quick size white 16 family rolls = 40 regular rolls", False),

        # ✅ Show HN 去噪通过
        ("Show HN: a lightweight pdf editor for macos Editor", True),

        # ✅ 纯 repo 名通过
        ("git-cliff Generator", True),

        # 🚫 中文八卦/闲聊
        ("男子煮粽子时狗狗狂叫 30秒后惊呆", False),
        ("我要给 glm5 道歉", False),
        ("雷军说当初不该和董明珠打赌", False),
        ("张靓颖清唱太多被罚款", False),
        ("龙舟经济火爆", False),
        ("爸爸不收红包是全国统一的吗", False),
        ("Codex 降智降麻了 听说 23 要上线了", False),
        ("理性女儿 × 感性爸爸 父亲节温情喜剧", False),
        ("现在 apple 礼品卡哪些区可以正常开通的", False),

        # ✅ 合法中英工具名
        ("Chinese PDF Converter", True),
        ("日本語 OCR Tool", True),
    ]

    if INTENT_CLASSIFIER_AVAILABLE:
        print(f"🤖 意图分类器: ✅ 已加载")
    else:
        print(f"⚠️ 意图分类器: ❌ 未加载（使用回退逻辑）")

    passed = 0
    failed = 0
    for text, expected in test_cases:
        result = is_valid_demand(text)
        status = "✅" if result == expected else "❌"
        if result == expected:
            passed += 1
        else:
            failed += 1
            if INTENT_CLASSIFIER_AVAILABLE and _ic:
                detail = _ic.classify(text)
                print(f"{status} '{text[:100]}' → got {result}, expected {expected}")
                print(f"    分类器: {detail['verdict']} score={detail['score']} intent={detail['intent']}")
                if detail.get('reasons'):
                    print(f"    原因: {detail['reasons']}")

    total = passed + failed
    print(f"\n自检完成: {passed}/{total} 通过" + (" 🎉" if failed == 0 else f" ({failed} 失败)"))
