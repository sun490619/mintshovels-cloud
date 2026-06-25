#!/usr/bin/env python3
"""
MintShovels 意图分类器 — 替代机械关键词黑名单的多维判定引擎
=============================================================
核心原理：不靠关键词"拦截"，而是对需求做多维打分，区分：
  • 真工具需求（有输入输出闭环）→ PASS
  • 社交闲聊/八卦/新闻 → BLOCK

用法:
  from intent_classifier import IntentClassifier
  ic = IntentClassifier()
  result = ic.classify("如何计算公积金贷款")
  # → {pass: True, intent: "calculator", score: 80, verdict: "PASS", canonical_name: "公积金贷款计算器"}
"""

import json
import os
import re
import math
from difflib import SequenceMatcher
from collections import Counter

BAD_CASES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bad_cases.json")


class IntentClassifier:
    def __init__(self, bad_cases_path=None):
        if bad_cases_path is None:
            bad_cases_path = BAD_CASES_PATH

        with open(bad_cases_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.negative_cases = data["negative_cases"]
        self.positive_cases = data["positive_cases"]
        self.intent_map = data["intent_to_template_map"]
        self.weights = data["scoring_weights"]

        # 预编译正则模式
        self._compile_patterns()

    def _compile_patterns(self):
        """预编译所有检测正则"""
        # 中文疑问句式 — 不再机械拦截，而是用于辅助评估
        self.cn_question_words = re.compile(
            r'(如何|怎么|怎样|为什么|为何|干嘛|是不是|有没有|该不该|能不能|要不要|谁知道|真的吗)'
        )

        # 工具名词检测
        self.tool_noun_patterns = [
            # 中文工具名词
            (re.compile(r'(生成器|生成)'), "generator"),
            (re.compile(r'(计算器|计算|算)'), "calculator"),
            (re.compile(r'(验证器|检测|验证|检查|校验|测试器|测试)'), "checker"),
            (re.compile(r'(转换器|转换|换算|转)'), "calculator"),
            (re.compile(r'(编码|解码|编解码)'), "encoder"),
            (re.compile(r'(压缩器|压缩)'), "processor"),
            (re.compile(r'(格式化|美化)'), "formatter"),
            (re.compile(r'(编辑器|编辑)'), "editor"),
            (re.compile(r'(下载器|下载)'), "downloader"),
            (re.compile(r'(提取器|提取)'), "extractor"),
            (re.compile(r'(分析器|分析)'), "analyzer"),
            (re.compile(r'(扫描器|扫描)'), "scanner"),
            (re.compile(r'(爬虫)'), "scraper"),
            (re.compile(r'(脚本|工具)'), "script"),
            (re.compile(r'(去重)'), "processor"),
            (re.compile(r'(翻译器|翻译)'), "translator"),
            (re.compile(r'(处理器|处理)'), "processor"),
            # 英文工具名词
            (re.compile(r'\b(Generator|generator)\b'), "generator"),
            (re.compile(r'\b(Calculator|calculator|Calc|calc)\b'), "calculator"),
            (re.compile(r'\b(Checker|checker|Validator|validator|Tester|tester)\b'), "checker"),
            (re.compile(r'\b(Converter|converter|Encoder|encoder|Decoder|decoder)\b'), "encoder"),
            (re.compile(r'\b(Compressor|compressor)\b'), "processor"),
            (re.compile(r'\b(Formatter|formatter|Beautifier|beautifier)\b'), "formatter"),
            (re.compile(r'\b(Editor|editor)\b'), "editor"),
            (re.compile(r'\b(Downloader|downloader)\b'), "downloader"),
            (re.compile(r'\b(Extractor|extractor)\b'), "extractor"),
            (re.compile(r'\b(Analyzer|analyzer)\b'), "analyzer"),
            (re.compile(r'\b(Scanner|scanner)\b'), "scanner"),
            (re.compile(r'\b(Scraper|scraper|Crawler|crawler)\b'), "scraper"),
            (re.compile(r'\b(Tracker|tracker|Monitor|monitor)\b'), "tracker"),
            (re.compile(r'\b(Shortener|shortener|Minifier|minifier)\b'), "formatter"),
            (re.compile(r'\b(Translator|translator)\b'), "translator"),
            (re.compile(r'\b(Upscaler|upscaler|Enhancer|enhancer)\b'), "processor"),
            (re.compile(r'\b(Tool|tool|Utility|utility|Script|script)\b'), "script"),
            (re.compile(r'\b(Manager|manager|Builder|builder|Creator|creator)\b'), "script"),
        ]

        # 数据闭环检测 — 有无明确输入→输出
        self.data_closure_patterns = [
            # 有明确输入输出对
            re.compile(r'(输入|导入|上传|粘贴|填写).*(输出|导出|下载|生成|得到|返回)'),
            re.compile(r'(转|转换|换算|计算).*(为|成|到)'),
            re.compile(r'(输入|Input).*(Output|输出)'),
            re.compile(r'(从|from).*(到|to|into)'),
            re.compile(r'(验证|检查|检测|校验).*(是否|格式|有效|合法)'),
            re.compile(r'(解析|格式化|美化|压缩).*(JSON|XML|HTML|CSS|代码|文本|图片)'),
        ]

        # 新闻/媒体检测
        self.news_patterns = [
            re.compile(r'\b(news|breaking|just in|leaked|confirmed|report|statement|exclusive|revealed|announced)\b', re.I),
            re.compile(r'\b(bbc|cnn|fox news|msnbc|bloomberg|reuters|wsj|npr|politico)\b', re.I),
            re.compile(r'\b(the economist|the guardian|the times|washington post|new york times)\b', re.I),
            re.compile(r'\b(says|said|told|reported|according to)\b', re.I),
            re.compile(r'[\u4e00-\u9fff]*(新闻|报道|快讯|头条|突发)'),
        ]

        # 社交闲聊检测
        self.social_chatter_patterns = [
            re.compile(r'.*(听说|据说|传闻|有人说|大家|各位|兄弟们).*'),
            re.compile(r'.*(太棒了|厉害了|绝了|牛了|逆天|无语|服了).*'),
            re.compile(r'.*(在线等|跪求|求求|求助).*'),
            re.compile(r'.*(搞笑|离谱|牛逼|牛批).*'),
            re.compile(r'(是不是|有没有|该不该|能不能|要不要).*(吗|呢|啦|吧|啊)'),
        ]

        # 名人/八卦检测
        self.celebrity_patterns = [
            re.compile(r'(雷军|董明珠|曾沛慈|张靓颖|马斯克|特朗普|拜登)'),
            re.compile(r'\b(celebrity|actor|actress|singer|rapper|influencer)\b', re.I),
            re.compile(r'\b(divorce|married|dating|pregnant|baby)\b', re.I),
            re.compile(r'(打赌|赌约|后悔|不该)'),
        ]

        # 娱乐/体育
        self.entertainment_patterns = [
            re.compile(r'(演唱会|舞台|粉丝|直播间|主播|综艺)'),
            re.compile(r'(第.*集|喜剧|动画|电影|票房)'),
            re.compile(r'\b(box office|opening weekend|netflix|disney|marvel)\b', re.I),
            re.compile(r'\b(nfl|nba|premier league|super bowl|world cup)\b', re.I),
        ]

        # 商品/广告
        self.product_patterns = [
            re.compile(r'\b(\d+)\s*(family|regular|mega|jumbo|double)\s*(rolls?|packs?)', re.I),
            re.compile(r'(paper towels|toilet paper|laundry|dish soap)', re.I),
            re.compile(r'(gift card|礼品卡|on sale|clearance)', re.I),
        ]

        # 技术概念检测 — 有tech名词加分
        self.tech_keywords = re.compile(
            r'\b(AI|API|JSON|XML|CSV|PDF|HTML|CSS|SQL|URL|HTTP|REST|CRUD|'
            r'CLI|GUI|SDK|OCR|ML|NLP|3D|2D|RGB|HEX|UUID|SHA|MD5|AES|JWT|'
            r'OAuth|DNS|SSL|TLS|VPN|SSH|FTP|IP|TCP|UDP|DOM|regex|Base64|'
            r'WebSocket|Webhook|Docker|Kubernetes|Git|CI/CD)\b', re.I
        )

        # 汉语工具词
        self.cn_tool_keywords = re.compile(
            r'(密码|颜色|数字|姓名|邮箱|日期|网络|地址|文件|文本|代码|链接|域名|'
            r'图片|音频|视频|加密|解密|哈希|编码|解码|压缩|解压|'
            r'身份证|手机号|银行卡|车牌号|邮编|条形码|二维码)'
        )

    # ══════════════════════════════════════════════════════════
    # 多维打分
    # ══════════════════════════════════════════════════════════

    def score_data_closure(self, text: str) -> int:
        """评估是否有数据处理闭环 (输入→输出)"""
        score = 0
        text_lower = text.lower()

        for pattern in self.data_closure_patterns:
            if pattern.search(text) or pattern.search(text_lower):
                score += 10

        # 额外加分：包含技术标准名称 + 动词
        if re.search(r'(JSON|CSV|PDF|XML|HTML|CSS|SQL|URL).*(格式|化|处理|验证|解析|转)', text):
            score += 10
        if re.search(r'(密码|UUID|颜色|IP|邮箱|Emoji|Hex|SHA|MD5|Base64).*(生成|创建|随机|产生|编码|解码)', text):
            score += 10
        if re.search(r'(计算|换算|转换|转化).*(利率|汇率|温度|长度|重量|面积|体积|BMI|贷款|月供|利息)', text):
            score += 10
        # 短名称但包含工具名词的加分
        if re.search(r'(生成器|计算器|验证器|转换器|编码器|解码器|测试器|分析器|压缩器)', text):
            score += 10
        if re.search(r'(Generator|Calculator|Checker|Converter|Encoder|Decoder|Tester|Analyzer|Compressor)', text):
            score += 10
        # 英文工具词组合加分（Image Upscaler, Price Tracker, URL Shortener等）
        if re.search(r'\b(Image|Photo|Video|Audio|File|PDF|URL|Link|Code|Text|Price|Data|DNS|IP|Crypto|Stock)\b\s+\b(Upscaler|Tracker|Shortener|Converter|Generator|Editor|Analyzer|Checker|Manager|Monitor|Downloader|Extractor|Creator|Builder|Viewer|Finder|Scanner)\b', text, re.I):
            score += 15

        return min(score, self.weights["has_data_closure"])

    def score_tool_noun(self, text: str) -> int:
        """评估是否包含工具名词"""
        for pattern, intent in self.tool_noun_patterns:
            if pattern.search(text):
                return self.weights["has_tool_noun"]
        return 0

    def score_positive_match(self, text: str) -> int:
        """与正面案例库的相似度匹配"""
        text_lower = text.lower()
        best_score = 0

        for case in self.positive_cases:
            case_text = case["text"].lower()
            # 关键词重合度
            keywords = case.get("keywords", [])
            matched = sum(1 for kw in keywords if kw.lower() in text_lower)
            if keywords:
                ratio = matched / len(keywords)
                if ratio > 0.4:
                    best_score = max(best_score, int(ratio * self.weights["matches_positive_case"]))

            # 字符串相似度
            sim = SequenceMatcher(None, text_lower[:100], case_text[:100]).ratio()
            if sim > 0.5:
                best_score = max(best_score, int(sim * self.weights["matches_positive_case"]))

        return min(best_score, self.weights["matches_positive_case"])

    def score_negative_match(self, text: str) -> int:
        """与反面案例库的相似度匹配 — 返回负分"""
        text_lower = text.lower()
        worst_score = 0

        for case in self.negative_cases:
            case_text = case["text"].lower()
            keywords = case.get("keywords", [])

            # 关键词命中
            matched = sum(1 for kw in keywords if kw.lower() in text_lower)
            if keywords and matched >= 2:
                ratio = matched / len(keywords)
                penalty = int(ratio * abs(self.weights["matches_negative_case"]))
                worst_score = max(worst_score, penalty)

            # 字符串相似度
            sim = SequenceMatcher(None, text_lower[:120], case_text[:120]).ratio()
            if sim > 0.4:
                penalty = int(sim * abs(self.weights["matches_negative_case"]))
                worst_score = max(worst_score, penalty)

        if worst_score > 0:
            return -worst_score
        return 0

    def score_news_headline(self, text: str) -> int:
        """检测是否为新闻标题 — 返回负分"""
        text_lower = text.lower()

        for pattern in self.news_patterns:
            if pattern.search(text_lower) or pattern.search(text):
                return self.weights["is_news_headline"]  # 直接返回json中的负分值

        # 额外检测：标题式大写 + 动词过去式
        if re.search(r'.*\b(scores|plunges|surges|hits|strikes|unveils|launches)\b', text_lower, re.I):
            if len(text.split()) <= 10:
                return self.weights["is_news_headline"]

        return 0

    def score_social_chatter(self, text: str) -> int:
        """检测是否为社交闲聊 — 返回负分"""
        text_lower = text.lower()

        for pattern in self.social_chatter_patterns:
            if pattern.search(text_lower) or pattern.search(text):
                return self.weights["is_social_chatter"]

        return 0

    def score_celebrity_gossip(self, text: str) -> int:
        """检测是否为名人八卦 — 返回负分"""
        text_lower = text.lower()

        for pattern in self.celebrity_patterns:
            if pattern.search(text_lower) or pattern.search(text):
                return self.weights["is_celebrity_gossip"]

        # 娱乐/体育
        for pattern in self.entertainment_patterns:
            if pattern.search(text_lower) or pattern.search(text):
                return self.weights["is_celebrity_gossip"]

        return 0

    def score_personal_statement(self, text: str) -> int:
        """检测是否为个人陈述/感受 — 返回负分"""
        text_lower = text.lower()

        personal_patterns = [
            re.compile(r'(我要|我想|我觉得|我认为|我猜|我不).*(道歉|后悔|难过|开心)'),
            re.compile(r'(高估|低估).*(能力|水平)'),
            re.compile(r'\bI\b.*\b(think|believe|feel|guess|wish|hope|wonder)\b', re.I),
        ]

        for pattern in personal_patterns:
            if pattern.search(text_lower) or pattern.search(text):
                return self.weights["is_personal_statement"]

        return 0

    def score_computation_path(self, text: str) -> int:
        """评估是否存在可计算路径 — 能否映射到具体算法/公式"""
        text_lower = text.lower()

        score = 0

        # 技术关键词
        if self.tech_keywords.search(text):
            score += 10

        # 中文工具关键词
        if self.cn_tool_keywords.search(text):
            score += 10

        # 短名但包含工具名词的组合自动得分
        if re.search(r'(生成器|计算器|验证器|测试器|转换器|编码器|解码器|分析器)', text):
            score += 10

        # 英文工具名组合得分
        if re.search(r'\b(Up|scal|Track|Short|Convert|Generat|Edit|Analy|Check|Manag|Monitor|Download|Extract|Creat|Build|View|Find|Scan|Compress|Formatt|Encod|Decod|Upscal)\w*\b', text, re.I):
            score += 10

        # 可计算场景
        computable = [
            (r'(生成|创建|产生|随机).*(密码|UUID|GUID|数字|编号|颜色|姓名|邮箱|地址|IP)', 10),
            (r'(计算|算).*(利率|利息|月供|贷款|BMI|面积|体积|百分比|折扣|小费)', 10),
            (r'(验证|检查|校验|检测).*(邮箱|URL|密码|JSON|IP|正则|格式)', 10),
            (r'(格式化|美化|压缩).*(JSON|代码|文本|HTML|CSS)', 5),
            (r'(编码|解码).*(Base64|URL|HTML|Unicode)', 5),
            (r'(PDF|CSV|XML|HTML).*(转|处理|分析|格式化)', 5),
            (r'(SHA|MD5|哈希|Hash).*(生成|计算)', 5),
            (r'(颜色|调色板|Color|Palette).*(生成|创建)', 5),
            (r'(Emoji|表情).*(生成|随机)', 5),
        ]

        for pattern, pts in computable:
            if re.search(pattern, text):
                score += pts

        return min(score, self.weights["has_computation_path"])

    def score_language_quality(self, text: str) -> int:
        """评估语言质量 — 命名是否像正常工具名"""
        text_lower = text.lower()

        score = self.weights["language_quality"]  # 起始满分

        # 扣分项
        # 超长句子 (像新闻标题而不像工具名)
        words = text.split()
        if len(words) > 12:
            score -= 6
        elif len(words) > 8:
            score -= 3

        # 中英混杂但无明显技术词
        has_cn = bool(re.search(r'[\u4e00-\u9fff]', text))
        has_en = bool(re.search(r'[a-zA-Z]{3,}', text))
        if has_cn and has_en and not self.tech_keywords.search(text):
            score -= 4

        # 带媒体来源标识
        if re.search(r'[-–—]\s*(the |wsj|bbc|cnn|reuters)', text_lower):
            score -= 5

        # 商品规格描述
        for pattern in self.product_patterns:
            if pattern.search(text_lower):
                score -= 5
                break

        return max(0, score)

    # ══════════════════════════════════════════════════════════
    # 意图分类
    # ══════════════════════════════════════════════════════════

    def get_intent(self, text: str) -> str:
        """识别意图类型"""
        text_lower = text.lower()

        # Calculator意图
        calc_signals = sum(1 for kw in ['计算', '算', '换算', '转换', '率', 'calculator'] if kw in text_lower)
        if calc_signals >= 2 or ('计算' in text_lower and any(kw in text_lower for kw in ['贷款', '利率', 'BMI', '利息', '月供', '面积', '体积', '百分比', '折扣', '小费'])):
            return "calculator"

        # Checker意图
        check_signals = sum(1 for kw in ['验证', '检测', '检查', '校验', '测试', '是否', '格式', '合规', '有效性'] if kw in text_lower)
        if check_signals >= 2:
            return "checker"

        # Generator意图
        gen_signals = sum(1 for kw in ['生成', '创建', '产生', '随机', 'generator', 'generate'] if kw in text_lower)
        if gen_signals >= 1:
            return "generator"

        # 有技术名词的默认generator
        if self.tech_keywords.search(text) and ('生成' in text_lower or 'create' in text_lower or 'gen' in text_lower):
            return "generator"

        # Converter
        if any(kw in text_lower for kw in ['转', '转换', 'convert', '编码', '解码', 'encode', 'decode']):
            return "calculator"

        # 默认
        return "generator"

    # ══════════════════════════════════════════════════════════
    # 主分类接口
    # ══════════════════════════════════════════════════════════

    def classify(self, text: str) -> dict:
        """
        对需求文本做多维打分分类

        返回:
          {
            "pass": bool,
            "score": int,
            "verdict": "PASS" | "BLOCK" | "WARN",
            "intent": "calculator" | "checker" | "generator" | "script" | "garbage",
            "canonical_name": str | None,
            "scores_detail": {dimension: score, ...},
            "reasons": [str, ...]
          }
        """
        if not text or not isinstance(text, str) or len(text.strip()) < 2:
            return {
                "pass": False, "score": 0, "verdict": "BLOCK",
                "intent": "garbage", "canonical_name": None,
                "scores_detail": {}, "reasons": ["输入为空或过短"]
            }

        text = text.strip()

        # ── 多维打分 ──
        scores = {
            "data_closure": self.score_data_closure(text),
            "tool_noun": self.score_tool_noun(text),
            "positive_match": self.score_positive_match(text),
            "negative_match": self.score_negative_match(text),
            "news_headline": self.score_news_headline(text),
            "social_chatter": self.score_social_chatter(text),
            "celebrity_gossip": self.score_celebrity_gossip(text),
            "personal_statement": self.score_personal_statement(text),
            "computation_path": self.score_computation_path(text),
            "language_quality": self.score_language_quality(text),
        }

        total = sum(scores.values())
        threshold = self.weights["threshold_pass"]

        # 硬性否决（以下情况无论总分多少都拒绝）
        # 惩罚分数 < 0 说明匹配到了否定模式
        reasons = []
        hard_block = False
        if scores["celebrity_gossip"] < 0:
            hard_block = True
            reasons.append("名人八卦/娱乐内容")
        if scores["social_chatter"] < 0:
            hard_block = True
            reasons.append("社交闲聊句式")
        if scores["personal_statement"] < 0:
            hard_block = True
            reasons.append("个人陈述/情感表达")
        if scores["news_headline"] < 0:
            hard_block = True
            reasons.append("新闻标题/媒体内容")

        # 门槛判定
        if total >= threshold and not hard_block:
            verdict = "PASS"
            intent = self.get_intent(text)
        elif total >= threshold * 0.6 and not hard_block:
            verdict = "WARN"
            intent = self.get_intent(text)
        else:
            verdict = "BLOCK"
            intent = "garbage"
            if not reasons:
                if total < threshold * 0.6:
                    reasons.append(f"多维评分 {total} 低于门槛 {int(threshold * 0.6)}")
                else:
                    reasons.append("综合评估不合格")

        # ── 生成规范名称 ──
        canonical_name = None
        if verdict in ("PASS", "WARN"):
            canonical_name = self._generate_canonical_name(text, intent)

        return {
            "pass": verdict != "BLOCK",
            "score": total,
            "verdict": verdict,
            "intent": intent,
            "canonical_name": canonical_name,
            "scores_detail": scores,
            "reasons": reasons if reasons else ["通过多维判定"],
        }

    def _generate_canonical_name(self, text: str, intent: str) -> str:
        """根据意图生成规范工具名"""
        text_lower = text.lower()

        if intent == "calculator":
            # 从文本中提取计算对象
            calc_objects = {
                "贷款": "贷款计算器", "公积金": "公积金贷款计算器",
                "房贷": "房贷月供计算器", "月供": "月供计算器",
                "利息": "利息计算器", "利率": "利率计算器",
                "BMI": "BMI计算器", "bmi": "BMI计算器",
                "身体质量": "BMI身体质量指数计算器",
                "百分比": "百分比计算器", "比例": "比例计算器",
                "折扣": "折扣计算器", "小费": "小费分摊计算器",
                "面积": "面积计算器", "体积": "体积计算器",
                "单位": "单位换算器", "换算": "单位换算器",
                "温度": "温度转换器", "长度": "长度换算器",
                "重量": "重量换算器", "汇率": "汇率换算器",
                "编码": "Base64编解码器", "解码": "Base64编解码器",
                "base64": "Base64编解码器",
            }
            for kw, name in calc_objects.items():
                if kw in text_lower:
                    return name
            # 从文本末尾提取关键词
            words = text.replace(" ", "").replace("-", "").replace("_", "")
            match = re.search(r'[\u4e00-\u9fff]{2,4}(计算|换算|转换)', words)
            if match:
                return match.group()
            return f"多功能计算器"

        elif intent == "checker":
            check_objects = {
                "JSON": "JSON格式验证器", "json": "JSON格式验证器",
                "邮箱": "邮箱格式验证器", "email": "邮箱格式验证器",
                "邮件": "邮箱格式验证器", "mail": "邮箱格式验证器",
                "URL": "URL链接验证器", "url": "URL链接验证器",
                "网址": "网址格式验证器", "链接": "链接验证器",
                "密码": "密码强度检测器", "password": "Password Strength Checker",
                "口令": "密码强度检测器",
                "IP": "IP地址验证器", "ip": "IP地址验证器",
                "正则": "正则表达式测试器", "regex": "正则表达式测试器",
                "格式": "格式验证器", "合规": "合规检测器",
            }
            for kw, name in check_objects.items():
                if kw in text_lower:
                    return name
            return f"数据格式验证器"

        elif intent == "generator":
            gen_objects = {
                "密码": "安全密码生成器", "password": "安全密码生成器",
                "UUID": "UUID生成器", "uuid": "UUID生成器", "GUID": "UUID生成器",
                "颜色": "颜色调色板生成器", "color": "颜色调色板生成器",
                "调色板": "颜色调色板生成器", "palette": "颜色调色板生成器",
                "数字": "数字生成器", "number": "数字生成器",
                "姓名": "姓名生成器", "名字": "姓名生成器", "name": "姓名生成器",
                "邮箱": "邮箱地址生成器", "email": "邮箱地址生成器",
                "日期": "日期生成器", "date": "日期生成器",
                "IP": "IP地址生成器", "ip address": "IP地址生成器",
                "地址": "地址生成器",
                "Emoji": "Emoji表情生成器", "emoji": "Emoji表情生成器",
                "表情": "Emoji表情生成器",
                "Hex": "十六进制生成器", "hex": "十六进制生成器",
                "哈希": "哈希值生成器", "SHA": "哈希值生成器",
                "单词": "随机单词生成器", "word": "随机单词生成器",
                "代码": "代码片段生成器", "code": "代码片段生成器",
                "URL": "URL生成器", "链接": "URL生成器",
                "短链接": "短链接生成器",
            }
            for kw, name in gen_objects.items():
                if kw in text_lower:
                    return name
            return f"数据生成器"

        elif intent == "script":
            script_objects = {
                "CSV": "CSV数据分析工具", "csv": "CSV数据分析工具",
                "JSON格式化": "JSON格式化工具",
                "文本": "文本处理工具", "text": "文本处理工具",
                "文件": "文件整理工具", "整理": "文件整理工具",
                "加密": "加密哈希工具", "哈希": "加密哈希工具",
                "密码生成": "安全密码生成器",
            }
            for kw, name in script_objects.items():
                if kw in text_lower:
                    return name
            return f"数据处理脚本"

        return text.strip()

    # ══════════════════════════════════════════════════════════
    # 批量分类 + 名称重生成
    # ══════════════════════════════════════════════════════════

    def classify_batch(self, texts: list) -> list:
        """批量分类"""
        return [self.classify(str(t)) for t in texts]

    def regenerate_name(self, name: str, name_zh: str = "", tool_id: str = "") -> str:
        """
        为存量工具重新生成规范名称
        规则：
        1. 去掉 "Random " 前缀
        2. 去掉无意义后缀 " Generator" / " 生成器"（除非是真正的生成器）
        3. 根据模板类型选择合适的后缀
        """
        cleaned = name.strip()
        original = cleaned

        # 1. 去Random前缀
        cleaned = re.sub(r'^Random\s+', '', cleaned, flags=re.IGNORECASE).strip()

        # 2. 提取核心关键词
        # 如果cleaned太短或只剩数字/符号，保留原名
        if len(cleaned) < 2:
            return original

        # 3. 分类这个名称
        result = self.classify(cleaned)

        if result["verdict"] == "BLOCK":
            # 这是垃圾名，需要从数据库清理
            return f"[需清理] {cleaned}"
        elif result["canonical_name"]:
            return result["canonical_name"]

        # 4. 用name_zh辅助判断
        if name_zh:
            zh_result = self.classify(name_zh)
            if zh_result["canonical_name"]:
                return zh_result["canonical_name"]

        return cleaned


# ══════════════════════════════════════════════════════════
# 自检
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    ic = IntentClassifier()

    test_cases = [
        # ✅ 应该是PASS的工具需求
        ("如何计算公积金贷款", True),
        ("怎么验证JSON格式", True),
        ("PDF转Word转换器", True),
        ("随机密码生成工具", True),
        ("BMI身体质量指数计算器", True),
        ("CSV数据分析工具", True),
        ("UUID生成器", True),
        ("房贷月供计算器", True),
        ("Base64编码解码器", True),
        ("颜色调色板生成器", True),
        ("正则表达式测试器", True),
        ("单位换算器 温度长度重量", True),
        ("图片压缩工具", True),
        ("SHA256哈希生成器", True),
        ("小费分摊计算器 AA制", True),

        # 🚫 应该是BLOCK的垃圾
        ("男子煮粽子时狗狗狂叫 30秒后惊呆", False),
        ("我要给 glm5 道歉", False),
        ("高估了 gpt5 能力", False),
        ("雷军说当初不该和董明珠打赌", False),
        ("张靓颖清唱太多被罚款", False),
        ("龙舟经济火爆", False),
        ("爸爸不收红包是全国统一的吗", False),
        ("Codex 降智降麻了 听说 23 要上线了", False),
        ("理性女儿 × 感性爸爸 父亲节温情喜剧", False),
        ("现在 apple 礼品卡哪些区可以正常开通的", False),
        ("给一张照片然后直接用自己动作和表情来生成这个角色的视频 这个怎么实现的", False),
        ("Ai 算力大模型优逆讨论", False),
        ("America's savings rate has plunged - the economist", False),
        ("Depop unisex nails", False),
        ("Cape verde fan goes wild live on bbc news as his country scores", False),
        ("Toy story scores record opening weekend for franchise", False),
        ("Bounty paper towels quick size white 16 family rolls = 40 regular rolls", False),
        ("出易盾协议源码 通杀所有类型验证码", False),
        ("Crazy fruit shooter", False),
        ("最新突发新闻快讯", False),
    ]

    passed = 0
    failed = 0

    print(f"{'='*70}")
    print(f"🧪 意图分类器自检 - {len(test_cases)} 个测试用例")
    print(f"{'='*70}\n")

    for text, expected_pass in test_cases:
        result = ic.classify(text)
        actual_pass = result["pass"]
        status = "✅" if actual_pass == expected_pass else "❌"

        if actual_pass == expected_pass:
            passed += 1
        else:
            failed += 1

        detail = f"score={result['score']:3d} | {result['verdict']:5s} | {result['intent']:10s}"
        if result.get("canonical_name"):
            detail += f" | → '{result['canonical_name']}'"

        if actual_pass != expected_pass:
            print(f"{status} MISMATCH | 期望={'PASS' if expected_pass else 'BLOCK'} | {detail}")
            print(f"   文本: '{text[:80]}'")
            if result.get("reasons"):
                print(f"   原因: {result['reasons']}")
            print(f"   分项: {result['scores_detail']}")
            print()

    total = passed + failed
    print(f"\n{'='*70}")
    print(f"📊 自检结果: {passed}/{total} 通过", end="")
    if failed == 0:
        print(" 🎉 全部通过！")
    else:
        print(f" ({failed} 失败)")
    print(f"{'='*70}")
