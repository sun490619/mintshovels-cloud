#!/usr/bin/env python3
"""
MintShovels AI 客户端 — 统一接口，多层模型调度
================================================
支持:
  - Ollama 本地模型（免费，轻任务首选）
  - DeepSeek API（极便宜 ~0.14元/百万token，重任务主力）
  - Google Gemini API（免费额度，中等任务）
  - HuggingFace Inference API（免费，终极兜底）
  - OpenAI API（付费，重任务备选）
  - Anthropic Claude API（付费，代码生成备选）

分层策略（2026-06-27 更新，免费优先、花钱兜底）:
  关口① 需求分析: Ollama(本地免费) → Gemini(免费) → HuggingFace(免费) → DeepSeek(0.14元/M) → 规则回退
  关口② 代码生成: Gemini(免费) → HuggingFace StarCoder2(免费) → Ollama(免费) → DeepSeek(付费保底)
  关口③ 质量验证: Ollama(本地免费) → Gemini(免费) → HuggingFace(免费) → DeepSeek(0.14元/M) → 规则回退
"""

import json
import os
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any

# ─── 加载 .env 文件 ───────────────────────────────────────────────

def _load_dotenv(env_path: str = None):
    """简易 .env 加载器，不依赖 python-dotenv"""
    if env_path is None:
        # 从当前文件向上查找 .env
        candidates = [
            Path(__file__).resolve().parent.parent / ".env",  # engine/..  = 项目根
            Path.cwd() / ".env",
        ]
        env_path = None
        for c in candidates:
            if c.exists():
                env_path = str(c)
                break
    if not env_path or not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # 跳过空行和注释
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            # 去掉引号
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            if key and value and key not in os.environ:
                os.environ[key] = value

_load_dotenv()

# ─── 配置 ─────────────────────────────────────────────────────────

# 从环境变量读取 API Key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
HUGGINGFACE_API_KEY = os.environ.get("HUGGINGFACE_API_KEY", "")

# Google Gemini 模型（从环境变量读取，默认 2.0 flash）
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

# 本地请求禁用代理（macOS 可能拦截 localhost）
LOCAL_PROXIES = {"http": None, "https": None}

# DeepSeek 配置
DEEPSEEK_BASE = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"

# HuggingFace 配置
HF_BASE = "https://api-inference.huggingface.co"
HF_LIGHT_MODEL = "mistralai/Mixtral-8x7B-Instruct-v0.1"   # 通用轻任务
HF_HEAVY_MODEL = "bigcode/starcoder2-15b"                   # 代码生成专项

# 超时配置
LIGHT_TIMEOUT = 60     # 轻任务超时
HEAVY_TIMEOUT = 180    # 代码生成超时

# ─── 核心接口 ─────────────────────────────────────────────────────

class AIClient:
    """统一 AI 调用接口 — 四路资源智能调度"""
    
    def __init__(self):
        self._ollama_available = None
        self._openai_available = None
        self._claude_available = None
        self._gemini_available = None
        self._deepseek_available = None
        self._huggingface_available = None
    
    # ── 可用性检测 ──
    
    def ollama_available(self) -> bool:
        if self._ollama_available is None:
            try:
                r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5, proxies=LOCAL_PROXIES)
                if r.status_code == 200:
                    models = [m["name"] for m in r.json().get("models", [])]
                    self._ollama_available = any(OLLAMA_MODEL.split(":")[0] in m for m in models)
                else:
                    self._ollama_available = False
            except Exception:
                self._ollama_available = False
        return self._ollama_available
    
    def openai_available(self) -> bool:
        if self._openai_available is None:
            self._openai_available = bool(OPENAI_API_KEY)
        return self._openai_available
    
    def claude_available(self) -> bool:
        if self._claude_available is None:
            self._claude_available = bool(ANTHROPIC_API_KEY)
        return self._claude_available
    
    def gemini_available(self) -> bool:
        if self._gemini_available is None:
            self._gemini_available = bool(GEMINI_API_KEY)
        return self._gemini_available
    
    def deepseek_available(self) -> bool:
        if self._deepseek_available is None:
            self._deepseek_available = bool(DEEPSEEK_API_KEY)
        return self._deepseek_available
    
    def huggingface_available(self) -> bool:
        if self._huggingface_available is None:
            self._huggingface_available = bool(HUGGINGFACE_API_KEY)
        return self._huggingface_available
    
    # ── 轻任务：需求分类/质量验证 ──
    #  优先级: Ollama(本地免费) → Gemini(免费额度) → HuggingFace(免费API) → DeepSeek(廉价保底)
    
    def light_chat(self, system_prompt: str, user_message: str, 
                   expect_json: bool = False) -> str:
        """
        轻任务调用（免费优先，自动降级）
        """
        # 1) Ollama 本地免费（hermes3 8B 足够应付轻任务）
        if self.ollama_available():
            try:
                return self._ollama_chat(system_prompt, user_message, expect_json, LIGHT_TIMEOUT)
            except Exception:
                print("  ⚠️  Ollama 失败，降级到 Gemini...")
        
        # 2) Gemini 免费额度
        if self.gemini_available():
            try:
                return self._gemini_chat(system_prompt, user_message, expect_json)
            except Exception:
                print("  ⚠️  Gemini 失败，降级到 HuggingFace...")
        
        # 3) HuggingFace 免费 API
        if self.huggingface_available():
            try:
                return self._huggingface_chat(system_prompt, user_message, expect_json, LIGHT_TIMEOUT, HF_LIGHT_MODEL)
            except Exception:
                print("  ⚠️  HuggingFace 失败，降级到 DeepSeek...")
        
        # 4) DeepSeek 花钱保底
        if self.deepseek_available():
            try:
                print("  💰 免费链路全挂，启用 DeepSeek 付费保底...")
                return self._deepseek_chat(system_prompt, user_message, expect_json, LIGHT_TIMEOUT)
            except Exception:
                print("  ⚠️  DeepSeek 也失败，回退到规则判断...")
        
        # 最终回退：纯规则判断
        return self._rule_fallback(user_message)
    
    # ── 重任务：代码生成 ──
    #  优先级: Ollama(本地免费首试) → Gemini(免费) → HuggingFace StarCoder2(免费) → DeepSeek(付费保底)
    #  每个免费环节都有质量检测，不合格立即跳过，不浪费算力
    
    def _heavy_quality_ok(self, result: str) -> bool:
        """检查生成的代码质量是否过关"""
        if not result or len(result) < 300:
            return False
        # 至少要有基本 HTML 结构或明显的代码特征
        has_html = any(tag in result.lower() for tag in ["<!doctype", "<html", "</html>", "<body", "</body>"])
        has_code = any(tag in result for tag in ["<script", "<style", "function", "const ", "let "])
        return has_html or has_code
    
    def heavy_chat(self, system_prompt: str, user_message: str) -> str:
        """
        重任务调用（免费优先 + 质量把关，不合格自动升级到 DeepSeek）
        """
        # 1) Ollama 本地免费 — 先试，不好立马换
        if self.ollama_available():
            try:
                result = self._ollama_chat(system_prompt, user_message, False, HEAVY_TIMEOUT)
                if self._heavy_quality_ok(result):
                    print("  ✅ Ollama 本地生成，质量过关")
                    return result
                else:
                    print("  ⚠️  Ollama 质量不达标（%d字符），跳过..." % len(result))
            except Exception:
                print("  ⚠️  Ollama 不可用，降级到 Gemini...")
        
        # 2) Gemini 免费额度
        if self.gemini_available():
            try:
                result = self._gemini_chat(system_prompt, user_message, False)
                if self._heavy_quality_ok(result):
                    print("  ✅ Gemini 免费生成，质量过关")
                    return result
                else:
                    print("  ⚠️  Gemini 质量不达标（%d字符），跳过..." % len(result))
            except Exception:
                print("  ⚠️  Gemini 不可用，降级到 HuggingFace...")
        
        # 3) HuggingFace StarCoder2 代码专项免费模型
        if self.huggingface_available():
            try:
                print("  ℹ️  使用 HuggingFace StarCoder2 生成代码（免费）")
                result = self._huggingface_chat(system_prompt, user_message, False, HEAVY_TIMEOUT, HF_HEAVY_MODEL)
                if self._heavy_quality_ok(result):
                    print("  ✅ HuggingFace 免费生成，质量过关")
                    return result
                else:
                    print("  ⚠️  HuggingFace 质量不达标（%d字符），跳过..." % len(result))
            except Exception:
                print("  ⚠️  HuggingFace 不可用，降级到 DeepSeek...")
        
        # 4) DeepSeek 付费保底 — 这都挂了就真没办法了
        if self.deepseek_available():
            try:
                print("  💰 免费都不行，启用 DeepSeek 付费保底...")
                return self._deepseek_chat(system_prompt, user_message, False, HEAVY_TIMEOUT)
            except Exception:
                print("  ⚠️  DeepSeek 也失败了...")
        
        raise RuntimeError("无可用的 AI 模型（所有链路均已尝试失败）")
    
    # ── Ollama ──
    
    def _ollama_chat(self, system: str, user: str, expect_json: bool, timeout: int) -> str:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            "stream": False,
            "options": {"temperature": 0.3 if expect_json else 0.7}
        }
        r = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=timeout, proxies=LOCAL_PROXIES)
        r.raise_for_status()
        content = r.json()["message"]["content"]
        if expect_json:
            content = _extract_json(content)
        return content
    
    # ── OpenAI ──
    
    def _openai_chat(self, system: str, user: str) -> str:
        payload = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            "temperature": 0.7
        }
        try:
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json=payload, timeout=HEAVY_TIMEOUT
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  ❌ OpenAI 调用失败: {e}")
            raise
    
    # ── Anthropic Claude ──
    
    def _claude_chat(self, system: str, user: str) -> str:
        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 8192,
            "system": system,
            "messages": [{"role": "user", "content": user}]
        }
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                },
                json=payload, timeout=HEAVY_TIMEOUT
            )
            r.raise_for_status()
            return r.json()["content"][0]["text"]
        except Exception as e:
            print(f"  ❌ Claude 调用失败: {e}")
            raise
    
    # ── Google Gemini ──
    
    def _gemini_chat(self, system: str, user: str, expect_json: bool) -> str:
        combined = f"{system}\n\n{user}"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": combined}]}],
            "generationConfig": {"temperature": 0.3 if expect_json else 0.7}
        }
        r = requests.post(url, json=payload, timeout=LIGHT_TIMEOUT)
        r.raise_for_status()
        content = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        if expect_json:
            content = _extract_json(content)
        return content
    
    # ── DeepSeek (OpenAI 兼容格式) ──
    
    def _deepseek_chat(self, system: str, user: str, expect_json: bool, timeout: int) -> str:
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            "temperature": 0.3 if expect_json else 0.7,
            "max_tokens": 4096
        }
        r = requests.post(
            f"{DEEPSEEK_BASE}/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload, timeout=timeout
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        if expect_json:
            content = _extract_json(content)
        return content
    
    # ── HuggingFace Inference API ──
    
    def _huggingface_chat(self, system: str, user: str, expect_json: bool, 
                          timeout: int, model: str) -> str:
        """HuggingFace 免费 Inference API（chat completion 格式）"""
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            "temperature": 0.3 if expect_json else 0.7,
            "max_tokens": 2048
        }
        
        # 第一次尝试
        r = requests.post(
            f"{HF_BASE}/models/{model}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload, timeout=timeout
        )
        
        # 503 = 模型冷启动加载中，等待后重试一次
        if r.status_code == 503:
            estimated = r.json().get("estimated_time", 30)
            print(f"  ⏳ HuggingFace 模型冷启动中... 等待 {estimated:.0f}s")
            time.sleep(min(estimated, 60))
            r = requests.post(
                f"{HF_BASE}/models/{model}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
                    "Content-Type": "application/json"
                },
                json=payload, timeout=timeout
            )
        
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        if expect_json:
            content = _extract_json(content)
        return content
    
    # ── 纯规则回退 ──
    
    def _rule_fallback(self, text: str) -> str:
        """无 AI 时的纯规则判断（比硬编码查表强点有限）"""
        text_lower = text.lower()
        
        # 工具信号词
        tool_signals = [
            "tool", "generator", "converter", "checker", "calculator",
            "builder", "maker", "creator", "downloader", "manager",
            "tracker", "viewer", "editor", "formatter", "validator",
            "analyzer", "optimizer", "form", "dashboard", "monitor",
            "爬虫", "生成器", "检测器", "转换器", "计算器", "工具"
        ]
        
        score = sum(2 for s in tool_signals if s in text_lower)
        
        # 非工具信号
        non_tool_signals = [
            "how", "why", "what is", "怎么", "如何", "为什么",
            "question", "help", "请帮忙", "求助", "讨论"
        ]
        penalty = sum(2 for s in non_tool_signals if s in text_lower)
        
        final = score - penalty
        result = json.dumps({
            "is_demand": final > 0,
            "score": max(0, final),
            "type": "tool" if final > 2 else "knowledge" if final > 0 else "chatter",
            "reason": f"关键词匹配: +{score} -{penalty}"
        }, ensure_ascii=False)
        return result


# ─── 工具函数 ─────────────────────────────────────────────────────

def _extract_json(text: str) -> str:
    """从 AI 输出中提取 JSON 部分"""
    # 尝试提取 ```json ... ``` 块
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        return text[start:end].strip()
    if "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        return text[start:end].strip()
    # 尝试找 { } 块
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start >= 0 and brace_end > brace_start:
        return text[brace_start:brace_end + 1].strip()
    return text.strip()


# ─── 全局单例 ─────────────────────────────────────────────────────

_client = None

def get_client() -> AIClient:
    global _client
    if _client is None:
        _client = AIClient()
    return _client


# ─── 自检 ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    client = get_client()
    print("=== AI Client 自检 ===")
    print(f"  Ollama:   {'✅' if client.ollama_available() else '❌ 未启动'}  ({OLLAMA_BASE})")
    print(f"  DeepSeek: {'✅' if client.deepseek_available() else '❌ 未配置'}  ({DEEPSEEK_MODEL})")
    print(f"  Gemini:   {'✅' if client.gemini_available() else '❌ 未配置'}")
    print(f"  HF:       {'✅' if client.huggingface_available() else '❌ 未配置'}  ({HF_LIGHT_MODEL.split('/')[-1]})")
    print(f"  OpenAI:   {'✅' if client.openai_available() else '❌ 未配置'}")
    print(f"  Claude:   {'✅' if client.claude_available() else '❌ 未配置'}")
    
    # 测试 light_chat 用到的第一条可用链路
    print(f"\n  🔬 测试 light_chat...")
    try:
        result = client.light_chat(
            "你是一个需求分析器。请用 JSON 回复。",
            '判断: "I need a PDF to Markdown converter tool" 是否有工具需求？'
            '返回格式: {"is_demand": true/false, "tool_idea": "具体工具名", "score": 1-10}',
            expect_json=True
        )
        print(f"  📊 结果: {result[:300]}")
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
    
    # 测试 heavy_chat 用到的第一条可用链路
    print(f"\n  🔬 测试 heavy_chat...")
    try:
        result = client.heavy_chat(
            "你是一个前端工具生成器。回复纯 HTML 代码。",
            "生成一个简单的 HTML 倒计时工具页面"
        )
        print(f"  📊 结果长度: {len(result)} 字符")
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
    
    print("\n✅ 自检完成")
