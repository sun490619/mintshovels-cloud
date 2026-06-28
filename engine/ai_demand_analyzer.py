#!/usr/bin/env python3
"""
MintShovels AI 需求分析器 — 关口①
=====================================
替代硬编码 KEYWORD_TOOL_MAP，用 AI 理解原始信号，
提取具体、新颖的工具需求描述。

核心能力:
  1. 从模糊信号中提取"用户到底想要什么"
  2. 区分工具型需求 vs 知识/方法型需求
  3. 生成具体的工具名称、功能描述、技术参数
  4. 评估需求的可行性和价值

用法:
  from engine.ai_demand_analyzer import AIDemandAnalyzer
  analyzer = AIDemandAnalyzer()
  results = analyzer.analyze_signals(tool_signals[:30])
  # → [{"name": "...", "name_zh": "...", "desc": "...", "type": "tool"|"knowledge", ...}, ...]
"""

import json
import os
import re
import sys
import time
from typing import Optional, Dict, Any, List

# 导入 AI 客户端
ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE_DIR)

try:
    from ai_client import get_client, AIClient
except ImportError:
    get_client = None
    AIClient = None

REPORT_DIR = os.path.join(os.path.dirname(ENGINE_DIR), "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

# ─── 辅助函数 ───────────────────────────────────────────────────────

def _clean_word(word: str) -> str:
    """清理词干，移除连字符和数字后缀，保留核心英文词"""
    w = word.strip('-').strip()
    # 移除末尾数字（如 "scraper2" → "scraper"）
    w = re.sub(r'\d+$', '', w)
    return w

# ─── AI 驱动需求分析 ───────────────────────────────────────────────

class AIDemandAnalyzer:
    """
    AI 需求分析器 — 关口①
    用 AI 理解原始信号，提取具体工具需求
    """
    
    def __init__(self):
        self.client = get_client() if get_client else None
    
    @property
    def available(self) -> bool:
        """AI 是否可用"""
        if not self.client:
            return False
        return (self.client.ollama_available() or 
                self.client.gemini_available() or 
                self.client.openai_available() or 
                self.client.claude_available())
    
    def analyze_signals(self, signals: List[str], max_results: int = 15) -> list:
        """
        分析一批原始信号，提取具体工具需求
        
        Args:
            signals: 原始文本信号列表（已通过闲聊过滤的工具相关信号）
            max_results: 最多返回多少条需求
        
        Returns:
            [{"name": "English Tool Name", "name_zh": "中文工具名", 
              "desc": "功能描述", "type": "tool"|"knowledge",
              "category": "dev"|"media"|"finance"|..., 
              "subcat": "generator"|"checker"|"...",
              "priority": 1-10, "source_signal": "原始信号文本"}, ...]
        """
        if not signals and max_results < 1:
            return []
        
        if not self.available:
            print("  ⚠️ AI 不可用，回退到关键词规则分析")
            return self._rule_based_analysis(signals[:max_results*2], max_results)
        
        # 分批处理（每批最多25条信号，避免token溢出）
        all_results = []
        batch_size = 25
        for i in range(0, min(len(signals), max_results * 3), batch_size):
            batch = signals[i:i+batch_size]
            if not batch:
                break
            
            results = self._ai_analyze_batch(batch)
            all_results.extend(results)
            
            if len(all_results) >= max_results * 2:
                break
        
        # 去重排序
        return self._dedup_and_rank(all_results, max_results)
    
    def _ai_analyze_batch(self, signals: List[str]) -> list:
        """用 AI 分析一批信号"""
        system_prompt = """你是一个技术需求分析专家。你的任务是从互联网讨论中识别出具体的工具需求。

对于每条值得关注的信号，返回一个 JSON 对象，包含:

{
  "name": "英文工具名 (2-4个词, PascalCase)",
  "name_zh": "中文工具名 (4-8个字)",
  "desc": "一句话功能描述 (英文, 15-30词)",
  "type": "tool 还是 knowledge",
  "category": "分类: dev/media/finance/productivity/ai/misc",
  "subcat": "子类: generator/checker/calculator/converter/editor/scraper/analyzer/downloader/formatter/tracker/knowledge/misc",
  "priority": 1-10 (10=最高优先级, 基于需求明确度和可行性),
  "reason": "为什么这是有价值的工具需求 (一句话)"
}

规则:
1. type="tool": 可以用一个交互式网页工具解决的问题（输入→处理→输出）
2. type="knowledge": 方法/教程/方案类型的问题（不是工具，但可以生成解决指南）
3. 只返回真正有具体需求的条目，忽略空洞或泛泛的内容
4. name 要具体，不要 "Generator Tool" 这种泛称
5. 如果某条信号不包含明确工具需求，跳过它

请只返回 JSON 数组，格式: [{{...}}, {{...}}]"""

        # 构建用户消息
        signals_text = "\n".join(f"[{j+1}] {s[:200]}" for j, s in enumerate(signals))
        
        user_message = f"""请分析以下互联网讨论片段，找出其中的具体工具需求。

{signals_text}

请返回 JSON 数组，每个元素一个需求对象。只返回有价值的需求，忽略无需求的信号。"""

        try:
            response = self.client.light_chat(system_prompt, user_message, expect_json=True)
            if not response or response == "{}":
                return []
            
            results = json.loads(response)
            if not isinstance(results, list):
                results = [results]
            
            # 关联原始信号
            valid_results = []
            for r in results:
                if not isinstance(r, dict):
                    continue
                name = r.get("name", "").strip()
                name_zh = r.get("name_zh", "").strip()
                if not name or len(name) < 3:
                    continue
                
                valid_results.append({
                    "name": self._clean_name(name),
                    "name_zh": name_zh or self._name_to_cn(name),
                    "desc": r.get("desc", f"{name} - AI recommended tool"),
                    "type": r.get("type", "tool"),
                    "category": r.get("category", "misc"),
                    "subcat": r.get("subcat", "misc"),
                    "priority": min(10, max(1, r.get("priority", 5))),
                    "reason": r.get("reason", "AI分析需求"),
                    "ai_generated": True,
                })
            
            return valid_results
            
        except json.JSONDecodeError as e:
            print(f"  ⚠️ AI 返回非JSON: {e}")
            return []
        except Exception as e:
            print(f"  ⚠️ AI 分析异常: {e}")
            return []
    
    def _rule_based_analysis(self, signals: List[str], max_results: int) -> list:
        """无 AI 时的规则分析回退（比旧版查表强）"""
        import re
        
        results = []
        seen_names = set()
        
        # 智能关键词→工具名映射 (编译为正则对象，顺序很重要：具体模式在前)
        # 策略: (\w[\w-]*) 贪婪匹配前缀词, [\s-]+ 强制至少一个分隔符
        patterns = [
            # --- 转换类①: "convert Foo to Bar" ---
            (re.compile(r'convert\s+(\w+)\s+(?:to|2)\s+(\w+)', re.I),
             lambda m: f"{m.group(1).title()} to {m.group(2).title()} Converter",
             lambda m: f"{m.group(1).upper()}转{m.group(2).upper()}",
             "media", "converter"),
            
            # --- 转换类②: "Foo to Bar Converter" ---
            (re.compile(r'(\w+)\s+(?:to|2)\s+(\w+)', re.I),
             lambda m: f"{m.group(1).title()} to {m.group(2).title()} Converter",
             lambda m: f"{m.group(1).upper()}转{m.group(2).upper()}",
             "media", "converter"),
            
            # --- 仪表盘/面板 (先匹配，比单词后缀更具体) ---
            (re.compile(r'(\w[\w-]*)[\s-]+(?:dashboard|panel)', re.I),
             lambda m: f"{_clean_word(m.group(1)).title()} Dashboard",
             lambda m: f"{_clean_word(m.group(1)).title()}仪表盘",
             "productivity", "dashboard"),
            
            # --- 生成器 ---
            (re.compile(r'(\w[\w-]*)[\s-]+(?:gen(?:erator)?|generat)', re.I),
             lambda m: f"{_clean_word(m.group(1)).title()} Generator",
             lambda m: f"{_clean_word(m.group(1)).title()}生成器",
             "misc", "generator"),
             
            # --- 检测/验证 ---
            (re.compile(r'(\w[\w-]*)[\s-]+(?:check(?:er)?|valid(?:ator)?|test(?:er)?|scann(?:er)?|detect(?:or)?)', re.I),
             lambda m: f"{_clean_word(m.group(1)).title()} Checker",
             lambda m: f"{_clean_word(m.group(1)).title()}检测器",
             "dev", "checker"),
             
            # --- 计算器 ---
            (re.compile(r'(\w[\w-]*)[\s-]+(?:calc(?:ulator)?|comput)', re.I),
             lambda m: f"{_clean_word(m.group(1)).title()} Calculator",
             lambda m: f"{_clean_word(m.group(1)).title()}计算器",
             "misc", "calculator"),
             
            # --- 分析/解析 ---
            (re.compile(r'(\w[\w-]*)[\s-]+(?:analyz(?:er)?|pars(?:er)?)', re.I),
             lambda m: f"{_clean_word(m.group(1)).title()} Analyzer",
             lambda m: f"{_clean_word(m.group(1)).title()}分析器",
             "dev", "analyzer"),
             
            # --- 抓取 ---
            (re.compile(r'(\w[\w-]*)[\s-]+(?:scrap(?:er)?|crawl(?:er)?)', re.I),
             lambda m: f"{_clean_word(m.group(1)).title()} Scraper",
             lambda m: f"{_clean_word(m.group(1)).title()}抓取器",
             "dev", "scraper"),
             
            # --- 追踪/监控 ---
            (re.compile(r'(\w[\w-]*)[\s-]+(?:track(?:er)?|monitor)', re.I),
             lambda m: f"{_clean_word(m.group(1)).title()} Tracker",
             lambda m: f"{_clean_word(m.group(1)).title()}追踪器",
             "productivity", "tracker"),
             
            # --- 下载 ---
            (re.compile(r'(\w[\w-]*)[\s-]+(?:download(?:er)?)', re.I),
             lambda m: f"{_clean_word(m.group(1)).title()} Downloader",
             lambda m: f"{_clean_word(m.group(1)).title()}下载器",
             "media", "downloader"),
             
            # --- 格式化/美化 ---
            (re.compile(r'(\w[\w-]*)[\s-]+(?:format(?:ter)?|beautif(?:ier)?|minif(?:ier)?)', re.I),
             lambda m: f"{_clean_word(m.group(1)).title()} Formatter",
             lambda m: f"{_clean_word(m.group(1)).title()}格式化工具",
             "dev", "formatter"),
            
            # --- 优化/压缩 ---
            (re.compile(r'(\w[\w-]*)[\s-]+(?:optimiz(?:er)?|compress(?:or)?)', re.I),
             lambda m: f"{_clean_word(m.group(1)).title()} Optimizer",
             lambda m: f"{_clean_word(m.group(1)).title()}优化器",
             "dev", "optimizer"),
            
            # --- 编辑器 ---
            (re.compile(r'(\w[\w-]*)[\s-]+(?:editor|edit)', re.I),
             lambda m: f"{_clean_word(m.group(1)).title()} Editor",
             lambda m: f"{_clean_word(m.group(1)).title()}编辑器",
             "dev", "editor"),
        ]
        
        for signal in signals:
            if not signal or len(signal) < 5:
                continue
            
            for pat, name_fn, zh_fn, cat, subcat in patterns:
                found = False
                for m in pat.finditer(signal):
                    raw_word = m.group(1).lower()
                    # 过滤掉无意义的占位词
                    stop_words = {'a', 'an', 'the', 'tool', 'need', 'want', 'best', 
                                 'new', 'free', 'simple', 'basic', 'use', 'using',
                                 'make', 'get', 'how', 'what', 'why', 'show', 'hn',
                                 'just', 'like', 'can', 'this', 'that', 'with', 'for',
                                 'build', 'built', 'is', 'it', 'be', 'of', 'in', 'on',
                                 'or', 'and', 'to', 'from', 'very', 'really', 'good'}
                    if raw_word in stop_words or len(raw_word) < 3:
                        continue
                    
                    name = name_fn(m)
                    if name not in seen_names and len(name) < 50:
                        seen_names.add(name)
                        results.append({
                            "name": self._clean_name(name),
                            "name_zh": zh_fn(m),
                            "desc": f"基于信号分析的{cat}工具",
                            "type": "tool",
                            "category": cat,
                            "subcat": subcat,
                            "priority": 3,
                            "reason": f"规则匹配",
                            "ai_generated": False,
                        })
                        found = True
                        break
                if found:
                    break
            
            if len(results) >= max_results:
                break
        
        return results[:max_results]
    
    def _dedup_and_rank(self, results: list, max_results: int) -> list:
        """去重并按优先级排序"""
        seen_names = set()
        unique = []
        for r in sorted(results, key=lambda x: -x.get("priority", 5)):
            name_lower = r["name"].lower()
            if name_lower not in seen_names:
                seen_names.add(name_lower)
                unique.append(r)
        return unique[:max_results]
    
    def _clean_name(self, name: str) -> str:
        """清理工具名"""
        import re
        # 去掉引号
        name = name.strip('"\'')
        # 确保首字母大写
        words = name.split()
        name = " ".join(w[0].upper() + w[1:] if w else w for w in words)
        # 限制长度
        return name[:60]
    
    def _name_to_cn(self, name: str) -> str:
        """简单英文→中文工具名转换"""
        translations = {
            "generator": "生成器", "checker": "检测器", "calculator": "计算器",
            "converter": "转换器", "editor": "编辑器", "viewer": "查看器",
            "downloader": "下载器", "extractor": "提取器", "analyzer": "分析器",
            "scraper": "抓取器", "formatter": "格式化工具", "tracker": "追踪器",
            "validator": "验证器", "compressor": "压缩器", "encoder": "编码器",
            "decoder": "解码器", "optimizer": "优化器", "monitor": "监控器",
            "manager": "管理器", "builder": "构建器", "creator": "创建器",
            "scanner": "扫描器", "timer": "计时器", "counter": "计数器",
            "merger": "合并器", "splitter": "分割器", "translator": "翻译器",
            "summarizer": "摘要器", "resizer": "缩放器", "renamer": "重命名器",
        }
        
        name_lower = name.lower()
        for en, zh in translations.items():
            if en in name_lower:
                base = name_lower.replace(en, "").strip()
                if base:
                    return f"{base.title()}{zh}"
                return f"{zh}"
        return name


# ─── 知识/方案型需求处理 ──────────────────────────────────────────

def analyze_for_knowledge_content(signals: List[str], client=None) -> list:
    """
    从信号中识别知识/方法型需求（非工具型）
    返回方案/教程页面的内容描述
    """
    if not signals:
        return []
    
    # 先用规则过滤明显是 chatty/非知识型的内容
    import re
    knowledge_signals = []
    for s in signals:
        if not s or len(s) < 10:
            continue
        # how to, 怎么, 如何 等知识型信号
        if re.search(r'(how\s+to|怎么|如何|方法|技巧|best\s+practice|tutorial|guide)', s, re.I):
            knowledge_signals.append(s[:300])
    
    if not knowledge_signals:
        return []
    
    if not client:
        try:
            from ai_client import get_client
            client = get_client()
        except ImportError:
            pass
    
    if not client or not (client.ollama_available() or client.gemini_available()):
        return _rule_knowledge_analysis(knowledge_signals[:10])
    
    system_prompt = """你是技术方案分析师。从以下讨论中提取可以写成教程/指南的知识型内容。

返回 JSON 数组:
[{
  "title": "教程标题",
  "title_zh": "中文标题",
  "summary": "2-3句话摘要",
  "tags": ["tag1", "tag2"],
  "difficulty": "beginner/intermediate/advanced"
}]

只返回真正的教程/指南级别的需求，忽略简单问题。"""

    signals_text = "\n".join(f"[{j+1}] {s}" for j, s in enumerate(knowledge_signals[:20]))
    
    try:
        response = client.light_chat(
            system_prompt,
            f"以下讨论中哪些可以写成教程？\n\n{signals_text}",
            expect_json=True
        )
        if response and response != "{}":
            results = json.loads(response)
            if isinstance(results, list):
                return results
    except Exception:
        pass
    
    return _rule_knowledge_analysis(knowledge_signals[:10])


def _rule_knowledge_analysis(signals: list) -> list:
    """规则回退：识别知识型需求"""
    import re
    results = []
    for s in signals:
        s = s.strip()
        if len(s) < 15:
            continue
        
        # 提取核心主题
        topic = re.sub(r'how\s+to\s+', '', s, flags=re.I)
        topic = re.sub(r'[怎么|如何|方法|技巧]', '', topic)
        topic = topic.strip(" ?？")[:80]
        
        if topic:
            results.append({
                "title": f"How to {topic}",
                "title_zh": f"{topic}方法指南",
                "summary": topic,
                "tags": ["tutorial"],
                "difficulty": "intermediate"
            })
    
    return results[:5]


# ─── 自检 ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    analyzer = AIDemandAnalyzer()
    print("=== AI Demand Analyzer 自检 ===")
    print(f"  AI 可用: {'✅' if analyzer.available else '❌ (回退规则模式)'}")
    
    test_signals = [
        "I replaced $500/mo in freelance tools with 20 ChatGPT prompts — featured on Hacker News",
        "Show HN: I built a CLI tool that converts any website to a clean Markdown file",
        "How to optimize React app bundle size — dev.to article",
        "What's the best tool for bulk image compression? I have 5000 product photos",
        "Need a simple online JSON to CSV converter that handles nested objects",
        "Someone explain how to set up Cloudflare Workers with custom domains please",
        "python package: fastapi-sqlmodel-crud — CRUD generator for FastAPI + SQLModel",
        "github trending topic: gemini-code-assist",
    ]
    
    print(f"\n  测试信号: {len(test_signals)} 条")
    results = analyzer.analyze_signals(test_signals, max_results=8)
    
    print(f"\n  分析结果: {len(results)} 个需求")
    for i, r in enumerate(results):
        ai_badge = "🧠" if r.get("ai_generated") else "📋"
        print(f"  {ai_badge} [{r['priority']}/10] {r['name']} ({r['name_zh']})")
        print(f"      [{r['category']}/{r['subcat']}] {r.get('desc', '')[:60]}")
    
    print("\n✅ 自检完成")
