#!/usr/bin/env python3
"""
LLM 意图分类器 v2.0
====================
取代 demand_filter.py（800行黑名单）+ intent_classifier.py（700行规则）
改用 Google Gemini API 做语义理解，判断文本是否属于"未满足的真需求"。

核心能力：
  1. 不受关键词限制，理解隐喻/创意表达（如"两座大山合成一座"）
  2. 100+ 语言母语级理解，全球搜索全覆盖
  3. 区分"已有工具的需求" vs "真空需求"
  4. 自动生成规范工具名
  5. 输出置信度，低置信度交给人工
  6. Gemini 2.0 Flash 免费额度 1500次/天，完全够用

用法:
  from llm_intent_classifier import LLMIntentClassifier
  lic = LLMIntentClassifier()
  result = lic.classify("我想把两座大山合成一座")
"""

import json
import os
import re
import time
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MISTAKE_BOOK_PATH = os.path.join(SCRIPT_DIR, "mistake_book.json")

# Gemini 预览模型速率限制：约 2次/分钟
RATE_LIMIT_DELAY = 35  # 每次请求间隔秒数（60/2 + 缓冲）


class LLMIntentClassifier:
    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        if not self.api_key or not self.model:
            # 尝试从 .env 读取
            env_path = os.path.join(SCRIPT_DIR, ".env")
            if os.path.exists(env_path):
                env_vars = {}
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            env_vars[k.strip()] = v.strip()
                if not self.api_key:
                    self.api_key = env_vars.get("GEMINI_API_KEY")
                if not self.model or self.model == "gemini-2.0-flash":
                    self.model = env_vars.get("GEMINI_MODEL", self.model)
        if not self.api_key:
            raise ValueError("❌ 未找到 GEMINI_API_KEY，请在 .env 中配置")
        # Gemini API 格式：key 通过 URL 参数传递
        self.api_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        self.few_shot_examples = self._load_mistake_examples()

    def _load_mistake_examples(self) -> list:
        """从错题本加载经验案例，注入 prompt"""
        if not os.path.exists(MISTAKE_BOOK_PATH):
            return []
        try:
            with open(MISTAKE_BOOK_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("corrections", [])[-20:]
            examples = []
            for item in items:
                text = item["text"][:120]
                correct = item.get("correct_verdict", "UNKNOWN")
                reason = item.get("learned_pattern", "")
                label = "YES" if correct == "PASS" else "NO"
                examples.append(f"  文本: 「{text}」 → 是工具需求: {label}   ({reason})")
            return examples
        except Exception:
            return []

    def _build_prompt(self, text: str) -> str:
        few_shot_block = ""
        if self.few_shot_examples:
            few_shot_block = "\n## 错题本经验（最近判断失误的案例，请引以为戒）\n"
            for ex in self.few_shot_examples[:10]:
                few_shot_block += f"{ex}\n"

        return f"""你是"未满足的工具需求"识别专家。你的任务是判断一段文本是否描述了一个真实存在的、但市面上不一定有现成工具的需求，并评估把它做成在线工具的可行性。

## 什么是"可以做成的工具需求"
用户描述的某个操作、功能、转换，可以做成一个在线小工具（网页打开 → 输入 → 输出）。
- 关键词不重要，重点是"有没有可操作的数据流"
- 创意的、隐喻的表达也接受（如"我想把两座大山合成一座" → 可能是图片合成工具）
- 描述的场景不限于 JSON/PDF/密码/计算 这些老套类别

## 可行性判断标准（is_feasible）
即使满足"工具需求"定义，也要判断技术上能否做成在线工具：
- ✅ feasible（可行）：有明确的输入→处理→输出逻辑，纯软件可实现
  例："图片转像素画" → 可行（前端Canvas处理）
  例："Markdown转Word" → 可行（格式转换）
  例："对比两个数据库表差异" → 可行（SQL查询+前端展示）
- ❌ not feasible（不可行）：
  1. 物理/硬件限制：需要物理设备才能实现（如"检测谁偷了外卖""自动扫地"）
  2. 数据不切实际：需要海量私有数据（如"预测明天股票涨跌精准到分"）
  3. 依赖第三方强权：需破解/绕过平台限制（如"一键下载全网付费音乐""破解XX会员"）
  4. 违法红线：涉及破解/盗版/入侵（如"通杀验证码""破解WiFi密码"）
  5. 纯AI幻觉需求：期望AI做到超出当前技术边界（如"自动写一本畅销小说保证月入过万"）

## 什么不是工具需求
- 纯闲聊、八卦、个人感受（如"今天心情不好"）
- 新闻事件描述（如"某公司发布了新产品"）
- 商品广告（如"16卷家庭装纸巾"）
- 违法/破解内容（如"通杀所有验证码"）
- 社交媒体互动（如"大家觉得这个怎么样"）
- 喊口号/感叹（如"太棒了绝了"）

## 特别提醒
- "如何使图片更清晰" → YES，这是图片增强需求，feasible
- "怎么让电脑不卡" → YES，这是系统优化需求，feasible但受限于系统权限
- "Netflix 能不能后台播放" → YES，这是视频播放控制需求，技术上可实现
- "有什么工具能把GIF拼成一张长图" → YES，这是GIF拼接需求，feasible
- "Trump 打赌输了" → NO，这是八卦
- "张靓颖演唱会太棒了" → NO，这是娱乐闲聊
- "一键下载网易云所有付费歌曲" → 可能是需求但不可行（违法+依赖破解）
- "自动检测谁偷了我的外卖" → 不可行（需要物理硬件+视频监控接入）
{few_shot_block}
## 任务
分析以下文本，只回复 JSON：

文本：{text[:500]}

严格按以下 JSON 格式回复，不要包含其他内容：
{{"is_demand": true/false, "is_unmet": true/false, "is_feasible": true/false, "canonical_name": "规范工具名", "tool_type": "generator|calculator|checker|converter|processor|script|other", "confidence": 0-100, "reason": "一句话理由", "feasibility_reason": "一句话说明可行或不可行的原因"}}"""

    def classify(self, text: str) -> dict:
        """
        对文本做意图分类

        返回:
          {
            "pass": bool,          # 是否通过（值得做工具）
            "is_unmet": bool,      # 是否是真空需求（市面上少见）
            "is_feasible": bool,   # 技术上是否可行（能做出来）
            "canonical_name": str, # 规范工具名
            "tool_type": str,      # 工具类型
            "confidence": int,     # 置信度 0-100
            "reason": str,         # 判断理由
            "feasibility_reason": str, # 可行性说明
            "verdict": str,        # PASS / WARN / BLOCK
            "raw_text": str,       # 原始文本
          }
        """
        if not text or not isinstance(text, str) or len(text.strip()) < 2:
            return self._quick_block("输入过短")

        text = text.strip()

        # 快速预筛：极端明显的垃圾（纯数字/纯符号/超长乱码）
        if len(text) > 500:
            return self._quick_block("文本过长")
        if re.match(r'^[\d\s\W]+$', text):
            return self._quick_block("纯数字或符号")

        try:
            return self._call_llm(text)
        except Exception as e:
            return self._quick_block(f"LLM调用失败: {e}")

    def _quick_block(self, reason: str) -> dict:
        return {
            "pass": False, "is_unmet": False, "is_feasible": False,
            "canonical_name": None, "tool_type": "other",
            "confidence": 100, "reason": reason,
            "feasibility_reason": "",
            "verdict": "BLOCK", "raw_text": ""
        }

    def _call_llm(self, text: str) -> dict:
        prompt = self._build_prompt(text)
        payload = json.dumps({
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 400,
            }
        }).encode("utf-8")

        last_error = None
        # 预览模型速率极低（~2次/分钟），不做重试，由 classify_batch 的间隔保证
        for attempt in range(1):
            try:
                req = urllib.request.Request(
                    self.api_url,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read())
                break  # 成功，跳出重试循环
            except urllib.error.HTTPError as e:
                last_error = e
                body = e.read().decode("utf-8", errors="replace")
                if e.code == 429:
                    wait = 60  # 预览模型需等 60 秒
                    time.sleep(wait)
                    continue
                raise RuntimeError(f"Gemini API {e.code}: {body[:200]}")
            except urllib.error.URLError as e:
                last_error = e
                if attempt < 3:
                    time.sleep(10)
                    continue
                raise
        else:
            # 所有重试都失败了
            raise RuntimeError(f"Gemini API 重试耗尽: {last_error}")

        # Gemini 响应格式
        content = data["candidates"][0]["content"]["parts"][0]["text"].strip()

        # 解析 JSON 回复
        try:
            # 清理可能的 markdown 包裹
            content = re.sub(r'```json\s*', '', content)
            content = re.sub(r'```\s*', '', content)
            parsed = json.loads(content)
        except json.JSONDecodeError:
            # 尝试手动提取
            parsed = self._fallback_parse(content)

        is_demand = parsed.get("is_demand", False)
        is_unmet = parsed.get("is_unmet", False)
        is_feasible = parsed.get("is_feasible", True)  # 默认True，LLM没返回时不误杀
        confidence = int(parsed.get("confidence", 50))
        reason = parsed.get("reason", "")
        feasibility_reason = parsed.get("feasibility_reason", "")

        # 判定逻辑
        if is_demand and not is_feasible:
            verdict = "WARN"  # 是需求但做不了 → 人工确认
        elif is_demand and confidence >= 70:
            verdict = "PASS"
        elif is_demand and confidence >= 40:
            verdict = "WARN"
        elif is_unmet and not is_demand and confidence >= 50:
            verdict = "WARN"
        else:
            verdict = "BLOCK"

        return {
            "pass": verdict != "BLOCK",
            "is_unmet": is_unmet,
            "is_feasible": is_feasible,
            "canonical_name": parsed.get("canonical_name", None),
            "tool_type": parsed.get("tool_type", "other"),
            "confidence": confidence,
            "reason": reason,
            "feasibility_reason": feasibility_reason,
            "verdict": verdict,
            "raw_text": text,
        }

    def _fallback_parse(self, content: str) -> dict:
        """当 JSON 解析失败时的手动提取"""
        result = {"is_demand": False, "is_unmet": False, "is_feasible": True,
                  "canonical_name": None, "tool_type": "other",
                  "confidence": 30, "reason": "JSON解析失败", "feasibility_reason": ""}
        cl = content.lower()
        if '"is_demand": true' in cl or '"is_demand":true' in cl:
            result["is_demand"] = True
        if '"is_unmet": true' in cl or '"is_unmet":true' in cl:
            result["is_unmet"] = True
        # 尝试提取 confidence
        conf_match = re.search(r'"confidence"\s*:\s*(\d+)', cl)
        if conf_match:
            result["confidence"] = int(conf_match.group(1))
        return result

    def classify_batch(self, texts: list) -> list:
        results = []
        for i, t in enumerate(texts):
            if i > 0:
                time.sleep(RATE_LIMIT_DELAY)  # 遵守 15 RPM 限制
            results.append(self.classify(str(t)))
        return results


# ═══ 自检 ═══
if __name__ == "__main__":
    lic = LLMIntentClassifier()

    tests = [
        "我想把两座大山合成一座",
        "如何使图片更清晰",
        "怎么让电脑不卡",
        "Netflix 能不能后台播放视频",
        "有什么工具能把多个GIF拼成一张长图",
        "雷军说当初不该和董明珠打赌",
        "张靓颖演唱会太棒了",
        "Bounty paper towels 16 rolls",
        "有没有那种能自动把语音转成思维导图的工具",
        "我现在每次都要手动把Markdown复制到Word排版",
    ]

    print("🧪 LLM 意图分类器自检\n")
    for t in tests:
        r = lic.classify(t)
        emoji = "✅" if r["pass"] else "🚫"
        warn = " ⚠️" if r["verdict"] == "WARN" else ""
        feasible = "🔧" if r.get("is_feasible") else "❌不可行"
        print(f"{emoji}{warn} [{r['verdict']:5s}] conf={r['confidence']:2d} {feasible} | {t[:50]}")
        if r["canonical_name"]:
            print(f"    → 工具名: {r['canonical_name']}")
        print(f"    → 理由: {r['reason']}")
        if r.get("feasibility_reason"):
            print(f"    → 可行性: {r['feasibility_reason']}")
        print()
