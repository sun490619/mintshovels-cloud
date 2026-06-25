#!/usr/bin/env python3
"""
全网需求抓取器 v1.0
===================
从 Reddit、Hacker News、Stack Overflow 抓取可能包含工具需求的文本，
喂给需求甄别流水线。

数据源（全部免费，无需 API Key）：
- Reddit JSON API: r/SomebodyMakeThis, r/AppIdeas, r/software, r/webdev
- Hacker News API: Show HN, Ask HN
- Stack Exchange API: Stack Overflow 热门问题

用法:
  python3 demand_scraper.py                  # 抓取所有源 + 跑流水线
  python3 demand_scraper.py --limit 30       # 每个源最多30条
  python3 demand_scraper.py --source reddit  # 只抓 Reddit
  python3 demand_scraper.py --dry-run        # 只抓不跑流水线
  python3 demand_scraper.py --schedule       # 进入定时循环模式(每2小时)
"""

import json
import os
import sys
import time
import argparse
import hashlib
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(SCRIPT_DIR, "scraper_cache.json")
SEEN_PATH = os.path.join(SCRIPT_DIR, "scraper_seen.json")

# ═══ Reddit 搜索目标（通过 DuckDuckGo 间接搜索） ═══
REDDIT_SUBREDDITS = [
    "SomebodyMakeThis",   # 专门提工具需求
    "AppIdeas",           # App 创意
    "software",           # 软件讨论
]

SEARCH_QUERIES_DDG = [
    'site:reddit.com "is there a tool"',
    'site:reddit.com "wish there was"',
    'site:reddit.com "looking for a tool"',
    'site:reddit.com "any tool that can"',
    'site:reddit.com "does anyone know a tool"',
]

# ═══ Hacker News ═══
HN_SEARCH_QUERIES = [
    "Show HN",
    "Ask HN: tool",
    "Ask HN: is there",
    "Ask HN: looking for",
]

# ═══ Stack Exchange ═══
STACKEXCHANGE_TAGS = [
    "software-development",
    "tools",
    "automation",
    "web-development",
]

# ═══ 核心抓取逻辑 ═══

class DemandScraper:
    def __init__(self, limit_per_source=25):
        self.limit = limit_per_source
        self.seen = self._load_seen()
        self.candidates = []
        self.sources_stats = {}

    def _fetch_json(self, url: str, timeout=15) -> dict:
        """通用 JSON API 抓取"""
        # 轮换 User-Agent 绕过反爬
        user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "python-requests/2.31.0",
        ]
        import random
        headers = {
            "User-Agent": random.choice(user_agents),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content = resp.read().decode("utf-8")
                return json.loads(content)
        except urllib.error.HTTPError as e:
            if e.code == 403:
                # 打印更详细的错误帮助定位
                body = e.read().decode("utf-8", errors="ignore")[:200]
                print(f"  ⚠️  403 Forbidden: {url[:70]}... ({body[:100]})" if body else f"  ⚠️  403: {url[:70]}")
            else:
                print(f"  ⚠️  抓取失败 {url[:70]}: HTTP {e.code}")
            return {}
        except Exception as e:
            print(f"  ⚠️  抓取失败 {url[:70]}: {e}")
            return {}

    def _hash(self, text: str) -> str:
        return hashlib.md5(text.strip().lower().encode()).hexdigest()

    def _is_new(self, text: str) -> bool:
        h = self._hash(text)
        if h in self.seen:
            return False
        self.seen.add(h)
        return True

    def _add_candidate(self, text: str, source: str, url: str = ""):
        if len(text) < 15:
            return
        if len(text) > 500:
            text = text[:500]
        if self._is_new(text):
            self.candidates.append({
                "text": text.strip(),
                "source": source,
                "url": url,
                "fetched_at": datetime.now().isoformat(),
            })

    # ═══ Reddit（通过 DuckDuckGo 间接搜索） ═══
    def scrape_reddit(self) -> int:
        count = 0
        print(f"🔍 Reddit: 通过搜索引擎间接抓取...")

        for query in SEARCH_QUERIES_DDG:
            encoded = urllib.parse.quote(query)
            # DuckDuckGo HTML 搜索（比 Google 更容易爬）
            url = f"https://html.duckduckgo.com/html/?q={encoded}"
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                })
                with urllib.request.urlopen(req, timeout=10) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                    import re
                    # 提取搜索结果摘要
                    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
                    titles = re.findall(r'class="result__title"[^>]*>.*?<a[^>]*>(.*?)</a>', html, re.DOTALL)
                    for t in titles:
                        clean = re.sub(r'<[^>]+>', '', t).strip()
                        if clean and len(clean) > 15:
                            self._add_candidate(clean, f"reddit/ddg", "")
                            count += 1
            except Exception as e:
                pass
            time.sleep(0.5)

        self.sources_stats["reddit"] = count
        print(f"  ✅ Reddit(间接): {count} 条新候选")
        return count

    # ═══ GitHub Issues（寻找工具/功能需求） ═══
    def scrape_github(self) -> int:
        count = 0
        print("🔍 GitHub: 搜索 Issues 中的工具需求...")

        queries = [
            '"is there a tool"+language:english',
            '"wish there was"+language:english',
            '"looking for a tool"+language:english',
        ]

        for query in queries[:2]:
            encoded = urllib.parse.quote(query)
            url = f"https://api.github.com/search/issues?q={encoded}&sort=created&order=desc&per_page=10"
            data = self._fetch_json(url)
            items = data.get("items", [])
            for item in items:
                title = item.get("title", "")
                body = (item.get("body", "") or "")[:300]
                html_url = item.get("html_url", "")
                full_text = title
                if body:
                    full_text += " " + body
                if full_text.strip() and len(full_text) > 15:
                    self._add_candidate(full_text, "github", html_url)
                    count += 1
            time.sleep(1)

        self.sources_stats["github"] = count
        print(f"  ✅ GitHub: {count} 条新候选")
        return count

    # ═══ Hacker News ═══
    def scrape_hn(self) -> int:
        count = 0
        print("🔍 Hacker News: 抓取最新帖子...")

        # 获取最新帖子 ID
        max_item = self._fetch_json("https://hacker-news.firebaseio.com/v0/maxitem.json")
        if not max_item:
            return 0

        max_id = int(max_item)
        fetched = 0
        for item_id in range(max_id, max(0, max_id - 500), -1):
            if fetched >= self.limit:
                break
            url = f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
            data = self._fetch_json(url)
            if not data or data.get("type") != "story":
                continue
            title = data.get("title", "")
            if not title:
                continue
            # 只收集可能的工具需求
            demand_keywords = ["tool", "app", "website", "is there", "show hn", "ask hn",
                               "how to", "anyone know", "recommend", "alternative to",
                               "looking for", "wish", "idea"]
            title_lower = title.lower()
            if any(kw in title_lower for kw in demand_keywords):
                item_url = data.get("url", f"https://news.ycombinator.com/item?id={item_id}")
                self._add_candidate(title, "hackernews", item_url)
                count += 1
            fetched += 1

        self.sources_stats["hackernews"] = count
        print(f"  ✅ HN: {count} 条新候选")
        return count

    # ═══ Stack Overflow ═══
    def scrape_stackoverflow(self) -> int:
        count = 0
        print("🔍 Stack Overflow: 抓取工具推荐类问题...")

        search_terms = [
            "is there a tool",
            "tool to",
            "software recommendation",
            "looking for a",
            "any tool",
        ]

        for term in search_terms:
            encoded = urllib.parse.quote(term)
            url = (f"https://api.stackexchange.com/2.3/search?"
                   f"order=desc&sort=votes&intitle={encoded}&"
                   f"site=stackoverflow&pagesize=10&filter=withbody")
            data = self._fetch_json(url)
            items = data.get("items", [])
            for item in items:
                title = item.get("title", "")
                link = item.get("link", "")
                body = (item.get("body_markdown", "") or "")[:200]
                full_text = title
                if body:
                    full_text += " " + body
                if full_text.strip() and len(full_text) > 15:
                    # _add_candidate 内部会做 _is_new 去重
                    self._add_candidate(full_text, "stackoverflow", link)
                    count += 1
            time.sleep(0.5)

        self.sources_stats["stackoverflow"] = count
        print(f"  ✅ Stack Overflow: {count} 条新候选")
        return count

    # ═══ 全量抓取 ═══
    def scrape_all(self, sources=None):
        """全量抓取，返回候选列表"""
        all_sources = {"reddit", "hackernews", "stackoverflow", "github"}
        if sources:
            all_sources = all_sources & set(sources)

        print(f"\n🚀 全网需求抓取 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 50)

        total = 0
        if "reddit" in all_sources:
            total += self.scrape_reddit()
        if "hackernews" in all_sources:
            total += self.scrape_hn()
        if "stackoverflow" in all_sources:
            total += self.scrape_stackoverflow()
        if "github" in all_sources:
            total += self.scrape_github()

        self._save_seen()
        self._save_cache()

        print("=" * 50)
        print(f"📊 总计: {total} 条新候选 | 数据源: {self.sources_stats}")
        return self.candidates

    # ═══ 缓存管理 ═══
    def _load_seen(self) -> set:
        if os.path.exists(SEEN_PATH):
            try:
                with open(SEEN_PATH, "r") as f:
                    return set(json.load(f))
            except Exception:
                pass
        return set()

    def _save_seen(self):
        with open(SEEN_PATH, "w") as f:
            json.dump(list(self.seen), f)

    def _save_cache(self):
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "updated_at": datetime.now().isoformat(),
                "sources": self.sources_stats,
                "candidates_count": len(self.candidates),
                "candidates": self.candidates,
            }, f, ensure_ascii=False, indent=2)


# ═══ 定时运行 ═══
def run_scheduled(interval_minutes=120, limit=25):
    """定时循环：每 N 分钟抓一次 + 跑流水线"""
    print(f"⏰ 定时模式启动 | 间隔: {interval_minutes} 分钟")
    print(f"💡 Ctrl+C 退出\n")

    from demand_pipeline import DemandPipeline
    pipeline = DemandPipeline()

    while True:
        try:
            scraper = DemandScraper(limit_per_source=limit)
            candidates = scraper.scrape_all()

            if candidates:
                texts = [c["text"] for c in candidates]
                print(f"\n🔄 送入流水线: {len(texts)} 条")
                results = pipeline.process_batch(texts, verbose=False)
                pipeline.enqueue_warn(results)
                pipeline.print_summary()
            else:
                print("  📭 没有新增候选\n")

            print(f"💤 等待 {interval_minutes} 分钟...\n")
            time.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            print("\n👋 定时模式退出")
            break
        except Exception as e:
            print(f"⚠️ 运行出错: {e}，5分钟后重试...")
            time.sleep(300)


# ═══ CLI ═══
def main():
    parser = argparse.ArgumentParser(description="MintShovels 全网需求抓取器 v1.0")
    parser.add_argument("--limit", type=int, default=25, help="每个源最多抓取数")
    parser.add_argument("--source", choices=["reddit", "hackernews", "stackoverflow", "github"],
                        help="只抓指定源")
    parser.add_argument("--dry-run", action="store_true", help="只抓不跑流水线")
    parser.add_argument("--schedule", action="store_true", help="定时循环模式")
    parser.add_argument("--interval", type=int, default=120, help="定时间隔(分钟)")
    parser.add_argument("--no-pipeline", action="store_true", help="不跑流水线")

    args = parser.parse_args()

    if args.schedule:
        run_scheduled(interval_minutes=args.interval, limit=args.limit)
        return

    # 单次抓取
    sources = [args.source] if args.source else None
    scraper = DemandScraper(limit_per_source=args.limit)
    candidates = scraper.scrape_all(sources=sources)

    if not candidates:
        print("\n📭 没有抓到新候选（可能都已被处理过）")
        return

    if args.dry_run or args.no_pipeline:
        print(f"\n📋 候选预览（前10条）:")
        for c in candidates[:10]:
            print(f"  [{c['source']}] {c['text'][:80]}")
        if len(candidates) > 10:
            print(f"  ... 还有 {len(candidates)-10} 条")
        return

    # 跑流水线
    print(f"\n🔄 送入流水线: {len(candidates)} 条")
    from demand_pipeline import DemandPipeline
    pipeline = DemandPipeline()
    texts = [c["text"] for c in candidates]
    results = pipeline.process_batch(texts, verbose=True)
    pipeline.enqueue_warn(results)
    pipeline.print_summary()

    # 保存完整报告
    report_path = os.path.join(SCRIPT_DIR, "demand_report.json")
    pipeline.save_results(results, report_path)


if __name__ == "__main__":
    main()
