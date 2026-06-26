#!/usr/bin/env python3
"""
MintShovels 需求雷达 v2.1 — 仅用免费无需API Key的水源

═══ 架构升级 (v2.0 → v2.1) ═══
  v2.0: 25个水源 → 14个需API/已挂，实际只有9个可用
  v2.1: 砍掉14个失效源，新加入6个已验证免费源，共计19个活跃水源

数据源 (五大水系 → 纯免费):
  1. 开发者问答枢纽: GitHub Trending, Stack Overflow RSS, V2EX API, Dev.to RSS, Lobsters RSS
  2. 海外效率创客社区: ProductHunt, HN Algolia(首页+Show+Ask), HackerNoon RSS, InfoQ RSS
  3. 全球搜索趋势: Google Trends RSS, 百度热搜
  4. 维基百科与AI趋势: Wikipedia API, HuggingFace API, arXiv API, Papers With Code API
  5. 包注册+技术主题: npm Registry Search API, GitHub Topics

已移除 (v2.0中已挂):
  Reddit(403) / 知乎(401) / 微博(403) / Quora(403) / 36Kr/NPM RSS(403) / 
  少数派/Dribbble/Bing/Medium/PyPI (返回0或无数据)

核心升级:
  🧠 工具特质自动识别 — 动态检测"输入→处理→输出"动作特征
  🚫 闲聊二次过滤   — 抓取瞬间前置过滤新闻/八卦/情绪吐槽
  🔒 配合门禁系统   — 多道过滤守死33精品底线

输出: demand_report.json (供 auto_factory.py 消费)
"""

import json
import re
import os
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# ── 引入硬核甄别过滤器 ──
try:
    from engine.demand_filter import is_valid_demand, filter_demand_list, is_professional_tool_name
except ModuleNotFoundError:
    from demand_filter import is_valid_demand, filter_demand_list, is_professional_tool_name

REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# 🧠 工具特质自动识别引擎 (ToolTraitRecognizer)
# ═══════════════════════════════════════════════════════════════

class ToolTraitRecognizer:
    """
    动态工具特质识别模型 — 不依赖写死的关键词字典
    通过多维度语义模式识别一段文本是否描述了"工具需求"
    
    核心原理:
      1. 动作特征识别 — "输入→自动化处理→输出"的计算/转换/生成诉求
      2. 工具名词检测 — 专业工具后缀 (Converter, Generator, Checker...)
      3. 技术概念检测 — 技术缩写/协议/格式名词 (JSON, API, PDF, CSV...)
      4. 非工具闲聊过滤 — 新闻/八卦/情绪/吐槽判断
    """

    # ── 动作特征模式 (多语言) ──
    ACTION_PATTERNS = {
        # 中文动作词 — 表示自动化/转换/生成行为的动词+宾语组合
        "cn_transform": re.compile(
            r'(批量|一键|自动|快速|在线|免费|实时|智能|'
            r'格式转换|格式互转|互相转换|转换器?|转化|'
            r'生成器?|制作器?|编辑器?|查看器?|检查器?|检测器?|'
            r'下载器?|上传器?|提取器?|解析器?|压缩器?|解压器?|'
            r'合并|分割|拆分|裁剪|缩放|旋转|翻转|'
            r'编码|解码|加密|解密|哈希|签名|验证|'
            r'计算器?|计数器?|计时器?|定时器?|'
            r'翻译器?|对比器?|合并器?|拆分器?|'
            r'优化|美化|格式化|压缩|解压缩|打包|解包)'
        ),
        # 英文动作词 — 表示工具功能的后缀和动词
        "en_action": re.compile(
            r'\b('
            r'generator|converter|checker|validator|viewer|editor|'
            r'compressor|downloader|uploader|extractor|parser|analyzer|'
            r'formatter|encoder|decoder|encryptor|decryptor|'
            r'scanner|monitor|tracker|calculator|counter|timer|'
            r'merger|splitter|resizer|cropper|optimizer|'
            r'minifier|beautifier|translator|summarizer|'
            r'batch\s*\w+|one-click\s*\w+|auto\s*\w+|'
            r'convert\s*\w+to|transform\s*\w+to|'
            r'generate|validate|compress|decompress|'
            r'encode|decode|encrypt|decrypt|hash|sign|verify'
            r')\b', re.IGNORECASE
        ),
        # 输入→输出转换链式表达
        "io_chain": re.compile(
            r'('
            r'\w+\s*(→|->|=>|→|to|转|转换为|转换成|变成)\s*\w+|'
            r'\w+\s*(format|格式)\s*(conversion|转换)|'
            r'from\s+\w+\s+to\s+\w+|'
            r'(input|upload|paste|输入|上传|粘贴).*(output|download|get|输出|下载|得到)'
            r')', re.IGNORECASE
        ),
    }

    # ── 工具名词后缀 (中英文) ──
    TOOL_SUFFIXES_CN = [
        '生成器', '转换器', '检查器', '验证器', '编辑器', '查看器',
        '压缩器', '下载器', '提取器', '解析器', '计算器', '计数器',
        '计时器', '翻译器', '合并器', '拆分器', '加密器', '解密器',
        '编码器', '解码器', '格式化工具', '优化器', '扫描器', '监控器',
        '追踪器', '生成工具', '检测工具', '转换工具', '编辑工具',
        '工具箱', '助手', '帮手', '小工具',
    ]

    TOOL_SUFFIXES_EN = [
        'generator', 'converter', 'checker', 'validator', 'viewer',
        'editor', 'compressor', 'downloader', 'uploader', 'extractor',
        'parser', 'analyzer', 'formatter', 'encoder', 'decoder',
        'encryptor', 'decryptor', 'scanner', 'monitor', 'tracker',
        'calculator', 'counter', 'timer', 'merger', 'splitter',
        'resizer', 'cutter', 'optimizer', 'minifier', 'beautifier',
        'translator', 'summarizer', 'tool', 'utility', 'helper',
    ]

    # ── 技术/格式/协议名词 ──
    TECH_SIGNALS = re.compile(
        r'\b('
        r'json|xml|yaml|toml|csv|tsv|sql|html|css|js|javascript|typescript|'
        r'python|rust|go|golang|java|swift|kotlin|'
        r'api|rest|graphql|grpc|websocket|http|https|ftp|sftp|'
        r'pdf|docx?|xlsx?|pptx?|md|markdown|txt|rtf|'
        r'png|jpe?g|gif|svg|webp|avif|mp4|mp3|wav|ogg|webm|'
        r'base64|hex|binary|utf-?8|ascii|unicode|'
        r'sha\d+|md5|aes|rsa|hmac|jwt|oauth|saml|'
        r'git|docker|kubernetes|k8s|npm|pip|'
        r'url|uri|dns|ip|tcp|udp|ssl|tls|'
        r'latex|regex|regexp|'
        r'crypto|blockchain|token|nft|web3|'
        r'css\s*flex|css\s*grid|tailwind|bootstrap|react|vue|angular|svelte|'
        r'openai|chatgpt|llm|gpt|claude|gemini|stable\s*diffusion'
        r')\b', re.IGNORECASE
    )

    # ── 用户痛苦/需求表达式 ──
    PAIN_EXPRESSIONS = re.compile(
        r'('
        r'how\s*(to|can\s*i|do\s*i)\s+\w+|'
        r'is\s+there\s+(a|an|any)\s+\w+\s+tool|'
        r'(best|free|open.source)\s+\w+\s+tool|'
        r'i\s+need\s+(a|an)\s+\w+\s+tool|'
        r'looking\s+for\s+(a|an)\s+\w+\s+tool|'
        r'recommend\s+(me\s+)?(a|an)\s+\w+\s+tool|'
        r'怎么|如何|怎样|有没有|求推荐|求一个|'
        r'有没有什么|哪里可以|用什么|有没有人'
        r')', re.IGNORECASE
    )

    def analyze(self, text: str) -> dict:
        """
        对一段文本执行工具特质多维度分析
        返回: {is_tool_signal, confidence, features, reasons}
        """
        if not text or len(text) < 3:
            return {"is_tool_signal": False, "confidence": 0, "features": [], "reasons": ["文本过短"]}

        features = []
        score = 0

        # 1. 动作特征检测 (最高权重)
        cn_transform = self.ACTION_PATTERNS["cn_transform"].findall(text)
        en_action = self.ACTION_PATTERNS["en_action"].findall(text)
        io_chain = self.ACTION_PATTERNS["io_chain"].findall(text)

        if cn_transform:
            features.append(f"中文动作特征: {cn_transform[:3]}")
            score += 30
        if en_action:
            features.append(f"英文动作特征: {en_action[:3]}")
            score += 25
        if io_chain:
            features.append(f"输入→输出链式: {io_chain[:2]}")
            score += 20

        # 2. 工具名词检测
        cn_tool_suffix = [s for s in self.TOOL_SUFFIXES_CN if s in text]
        en_tool_suffix = [s for s in self.TOOL_SUFFIXES_EN if s.lower() in text.lower()]

        if cn_tool_suffix:
            features.append(f"中文工具名词: {cn_tool_suffix[:3]}")
            score += 20
        if en_tool_suffix:
            features.append(f"英文工具名词: {en_tool_suffix[:3]}")
            score += 15

        # 3. 技术信号检测
        tech_matches = self.TECH_SIGNALS.findall(text)
        if tech_matches:
            features.append(f"技术概念: {list(set(tech_matches))[:5]}")
            score += 15

        # 4. 用户痛苦/需求表达
        pain_matches = self.PAIN_EXPRESSIONS.findall(text)
        if pain_matches:
            features.append(f"需求表达: {pain_matches[:2]}")
            score += 10

        # 判定
        if score >= 30:
            confidence = min(100, score)
            return {
                "is_tool_signal": True,
                "confidence": confidence,
                "features": features,
                "score": score,
                "reasons": [],
            }
        elif score >= 15:
            return {
                "is_tool_signal": True,
                "confidence": score,
                "features": features,
                "score": score,
                "reasons": ["低置信度—可能需人工审查"],
            }
        else:
            return {
                "is_tool_signal": False,
                "confidence": score,
                "features": features,
                "score": score,
                "reasons": ["未检测到工具特质信号"],
            }


# ═══════════════════════════════════════════════════════════════
# 🚫 闲聊/非工具内容前置过滤器 (ChatterFilter)
# ═══════════════════════════════════════════════════════════════

class ChatterFilter:
    """
    抓取瞬间前置过滤器 — 在雷达采集阶段就拦截非工具内容
    
    即使数据来自高流量平台，如果内容属于以下类别，当场拦截:
      1. 新闻八卦 (政治/娱乐/体育/社会新闻)
      2. 纯情绪吐槽 (无实质工具需求)
      3. 名人/明星相关
      4. 广告/促销/优惠
      5. 招聘/求职
      6. 纯闲聊/灌水
    """

    # ── 新闻类关键词 ──
    NEWS_PATTERNS = re.compile(
        r'\b('
        r'breaking|just in|announce(d|ment)|'
        r'confirms|reveals|leaked|exclusive|'
        r'election|poll|vote|president|congress|senate|parliament|'
        r'\bwar\b|conflict|crisis|disaster|earthquake|flood|hurricane|'
        r'nasdaq|dow|s\s*&\s*p|bitcoin|ethereum|price\s*surge|'
        r'breaking\s*news|latest\s*news|headline|'
        r'新闻|突发|最新|刚刚|曝光|爆料|确认|公布|'
        r'宣布|声明|调查|数据显示|'
        r'震惊|重磅|紧急|快讯|速报|'
        r'选举|投票|总统|国会|战争|冲突|危机|'
        r'股市|股票|涨停|跌停|大盘|行情|'
        r'死了|去世|逝世|遇难|车祸|事故|火灾|地震'
        r')\b', re.IGNORECASE
    )

    # ── 娱乐/体育/游戏类(非工具向) ──
    ENTERTAINMENT_PATTERNS = re.compile(
        r'\b('
        r'celebrity|actress|singer|famous|hollywood|'
        r'movie|film|tv\s*show|episode|season|trailer|netflix|'
        r'sports|football|basketball|soccer|baseball|nfl|nba|mlb|'
        r'game\s*review|gameplay|walkthrough|esports|gaming\s*news|'
        r'music|album|concert|tour|festival|'
        r'fashion|beauty|makeup|skincare|outfit|'
        r'明星|演员|歌手|电影|电视剧|综艺|娱乐|八卦|'
        r'足球|篮球|比赛|联赛|世界杯|欧冠|nba|英超|'
        r'游戏|手游|电竞|皮肤|抽卡|'
        r'演唱会|新歌|专辑|mv|'
        r'穿搭|美妆|护肤|发型|'
        r'出轨|离婚|结婚|恋情|绯闻'
        r')\b', re.IGNORECASE
    )

    # ── 纯情绪/吐槽/灌水 ──
    CHATTER_PATTERNS = re.compile(
        r'('
        r'lol|lmao|rofl|wtf|omg|tbh|imo|imho|fyi|'
        r'rant|vent|unpopular\s*opinion|hot\s*take|'
        r'what\s*do\s*you\s*think|does\s*anyone\s*else|'
        r'am\s*i\s*the\s*only|change\s*my\s*mind|'
        r'吐槽|无语|服了|绝了|笑死|笑不活|'
        r'这也太|我真的|我也是|谁懂|救命|'
        r'好烦|好累|崩溃|心态|麻了|'
        r'哈哈哈哈|哈哈哈|呵呵|嘿嘿|'
        r'有没有人跟我一样|你们觉得|大家觉得|'
        r'想不通|搞不懂|不明白|'
        r'涨工资|加班|老板|同事|领导|'
        r'烦死了|气死了|太坑了|真无语'
        r')', re.IGNORECASE
    )

    # ── 广告/促销 ──
    AD_PATTERNS_CN = re.compile(
        r'(促销|打折|优惠|满减|秒杀|抢购|限时|'
        r'优惠券|折扣|特价|清仓|'
        r'点击购买|立即购买|马上抢|'
        r'拼团|砍价|红包|补贴|'
        r'特卖|大促|预售|团购|'
        r'减\d+元|直降)'
    )
    AD_PATTERNS_EN = re.compile(
        r'\b('
        r'discount|sale|deal|coupon|promo|offer|limited\s*time|'
        r'buy\s*now|shop\s*now|sign\s*up|subscribe|free\s*trial|'
        r'\%\s*off|\$\d+\s*off|\d+\%\s*off'
        r')\b', re.IGNORECASE
    )

    # ── 招聘/求职 ──
    JOB_PATTERNS = re.compile(
        r'('
        r'hiring|job opening|career|internship|remote\s*job|'
        r'apply now|position|salary|\$\d+k|'
        r'招聘|求职|找工作|投简历|面试|offer|'
        r'内推|实习|校招|社招|跳槽|薪资'
        r')', re.IGNORECASE
    )

    def is_chatter(self, text: str) -> dict:
        """
        判断文本是否为非工具闲聊
        返回: {is_chatter, category, matched_patterns}
        """
        if not text:
            return {"is_chatter": True, "category": "empty", "matched": []}

        checks = [
            ("news", self.NEWS_PATTERNS),
            ("entertainment", self.ENTERTAINMENT_PATTERNS),
            ("chatter", self.CHATTER_PATTERNS),
            ("ad_cn", self.AD_PATTERNS_CN),
            ("ad_en", self.AD_PATTERNS_EN),
            ("job", self.JOB_PATTERNS),
        ]

        for category, pattern in checks:
            matches = pattern.findall(text)
            if matches:
                # 统一 ad 类别
                display_cat = "ad" if category.startswith("ad") else category
                return {
                    "is_chatter": True,
                    "category": display_cat,
                    "matched": matches[:3],
                }

        return {"is_chatter": False, "category": "ok", "matched": []}


# ═══════════════════════════════════════════════════════════════
# 🌊 高流量水源采集函数
# ═══════════════════════════════════════════════════════════════

def fetch_url(url, headers=None, timeout=15):
    """简单的 HTTP GET，返回文本"""
    if headers is None:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  ⚠️ Failed to fetch {url[:80]}: {e}")
        return None


# ═══════════════════════ 原有10水源 (保留) ═══════════════════

def scrape_producthunt():
    """从 ProductHunt 首页抓取热门产品名"""
    print("🔍 [1/25] Scraping ProductHunt...")
    html = fetch_url("https://www.producthunt.com/")
    if not html:
        return []
    patterns = [
        r'data-test="post-name"[^>]*>([^<]+)<',
        r'class="[^"]*postName[^"]*"[^>]*>([^<]+)<',
        r'"name":"([^"]+)"',
    ]
    products = []
    for pattern in patterns:
        matches = re.findall(pattern, html)
        for m in matches:
            name = m.strip()
            if name and len(name) > 2 and len(name) < 100 and name not in products:
                if not re.match(r'^[0-9\s\{\}\[\]\(\)\.\,\;\:\!\?\@\#\$\%\^\&\*\+\=]+$', name):
                    products.append(name)
    products = list(dict.fromkeys(products))[:20]
    print(f"  ✅ {len(products)} products")
    return products


def scrape_github_trending():
    """从 GitHub Trending 抓取热门仓库"""
    print("🔍 [2/25] Scraping GitHub Trending...")
    html = fetch_url("https://github.com/trending")
    if not html:
        return []
    repos = []
    matches = re.findall(r'href="/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"', html)
    seen = set()
    skip_patterns = ["explore", "topics", "trending", "collections", "events",
                    "sponsors", "settings", "notifications", "login", "signup",
                    "marketplace", "features", "security", "pricing"]
    for m in matches:
        parts = m.split("/")
        if len(parts) == 2:
            owner, name = parts
            if owner.lower() not in skip_patterns and name.lower() not in skip_patterns:
                if '"' not in m and '<' not in m and '>' not in m and m not in seen:
                    seen.add(m)
                    repos.append(m)
    repos = repos[:20]
    descriptions = []
    desc_match = re.findall(r'<p class="col-9 color-fg-muted my-1 pr-4">\s*([^<]+)\s*</p>', html)
    if desc_match:
        descriptions = desc_match
    result = []
    for i, repo in enumerate(repos):
        item = {"repo": repo, "url": f"https://github.com/{repo}"}
        if i < len(descriptions):
            item["description"] = descriptions[i]
        result.append(item)
    print(f"  ✅ {len(result)} repos")
    return result


def analyze_search_logs(api_base="https://efficient-reverence-production-1b4a.up.railway.app"):
    """从后端获取搜索日志"""
    print("🔍 [3/25] Analyzing search logs...")
    try:
        data = fetch_url(f"{api_base}/v1/search-log")
        if data:
            log = json.loads(data)
            top = log.get("top_queries", [])
            print(f"  ✅ {len(top)} queries")
            return [{"query": q, "count": c} for q, c in top]
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
    return []


def fetch_pain_points():
    """
    🧠 最高优先级水源: 读取 AI 商机捕手收集的用户真实痛点
    
    这些是用户在网站上搜索不到工具后，通过 AI 机器人提交的真实需求。
    优先级最高，绕过闲聊过滤器，直接进入工具特质识别 + 门禁质检。
    """
    pain_path = os.path.join(REPORT_DIR, "pain_points.json")
    if not os.path.exists(pain_path):
        return []
    
    try:
        with open(pain_path, "r", encoding="utf-8") as f:
            points = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []
    
    # 只取 pending 状态的，避免重复处理
    pending = [p for p in points if p.get("status") == "pending"]
    
    results = []
    for p in pending:
        entry = {
            "query": p.get("query", ""),
            "pain_summary": p.get("pain_summary", ""),
            "tool_idea": p.get("tool_idea", ""),
            "category": p.get("category", ""),
            "source": p.get("source", "pain-point"),
            "priority": p.get("priority", "highest"),
            "collected_at": p.get("collected_at", ""),
        }
        results.append(entry)
    
    # 标记为已处理
    for p in points:
        if p.get("status") == "pending":
            p["status"] = "radar_processed"
    try:
        with open(pain_path, "w", encoding="utf-8") as f:
            json.dump(points, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"⚠️ 无法写入需求数据: {pain_path} — {e}")
    
    return results


def fetch_v2ex_hot():
    """从 V2EX API 抓取热门话题"""
    print("🔍 [4/25] Fetching V2EX...")
    try:
        data = fetch_url("https://www.v2ex.com/api/topics/hot.json")
        if not data:
            return []
        topics = json.loads(data)
        titles = [t["title"] for t in topics[:20] if t.get("title") and len(t["title"]) > 3]
        print(f"  ✅ {len(titles)} topics")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_stackoverflow_hot():
    """从 Stack Overflow 热门问题 RSS 抓取"""
    print("🔍 [5/25] Fetching Stack Overflow...")
    try:
        import xml.etree.ElementTree as ET
        # 修正: 用 tagnames 参数 (非 tagged)
        data = fetch_url("https://stackoverflow.com/feeds/tag?tagnames=python&sort=votes")
        if not data:
            return []
        root = ET.fromstring(data)
        ns = {"": "http://www.w3.org/2005/Atom"}
        titles = []
        for entry in root.findall(".//entry", ns)[:15]:
            title_el = entry.find("title", ns)
            if title_el is not None and title_el.text:
                title = title_el.text.strip()
                if title and len(title) > 5:
                    titles.append(title)
        print(f"  ✅ {len(titles)} questions")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


REDDIT_SUBREDDITS = [
    ("automation", "https://www.reddit.com/r/automation/hot.json?limit=15"),
    ("productivity", "https://www.reddit.com/r/productivity/hot.json?limit=15"),
    ("SideProject", "https://www.reddit.com/r/SideProject/hot.json?limit=15"),
    ("Python", "https://www.reddit.com/r/Python/hot.json?limit=15"),
    ("selfhosted", "https://www.reddit.com/r/selfhosted/hot.json?limit=15"),
]

def fetch_reddit_trending():
    """从 Reddit 多个效率/工具相关 subreddit 抓取"""
    print("🔍 [6/25] Fetching Reddit...")
    reddit_headers = {"User-Agent": "MintShovels/2.0 (tool-discovery-bot; contact@mintshovels.com)"}
    all_titles = []
    for sub_name, url in REDDIT_SUBREDDITS:
        try:
            data = fetch_url(url, headers=reddit_headers)
            if not data:
                continue
            listing = json.loads(data)
            children = listing.get("data", {}).get("children", [])
            for child in children[:10]:
                post = child.get("data", {})
                title = post.get("title", "")
                if title and not title.startswith("[") and len(title) > 10:
                    all_titles.append(title)
        except Exception as e:
            print(f"  ⚠️ r/{sub_name}: {e}")
    titles = list(dict.fromkeys(all_titles))[:30]
    print(f"  ✅ {len(titles)} posts")
    return titles


def fetch_google_trends():
    """从 Google Trends RSS 抓取"""
    print("🔍 [7/25] Fetching Google Trends...")
    try:
        import xml.etree.ElementTree as ET
        data = fetch_url("https://trends.google.com/trending/rss?geo=US")
        if not data:
            return []
        root = ET.fromstring(data)
        titles = [item.find("title").text.strip() for item in root.findall(".//item")[:20]
                  if item.find("title") is not None and item.find("title").text]
        print(f"  ✅ {len(titles)} items")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_wikipedia_trending():
    """从 Wikipedia 抓取高频词条"""
    print("🔍 [8/25] Fetching Wikipedia...")
    try:
        data = fetch_url("https://en.wikipedia.org/w/api.php?action=query&list=recentchanges&rcnamespace=0&rclimit=20&format=json")
        if not data:
            return []
        result = json.loads(data)
        pages = result.get("query", {}).get("recentchanges", [])
        titles = [p["title"] for p in pages if "title" in p and len(p["title"]) > 3]
        print(f"  ✅ {len(titles)} pages")
        return titles[:20]
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_huggingface_trending():
    """从 HuggingFace 抓取热门模型"""
    print("🔍 [9/25] Fetching HuggingFace...")
    try:
        data = fetch_url("https://huggingface.co/api/models?sort=downloads&direction=-1&limit=20")
        if not data:
            return []
        models = json.loads(data)
        titles = []
        for m in models[:20]:
            model_id = m.get("id", "")
            pipeline_tag = m.get("pipeline_tag", "")
            if model_id:
                parts = model_id.split("/")
                if len(parts) >= 2:
                    titles.append(parts[1])
                    titles.append(f"{pipeline_tag} {parts[1]}" if pipeline_tag else parts[1])
        print(f"  ✅ {len(titles)} models")
        return titles[:30]
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_baidu_hot():
    """从百度热搜抓取"""
    print("🔍 [10/25] Fetching Baidu hot...")
    try:
        html = fetch_url("https://top.baidu.com/board?tab=realtime")
        if not html:
            return []
        matches = re.findall(r'"word":"([^"]+)"', html)
        titles = list(dict.fromkeys(matches))[:20]
        print(f"  ✅ {len(titles)} hot words")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


# ═══════════════════════ 🔥 新增: 无需 API 的免费高价值水源 ═══════════════════

def scrape_hn_show():
    """🔥 Show HN — 用户展示自己做的工具/产品 (Algolia 免费 API)"""
    print("🔍 [26] Scraping Show HN (Algolia)...")
    try:
        data = fetch_url("https://hn.algolia.com/api/v1/search_by_date?query=Show+HN&tags=story&hitsPerPage=20")
        if not data:
            return []
        result = json.loads(data)
        items = []
        for hit in result.get("hits", [])[:20]:
            title = hit.get("title", "")
            pts = hit.get("points", 0)
            url = hit.get("url", "")
            if title and "Show HN" in title:
                # 去掉 "Show HN: " 前缀
                clean = title.replace("Show HN:", "").replace("Show HN", "").strip(": ")
                if clean:
                    items.append(f"{clean} — featured on Hacker News (🔥{pts}pts)")
        print(f"  ✅ {len(items)} Show HN posts")
        return items
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def scrape_hn_ask_tools():
    """🔥 Ask HN — 搜索 'best tool' / 'recommend' 等工具需求问答 (Algolia 免费 API)"""
    print("🔍 [27] Scraping HN tool requests...")
    results = []
    queries = [
        "best+tool", "recommend+tool", "what+tool+do+you+use",
        "looking+for+tool", "alternatives+to", "free+online+tool"
    ]
    seen = set()
    for q in queries:
        try:
            data = fetch_url(f"https://hn.algolia.com/api/v1/search_by_date?query={q}&tags=story&hitsPerPage=8")
            if not data:
                continue
            result = json.loads(data)
            for hit in result.get("hits", [])[:8]:
                title = hit.get("title", "")
                pts = hit.get("points", 0)
                if title and len(title) > 10 and title not in seen:
                    seen.add(title)
                    # 加工具语义标签
                    results.append(f"{title} — user asking for tool recommendation (🔥{pts}pts)")
        except Exception:
            continue
    results = results[:30]
    print(f"  ✅ {len(results)} tool-related Ask HN posts")
    return results


def scrape_npm_registry():
    """🔥 npm 注册中心搜索 — 按流行度搜包 (免费 API, 无需 Key)"""
    print("🔍 [28] Scraping npm registry search...")
    results = []
    queries = ["generator", "converter", "formatter", "scraper", "downloader"]
    seen = set()
    for q in queries:
        try:
            data = fetch_url(f"https://registry.npmjs.org/-/v1/search?text={q}+tool&size=10&popularity=1.0")
            if not data:
                continue
            result = json.loads(data)
            for obj in result.get("objects", [])[:10]:
                pkg = obj.get("package", {})
                name = pkg.get("name", "")
                desc = pkg.get("description", "")
                if name and name not in seen and len(name) > 2:
                    seen.add(name)
                    combined = f"{name} — npm package: {desc}" if desc else f"{name} — npm package"
                    results.append(combined)
        except Exception:
            continue
    results = results[:30]
    print(f"  ✅ {len(results)} npm packages")
    return results


def scrape_github_topics():
    """🔥 GitHub Topics 页面 — 抓取热门技术主题名称 (关键词信号)"""
    print("🔍 [29] Scraping GitHub Topics...")
    try:
        html = fetch_url("https://github.com/topics")
        if not html:
            return []
        # 抓取 topic 名称
        topics = re.findall(r'data-ga-click="Topic,.*?"[^>]*>([^<]+)</', html)
        # 也抓 p-name 里的
        topics += re.findall(r'class="[^"]*topic[^"]*"[^>]*>([^<]+)<', html)
        # 还有 f3 lh-condensed 里的
        topics += re.findall(r'<p class="f3[^"]*"[^>]*>\s*([^<]+)\s*<', html)
        topics = list(set(t.strip().lower() for t in topics if len(t.strip()) > 2))
        # 格式化为信号: "github trending topic: xxx"
        results = [f"github trending topic: {t}" for t in topics[:25]]
        print(f"  ✅ {len(results)} topics")
        return results
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def scrape_hackernoon():
    """🔥 HackerNoon RSS — 技术博客，常涵盖新工具和开发者工具链"""
    print("🔍 [30] Fetching HackerNoon...")
    try:
        data = fetch_url("https://hackernoon.com/feed")
        if not data:
            return []
        titles = re.findall(r'<title>\s*<!\[CDATA\[([^\]]+)\]\]>\s*</title>', data)
        titles = [t for t in titles if len(t) > 10 and "HackerNoon" not in t][:20]
        print(f"  ✅ {len(titles)} articles")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def scrape_infoq():
    """🔥 InfoQ RSS — 技术新闻/工具/趋势 (免费 RSS)"""
    print("🔍 [31] Fetching InfoQ...")
    try:
        import xml.etree.ElementTree as ET
        data = fetch_url("https://feed.infoq.com/")
        if not data:
            return []
        root = ET.fromstring(data)
        titles = []
        for item in root.findall(".//item")[:20]:
            title_el = item.find("title")
            desc_el = item.find("description")
            if title_el is not None and title_el.text:
                title = title_el.text.strip()
                if desc_el is not None and desc_el.text:
                    title += " " + desc_el.text.strip()[:150]
                titles.append(title)
        print(f"  ✅ {len(titles)} articles")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []

def fetch_hacker_news():
    """Hacker News — 使用 Algolia 免费搜索 API (无需 API Key)"""
    print("🔍 [11/25] Fetching Hacker News (Algolia API)...")
    try:
        data = fetch_url("https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=25")
        if not data:
            return []
        result = json.loads(data)
        items = []
        for hit in result.get("hits", [])[:25]:
            title = hit.get("title", "")
            pts = hit.get("points", 0)
            comments = hit.get("num_comments", 0)
            if title:
                # 附带热度信息帮助分类器判断
                if pts > 50:
                    items.append(f"{title} 🔥{pts}pts 💬{comments}")
                else:
                    items.append(title)
        print(f"  ✅ {len(items)} items")
        return items
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_devto_trending():
    """Dev.to — 开发者社区热门文章 (RSS)"""
    print("🔍 [12/25] Fetching Dev.to...")
    try:
        data = fetch_url("https://dev.to/feed/tag/programming")
        if not data:
            return []
        # 简单正则提取 title
        titles = re.findall(r'<title>([^<]+)</title>', data)
        # 过滤掉频道名本身
        titles = [t for t in titles if t != "DEV Community" and len(t) > 5][:20]
        print(f"  ✅ {len(titles)} articles")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_lobsters():
    """Lobsters — 硬核技术社区 (RSS)"""
    print("🔍 [13/25] Fetching Lobsters...")
    try:
        data = fetch_url("https://lobste.rs/rss")
        if not data:
            return []
        titles = re.findall(r'<title>([^<]+)</title>', data)
        titles = [t for t in titles if t != "Lobsters" and len(t) > 5][:20]
        print(f"  ✅ {len(titles)} items")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_zhihu_hot():
    """知乎热榜 — 中文最大问答社区"""
    print("🔍 [14/25] Fetching Zhihu hot...")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        data = fetch_url("https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=20", headers=headers)
        if not data:
            return []
        result = json.loads(data)
        titles = []
        for item in result.get("data", [])[:20]:
            target = item.get("target", {})
            title = target.get("title", "")
            if title:
                titles.append(title)
        print(f"  ✅ {len(titles)} hot topics")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_weibo_hot():
    """微博热搜 — 实时热搜榜"""
    print("🔍 [15/25] Fetching Weibo hot...")
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        data = fetch_url("https://weibo.com/ajax/side/hotSearch", headers=headers)
        if not data:
            return []
        result = json.loads(data)
        titles = []
        for item in result.get("data", {}).get("realtime", [])[:20]:
            word = item.get("word", "")
            if word and len(word) > 1:
                titles.append(word)
        print(f"  ✅ {len(titles)} hot items")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_36kr():
    """36氪 — 科技创投媒体 (RSS)"""
    print("🔍 [16/25] Fetching 36Kr...")
    try:
        data = fetch_url("https://36kr.com/feed")
        if not data:
            return []
        titles = re.findall(r'<title>\s*<!\[CDATA\[([^\]]+)\]\]>\s*</title>', data)
        titles = [t for t in titles if t != "36氪" and len(t) > 5][:20]
        print(f"  ✅ {len(titles)} articles")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_sspai():
    """少数派 — 数字生活效率社区 (RSS)"""
    print("🔍 [17/25] Fetching Sspai...")
    try:
        data = fetch_url("https://sspai.com/feed")
        if not data:
            return []
        titles = re.findall(r'<title>\s*<!\[CDATA\[([^\]]+)\]\]>\s*</title>', data)
        titles = [t for t in titles if t != "少数派" and len(t) > 5][:20]
        print(f"  ✅ {len(titles)} articles")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_npm_trending():
    """npm — JavaScript 包注册中心热门 (RSS)"""
    print("🔍 [18/25] Fetching npm trending...")
    try:
        data = fetch_url("https://www.npmjs.com/feed")
        if not data:
            return []
        titles = re.findall(r'<title>([^<]+)</title>', data)
        titles = [t for t in titles if len(t) > 5 and t != "npm" and "feed" not in t.lower()][:20]
        print(f"  ✅ {len(titles)} packages")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_pypi_trending():
    """PyPI — Python 包索引热门 (RSS)"""
    print("🔍 [19/25] Fetching PyPI trending...")
    try:
        data = fetch_url("https://pypi.org/rss/packages.xml")
        if not data:
            return []
        titles = re.findall(r'<title>([^<]+)</title>', data)
        titles = [t for t in titles if len(t) > 5 and "PyPI" not in t][:20]
        print(f"  ✅ {len(titles)} packages")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_dribbble_popular():
    """Dribbble — 设计社区热门 (RSS)"""
    print("🔍 [20/25] Fetching Dribbble...")
    try:
        data = fetch_url("https://dribbble.com/shots/popular.rss")
        if not data:
            return []
        titles = re.findall(r'<title>([^<]+)</title>', data)
        titles = [t for t in titles if len(t) > 5 and "Dribbble" not in t][:20]
        print(f"  ✅ {len(titles)} shots")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_arxiv_ai():
    """arXiv — AI/ML 最新论文"""
    print("🔍 [21/25] Fetching arXiv cs.AI...")
    try:
        import xml.etree.ElementTree as ET
        data = fetch_url("http://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending&max_results=15")
        if not data:
            return []
        root = ET.fromstring(data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        titles = []
        for entry in root.findall(".//atom:entry", ns)[:15]:
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            if title_el is not None and title_el.text:
                title = title_el.text.strip().replace("\n", " ")
                if summary_el is not None and summary_el.text:
                    title += " " + summary_el.text.strip()[:200]
                titles.append(title)
        print(f"  ✅ {len(titles)} papers")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_paperswithcode():
    """Papers With Code — 最新论文+代码"""
    print("🔍 [22/25] Fetching Papers With Code...")
    try:
        data = fetch_url("https://paperswithcode.com/api/v1/papers/?ordering=-paper_published&items_per_page=15")
        if not data:
            return []
        result = json.loads(data)
        titles = []
        for paper in result.get("results", [])[:15]:
            title = paper.get("title", "")
            abstract = paper.get("abstract", "")
            if title:
                titles.append(f"{title} {abstract[:200]}" if abstract else title)
        print(f"  ✅ {len(titles)} papers")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_quora_tech():
    """Quora — 技术话题热门问答 (RSS)"""
    print("🔍 [23/25] Fetching Quora tech...")
    try:
        data = fetch_url("https://www.quora.com/rss/topic/Computer-Programming")
        if not data:
            return []
        titles = re.findall(r'<title>([^<]+)</title>', data)
        titles = [t for t in titles if len(t) > 10 and "Quora" not in t][:20]
        print(f"  ✅ {len(titles)} questions")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_bing_trends():
    """Bing 搜索趋势"""
    print("🔍 [24/25] Fetching Bing trends...")
    try:
        import xml.etree.ElementTree as ET
        data = fetch_url("https://www.bing.com/HPBeso")
        if not data:
            return []
        # Bing trends 可能返回 HTML
        matches = re.findall(r'title="([^"]+)"', data)
        matches = [m for m in matches if len(m) > 3][:20]
        if matches:
            print(f"  ✅ {len(matches)} trends")
            return matches
        # 回退方案
        return []
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


def fetch_medium_tech():
    """Medium — 技术标签热门文章"""
    print("🔍 [25/25] Fetching Medium tech...")
    try:
        data = fetch_url("https://medium.com/feed/tag/programming")
        if not data:
            return []
        titles = re.findall(r'<title>([^<]+)</title>', data)
        titles = [t for t in titles if len(t) > 5][:20]
        print(f"  ✅ {len(titles)} articles")
        return titles
    except Exception as e:
        print(f"  ⚠️ Failed: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
# 🔑 关键词 → 工具建议映射 (保留原有 + 扩展)
# ═══════════════════════════════════════════════════════════════

KEYWORD_TOOL_MAP = {
    # 媒体创作
    "video": ("media", "video", "tool", "Video Converter", "视频格式转换器"),
    "convert": ("media", "video", "tool", "Format Converter", "万能格式转换器"),
    "gif": ("media", "image", "tool", "GIF Maker", "GIF动图制作器"),
    "screenshot": ("media", "image", "tool", "Screenshot Tool", "网页截图工具"),
    "audio": ("media", "audio", "tool", "Audio Editor", "音频编辑器"),
    "mp3": ("media", "audio", "tool", "MP3 Cutter", "MP3剪辑器"),
    "subtitle": ("media", "video", "tool", "Subtitle Generator", "字幕生成器"),
    "image": ("media", "image", "tool", "Image Tool", "图片工具"),
    "photo": ("media", "image", "tool", "Photo Editor", "照片编辑器"),
    "crop": ("media", "image", "tool", "Image Cropper", "图片裁剪器"),
    "resize": ("media", "image", "tool", "Image Resizer", "图片缩放器"),
    "watermark": ("media", "image", "tool", "Watermark Tool", "水印工具"),
    "svg": ("media", "image", "tool", "SVG Editor", "SVG编辑器"),
    "webp": ("media", "image", "tool", "WebP Converter", "WebP转换器"),

    # 金融
    "crypto": ("finance", "crypto", "tool", "Crypto Price Tracker", "加密货币行情追踪"),
    "wallet": ("finance", "wallet", "tool", "Wallet Balance Checker", "钱包余额查询"),
    "gas": ("finance", "defi", "tool", "Gas Fee Tracker", "Gas费追踪器"),
    "token": ("finance", "defi", "tool", "Token Analyzer", "代币分析器"),
    "currency": ("finance", "currency", "tool", "Currency Converter", "货币转换器"),
    "exchange rate": ("finance", "currency", "tool", "Exchange Rate", "汇率换算"),
    "loan": ("finance", "calc", "tool", "Loan Calculator", "贷款计算器"),
    "mortgage": ("finance", "calc", "tool", "Mortgage Calculator", "按揭计算器"),

    # 办公效率
    "pdf": ("productivity", "office", "tool", "PDF Editor", "PDF编辑器"),
    "merge": ("productivity", "office", "tool", "File Merger", "文件合并器"),
    "text": ("productivity", "text", "tool", "Text Tools", "文本工具箱"),
    "markdown": ("productivity", "text", "tool", "Markdown Editor", "Markdown编辑器"),
    "excel": ("productivity", "office", "tool", "Excel Tools", "Excel工具箱"),
    "csv": ("productivity", "office", "tool", "CSV Editor", "CSV编辑器"),
    "translate": ("productivity", "text", "tool", "Translator", "在线翻译器"),
    "qr": ("productivity", "misc", "tool", "QR Code Generator", "二维码生成器"),
    "barcode": ("productivity", "misc", "tool", "Barcode Generator", "条形码生成器"),
    "note": ("productivity", "text", "tool", "Note Taker", "笔记工具"),
    "todo": ("productivity", "misc", "tool", "Todo List", "待办清单"),
    "word": ("productivity", "office", "tool", "Word Counter", "字数统计器"),
    "diff": ("productivity", "text", "tool", "Diff Checker", "文本对比器"),

    # 开发工具
    "json": ("dev", "code", "tool", "JSON Formatter", "JSON格式化"),
    "base64": ("dev", "encode", "tool", "Base64 Codec", "Base64编解码"),
    "regex": ("dev", "code", "tool", "Regex Tester", "正则测试器"),
    "api": ("dev", "api", "tool", "API Tester", "API测试工具"),
    "curl": ("dev", "api", "tool", "cURL Converter", "cURL转换器"),
    "hash": ("dev", "encode", "tool", "Hash Generator", "哈希生成器"),
    "uuid": ("dev", "code", "tool", "UUID Generator", "UUID生成器"),
    "color": ("dev", "code", "tool", "Color Picker", "取色器"),
    "sql": ("dev", "code", "tool", "SQL Formatter", "SQL格式化"),
    "html": ("dev", "code", "tool", "HTML Preview", "HTML预览器"),
    "css": ("dev", "code", "tool", "CSS Tools", "CSS工具箱"),
    "minify": ("dev", "code", "tool", "Code Minifier", "代码压缩器"),
    "beautify": ("dev", "code", "tool", "Code Beautifier", "代码美化器"),
    "lorem ipsum": ("dev", "code", "tool", "Lorem Ipsum Generator", "占位文本生成"),
    "placeholder": ("dev", "code", "tool", "Placeholder Image", "占位图生成"),
    "mock": ("dev", "code", "tool", "Mock Data Generator", "模拟数据生成"),

    # 游戏娱乐
    "random": ("gaming", "fun", "tool", "Random Generator", "随机生成器"),
    "dice": ("gaming", "game", "tool", "Dice Roller", "骰子工具"),
    "name": ("gaming", "fun", "tool", "Name Generator", "名字生成器"),
    "game": ("gaming", "game", "tool", "Game Tool", "游戏工具"),
    "spin": ("gaming", "fun", "tool", "Wheel Spinner", "幸运转盘"),
    "pick": ("gaming", "fun", "tool", "Random Picker", "随机选择器"),

    # AI 工具
    "ai": ("ai", "ai-chat", "tool", "AI Assistant", "AI助手"),
    "chatgpt": ("ai", "ai-chat", "tool", "Prompt Helper", "提示词助手"),
    "prompt": ("ai", "ai-chat", "tool", "Prompt Optimizer", "提示词优化"),
    "generate": ("ai", "ai-image", "tool", "AI Generator", "AI生成器"),
    "summarize": ("ai", "ai-writing", "tool", "AI Summarizer", "AI摘要"),
    "llm": ("ai", "ai-chat", "tool", "LLM Tool", "大模型工具"),
    "embedding": ("ai", "ai-data", "tool", "Embedding Tool", "向量嵌入工具"),

    # 通用
    "compress": ("media", "image", "tool", "Compressor", "压缩工具"),
    "download": ("media", "video", "tool", "Downloader", "下载器"),
    "calculator": ("misc", "misc", "tool", "Calculator", "计算器"),
    "timer": ("misc", "misc", "tool", "Timer", "计时器"),
    "password": ("dev", "encode", "tool", "Password Generator", "密码生成器"),
    "url": ("dev", "code", "tool", "URL Encoder", "URL编解码"),
    "check": ("dev", "code", "tool", "Checker Tool", "检测工具"),
    "format": ("dev", "code", "tool", "Formatter", "格式化工具"),
    "generator": ("misc", "misc", "tool", "Generator", "生成器"),
    "converter": ("media", "video", "tool", "Converter", "格式转换"),
    "editor": ("productivity", "text", "tool", "Editor", "编辑器"),
    "viewer": ("misc", "misc", "tool", "Viewer", "查看器"),
    "encoder": ("dev", "encode", "tool", "Encoder", "编码器"),
    "decoder": ("dev", "encode", "tool", "Decoder", "解码器"),
    "validator": ("dev", "code", "tool", "Validator", "验证器"),
    
    # 🆕 v2.1 新水源可能捕获的关键词
    "scraper": ("dev", "scraping", "tool", "Web Scraper", "网页抓取器"),
    "scrap": ("dev", "scraping", "tool", "Web Scraper", "网页抓取器"),
    "crawl": ("dev", "scraping", "tool", "Web Crawler", "网页爬虫"),
    "boilerplate": ("dev", "code", "tool", "Boilerplate Generator", "模板生成器"),
    "dashboard": ("productivity", "data", "tool", "Dashboard Builder", "仪表盘构建器"),
    "monitor": ("dev", "devops", "tool", "Site Monitor", "站点监控器"),
    "track": ("productivity", "tracking", "tool", "Tracker Tool", "追踪工具"),
    "notify": ("productivity", "notification", "tool", "Notification Tool", "通知工具"),
    "backup": ("dev", "devops", "tool", "Backup Tool", "备份工具"),
    "sync": ("productivity", "sync", "tool", "Sync Tool", "同步工具"),
    "deploy": ("dev", "devops", "tool", "Deploy Tool", "部署工具"),
    "optimize": ("dev", "perf", "tool", "Optimizer", "优化工具"),
    "benchmark": ("dev", "perf", "tool", "Benchmark Tool", "基准测试工具"),
    "schedule": ("productivity", "calendar", "tool", "Scheduler", "排程工具"),
    "reminder": ("productivity", "calendar", "tool", "Reminder Tool", "提醒工具"),
    "clipboard": ("productivity", "text", "tool", "Clipboard Manager", "剪贴板管理"),
    "snippet": ("dev", "code", "tool", "Code Snippet Manager", "代码片段管理"),
    "search": ("productivity", "search", "tool", "Search Tool", "搜索工具"),
    "filter": ("productivity", "data", "tool", "Data Filter", "数据筛选器"),
    "sort": ("productivity", "data", "tool", "Sorter Tool", "排序工具"),
    "extract": ("dev", "data", "tool", "Data Extractor", "数据提取器"),
    "rename": ("productivity", "file", "tool", "Batch Renamer", "批量改名器"),
    "watermark": ("media", "image", "tool", "Watermark Tool", "水印工具"),
    "thumbnail": ("media", "image", "tool", "Thumbnail Generator", "缩略图生成"),
    "screenshot": ("media", "image", "tool", "Screenshot Tool", "截图工具"),
    "ocr": ("ai", "ai-vision", "tool", "OCR Tool", "文字识别工具"),
    "tts": ("ai", "ai-audio", "tool", "Text-to-Speech", "文字转语音"),
    "speech": ("ai", "ai-audio", "tool", "Speech-to-Text", "语音转文字"),
    "diff": ("dev", "code", "tool", "Diff Viewer", "差异对比器"),
    "merge": ("dev", "code", "tool", "Merge Tool", "合并工具"),
    "compare": ("productivity", "text", "tool", "Compare Tool", "对比工具"),
    "split": ("productivity", "file", "tool", "File Splitter", "文件分割器"),
    "extract": ("dev", "data", "tool", "Extractor", "提取器"),
    "parser": ("dev", "code", "tool", "Parser", "解析器"),
    "preview": ("productivity", "file", "tool", "File Previewer", "文件预览器"),
    "render": ("media", "graphics", "tool", "Renderer", "渲染器"),
    "export": ("productivity", "office", "tool", "Exporter", "导出工具"),
    "import": ("productivity", "office", "tool", "Importer", "导入工具"),
    "migrate": ("dev", "database", "tool", "Migration Tool", "迁移工具"),
    "seed": ("dev", "database", "tool", "Seed Data Generator", "种子数据生成"),
    "fixture": ("dev", "database", "tool", "Test Fixture Generator", "测试夹具生成"),
    "mock": ("dev", "testing", "tool", "Mock Generator", "模拟数据生成"),
    "stub": ("dev", "testing", "tool", "Stub Generator", "桩代码生成"),
    "proxy": ("dev", "network", "tool", "Proxy Tool", "代理工具"),
    "tunnel": ("dev", "network", "tool", "Tunnel Tool", "隧道工具"),
    "dns": ("dev", "network", "tool", "DNS Tool", "DNS工具"),
    "cdn": ("dev", "network", "tool", "CDN Tool", "CDN工具"),
    "cache": ("dev", "perf", "tool", "Cache Manager", "缓存管理"),
    "queue": ("dev", "message", "tool", "Queue Manager", "队列管理"),
    "log": ("dev", "devops", "tool", "Log Viewer", "日志查看器"),
    "alert": ("dev", "devops", "tool", "Alert Manager", "告警管理"),
    "icon": ("media", "graphics", "tool", "Icon Generator", "图标生成器"),
    "font": ("media", "typography", "tool", "Font Tool", "字体工具"),
    "palette": ("media", "design", "tool", "Color Palette Generator", "配色生成器"),
    "gradient": ("media", "design", "tool", "Gradient Generator", "渐变生成器"),
    "layout": ("media", "design", "tool", "Layout Builder", "布局构建器"),
    "template": ("productivity", "office", "tool", "Template Builder", "模板构建器"),
    "form": ("dev", "web", "tool", "Form Builder", "表单构建器"),
    "survey": ("productivity", "data", "tool", "Survey Builder", "问卷构建器"),
    "poll": ("productivity", "data", "tool", "Poll Creator", "投票创建器"),
    "quiz": ("productivity", "education", "tool", "Quiz Generator", "测验生成器"),
    "flashcard": ("productivity", "education", "tool", "Flashcard Maker", "闪卡制作"),
    "mindmap": ("productivity", "education", "tool", "Mind Map Tool", "思维导图"),
    "flowchart": ("productivity", "diagram", "tool", "Flowchart Maker", "流程图制作"),
    "diagram": ("productivity", "diagram", "tool", "Diagram Tool", "图表工具"),
    "chart": ("productivity", "data", "tool", "Chart Generator", "图表生成器"),
    "graph": ("productivity", "data", "tool", "Graph Tool", "图形工具"),
    "whitepaper": ("productivity", "office", "tool", "Document Generator", "文档生成器"),
    "invoice": ("finance", "billing", "tool", "Invoice Generator", "发票生成器"),
    "receipt": ("finance", "billing", "tool", "Receipt Generator", "收据生成器"),
    "budget": ("finance", "personal", "tool", "Budget Planner", "预算规划器"),
    "expense": ("finance", "personal", "tool", "Expense Tracker", "花销追踪"),
    "tax": ("finance", "tax", "tool", "Tax Calculator", "税务计算器"),
    "tip": ("finance", "personal", "tool", "Tip Calculator", "小费计算器"),
    "split bill": ("finance", "personal", "tool", "Bill Splitter", "账单分摊"),
    "unit": ("misc", "misc", "tool", "Unit Converter", "单位换算"),
    "weather": ("misc", "weather", "tool", "Weather Tool", "天气工具"),
    "timezone": ("productivity", "time", "tool", "Timezone Converter", "时区转换"),
    "stopwatch": ("misc", "misc", "tool", "Stopwatch", "秒表"),
    "pomodoro": ("productivity", "time", "tool", "Pomodoro Timer", "番茄钟"),
    "habit": ("productivity", "personal", "tool", "Habit Tracker", "习惯追踪"),
    "journal": ("productivity", "personal", "tool", "Journal App", "日记工具"),
    "planner": ("productivity", "calendar", "tool", "Planner Tool", "规划工具"),
}


def suggest_tools_from_keywords(keywords):
    """根据关键词列表，生成工具建议"""
    suggestions = []
    seen_names = set()
    for kw in keywords:
        kw_lower = kw.lower()
        for key, (cat, subcat, ttype, name_en, name_zh) in KEYWORD_TOOL_MAP.items():
            if key in kw_lower and name_en not in seen_names:
                suggestions.append({
                    "keyword": kw,
                    "matched": key,
                    "category": cat,
                    "subcat": subcat,
                    "type": ttype,
                    "name": name_en,
                    "name_zh": name_zh,
                })
                seen_names.add(name_en)
    return suggestions


# ═══════════════════════════════════════════════════════════════
# 🌊 扩展水源配置清单 (供审查)
# ═══════════════════════════════════════════════════════════════

API_SOURCES = {
    # 🔥 v2.1: 只保留免费无需API Key的水源
    "开发者问答枢纽": {
        "github_trending": "https://github.com/trending",
        "stackoverflow_rss": "https://stackoverflow.com/feeds/tag?tagged=python&sort=votes",
        "v2ex_api": "https://www.v2ex.com/api/topics/hot.json",
        "devto_rss": "https://dev.to/feed/tag/programming",
        "lobsters_rss": "https://lobste.rs/rss",
    },
    "海外效率创客社区": {
        "producthunt": "https://www.producthunt.com/",
        "hacker_news_algolia": "https://hn.algolia.com/api/v1/search?tags=front_page",
        "hn_show_algolia": "https://hn.algolia.com/api/v1/search_by_date?query=Show+HN",
        "hn_ask_tools_algolia": "https://hn.algolia.com/api/v1/search_by_date?query=best+tool",
        "hackernoon_rss": "https://hackernoon.com/feed",
        "infoq_rss": "https://feed.infoq.com/",
    },
    "全球搜索趋势": {
        "google_trends_rss": "https://trends.google.com/trending/rss?geo=US",
        "baidu_hot": "https://top.baidu.com/board?tab=realtime",
    },
    "维基百科与AI趋势": {
        "wikipedia_api": "https://en.wikipedia.org/w/api.php?action=query&list=recentchanges...",
        "huggingface_api": "https://huggingface.co/api/models?sort=downloads...",
        "arxiv_ai": "http://export.arxiv.org/api/query?search_query=cat:cs.AI...",
        "paperswithcode": "https://paperswithcode.com/api/v1/papers/...",
    },
    "包注册+技术主题": {
        "npm_registry_search": "https://registry.npmjs.org/-/v1/search?...",
        "github_topics": "https://github.com/topics",
    },
    # 🚫 已退役 (v2.0中已挂, v2.1移除调用):
    # - Reddit 5 subs (403 Blocked)
    # - 知乎热榜 (401 需登录)
    # - 微博热搜 (403)
    # - Quora RSS (403)
    # - 36Kr RSS (无数据)
    # - 少数派 RSS (无数据)
    # - npm RSS (403)
    # - PyPI RSS (无数据)
    # - Dribbble RSS (不稳定)
    # - Bing Trends (无数据)
    # - Medium RSS (基本无数据)
    "搜索日志": {
        "search_log_api": "https://efficient-reverence-production-1b4a.up.railway.app/v1/search-log",
    },
}


# ═══════════════════════════════════════════════════════════════
# 📡 主流程 — 25+水源并行抓取 + 特质识别 + 闲聊过滤
# ═══════════════════════════════════════════════════════════════

def main():
    recognizer = ToolTraitRecognizer()
    chatter_filter = ChatterFilter()

    # 🔥 v2.1: 只保留已验证可用的免费水源 (无需 API Key)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "radar_version": "2.1",
        "sources": {
            # 开发者问答枢纽
            "github_trending": [], "stackoverflow": [], "v2ex": [],
            "devto": [], "lobsters": [],
            # 海外效率创客社区
            "producthunt": [], "hacker_news": [],
            "hn_show": [],  # 🆕 Show HN — 用户展示工具
            "hn_ask_tools": [],  # 🆕 Ask HN 工具需求
            "hackernoon": [],  # 🆕 HackerNoon RSS
            "infoq": [],  # 🆕 InfoQ RSS
            # 全球搜索趋势
            "google_trends": [], "baidu": [],
            # 维基百科与AI趋势
            "wikipedia": [], "huggingface": [], "arxiv": [],
            "paperswithcode": [],
            # 包注册中心
            "npm_registry": [],  # 🆕 npm 搜索API (替代RSS)
            # 技术主题
            "github_topics": [],  # 🆕 GitHub Topics 热门主题
            # 搜索日志 + AI商机捕手
            "search_log_top": [], "pain_points": [],
            # 🚫 已移除 (需API/登录/已失效):
            # Reddit(403)/知乎(401)/微博(403)/Quora(403)/Medium(挂)
            # 36Kr(0)/少数派(0)/npm RSS(403)/PyPI(0)/Dribbble(挂)/Bing(挂)
        },
        "tool_suggestions": [],
        "all_keywords": [],
        "filter_stats": {},
        "trait_analysis": {
            "total_captured": 0, "chatter_blocked": 0,
            "tool_signals_found": 0, "chatter_samples": [],
            "tool_signal_samples": [],
        },
    }

    all_raw_signals = []

    # ═══════════════════ 水系1: 开发者问答枢纽 (5源) ═══════════════════
    print("\n🌐 水系1: 开发者问答枢纽")
    
    gh_repos = scrape_github_trending()
    report["sources"]["github_trending"] = gh_repos
    for repo in gh_repos:
        parts = repo["repo"].split("/")
        if len(parts) == 2:
            owner, name = parts
            desc = repo.get("description", "")
            combined = f"{name} — {desc}" if desc else name
            all_raw_signals.append(combined)
            if desc and len(desc) > 5:
                all_raw_signals.append(desc)

    so_titles = fetch_stackoverflow_hot()
    report["sources"]["stackoverflow"] = so_titles
    all_raw_signals.extend(so_titles)

    v2ex_titles = fetch_v2ex_hot()
    report["sources"]["v2ex"] = v2ex_titles
    all_raw_signals.extend(v2ex_titles)

    devto_items = fetch_devto_trending()
    report["sources"]["devto"] = devto_items
    all_raw_signals.extend(devto_items)

    lobsters_items = fetch_lobsters()
    report["sources"]["lobsters"] = lobsters_items
    all_raw_signals.extend(lobsters_items)

    # ═══════════════════ 水系2: 海外效率创客社区 (6源) ═══════════════════
    print("\n💡 水系2: 海外效率创客社区")
    
    ph_products = scrape_producthunt()
    report["sources"]["producthunt"] = ph_products
    for p in ph_products:
        all_raw_signals.append(f"{p} — tool from ProductHunt")

    hn_items = fetch_hacker_news()
    report["sources"]["hacker_news"] = hn_items
    all_raw_signals.extend(hn_items)

    hn_show = scrape_hn_show()
    report["sources"]["hn_show"] = hn_show
    all_raw_signals.extend(hn_show)

    hn_ask = scrape_hn_ask_tools()
    report["sources"]["hn_ask_tools"] = hn_ask
    all_raw_signals.extend(hn_ask)

    hackernoon_items = scrape_hackernoon()
    report["sources"]["hackernoon"] = hackernoon_items
    all_raw_signals.extend(hackernoon_items)

    infoq_items = scrape_infoq()
    report["sources"]["infoq"] = infoq_items
    all_raw_signals.extend(infoq_items)

    # ═══════════════════ 水系3: 全球搜索趋势 (2源) ═══════════════════
    print("\n🔍 水系3: 全球搜索趋势")
    
    gt_titles = fetch_google_trends()
    report["sources"]["google_trends"] = gt_titles
    all_raw_signals.extend(gt_titles)

    baidu_titles = fetch_baidu_hot()
    report["sources"]["baidu"] = baidu_titles
    all_raw_signals.extend(baidu_titles)

    # ═══════════════════ 水系4: 维基百科与AI趋势 (4源) ═══════════════════
    print("\n📖 水系4: 维基百科 & AI趋势")
    
    wiki_titles = fetch_wikipedia_trending()
    report["sources"]["wikipedia"] = wiki_titles
    all_raw_signals.extend(wiki_titles)

    hf_titles = fetch_huggingface_trending()
    report["sources"]["huggingface"] = hf_titles
    all_raw_signals.extend(hf_titles)

    arxiv_items = fetch_arxiv_ai()
    report["sources"]["arxiv"] = arxiv_items
    all_raw_signals.extend(arxiv_items)

    pwc_items = fetch_paperswithcode()
    report["sources"]["paperswithcode"] = pwc_items
    all_raw_signals.extend(pwc_items)

    # ═══════════════════ 水系5: 包注册中心 + 技术主题 (2源) ═══════════════════
    print("\n📦 水系5: 包注册中心 + 技术主题")
    
    npm_items = scrape_npm_registry()
    report["sources"]["npm_registry"] = npm_items
    all_raw_signals.extend(npm_items)

    gh_topics = scrape_github_topics()
    report["sources"]["github_topics"] = gh_topics
    all_raw_signals.extend(gh_topics)

    # ── 搜索日志 ──
    search_queries = analyze_search_logs()
    report["sources"]["search_log_top"] = search_queries
    for sq in search_queries:
        all_raw_signals.append(sq["query"])

    # ═══════════════════════════════════════════════
    # 🧠 最高优先级: AI商机捕手用户痛点
    # ═══════════════════════════════════════════════
    print(f"\n🧠 [最高优先级] 读取 AI 商机捕手用户痛点...")
    pain_entries = fetch_pain_points()
    report["sources"]["pain_points"] = pain_entries
    all_raw_signals.extend([pe.get("query", "") for pe in pain_entries])
    print(f"  📡 捕获 {len(pain_entries)} 条用户真实痛点")

    # ══════════════════════════════════════════════════════════
    # 🧠 阶段 A: 工具特质自动识别 + 🚫 闲聊前置过滤
    # ══════════════════════════════════════════════════════════

    print(f"\n{'='*60}")
    print(f"🧠 阶段 A: 工具特质自动识别 + 闲聊二次过滤")
    print(f"{'='*60}")
    print(f"  原始信号总量: {len(all_raw_signals)}")

    tool_signals = []
    chatter_blocked = []
    chatter_samples = []
    tool_signal_samples = []

    # ═══════════════════════════════════════════════════
    # 🧨 最高优先级: AI商机捕手用户痛点 (绕过闲聊过滤)
    # ═══════════════════════════════════════════════════
    pain_priority_signals = []
    for pe in pain_entries:
        pq = pe.get("query", "")
        ps = pe.get("pain_summary", "")
        ti = pe.get("tool_idea", "")
        
        # 组合所有文本信息
        combined = f"{pq} | {ps} | {ti}".strip(" |")
        if len(combined) < 3:
            continue
        
        # 跳过闲聊过滤 — 用户真实需求直接进入特质识别
        trait = recognizer.analyze(combined)
        # 给痛点信号 +40 分人工加权 (用户亲口说的需求)
        trait["confidence"] = min(100, trait.get("confidence", 0) + 40)
        trait["score"] = trait.get("score", 0) + 40
        
        pain_priority_signals.append(combined)
        tool_signals.insert(0, combined)  # 插到最前面
        
        if len(tool_signal_samples) < 5:
            tool_signal_samples.insert(0, {
                "text": combined[:100],
                "confidence": trait["confidence"],
                "features": trait["features"] + ["🚨 用户痛点·最高优先级"],
                "source": pe.get("source", "pain-point"),
            })
    
    if pain_priority_signals:
        print(f"\n  🧨 用户痛点直通: {len(pain_priority_signals)} 条 (绕过闲聊过滤, +40分加权)")
        for pps in pain_priority_signals[:3]:
            print(f"     📌 {pps[:70]}")

    for signal in all_raw_signals:
        if not signal or len(signal) < 3:
            continue

        # 步骤1: 闲聊前置过滤 (第一道防线)
        chatter_result = chatter_filter.is_chatter(signal)
        if chatter_result["is_chatter"]:
            chatter_blocked.append(signal)
            if len(chatter_samples) < 10:
                chatter_samples.append({
                    "text": signal[:80],
                    "category": chatter_result["category"],
                    "matched": chatter_result["matched"],
                })
            continue

        # 步骤2: 工具特质自动识别
        trait_result = recognizer.analyze(signal)
        if trait_result["is_tool_signal"]:
            tool_signals.append(signal)
            if len(tool_signal_samples) < 15:
                tool_signal_samples.append({
                    "text": signal[:100],
                    "confidence": trait_result["confidence"],
                    "features": trait_result["features"],
                })

    # 保存特质分析结果
    report["trait_analysis"] = {
        "total_captured": len(all_raw_signals),
        "chatter_blocked": len(chatter_blocked),
        "chatter_rate": round(len(chatter_blocked) / max(len(all_raw_signals), 1) * 100, 1),
        "tool_signals_found": len(tool_signals),
        "tool_signal_rate": round(len(tool_signals) / max(len(all_raw_signals), 1) * 100, 1),
        "chatter_samples": chatter_samples,
        "tool_signal_samples": tool_signal_samples[:15],
    }

    print(f"  🚫 闲聊拦截: {len(chatter_blocked)} 条 ({report['trait_analysis']['chatter_rate']}%)")
    print(f"  🧠 工具信号: {len(tool_signals)} 条 ({report['trait_analysis']['tool_signal_rate']}%)")

    if chatter_samples:
        print(f"\n  📋 闲聊拦截样例:")
        for c in chatter_samples[:5]:
            print(f"     [{c['category']}] {c['text'][:60]}")

    if tool_signal_samples:
        print(f"\n  🧠 工具信号样例:")
        for t in tool_signal_samples[:5]:
            print(f"     [置信度{t['confidence']}%] {t['text'][:60]}")
            for f in t['features'][:2]:
                print(f"       ↳ {f}")

    # ══════════════════════════════════════════════════════════
    # 🔒 阶段 B: 硬核甄别过滤器 (demand_filter.py)
    # ══════════════════════════════════════════════════════════

    print(f"\n{'='*60}")
    print(f"🔒 阶段 B: 硬核甄别过滤器 (demand_filter)")
    print(f"{'='*60}")

    raw_count = len(tool_signals)
    valid_kw, rejected_kw = filter_demand_list(tool_signals)
    report["all_keywords"] = valid_kw
    report["filter_stats"] = {
        "raw_count": raw_count,
        "valid_count": len(valid_kw),
        "rejected_count": len(rejected_kw),
        "rejection_rate": round(len(rejected_kw) / max(raw_count, 1) * 100, 1),
        "rejected_samples": rejected_kw[:10],
    }
    print(f"  📊 {raw_count} → {len(valid_kw)} (拒绝率 {report['filter_stats']['rejection_rate']}%)")
    if rejected_kw:
        print(f"  🚫 拦截样例: {rejected_kw[:5]}")

    # ── 去重 + 工具建议 ──
    unique_keywords = list(dict.fromkeys(report["all_keywords"]))
    report["tool_suggestions"] = suggest_tools_from_keywords(unique_keywords)

    # ── 保存 ──
    report_path = os.path.join(REPORT_DIR, "demand_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # ══════════════════════════════════════════════════════════
    # 📊 最终统计报告
    # ══════════════════════════════════════════════════════════

    src = report["sources"]
    ta = report["trait_analysis"]

    print(f"\n{'='*60}")
    print(f"📊 MintShovels Demand Radar v2.1 — 19 个免费水源报告")
    print(f"{'='*60}")
    print(f"\n  🌐 开发者问答 (5源):")
    print(f"     GitHub Trending:     {len(src['github_trending'])} repos")
    print(f"     V2EX:                {len(src['v2ex'])} topics")
    print(f"     Dev.to:              {len(src['devto'])} articles")
    print(f"     Lobsters:            {len(src['lobsters'])} items")

    print(f"\n  💡 海外效率社区 (5源):")
    print(f"     ProductHunt:         {len(src['producthunt'])} products")
    print(f"     Hacker News (Algolia): {len(src['hacker_news'])} items")
    print(f"     🆕 Show HN:          {len(src['hn_show'])} posts")
    print(f"     🆕 Ask HN 工具需求:  {len(src['hn_ask_tools'])} posts")
    print(f"     🆕 HackerNoon:       {len(src['hackernoon'])} articles")

    print(f"\n  🔍 全球搜索趋势 (2源):")
    print(f"     Google Trends:       {len(src['google_trends'])} items")
    print(f"     百度热搜:            {len(src['baidu'])} items")

    print(f"\n  📖 维基百科 & AI (4源):")
    print(f"     Wikipedia:           {len(src['wikipedia'])} pages")
    print(f"     HuggingFace:         {len(src['huggingface'])} models")
    print(f"     arXiv cs.AI:         {len(src['arxiv'])} papers")
    print(f"     Papers With Code:    {len(src['paperswithcode'])} papers")

    print(f"\n  📦 包注册+技术主题 (2源):")
    print(f"     🆕 npm Registry:     {len(src['npm_registry'])} packages")
    print(f"     🆕 GitHub Topics:    {len(src['github_topics'])} topics")

    print(f"\n  📋 搜索日志:            {len(src['search_log_top'])} queries")
    print(f"  🧠 AI商机捕手(痛点):    {len(src['pain_points'])} 条")

    print(f"\n  ━━━ 已移除(需API/失效): Reddit/知乎/微博/Quora/36Kr/少数派/Dribbble/Bing/Medium/PyPI ╸ 14个（不再空跑）")
    
    print(f"\n  {'─' * 50}")
    print(f"  🧠 特质识别摘要:")
    print(f"     原始抓取: {ta['total_captured']} 条")
    print(f"     🚫 闲聊挡掉: {ta['chatter_blocked']} 条 ({ta['chatter_rate']}%)")
    print(f"     🧠 工具信号: {ta['tool_signals_found']} 条 ({ta['tool_signal_rate']}%)")
    print(f"  🔒 门禁过滤:")
    print(f"     工具信号 {report['filter_stats']['raw_count']} → 有效 {report['filter_stats']['valid_count']} (拒绝率 {report['filter_stats']['rejection_rate']}%)")
    print(f"  🔧 工具建议: {len(report['tool_suggestions'])}")

    print(f"\n  💾 Report saved: {report_path}")
    print(f"{'='*60}")

    if report["tool_suggestions"]:
        print("\n🔧 Top Tool Suggestions:")
        for s in report["tool_suggestions"][:10]:
            print(f"  • {s['name']} ({s['name_zh']}) → [{s['category']}/{s['subcat']}] matched: {s['keyword']}")

    return report


if __name__ == "__main__":
    main()
