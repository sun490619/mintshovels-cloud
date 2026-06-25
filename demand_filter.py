#!/usr/bin/env python3
"""
MintShovels 雷达需求甄别过滤器 v4.0
=====================================
v4.0 升级内容（意图驱动甄别，配合 intent_classifier.py 双引擎）：
  意图分类器(intent_classifier.py) 作为主引擎做 10 维打分，
  demand_filter.py 作为双保险硬拦截层，负责快速过滤明显垃圾。

v3.0 已有功能 (保留)：
  🔴 中文社交闲聊语气拦截：如何、怎么、为什么、吗、呢、啦、大家、听说、当初 等
  🔴 中文人名/八卦拦截：雷军、董明珠、曾沛慈 等
  🔴 中文社交句式拦截：是不是、有没有、该不该、能不能、收红包、打赌 等
  🔴 随机/闲聊前缀拦截：Random + 长句当工具名的套壳模式
  🔴 GitHub issue 中文提问拦截

v2.0 已有功能 (保留)：
  🔧 GitHub owner/repo 智能提取
  🔧 Show HN / Ask HN 前缀去噪
  🔧 新闻媒体/娱乐/商品黑名单
  🔧 Flask/报错/问题描述检测

甄别规则：
  🚫 黑名单关键词（中英文双语义）
  🚫 中文社交闲聊语气词
  🚫 提问句式（含 ? 或 中文疑问词）
  🚫 第一人称叙事
  🚫 超长句子
  🚫 无工具属性

用法: from demand_filter import is_valid_demand, is_professional_tool_name
"""

import re

# ═══════════════════════════════════════════════════════════
# 🧹 名称预处理：去噪 + 智能提取
# ═══════════════════════════════════════════════════════════


def preprocess_name(name: str) -> str:
    """
    对工具名称做预处理清洗，返回更干净的核心名用于后续评估。

    处理规则：
      1. 去掉 "Show HN: " / "Ask HN: " / "Tell HN: " 前缀
      2. GitHub owner/repo 格式：提取核心 repo 名，丢弃 : 后面的描述
      3. 去掉末尾的 emoji
      4. v3.0: 去掉 "Random " 前缀（自动工厂套壳模式）
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

    # ── 3. v3.0: 去掉 "Random " 前缀（自动工厂套壳标识）──
    cleaned = re.sub(r'^Random\s+', '', cleaned, flags=re.IGNORECASE).strip()

    # ── 4. 去掉末尾 emoji + 多余空格 ──
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned


# ═══════════════════════════════════════════════════════════
# 🚫 v3.0 中文语义黑名单（核心升级！）
# ═══════════════════════════════════════════════════════════

CN_SEMANTIC_BLACKLIST = [
    # ── 🔴 中文社交闲聊语气词 ──
    "如何", "怎么", "怎样", "为什么", "为何", "干嘛",
    "吗", "呢", "啦", "吧", "啊", "呀", "哦", "哈",
    "大家", "各位", "朋友们", "兄弟们",
    "听说", "据说", "传闻", "有人说",
    "当初", "当初不该", "当初要是",
    "是不是", "有没有", "该不该", "能不能", "要不要",
    "真的吗", "太棒了", "厉害了", "绝了", "牛了",

    # ── 🔴 中文社交闲聊句式 ──
    "不收红包", "收红包", "打赌", "赌约", "直言后悔",
    "再谈与", "与.*赌约",
    "全国统一", "全国统一的",
    "说当初不该", "不该和",
    "降智降麻了", "周额度",
    "我不知道", "我不懂", "我觉得", "我认为",
    "搞笑", "离谱", "逆天", "无语", "服了",

    # ── 🔴 中文人名/品牌/八卦 ──
    "雷军", "董明珠",
    "曾沛慈",
    "高考状元", "不建议.*考",

    # ── 🔴 中文娱乐/闲聊内容 ──
    "第.*集", "喜剧", "动画", "温情",
    "舞台", "演唱会", "粉丝",
    "直播间", "主播",
    "父亲节", "母亲节", "情人节",
    "感性.*理性", "不同频",

    # ── 🔴 中文非工具描述 ──
    "这个怎么", "那个怎么", "能不能帮忙",
    "谁知道", "有谁知道", "请教一下",
    "求助", "求救", "在线等",
    "跪求", "求求",
]


# ═══════════════════════════════════════════════════════════
# 🚫 v3.0 中文语义正则模式
# ═══════════════════════════════════════════════════════════

CN_REJECT_PATTERNS = [
    # 中文疑问句（以中文疑问词开头或包含）
    r'(如何|怎么|怎样|为什么|为何|干嘛|是不是|有没有|该不该|能不能|要不要|谁知道)',

    # 中文社交语气词结尾
    r'(吗|呢|啦|吧|啊|呀|哦|哈)$',

    # 中文闲聊叙事（听说/据说/有人说）
    r'(听说|据说|传闻|有人说|大家|各位)',

    # 中文"当初"叙事
    r'(当初不该|当初要是|早知道)',

    # 中文"再谈"模式
    r'(再谈|又谈|谈到).*(赌约|打赌|不和)',

    # 中文社交互动
    r'(不收红包|收红包|全国统一的)',

    # 中文第一人称
    r'(我不知道|我不懂|我觉得|我认为|我猜)',

    # 中文感叹
    r'(太棒了|厉害了|绝了|牛了|真.*绝)',

    # 中文降智/玄学话题
    r'(降智|降麻了)',

    # 中文节日/贺词
    r'(父亲节|母亲节|情人节|生日.*快乐|新年.*快乐)',

    # 中文娱乐内容
    r'(第.*集|舞台|演唱会|粉丝|直播间)',

    # 中文求助句式
    r'(求助|求救|在线等|跪求|求求)',

    # 中文名人八卦
    r'(雷军|董明珠|曾沛慈)',

    # 中文教育/考试闲聊
    r'(高考状元|不建议.*考)',

    # 中文"生成这个角色的视频" 等非工具功能描述
    r'(给一张照片|然后直接|用自己的动作|生成这个角色)',
]


# ═══════════════════════════════════════════════════════════
# 🚫 硬核黑名单关键词（v2.0 暴增版 + v3.0 补充）
# ═══════════════════════════════════════════════════════════

BLACKLIST_KEYWORDS = [
    # ── 新闻/政治 ──
    "breaking", "just in", "leaked", "confirmed", "report:", "update:",
    "statement", "exclusive", "revealed", "announced", "shocking",
    "scandal", "controversy", "resign", "election", "protest", "riot",
    "president", "congress", "senate", "parliament", "white house",
    "pentagon", "nato", "united nations", "regime", "coup", "sanction",
    "tariff", "trade war", "summit", "diplomacy", "ambassador",
    "democrat", "republican", "conservative", "liberal", "left-wing",
    "right-wing", "socialist", "communist", "fascist",
    "ukraine", "russia", "china", "taiwan", "gaza", "israel", "iran",
    "north korea", "putin", "zelensky", "xi", "biden", "trump",
    "musk", "bezos", "zuckerberg",

    # ── 🆕 新闻媒体域名 ──
    "bbc news", "bbc", "fox news", "fox 59", "fox 5", "fox 4", "fox 2",
    "cnn", "msnbc", "cnbc", "bloomberg", "npr", "politico",
    "the guardian", "the new york times", "new york times", "washington post",
    "wall street journal", "wsj", "reuters", "associated press", "ap news",
    "seattle times", "chicago tribune", "la times", "los angeles times",
    "usa today", "the hill", "the intercept", "vice news", "buzzfeed news",
    "sky news", "al jazeera", "the times", "the telegraph", "daily mail",
    "the sun", "mirror", "metro",

    # ── 娱乐/票房/流行文化 ──
    "toy story", "box office", "opening weekend", "franchise record",
    "pop culture", "pride month", "pride parade",
    "fan goes wild", "fans go wild", "crowd goes wild",
    "top charts", "tops charts", "charts for", "week running",
    "record opening",

    # ── 娱乐/八卦 ──
    "celebrity", "actor", "actress", "singer", "rapper", "influencer",
    "youtuber", "tiktok star", "instagram model", "onlyfans",
    "divorce", "married", "dating", "pregnant", "baby",
    "netflix show", "movie review", "box office", "grammy", "oscar",
    "emmy", "golden globe", "red carpet", "met gala",
    "concert", "tour", "album", "single release", "music video",
    "viral video", "trending now", "gone viral",
    "disney", "pixar", "marvel", "dc comics", "star wars", "harry potter",

    # ── 体育 ──
    "nfl", "nba", "mlb", "nhl", "premier league", "champions league",
    "super bowl", "world cup", "playoffs", "touchdown", "home run",
    "goal!", "transfer window", "trade deadline", "free agent",

    # ── 犯罪/暴力/天气 ──
    "cocaine", "heroin", "meth", "fentanyl", "drug bust", "drug cartel",
    "police uncover", "police arrested", "police found", "police seized",
    "arrested", "murdered", "killed", "convicted", "sentenced",
    "severe storms", "severe thunderstorm", "tornado", "hurricane",
    "earthquake", "tsunami", "flooding", "wildfire", "blizzard",

    # ── 非工具商品/日用品 ──
    "paper towels", "toilet paper", "bounty paper", "charmin",
    "tide pods", "laundry detergent", "dish soap",
    "family rolls", "regular rolls",
    "black friday", "cyber monday", "amazon deal", "price drop",
    "clearance sale", "on sale",

    # ── 社交媒体闲聊 ──
    "hot take", "unpopular opinion", "rant", "vent", "just saying",
    "no offense", "change my mind", "hear me out", "honestly",
    "personal opinion", "random thought",
    "shower thought", "am i the only", "does anyone else",
    "triggered", "cancel culture", "woke", "based",

    # ── 股市/币圈闲聊 ──
    "to the moon", "diamond hands", "paper hands", "wen lambo",
    "wen moon", "hodl", "buy the dip", "bear market", "bull market",

    # ── v3.0 新增：礼品卡/消费类闲聊 ──
    "gift card", "gift cards", "礼品卡", "apple 礼品",

    # ── 无意义的通用词 ──
    "hello world", "test test", "asdf", "lorem ipsum",
]

# ═══════════════════════════════════════════════════════════
# 🚫 正则模式黑名单（v2.0 升级版）
# ═══════════════════════════════════════════════════════════

REJECT_PATTERNS = [
    # 第一人称叙事
    r"\bI\b.*\b(think|believe|feel|guess|wish|hope|wonder|suppose|assume|reckon)\b",
    r"\b(my|our)\b.*\b(take|opinion|thought|experience|story|journey)\b",
    r"\b(in my|in our)\b.*\b(opinion|experience|view)\b",
    r"\bI'?ve\b.*\b(been|tried|found|discovered|built|made|created)\b",
    r"\bwe'?ve\b.*\b(been|tried|found|discovered|built|made|created)\b",

    # 社交媒体互动
    r"\banyone\b.*\b(else|know|have|tried|seen|heard|used)\b.*\??$",
    r"\b(does|do|is|are|was|were|has|have|should|can|could|would|will)\b.*\b(anyone|anybody|someone)\b",

    # 新闻事件描述
    r"\b(says|said|told|reported|according to)\b.*\b(will|would|should|must|going to)\b",
    r"\b(fired|laid off|resigns|quits|steps down|departs)\b",
    r"\b(dies?|killed|murdered|arrested|charged|sentenced|convicted)\b",
    r"\b(wins?|won|awarded|prize|elected|nominated)\b",

    # 气象/灾害新闻
    r"\b(storms?|tornado|hurricane|earthquake|flood|tsunami|wildfire|blizzard)\b.*\b(strikes?|hits?|batters?|devastates?|traveling|heading)\b",

    # 新闻标题风格
    r"^(happening|breaking|developing|unfolding)\b",

    # 股票/加密货币闲聊
    r"\b(price|market|stock|shares?|ticker|bullish|bearish|moon|dump|pump|hodl)\b.*\b(prediction|forecast|target|going to)\b",
    r"\b(to the moon|diamond hands|paper hands|wen (lambo|moon))\b",

    # GitHub issue 风格的无意义标题
    r"^(how|why|what|when|where|who|is it|can i|should i)\b.*\b(work|fix|solve|do|happen|mean)\b.*\??$",

    # 技术报错/故障描述
    r"\b(error|bug|fail|crash|broken|not working|doesn't work|won't work)\b.*\b(when|while|after|during|trying to|attempting)\b",
    r"\b(failure|failed)\b.*\b(create|connect|build|deploy|start|run|install|setup)\b",
    r"\b(wrong|missing|undefined|unsupported|deprecated)\b.*\b(in|with|when|using)\b",
    r"\b(dimmed|grayed out|greyed out)\b.*\b(toolbox|tools|menu|option|button)\b",
    r"\b(appended to|appended)\b.*\b(env var|environment|config|path|variable)\b",

    # 商品/广告描述
    r"\b(\d+)\s*(family|regular|mega|jumbo|double)\s*(rolls?|packs?)\b",
    r"\b(\d+)\s*(rolls?|packs?)\s*=\s*\d+\s*(regular)?\s*(rolls?|packs?)\b",
    r"\b(quick size|scented|unscented|fragrance free|hypoallergenic)\b",

    # v3.0 新增：Codex 版本讨论
    r"\b(codex|claude|gpt|gemini)\b.*\b(降智|降级|上线|额度|token|周额度)\b",
]


# ═══════════════════════════════════════════════════════════
# ✅ 工具后缀白名单
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
# 🆕 v4.1: 工具意图信号检测
# ═══════════════════════════════════════════════════════════

# 中文工具意图关键词 —— 如果文本包含这些词，
# 即使也有"如何/怎么"等疑问词，也判定为工具需求而非闲聊
CN_TOOL_INTENT_KEYWORDS = [
    # 工具类核心词
    "工具", "生成器", "计算器", "转换器", "编辑器", "格式化",
    "编码器", "解码器", "压缩器", "扫描器", "检测器", "分析器",
    # 在线/免费信号
    "在线", "免费", "无需注册", "无需登录",
    # 工具动作
    "生成", "计算", "转换", "压缩", "加密", "解密", "编码", "解码",
    "格式化", "校验", "验证", "提取", "合并", "拆分", "下载",
    "制作", "创建", "设计",
    # 工具场景
    "json", "pdf", "csv", "xml", "yaml", "markdown", "base64",
    "二维码", "条形码", "图片压缩", "文字识别",
    "api", "sdk", "cli",
    # 英文工具意图短语（可能出现在中英混合文本中）
    "free online", "online tool", "no signup", "no login",
    "without registration",
]


# 社交噪音信号 —— 即使文本包含工具关键词，如果有这些信号也仍是闲聊
CN_SOCIAL_NOISE_PATTERNS = [
    r'(太棒了|厉害了|绝了|牛了|真.*绝)',
    r'(大家|各位|朋友们|兄弟们).*(快来看|来看看|看一下)',
    r'(听说|据说|传闻|有人说).*(工具|软件|网站)',
    r'(降智|降麻了|额度|周额度)',
]


def _detect_tool_intent(text: str) -> bool:
    """
    v4.1: 检测文本是否包含明确的工具意图信号

    如果返回 True，意味着这段文字极可能是用户描述工具需求，
    即使包含"如何/怎么"等疑问词也应该放行（因为用户在问"如何做这个工具"）

    v4.1.1: 如果文本包含大量中文但只有英文后缀，不算工具意图
    （避免"雷军打赌 Generator"这种自动工厂套壳通过）

    Examples that return True:
      - "如何生成二维码在线工具"  (包含"二维码"+"工具"+"在线")
      - "怎么做一个免费的JSON格式化器"  (包含"JSON"+"格式化"+"免费")
      - "有没有好的PDF转换器推荐"  (包含"PDF"+"转换器")
      - "需要一个图片压缩工具"  (包含"图片压缩"+"工具")

    Examples that return False:
      - "雷军说当初不该和董明珠打赌"  (纯八卦，无工具信号)
      - "雷军说当初不该和董明珠打赌 Generator"  (中文八卦+英文后缀=不算)
      - "太棒了这个工具大家快来看"  (包含"工具"但有社交噪音)
    """
    if not text:
        return False

    text_lower = text.lower()

    # 先检查社交噪音 —— 有强社交信号的不算工具意图
    for pattern in CN_SOCIAL_NOISE_PATTERNS:
        if re.search(pattern, text_lower):
            return False

    # 检查中文工具意图关键词
    has_cn_tool_signal = False
    for kw in CN_TOOL_INTENT_KEYWORDS:
        if kw.lower() in text_lower:
            has_cn_tool_signal = True
            break

    # 检查英文工具后缀
    has_en_suffix = False
    for suffix in TOOL_SUFFIXES:
        if suffix.lower() in text_lower:
            has_en_suffix = True
            break

    # v4.1.1: 如果文本含中文杂音但没有中文工具关键词，
    # 仅靠英文后缀不算工具意图（防"雷军打赌 Generator"套壳）
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
    if has_chinese:
        # 中文文本必须至少有中文工具关键词才算工具意图
        if not has_cn_tool_signal:
            return False
        return True  # 有中文工具关键词 → 算工具意图

    # 纯英文/数字文本：有工具后缀就算
    if has_en_suffix:
        return True

    return bool(has_cn_tool_signal)


def is_professional_tool_name(name: str) -> bool:
    """
    判断是否为专业工具名称（v4.1 升级版）

    v4.1 新增：工具意图预检 —— 包含"工具/生成器/计算器"等关键词的信号，
    即使包含"如何/怎么"等疑问词也不拦截（用户可能在描述工具需求而非闲聊）

    v4.0 定位：作为硬拦截双保险层，配合 intent_classifier.py 主引擎使用

    返回 True = 合格工具名，False = 不合格（垃圾）
    """
    if not name or not isinstance(name, str):
        return False

    # ── 🧹 预处理：GitHub提取 + Show HN去噪 + Random去噪 ──
    cleaned_name = preprocess_name(name)
    cleaned_lower = cleaned_name.lower()
    words = cleaned_lower.split()

    # ── 长度检查 ──
    if len(words) > 15:
        return False

    if len(cleaned_name) > 80:
        return False

    if len(words) < 2:
        return False

    # ── 🆕 v4.1: 工具意图预检 ──
    # 检测文本是否包含明确的工具相关信号，
    # 如果有，跳过中文社交闲聊黑名单（但保留新闻/政治/娱乐等硬拦截）
    name_for_cn = name.lower()
    cleaned_for_cn = cleaned_name.lower()
    has_tool_intent_signal = _detect_tool_intent(name_for_cn) or _detect_tool_intent(cleaned_for_cn)

    # ── 🔴 v3.0: 中文语义黑名单检查 ──
    # v4.1: 如果检测到工具意图信号，跳过此层（疑问词如"如何/怎么"可能出现在工具需求描述中）
    if not has_tool_intent_signal:
        # 中文黑名单关键词检查
        for kw in CN_SEMANTIC_BLACKLIST:
            if kw.lower() in name_for_cn or kw.lower() in cleaned_for_cn:
                return False

        # 中文正则模式检查
        for pattern in CN_REJECT_PATTERNS:
            if re.search(pattern, name_for_cn) or re.search(pattern, cleaned_for_cn):
                return False

    # ── 英文黑名单关键词 ──
    for kw in BLACKLIST_KEYWORDS:
        if kw in cleaned_lower:
            return False

    # ── 英文正则模式过滤 ──
    for pattern in REJECT_PATTERNS:
        if re.search(pattern, cleaned_lower):
            return False

    # ── 提问句式 ──
    if "?" in cleaned_name:
        return False

    # ── 感叹号滥用 ──
    if cleaned_name.count("!") >= 2:
        return False

    # ── v3.0: "Random" 前缀检查（原始名称）──
    # 如果原始名称以 "Random " 开头且预处理后仍有大量中文字符，拒绝
    if name.lower().startswith("random ") and len(cleaned_name) > 30:
        # 预处理去掉 Random 后如果还很长，说明后面跟的是聊天废话
        return False

    # ── 工具属性检查 ──
    has_tool_suffix = any(s in cleaned_lower for s in TOOL_SUFFIXES)
    if has_tool_suffix:
        return True

    # ── 技术性命名特征 ──
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
    判断雷达抓取到的需求是否为有效需求

    v3.0: 中英文双语义检查

    返回 True = 有效需求（可生成工具）
    返回 False = 垃圾需求（必须丢弃）
    """
    if not text or not isinstance(text, str):
        return False

    cleaned = text.strip()
    if not cleaned or len(cleaned) < 2:
        return False

    words = cleaned.split()

    # ── 短词模式（≤3词）：黑名单+中文语义+问号检查 ──
    if len(words) <= 3:
        name_lower = cleaned.lower()

        # 🆕 v4.1: 工具意图预检 —— 含工具信号的不拦截
        if not _detect_tool_intent(name_lower):
            # v3.0: 短词也检查中文语义
            for kw in CN_SEMANTIC_BLACKLIST:
                if kw.lower() in name_lower:
                    return False

            for pattern in CN_REJECT_PATTERNS:
                if re.search(pattern, name_lower):
                    return False

            if "?" in cleaned:
                return False
            if cleaned.count("!") >= 2:
                return False

        for kw in BLACKLIST_KEYWORDS:
            if kw in name_lower:
                return False
        return True

    # ── 长词模式（>3词）：全量严格审查 ──
    return is_professional_tool_name(cleaned)


def filter_demand_list(items: list) -> tuple:
    """
    批量过滤需求列表
    输入: ["AI Image Upscaler", "Breaking: Trump says...", "PDF Converter"]
    输出: (valid_items, rejected_items)
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
    non_rate = (invalid / total * 100) if total > 0 else 0.0

    return {
        "total": total,
        "valid": valid,
        "invalid": invalid,
        "compliance_rate": round(rate, 1),
        "non_compliance_rate": round(non_rate, 1),
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

        # 🚫 不合格（长句套壳）
        ("Will the jetson nano 4gb be sufficient for our system?", False),
        ("How to move what's stored in the setup function?", False),
        ("Who here has worked with legacy? the longer you wait, the worse it gets", False),
        ("Backgroundworker is dimmed in toolbox- what is wrong in my web solution?", False),
        ("Trying to send event reminders from my google sheet to a discord channel", False),

        # 🚫 不合格（新闻/政治）
        ("Trump vents growing frustrations with reflecting-pool problems - wsj", False),
        ("Starmer is on the precipice as pressure builds for the uk leader to resign", False),
        ("Vance says us hopes to transform middle east as iran talks begin", False),
        ("'regime change but in a velvet glove': how kevin warsh has set out to remake the", False),

        # 🚫 不合格（娱乐/八卦）
        ("Netflix show tops charts for third week running", False),
        ("Celebrity divorce shocks fans worldwide", False),

        # 🚫 不合格（商品描述）
        ("Bounty paper towels quick size white 16 family rolls = 40 regular rolls", False),

        # ✅ Show HN 去噪通过
        ("Show HN: a lightweight pdf editor for macos Editor", True),

        # 🚫 GitHub长描述
        ("Orhun/git-cliff a highly customizable changelog generator that follows conventional commits Generator", False),

        # ✅ 纯 repo 名通过
        ("git-cliff Generator", True),

        # 🚫 体育/商品/天气/违法（v2.0漏杀补丁）
        ("Toy story scores record opening weekend for franchise Generator", False),
        ("Severe storms traveling across indiana on father's day Generator", False),
        ("Australian police uncover tons of cocaine Generator", False),
        ("Cape verde fan goes wild live on bbc news as his country scores Generator", False),
        ("Flask app run from_envvar gets the root_path appended to env var Generator", False),
        ("Failure to create a new firebase project failure to add firebase to google cloud Generator", False),

        # ✅ Show HN通过
        ("Show HN: minipcs Generator", True),

        # ═══════════════════════════════════════════
        # 🔴 v3.0: 中文社交闲聊测试
        # ═══════════════════════════════════════════

        # 🚫 中文社交闲聊（黑名单关键词拦截）
        ("Random 雷军说当初不该和董明珠打赌 Generator", False),
        ("Random 雷军再谈与董明珠赌约直言后悔 Generator", False),
        ("Random 爸爸不收红包是全国统一的吗 Generator", False),
        ("Random 理性女儿 × 感性爸爸父亲节温情喜剧 Generator", False),

        # 🚫 中文闲聊语气
        ("Random Codex 降智降麻了 听说 23 要上线了 Generator", False),
        ("Random Codex 的周额度怎么还会增加 Generator", False),

        # 🚫 中文问句
        ("Random 曾沛慈｜怎么说我不爱你 舞台 Generator", False),
        ("Random 我不知道您是怎么了 Generator", False),

        # 🚫 中文非工具功能描述
        ("Random 给一张照片然后直接用自己动作和表情来生成这个角色的视频 这个怎么实现的 Generator", False),

        # 🚫 中文礼品卡闲聊
        ("Random 现在 apple 礼品卡哪些区可以正常开通的 为什么加拿大的礼品没办法开通 Generator", False),

        # 🚫 中文教育闲聊
        ("Random 干货 为什么不建议你今年考高考状元 Generator", False),

        # 🚫 中文求助
        ("Random 求助 这个怎么弄 Generator", False),
        ("Random 有没有人知道怎么用 Generator", False),

        # 🚫 中文感叹
        ("Random 太棒了这个工具 Generator", False),
        ("Random 绝了这个转换器大家快来看 Generator", False),

        # ✅ 合法的中英混合工具名（不包含语气词的才能通过）
        ("Chinese PDF Converter", True),
        ("日本語 OCR Tool", True),
    ]

    passed = 0
    failed = 0
    for text, expected in test_cases:
        if len(text.split()) <= 3:
            result = is_valid_demand(text)
        else:
            result = is_professional_tool_name(text)
        status = "✅" if result == expected else "❌"
        if result == expected:
            passed += 1
        else:
            failed += 1
        if result != expected:
            print(f"{status} '{text[:100]}' → got {result}, expected {expected}")

    total = passed + failed
    print(f"\n自检完成: {passed}/{total} 通过" + (" 🎉" if failed == 0 else f" ({failed} 失败)"))
