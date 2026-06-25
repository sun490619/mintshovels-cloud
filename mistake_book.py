#!/usr/bin/env python3
"""
错题本 v1.0
===========
LLM意图分类器的自学习机制。

工作原理：
  1. 每次 LLM 判一条需求 → 结果存入 history
  2. 如果人工纠正（说"这个应该是工具/不是工具"）→ 记入 corrections
  3. 下次 LLM 分类时，自动从 corrections 中抽取最新经验注入 prompt
  4. 分析 corrections 中的模式，生成 learned_patterns（举一反三）

存储格式 (mistake_book.json):
{
  "version": "1.0",
  "total_judged": 0,
  "total_corrected": 0,
  "history": [...],       # 最近 500 条判定记录
  "corrections": [...],   # 人工纠正记录（永久保留）
  "learned_patterns": [...], # 从纠正中抽取的模式
}
"""

import json
import os
import re
from datetime import datetime
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BOOK_PATH = os.path.join(SCRIPT_DIR, "mistake_book.json")


class MistakeBook:
    def __init__(self, path=None):
        self.path = path or BOOK_PATH
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "version": "1.0",
            "total_judged": 0,
            "total_corrected": 0,
            "history": [],
            "corrections": [],
            "learned_patterns": [],
        }

    def _save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def record(self, text: str, result: dict):
        """
        记录一次 LLM 判定结果
        """
        entry = {
            "text": text,
            "timestamp": datetime.now().isoformat(),
            "pass": result.get("pass", False),
            "verdict": result.get("verdict", "UNKNOWN"),
            "canonical_name": result.get("canonical_name"),
            "confidence": result.get("confidence", 0),
            "reason": result.get("reason", ""),
            "is_unmet": result.get("is_unmet", False),
            "is_feasible": result.get("is_feasible", True),
            "feasibility_reason": result.get("feasibility_reason", ""),
        }
        self.data["history"].append(entry)
        self.data["total_judged"] += 1

        # 只保留最近 500 条
        if len(self.data["history"]) > 500:
            self.data["history"] = self.data["history"][-500:]

        self._save()

    def correct(self, text: str, correct_verdict: str, user_note: str = ""):
        """
        人工纠正：用户说"这个应该是PASS/BLOCK"

        correct_verdict: "PASS" 或 "BLOCK"
        """
        # 找到最近的同名记录
        recent = None
        for h in reversed(self.data["history"]):
            if h["text"] == text:
                recent = h
                break

        system_verdict = recent["verdict"] if recent else "UNKNOWN"

        # 抽取模式
        pattern = self._extract_pattern(text, correct_verdict, system_verdict)

        correction = {
            "text": text,
            "timestamp": datetime.now().isoformat(),
            "system_verdict": system_verdict,
            "correct_verdict": correct_verdict,
            "user_note": user_note,
            "learned_pattern": pattern,
        }
        self.data["corrections"].append(correction)
        self.data["total_corrected"] += 1

        # 更新 learned_patterns
        self._derive_patterns()

        self._save()
        return correction

    def _extract_pattern(self, text: str, correct: str, system: str) -> str:
        """
        从纠正案例中提取模式
        如："Netflix 能不能后台播放" → "视频平台名+功能需求=工具需求(不是娱乐闲聊)"
        """
        tl = text.lower()

        # 误杀案例：系统判 BLOCK，用户纠正为 PASS
        if system == "BLOCK" and correct == "PASS":
            if re.search(r'(netflix|youtube|b站|bilibili|spotify|抖音|tiktok)', tl):
                return "视频/流媒体平台名 + 功能需求 = 工具需求（不是娱乐闲聊）"
            if re.search(r'(如何|怎么|怎样|为什么).*(清晰|快|流畅|不卡|方便|简单|自动化)', tl):
                return "中文疑问词 + 优化/改进诉求 = 工具需求（不是社交闲聊）"
            if re.search(r'(能不能|可不可以|是否).*(播放|运行|打开|操作|处理)', tl):
                return "'能不能' + 功能动作 = 工具需求（不是无意义提问）"
            if re.search(r'(怎么|如何).*(下载|保存|导出|备份|同步)', tl):
                return "操作疑问 = 工具需求（如下载/保存工具）"
            return "误杀：系统因关键词被拦截，但实际有工具需求语义"

        # 漏网案例：系统判 PASS，用户纠正为 BLOCK
        if system == "PASS" and correct == "BLOCK":
            if re.search(r'(新闻|报道|快讯|突发|直播)', tl):
                return "新闻类内容 = 不是工具需求"
            return "漏网：系统误判为工具需求，实际为闲聊/八卦"

        return "手动纠正"

    def _derive_patterns(self):
        """
        从所有纠正中提取高频模式，生成 learned_patterns
        """
        patterns = []
        for c in self.data["corrections"][-50:]:
            p = c.get("learned_pattern", "")
            if p and p != "手动纠正":
                patterns.append(p)

        counter = Counter(patterns)
        self.data["learned_patterns"] = [
            {"pattern": p, "count": n}
            for p, n in counter.most_common(10)
        ]

    def get_recent_examples(self, n: int = 10) -> list:
        """
        获取最近的纠正案例，用于注入 LLM prompt
        """
        corrections = self.data["corrections"][-n:]
        return [
            {
                "text": c["text"][:120],
                "system_verdict": c["system_verdict"],
                "correct_verdict": c["correct_verdict"],
                "learned_pattern": c.get("learned_pattern", ""),
            }
            for c in corrections
        ]

    def get_stats(self) -> dict:
        return {
            "total_judged": self.data["total_judged"],
            "total_corrected": self.data["total_corrected"],
            "correction_rate": f"{self.data['total_corrected'] / max(self.data['total_judged'], 1) * 100:.1f}%",
            "learned_patterns_count": len(self.data.get("learned_patterns", [])),
        }

    def print_learned(self):
        """打印已经学到的模式"""
        patterns = self.data.get("learned_patterns", [])
        corrections = self.data.get("corrections", [])
        stats = self.get_stats()
        if not patterns and not corrections:
            print("📖 错题本为空，还没有学到任何东西。")
            return
        print(f"📖 错题本概况：共判断 {stats['total_judged']} 次，纠正 {stats['total_corrected']} 次")
        if patterns:
            print("\n🧠 自动学到的模式：")
            for p in patterns:
                print(f"   • {p['pattern']}（累计 {p['count']} 次）")
        if corrections:
            print(f"\n✍️ 人工纠正记录（最近 {min(len(corrections), 5)} 条）：")
            for c in corrections[-5:]:
                emoji = "✅" if c["correct_verdict"] == "PASS" else "🚫"
                print(f"   {emoji} {c['text'][:50]} → {c['correct_verdict']}")


# ═══ 自检 ═══
if __name__ == "__main__":
    mb = MistakeBook()

    # 模拟记录
    mb.record("我想把两座大山合成一座", {
        "pass": True, "verdict": "PASS",
        "canonical_name": "创意合成拼接器",
        "confidence": 75, "reason": "可能是图片合成需求",
        "is_unmet": True,
    })

    # 模拟纠正
    mb.correct("Netflix 能不能后台播放视频", "PASS", "这不是娱乐闲聊，是真实功能需求")
    mb.correct("如何使图片更清晰", "PASS", "图片增强是实实在在的工具需求")

    print("📊 错题本统计：")
    for k, v in mb.get_stats().items():
        print(f"  {k}: {v}")
    print()
    mb.print_learned()
