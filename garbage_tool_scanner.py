#!/usr/bin/env python3
"""
MintShovels 垃圾工具扫描器
============================
只扫描、拉清单，绝不删除！
输出: 垃圾工具样本审计清单

识别规则：
  R1: 名称超过15个单词 → 完整长句套壳
  R2: 含问号 → 社区提问套壳
  R3: 新闻标题特征词 → 社会热点闲聊
  R4: 社交媒体闲聊特征 → 八卦娱乐
  R5: 名称>80字符 → 畸形长名称
  R6: 事件描述特征 → 非工具属性
  R7: 名称>50字符且无工具后缀 → 缺工具属性

用法: python3 garbage_tool_scanner.py
"""

import json
import os
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOL_FACTORY_DIR = os.environ.get(
    "TOOL_FACTORY_DIR",
    os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), "tool-factory")
)
TOOLS_PATH = os.path.join(TOOL_FACTORY_DIR, "backups", "generated_tools.json")


def is_garbage(tool):
    """判断一个工具是否为垃圾（套壳长句/社交闲聊/新闻等）"""
    name = tool["name"]
    name_lower = name.lower()
    reasons = []

    # R1: 名称超过15个单词 → 完整长句套壳
    word_count = len(name.split())
    if word_count > 15:
        reasons.append(f"长句子({word_count}词)")

    # R2: 含问号 → 社区提问套壳
    if "?" in name:
        reasons.append("提问句式")

    # R3: 新闻标题特征词
    news_patterns = [
        r"\bbreaking\b", r"\bjust in\b", r"\bleaked\b", r"\bconfirmed\b",
        r"\breport:\b", r"\bupdate:\b", r"\bstatement\b", r"\bexclusive\b",
        r"\brevealed\b", r"\bannounced\b", r"\bshocking\b", r"\bviral\b",
        r"\btrending\b", r"\bscandal\b", r"\bcontroversy\b",
        r"\bresign\b", r"\belection\b", r"\bprotest\b", r"\bcrash\b",
    ]
    for pat in news_patterns:
        if re.search(pat, name_lower):
            reasons.append(f"新闻标题({pat})")
            break

    # R4: 社交媒体闲聊特征
    social_patterns = [
        r"\bI\b.*\b(think|believe|feel|guess|wish|hope)\b",
        r"\b(my|our)\b.*\b(take|opinion|thought|experience)\b",
        r"!!!+", r"\bOMG\b", r"\bLOL\b", r"\bwtf\b",
        r"\bhot take\b", r"\bunpopular opinion\b",
        r"\b(should|must|need to|have to)\b.*\b(you|we|everyone)\b",
        r"\banyone\b.*\b(else|know|have|tried)\b",
    ]
    for pat in social_patterns:
        if re.search(pat, name_lower):
            reasons.append(f"社交媒体闲聊({pat})")
            break

    # R5: 名称>80字符 → 畸形长名称
    if len(name) > 80:
        reasons.append("超长名称(>80字符)")

    # R6: 事件描述
    event_patterns = [
        r"\d{4}-\d{2}-\d{2}",
        r"\bvs\b.*\bvs\b",
        r"\bdies?\b\s(at|in|aged)",
        r"\bwon\b.*\b(award|prize|election)",
        r"\bhacked?\b", r"\bscam\b", r"\bexposed\b",
        r"\b(fired|laid off|resigns)\b",
        r"\b(says|said)\b.*\b(will|would|should|must)\b",
    ]
    for pat in event_patterns:
        if re.search(pat, name_lower):
            reasons.append(f"事件描述({pat})")
            break

    # R7: 名称>50字符且无明确工具后缀词
    tool_suffixes = [
        "generator", "converter", "checker", "calculator", "editor",
        "viewer", "formatter", "validator", "analyzer", "tracker",
        "downloader", "compressor", "encoder", "decoder", "scanner",
        "finder", "extractor", "monitor", "optimizer", "detector",
        "tester", "builder", "creator", "manager", "explorer",
        "debugger", "profiler", "inspector", "visualizer", "renderer",
        "splitter", "merger", "uploader", "scheduler", "notifier",
        "translator", "summarizer", "parser", "minifier", "beautifier",
    ]
    if len(name) > 50:
        has_suffix = any(s in name_lower for s in tool_suffixes)
        if not has_suffix:
            reasons.append("缺乏工具后缀(>50字符)")

    return reasons


def run_scan():
    """扫描全库并输出审计清单"""
    if not os.path.exists(TOOLS_PATH):
        print(f"❌ 找不到工具数据库: {TOOLS_PATH}")
        return

    tools = json.load(open(TOOLS_PATH))

    garbage_tools = []
    reason_stats = {}
    for tool in tools:
        reasons = is_garbage(tool)
        if reasons:
            garbage_tools.append((tool, reasons))
            for r in reasons:
                reason_stats[r] = reason_stats.get(r, 0) + 1

    total = len(tools)
    garbage_count = len(garbage_tools)
    clean_count = total - garbage_count

    print()
    print("=" * 75)
    print("  🗑️  MintShovels 全站工具品质大审计")
    print("=" * 75)
    print(f"  全库工具总数:   {total}")
    print(f"  正常工具数:     {clean_count}  ({clean_count/total*100:.1f}%)")
    print(f"  垃圾工具数:     {garbage_count}  ({garbage_count/total*100:.1f}%)")
    print()

    print("  垃圾成因分布:")
    for reason, count in sorted(reason_stats.items(), key=lambda x: -x[1]):
        print(f"    • {reason}: {count} 个")
    print()

    # ===== 样本展示（前20条）=====
    print("=" * 75)
    print("  📋 垃圾工具样本审计清单（前 20 条）")
    print("=" * 75)

    for i, (tool, reasons) in enumerate(garbage_tools[:20], 1):
        name = tool["name"]
        cat = tool.get("category", "?")
        reason_str = " + ".join(reasons)
        print(f"\n  [{i:2d}] 🔴 {reason_str}")
        print(f"       分类: {cat} | ID: {tool['id']}")
        print(f"       原名: {name[:120]}")
        if len(name) > 120:
            print(f"             ...(共{len(name)}字符)")

    # ===== 按分类统计 =====
    print()
    print("-" * 75)
    print("  各分类垃圾占比:")
    for cat in sorted(set(t["category"] for t in tools)):
        cat_total = sum(1 for t in tools if t["category"] == cat)
        cat_garbage = sum(1 for t, _ in garbage_tools if t["category"] == cat)
        pct = cat_garbage / cat_total * 100 if cat_total > 0 else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        icon = "🔴" if pct > 2 else "🟢"
        print(f"  {icon} {cat:15s}: {cat_garbage:4d}/{cat_total:4d} = {pct:5.1f}% {bar}")

    print()
    print("=" * 75)
    print("  ⚠️  以上为扫描结果，未执行任何删除操作！")
    print("  请审阅后下达清理指令。")
    print("=" * 75)
    print()

    # 保存完整清单到文件
    report = {
        "scan_time": __import__("datetime").datetime.now().isoformat(),
        "total_tools": total,
        "clean_count": clean_count,
        "garbage_count": garbage_count,
        "garbage_pct": round(garbage_count / total * 100, 1),
        "reason_stats": reason_stats,
        "garbage_tools": [
            {
                "id": t["id"],
                "name": t["name"],
                "category": t.get("category", "?"),
                "reasons": reasons,
            }
            for t, reasons in garbage_tools
        ],
    }
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "garbage_audit_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  📄 完整审计报告已保存: {report_path}")
    print(f"     包含全部 {garbage_count} 个垃圾工具的详细记录")

    return garbage_tools, reason_stats


if __name__ == "__main__":
    run_scan()
