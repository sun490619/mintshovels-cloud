#!/usr/bin/env python3
"""
需求甄别流水线 v1.1
====================
端到端串联：痛点信号检测 → LLM 意图分类 → 自动入审核队列 → 人工翻牌 → 错题本记录

用法:
  python3 demand_pipeline.py --text "我想把两座大山合成一座"
  python3 demand_pipeline.py --file candidates.txt
  python3 demand_pipeline.py --review          # 进入人工审核模式
  python3 demand_pipeline.py --review-status   # 查看待审核队列
  python3 demand_pipeline.py --text "Netflix 后台播放" --correct PASS
"""

import json
import os
import sys
import argparse
from datetime import datetime

# 导入三个模块
from pain_point_search import detect_pain_signal, ALL_PAIN_KEYWORDS
from llm_intent_classifier import LLMIntentClassifier
from mistake_book import MistakeBook

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_PATH = os.path.join(SCRIPT_DIR, "pipeline_results.json")
REVIEW_QUEUE_PATH = os.path.join(SCRIPT_DIR, "review_queue.json")


class DemandPipeline:
    def __init__(self):
        self.classifier = LLMIntentClassifier()
        self.mistake_book = MistakeBook()
        self.stats = {"total": 0, "passed": 0, "blocked": 0, "warned": 0}

    def process(self, text: str, verbose: bool = False) -> dict:
        """
        处理一条文本：
        1. 检测痛点信号
        2. LLM 意图分类
        3. 记录到错题本
        """
        self.stats["total"] += 1

        # ── 第一步：痛点信号检测 ──
        pain = detect_pain_signal(text)

        # ── 第二步：LLM 分类 ──
        result = self.classifier.classify(text)

        # ── 第三步：记录到错题本 ──
        self.mistake_book.record(text, result)

        # 统计
        if result["verdict"] == "PASS":
            self.stats["passed"] += 1
        elif result["verdict"] == "WARN":
            self.stats["warned"] += 1
        else:
            self.stats["blocked"] += 1

        # 合并结果
        output = {
            "text": text,
            "pain_signal": pain,
            "classification": result,
            "timestamp": datetime.now().isoformat(),
        }

        if verbose:
            self._print_result(output)

        return output

    def process_batch(self, texts: list, verbose: bool = True) -> list:
        results = []
        for i, text in enumerate(texts):
            if verbose:
                print(f"[{i+1}/{len(texts)}] ", end="")
            results.append(self.process(text.strip(), verbose=verbose))
        return results

    def correct(self, text: str, verdict: str, note: str = ""):
        """人工纠正一条"""
        correction = self.mistake_book.correct(text, verdict, note)
        print(f"✅ 已纠正: '{text[:50]}' → {verdict}")
        print(f"   学到的模式: {correction.get('learned_pattern', '—')}")

    def print_summary(self):
        print(f"\n{'='*50}")
        print(f"📊 流水线处理总结")
        print(f"{'='*50}")
        print(f"  总数: {self.stats['total']}")
        print(f"  ✅ PASS: {self.stats['passed']} (值得做工具)")
        print(f"  ⚠️  WARN: {self.stats['warned']} (需人工确认)")
        print(f"  🚫 BLOCK: {self.stats['blocked']} (不是需求)")
        print(f"{'='*50}")
        mb_stats = self.mistake_book.get_stats()
        print(f"📖 错题本: {mb_stats['total_corrected']} 条纠正记录")
        print()

    def _print_result(self, output: dict):
        r = output["classification"]
        pain = output["pain_signal"]
        emoji = "✅" if r["pass"] else "🚫"
        warn = " ⚠️" if r["verdict"] == "WARN" else ""
        feasible = " 🔧可行" if r.get("is_feasible") else (" ❌不可行" if r.get("is_feasible") is False else "")
        print(f"{emoji}{warn} [{r['verdict']:5s}] conf={r['confidence']:2d}% | "
              f"痛点L{pain['level']}" if pain["has_signal"] else "无痛点", end="")
        print(f" | {output['text'][:60]}")
        if r["canonical_name"]:
            print(f"    → 工具名: {r['canonical_name']}")
        print(f"    → {r['reason']}")
        if r.get("feasibility_reason"):
            print(f"    → 可行性{feasible}: {r['feasibility_reason']}")

    def save_results(self, results: list, path=None):
        path = path or RESULTS_PATH
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "stats": self.stats,
                "results": results,
            }, f, ensure_ascii=False, indent=2)
        print(f"💾 结果已保存到 {path}")

    # ═══ 人工审核队列 ═══
    def _load_review_queue(self) -> list:
        """加载待审核队列"""
        if os.path.exists(REVIEW_QUEUE_PATH):
            try:
                with open(REVIEW_QUEUE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return []

    def _save_review_queue(self, queue: list):
        """保存审核队列"""
        with open(REVIEW_QUEUE_PATH, "w", encoding="utf-8") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)

    def enqueue_warn(self, results: list):
        """将 WARN 级别的结果自动加入审核队列"""
        queue = self._load_review_queue()
        existing_texts = {item["text"] for item in queue}
        added = 0
        for r in results:
            if r["classification"]["verdict"] == "WARN":
                text = r["text"]
                if text not in existing_texts:
                    queue.append({
                        "text": text,
                        "canonical_name": r["classification"].get("canonical_name"),
                        "confidence": r["classification"]["confidence"],
                        "reason": r["classification"]["reason"],
                        "is_feasible": r["classification"].get("is_feasible"),
                        "feasibility_reason": r["classification"].get("feasibility_reason", ""),
                        "pain_level": r["pain_signal"]["level"] if r["pain_signal"]["has_signal"] else 0,
                        "status": "pending",
                        "added_at": datetime.now().isoformat(),
                    })
                    existing_texts.add(text)
                    added += 1
        if added > 0:
            self._save_review_queue(queue)
            print(f"📋 {added} 条 WARN 已加入审核队列（共 {len(queue)} 条待审核）")

    def review_interactive(self):
        """交互式人工审核：逐条展示 WARN，用户按键决定"""
        queue = self._load_review_queue()
        pending = [item for item in queue if item.get("status") == "pending"]
        if not pending:
            print("✅ 审核队列为空，没有待处理项。")
            return

        print(f"\n📋 待审核队列：{len(pending)} 条\n")
        print("操作键: [P] 批准(值得做)  [B] 驳回(不做)  [S] 跳过  [Q] 退出")
        print("-" * 60)

        reviewed = 0
        for i, item in enumerate(pending):
            print(f"\n[{i+1}/{len(pending)}]")
            print(f"  📝 {item['text']}")
            if item.get("canonical_name"):
                print(f"  🏷️  工具名: {item['canonical_name']}")
            print(f"  📊 置信度: {item.get('confidence', '?')}%")
            print(f"  💡 理由: {item.get('reason', '—')}")
            if item.get("feasibility_reason"):
                feasible_icon = "🔧可行" if item.get("is_feasible") else "❌不可行"
                print(f"  {feasible_icon}: {item['feasibility_reason']}")

            while True:
                choice = input("  👉 [P/B/S/Q]: ").strip().upper()
                if choice == "P":
                    item["status"] = "approved"
                    item["reviewed_at"] = datetime.now().isoformat()
                    self.mistake_book.correct(item["text"], "PASS",
                                              f"人工审核批准: {item.get('reason', '')[:80]}")
                    print("  ✅ 已批准 → 进错题本")
                    reviewed += 1
                    break
                elif choice == "B":
                    item["status"] = "rejected"
                    item["reviewed_at"] = datetime.now().isoformat()
                    self.mistake_book.correct(item["text"], "BLOCK",
                                              f"人工审核驳回: {item.get('reason', '')[:80]}")
                    print("  🚫 已驳回 → 进错题本")
                    reviewed += 1
                    break
                elif choice == "S":
                    print("  ⏭️  跳过")
                    break
                elif choice == "Q":
                    print("  👋 退出审核")
                    self._save_review_queue(queue)
                    print(f"📊 本次审核: {reviewed} 条，剩余 {sum(1 for q in queue if q.get('status')=='pending')} 条待处理")
                    return
                else:
                    print("  ❓ 请按 P(批准)/B(驳回)/S(跳过)/Q(退出)")

            self._save_review_queue(queue)  # 每条决定后实时保存

        remaining = sum(1 for q in queue if q.get("status") == "pending")
        print(f"\n📊 审核完成: {reviewed} 条处理，{remaining} 条待处理")

    def review_status(self):
        """查看审核队列状态"""
        queue = self._load_review_queue()
        pending = [item for item in queue if item.get("status") == "pending"]
        approved = [item for item in queue if item.get("status") == "approved"]
        rejected = [item for item in queue if item.get("status") == "rejected"]

        print(f"\n📋 审核队列状态")
        print(f"{'='*50}")
        print(f"  ⏳ 待审核: {len(pending)}")
        print(f"  ✅ 已批准: {len(approved)}")
        print(f"  🚫 已驳回: {len(rejected)}")
        print(f"{'='*50}")

        if pending:
            print(f"\n⏳ 待审核 ({len(pending)} 条):")
            for item in pending[-5:]:
                print(f"  • {item['text'][:60]}")
            if len(pending) > 5:
                print(f"  ... 还有 {len(pending)-5} 条")


def main():
    parser = argparse.ArgumentParser(description="MintShovels 需求甄别流水线 v1.1")
    parser.add_argument("--text", type=str, help="单条文本")
    parser.add_argument("--file", type=str, help="文本文件（一行一条）")
    parser.add_argument("--correct", type=str, choices=["PASS", "BLOCK"],
                        help="人工纠正：PASS 或 BLOCK")
    parser.add_argument("--note", type=str, default="", help="纠正备注")
    parser.add_argument("--save", type=str, help="保存结果到文件")
    parser.add_argument("--learned", action="store_true", help="查看错题本已学模式")
    parser.add_argument("--test", action="store_true", help="运行内置测试用例")
    parser.add_argument("--review", action="store_true", help="进入人工审核模式")
    parser.add_argument("--review-status", action="store_true", help="查看审核队列状态")
    parser.add_argument("--auto-run", action="store_true", help="从 scraper_cache.json 自动处理（CI 模式）")

    args = parser.parse_args()

    if args.auto_run:
        cache_path = os.path.join(SCRIPT_DIR, "scraper_cache.json")
        if not os.path.exists(cache_path):
            print("No scraper cache found")
            return
        with open(cache_path) as f:
            cache = json.load(f)
        candidates = cache.get("candidates", [])
        if not candidates:
            print("No candidates in cache")
            return
        texts = [c["text"] for c in candidates]
        print(f"Processing {len(texts)} candidates from scraper cache")
        pipeline = DemandPipeline()
        results = pipeline.process_batch(texts, verbose=False)
        pipeline.enqueue_warn(results)
        pipeline.save_results(results, os.path.join(SCRIPT_DIR, "demand_report.json"))
        pipeline.print_summary()
        return

    pipeline = DemandPipeline()

    if args.learned:
        pipeline.mistake_book.print_learned()
        return

    if args.review:
        pipeline.review_interactive()
        return

    if args.review_status:
        pipeline.review_status()
        return

    if args.test:
        print("🧪 运行内置测试用例\n")
        test_texts = [
            "我想把两座大山合成一座",
            "如何使图片更清晰",
            "怎么让电脑不卡",
            "Netflix 能不能后台播放视频",
            "有什么工具能把多个GIF拼成一张长图",
            "雷军说当初不该和董明珠打赌",
            "张靓颖演唱会太棒了",
            "Bounty paper towels 16 family rolls",
            "有没有那种能自动把语音转成思维导图的工具",
            "我现在每次都要手动把Markdown复制到Word排版",
            "出易盾协议源码 通杀所有类型验证码",
            "男子煮粽子时狗狗狂叫30秒后惊呆",
            "想把Excel里的表格自动转成可编辑的在线表单",
            "有没有工具能对比两个SQL数据库表差异",
            "两座大山合成一座 Mountains Merger",
        ]
        r = pipeline.process_batch(test_texts, verbose=True)
        pipeline.print_summary()
        # 自动将 WARN 入审核队列
        pipeline.enqueue_warn(r)
        return

    if args.text and args.correct:
        pipeline.correct(args.text, args.correct, args.note)
        return

    if args.text:
        result = pipeline.process(args.text, verbose=True)
        pipeline.print_summary()
        return

    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            texts = [line.strip() for line in f if line.strip()]
        results = pipeline.process_batch(texts, verbose=True)
        pipeline.print_summary()
        if args.save:
            pipeline.save_results(results, args.save)
        # 自动将 WARN 入审核队列
        pipeline.enqueue_warn(results)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
