#!/usr/bin/env python3
"""
MintShovels AI 质量验证器 — 关口③
=====================================
出厂前验证生成工具的质量，不合格则自动修复重试。

核心能力:
  1. 静态代码检查 — HTML结构、JS完整性、无TODO/占位符
  2. 功能完整性检测 — 是否有输入→处理→输出闭环
  3. AI辅助评估 — 让AI判断工具是否"名副其实"
  4. 自动修复重试 — 验证失败→AI修复→再验证（最多3次）

用法:
  from engine.ai_quality_validator import AIQualityValidator
  validator = AIQualityValidator()
  result = validator.validate_and_fix(html, demand)
  # → {"pass": True, "html": fixed_html} | {"pass": False, "issues": [...]}
"""

import json
import os
import re
import sys
from typing import Optional, Dict, Any, List

ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ENGINE_DIR)

try:
    from ai_client import get_client, AIClient
except ImportError:
    get_client = None
    AIClient = None

MAX_FIX_ATTEMPTS = 3


class AIQualityValidator:
    """
    AI 质量验证器 — 关口③
    验证+修复+再验证循环
    """
    
    def __init__(self):
        self.client = get_client() if get_client else None
    
    @property
    def available(self) -> bool:
        if not self.client:
            return False
        return (self.client.ollama_available() or 
                self.client.deepseek_available() or
                self.client.gemini_available() or
                self.client.huggingface_available())
    
    def validate_and_fix(self, html: str, demand: dict) -> Dict[str, Any]:
        """
        验证工具页面质量，不合格则自动修复
        
        Args:
            html: 生成的 HTML 页面
            demand: 原始需求 {"name": "...", "name_zh": "...", "desc": "...", ...}
        
        Returns:
            {"pass": bool, "html": str, "issues": [...], "fix_attempts": int, "score": int}
        """
        name = demand.get("name", "Unknown")
        
        # 第〇轮：数据丰富度检查（新关卡！拦截数据贫乏的工具）
        data_issues = self._data_richness_check(html, demand)
        if data_issues:
            print(f"  📊 数据丰富度检查发现 {len(data_issues)} 个问题:")
            for issue in data_issues:
                print(f"     • {issue}")
        
        # 第一轮：静态检查
        issues = self._static_check(html, demand) + data_issues
        
        if issues:
            print(f"  🔍 检查发现 {len(issues)} 个问题:")
            for issue in issues:
                print(f"     • {issue}")
            
            # 尝试修复
            for attempt in range(1, MAX_FIX_ATTEMPTS + 1):
                print(f"  🔧 第 {attempt}/{MAX_FIX_ATTEMPTS} 次自动修复...")
                
                if not self.available:
                    print(f"  ⚠️ AI 不可用，无法自动修复")
                    return {
                        "pass": False, 
                        "html": html, 
                        "issues": issues,
                        "fix_attempts": 0,
                        "score": 100 - len(issues) * 20
                    }
                
                fixed_html = self._ai_fix(html, issues + data_issues, demand)
                if not fixed_html:
                    print(f"  ❌ 修复失败（AI 无响应）")
                    continue
                
                remaining = self._static_check(fixed_html, demand) + self._data_richness_check(fixed_html, demand)
                if not remaining:
                    print(f"  ✅ 第 {attempt} 次修复成功！")
                    return {
                        "pass": True,
                        "html": fixed_html,
                        "issues": [],
                        "fix_attempts": attempt,
                        "score": 100
                    }
                else:
                    print(f"  ⚠️ 修复后仍有 {len(remaining)} 个问题")
                    html = fixed_html
                    issues = remaining
            
            # 所有修复尝试都失败
            return {
                "pass": len(issues) <= 2,  # 少于3个问题仍然接受
                "html": html,
                "issues": issues,
                "fix_attempts": MAX_FIX_ATTEMPTS,
                "score": 100 - len(issues) * 20
            }
        
        # 第二轮：功能完整性评分（AI 评估）
        score = 100
        if self.available:
            score = self._ai_functional_score(html, demand)
            print(f"  📊 AI 功能评分: {score}/100")
            
            if score < 60:
                print(f"  ⚠️ 功能评分过低，尝试 AI 增强...")
                enhanced = self._ai_enhance(html, demand, score)
                if enhanced:
                    html = enhanced
                    score = self._ai_functional_score(html, demand)
                    print(f"  📊 增强后评分: {score}/100")
        
        return {
            "pass": score >= 60,
            "html": html,
            "issues": [],
            "fix_attempts": 0,
            "score": score
        }
    
    def _data_richness_check(self, html: str, demand: dict) -> List[str]:
        """
        🆕 数据丰富度检查 — 关卡③前置
        检查工具的数据/内容是否"有料"，不再只是结构检查
        
        检测维度:
        1. 数组字面量的元素数量和多样性
        2. 生成器的组合爆炸度（first × last ≥ 阈值）
        3. 多语言工具的文化准确性（日文用漢字/かな，不用罗马字）
        4. 工具是否依赖空数据/硬编码少量数据
        """
        issues = []
        name = demand.get("name", "")
        name_zh = demand.get("name_zh", "")
        subcat = demand.get("subcat", "")
        category = demand.get("category", "")
        
        # 提取所有数组字面量
        arrays = re.findall(r'\[([\s\S]*?)\]', html)
        
        # 统计有效数组（至少包含引号字符串元素）
        string_arrays = []
        for arr in arrays:
            # 找引号包裹的元素
            items = re.findall(r'["\']([^"\']{2,})["\']', arr)
            if len(items) >= 3:  # 至少3个元素才算有意义的数据数组
                string_arrays.append({
                    "items": items,
                    "unique": len(set(items)),
                    "total": len(items),
                    "content": arr[:500]
                })
        
        total_data_items = sum(len(a["items"]) for a in string_arrays)
        
        # ── 生成器类工具的特殊检查 ──
        is_generator = any(kw in (name + name_zh + subcat).lower() 
                          for kw in ["generator", "生成器", "generat", "random", "随机", "name", "名字"])
        
        if is_generator:
            # 检查1: 总数据量
            if total_data_items < 50:
                issues.append(f"🔴 数据不足: 仅 {total_data_items} 条数据（生成器至少需要50条）")
            elif total_data_items < 100:
                issues.append(f"🟡 数据偏少: 仅 {total_data_items} 条数据（建议100+）")
            
            # 检查2: 组合多样性 (first × last)
            first_arrays = [a for a in string_arrays if any(
                kw in a["content"].lower() for kw in ["first", "given", "名", "fore"]
            )]
            last_arrays = [a for a in string_arrays if any(
                kw in a["content"].lower() for kw in ["last", "sur", "姓", "family"]
            )]
            
            if first_arrays and last_arrays:
                max_first = max(len(a["items"]) for a in first_arrays)
                max_last = max(len(a["items"]) for a in last_arrays)
                combos = max_first * max_last
                if combos < 200:
                    issues.append(f"🔴 组合数太少: {max_first}×{max_last}={combos}种（至少200种组合）")
            
            # 检查3: 数据唯一性（不能有明显重复）
            all_items = []
            for a in string_arrays:
                all_items.extend(a["items"])
            total = len(all_items)
            unique = len(set(all_items))
            if total > 0 and unique / total < 0.5:
                issues.append(f"🔴 数据重复率过高: {unique}/{total} 唯一 ({unique/total*100:.0f}%)")
        
        # ── 多语言文化准确性检查 ──
        is_japanese_tool = any(kw in (name + name_zh).lower() 
                               for kw in ["japan", "日", "nippon"])
        
        if is_japanese_tool:
            has_kanji = bool(re.search(r'[\u4e00-\u9fff]', html))
            has_kana = bool(re.search(r'[\u3040-\u309f\u30a0-\u30ff]', html))
            has_romaji_only = bool(re.search(r'[A-Z][a-z]+(?:shi|tsu|chi|ku|fu|su|nu|mu|ru|ki|gi|pi|bi|ya|yu|yo|wa|wo|ka|ga|sa|za|ta|da|na|ha|ba|pa|ma|ra)', html))
            
            # 如果有日文名字数组但没有汉字/假名，全用罗马字 = 问题
            jp_arrays = [a for a in string_arrays if any(
                kw in a["content"].lower() for kw in ["japan", "jp", "日", "nippon"]
            )]
            if jp_arrays and not has_kana and not has_kanji:
                # 确认是否所有日文都是罗马字（如 Tanaka, Suzuki 等）
                romaji_count = sum(1 for a in jp_arrays for item in a["items"] 
                                  if re.match(r'^[A-Z][a-z]+$', item))
                if romaji_count > 5:
                    issues.append(f"🔴 日文名使用了罗马字（{romaji_count}个），应使用漢字/かな/カタカナ")
        
        # ── 通用：检查数据是否全是数字/公式（非真实内容） ──
        if string_arrays:
            numeric_only = all(
                re.match(r'^[\d\.\,\-\+\s]+$', item) 
                for a in string_arrays for item in a["items"]
            ) if total_data_items > 0 else False
            
            if numeric_only and is_generator:
                issues.append("🟡 数据以数字为主，生成器可能需要真实文本数据")
        
        # ── 工具内容深度检查 ──
        tool_type_keywords = {
            "calculator": ["calc", "计算", "converter", "换算"],
            "checker": ["check", "validator", "验证", "检测"],
            "analyzer": ["analy", "分析", "parse", "解析"],
            "encoder": ["encode", "decode", "编码", "解码", "加密", "解密"],
        }
        
        detected_type = None
        for ttype, kws in tool_type_keywords.items():
            if any(kw in (name + name_zh + subcat + demand.get("desc", "")).lower() for kw in kws):
                detected_type = ttype
                break
        
        # 计算器类: 检查是否有多步计算（不只是加减）
        if detected_type == "calculator":
            calc_ops = len(re.findall(r'[\+\-\*\/\^%]|Math\.(pow|sqrt|abs|round|ceil|floor|sin|cos|tan|log|exp)', html))
            if calc_ops < 2:
                issues.append("🟡 计算器功能单一，建议增加多种计算模式")
        
        return issues
    
    def _static_check(self, html: str, demand: dict) -> List[str]:
        """静态代码检查"""
        issues = []
        
        # 1. 基本结构
        if not html.startswith("<!DOCTYPE"):
            issues.append("缺少 DOCTYPE 声明")
        if "<html" not in html:
            issues.append("缺少 <html> 标签")
        if "</html>" not in html:
            issues.append("缺少 </html> 闭合标签")
        if "<head" not in html:
            issues.append("缺少 <head> 标签")
        if "<body" not in html:
            issues.append("缺少 <body> 标签")
        
        # 2. 脚本
        has_script = "<script>" in html or "<script " in html
        has_closing_script = "</script>" in html
        if not has_script:
            issues.append("缺少 <script> 标签（无交互逻辑）")
        if has_script and not has_closing_script:
            issues.append("<script> 标签未闭合")
        
        # 3. 功能检测
        if "function " not in html:
            issues.append("无 JavaScript 函数定义")
        if "// TODO" in html:
            issues.append("包含 TODO 占位符（功能未完成）")
        if "alert(" in html or "prompt(" in html:
            issues.append("使用了 alert/prompt（应使用自定义UI）")
        
        # 4. 输入控件
        has_input = bool(re.search(r'<(input|textarea|select)\b', html, re.I))
        has_button = bool(re.search(r'<(button|input\b[^>]*type\s*=\s*["\']button)', html, re.I))
        if not has_input:
            issues.append("缺少输入控件（input/textarea/select）")
        if not has_button:
            issues.append("缺少按钮")
        
        # 5. 长度
        if len(html) < 500:
            issues.append(f"页面过短 ({len(html)} bytes)")
        
        # 6. 样式
        if "tailwind" not in html.lower():
            issues.append("未使用 Tailwind CSS")
        
        # 7. JS 实质内容 — 找到包含 function 的 script 标签
        all_scripts = re.findall(r'<script[^>]*>([\s\S]*?)</script>', html)
        meaningful_js = ""
        for script_content in all_scripts:
            if "function " in script_content:
                meaningful_js = script_content.strip()
                break
        if not meaningful_js and all_scripts:
            meaningful_js = all_scripts[-1].strip()
        
        if meaningful_js:
            js_code = meaningful_js
            if len(js_code) < 100:
                issues.append(f"JS 代码过短 ({len(js_code)} 字符)")
            
            # 检查是否有实质性操作（不只是console.log）
            meaningful_ops = re.findall(
                r'(getElementById|querySelector|createElement|innerHTML|textContent|'
                r'addEventListener|onclick|fetch|localStorage|JSON\.parse|JSON\.stringify|'
                r'crypto\.|Math\.|Array\.from|new Blob|URL\.createObjectURL|'
                r'navigator\.clipboard|encodeURIComponent|decodeURIComponent|btoa|atob)',
                js_code
            )
            if len(meaningful_ops) < 2:
                issues.append(f"JS 缺乏实质操作（仅有 {len(meaningful_ops)} 个 DOM/数据操作）")
        else:
            issues.append("未找到可执行的 JS 代码")
        
        return issues
    
    def _ai_fix(self, html: str, issues: List[str], demand: dict) -> Optional[str]:
        """用 AI 修复 HTML 中的问题"""
        if not self.client:
            return None
        
        system_prompt = """You are a frontend code reviewer. Fix the issues in the HTML page below.
ONLY return the complete fixed HTML. No explanations, no markdown wrapping."""

        issues_text = "\n".join(f"- {i}" for i in issues)
        name = demand.get("name", "")
        
        user_message = f"""This HTML tool page for "{name}" has the following issues:

{issues_text}

Fix ALL issues and return the complete corrected HTML. The page must have:
- Complete HTML structure (DOCTYPE, html, head, body)
- Tailwind CSS CDN
- Working JavaScript with real functionality
- Input controls and action buttons
- No TODOs or placeholder functions
- Error handling for invalid input

Current HTML:
```html
{html[:8000]}
```"""

        try:
            response = self.client.light_chat(system_prompt, user_message)
            if not response:
                return None
            
            # Extract HTML
            if "```html" in response:
                start = response.index("```html") + 7
                end = response.rindex("```")
                return response[start:end].strip()
            if "```" in response:
                start = response.index("```") + 3
                end = response.rindex("```")
                return response[start:end].strip()
            if "<!DOCTYPE" in response:
                doctype = response.index("<!DOCTYPE")
                end = response.rfind("</html>")
                if end > doctype:
                    return response[doctype:end + 7]
            return response.strip()
        except Exception:
            return None
    
    def _ai_functional_score(self, html: str, demand: dict) -> int:
        """AI 评估工具功能完整性（0-100分）"""
        if not self.client:
            return 70  # 默认及格
        
        name = demand.get("name", "")
        desc = demand.get("desc", "")
        
        # 提取 JS 代码（截取前6000字符）
        js_match = re.search(r'<script[^>]*>([\s\S]*?)</script>', html)
        js_code = js_match.group(1)[:6000] if js_match else ""
        
        # 提取 body 内部
        body_match = re.search(r'<body[^>]*>([\s\S]*?)</body>', html)
        body_content = body_match.group(1)[:3000] if body_match else ""
        
        system_prompt = """Score this tool page's functional completeness from 0-100.
Return ONLY a JSON object: {"score": <int>, "functional": <bool>, "reason": "<short>"}

Scoring criteria:
- 90-100: Full Input→Process→Output loop, multiple features, error handling, export, great UX
- 70-89: Working core feature, basic error handling, usable
- 50-69: Has core code but incomplete, rough UX
- 30-49: Minimal functionality, mostly UI shell
- 0-29: Non-functional, placeholder, or broken"""
        
        user_message = f"""Tool name: {name}
Description: {desc}

JS Code:
{js_code[:4000]}

HTML Body:
{body_content[:2000]}"""

        try:
            response = self.client.light_chat(system_prompt, user_message, expect_json=True)
            if response and response != "{}":
                result = json.loads(response)
                return min(100, max(0, result.get("score", 50)))
        except Exception:
            pass
        
        return 60
    
    def _ai_enhance(self, html: str, demand: dict, current_score: int) -> Optional[str]:
        """AI 增强工具功能（当评分过低时）"""
        if not self.client:
            return None
        
        name = demand.get("name", "")
        desc = demand.get("desc", "")
        
        system_prompt = """You are a frontend expert. Enhance this tool page to be more functional and complete.
Add missing features, improve error handling, add export/copy functionality.
Return ONLY the complete enhanced HTML. No explanations, no markdown wrapping."""

        user_message = f"""This tool page for "{name}" scored only {current_score}/100.
Description: {desc}

Please enhance it by adding:
1. Better error handling (show user-friendly messages, not just alerts)
2. Export functionality (download results as text file)
3. Copy to clipboard button
4. Stats/history display
5. Loading states for buttons
6. Clear/reset functionality
7. At least 1 more functional feature

Current HTML:
```html
{html[:10000]}
```"""

        try:
            response = self.client.light_chat(system_prompt, user_message)
            if not response:
                return None
            
            if "```html" in response:
                start = response.index("```html") + 7
                end = response.rindex("```")
                return response[start:end].strip()
            if "<!DOCTYPE" in response:
                doctype = response.index("<!DOCTYPE")
                end = response.rfind("</html>")
                if end > doctype:
                    return response[doctype:end + 7]
            return None
        except Exception:
            return None


# ─── 快速检查（用于管道中的门禁）──────────────────────────────────

def quick_gate_check(html: str, demand: dict) -> Dict[str, Any]:
    """
    快速门禁检查 — 不调用AI，纯静态检查
    用于管道中快速拦截明显不合格的工具
    
    🆕 v1.7: 新增数据丰富度检查
    """
    issues = []
    
    # 必须存在的元素
    required = [
        ("<!DOCTYPE", "DOCTYPE"),
        ("<html", "<html>"),
        ("</html>", "</html>"),
        ("<body", "<body>"),
        ("function ", "JS函数"),
    ]
    for tag, name in required:
        if tag not in html:
            issues.append(f"缺少{name}")
    
    # 禁止的内容
    forbidden = [
        ("// TODO", "TODO占位符"),
        ("// TODO: Customize", "模板占位符"),
        ("console.log(", "调试日志"),
    ]
    for tag, name in forbidden:
        if tag in html:
            issues.append(f"包含{name}")
    
    # JS 代码长度 — 找最后一个包含 function 的 script 标签
    all_scripts = re.findall(r'<script[^>]*>([\s\S]*?)</script>', html)
    meaningful_js = ""
    for script_content in all_scripts:
        if "function " in script_content:
            meaningful_js = script_content.strip()
            break
    if not meaningful_js and all_scripts:
        meaningful_js = all_scripts[-1].strip()
    
    if meaningful_js:
        js_len = len(meaningful_js)
        if js_len < 100:
            issues.append(f"JS代码过短({js_len}字符)")
    else:
        issues.append("未找到JS代码")
    
    # 🆕 数据丰富度快速检查
    name = demand.get("name", "")
    name_zh = demand.get("name_zh", "")
    subcat = demand.get("subcat", "")
    
    is_generator = any(kw in (name + name_zh + subcat).lower() 
                      for kw in ["generator", "生成器", "generat", "random", "随机", "name", "名字"])
    
    if is_generator:
        # 统计字符串数组中的元素
        arrays = re.findall(r'\[([^\]]*?)\](?!\s*\.\w+\()', meaningful_js) if meaningful_js else []
        total_items = 0
        for arr in arrays:
            items = re.findall(r'["\']([^"\']{2,})["\']', arr)
            total_items += len(items)
        
        if total_items < 30:
            issues.append(f"🔴 数据严重不足: 仅{total_items}个数据项（生成器至少30条）")
        elif total_items < 50:
            issues.append(f"🟡 数据偏少: 仅{total_items}个数据项（建议50+）")
        
        # 日文罗马字检查
        if any(kw in (name + name_zh).lower() for kw in ["japan", "日", "nippon"]):
            has_kana = bool(re.search(r'[\u3040-\u309f\u30a0-\u30ff]', html))
            has_kanji = bool(re.search(r'[\u4e00-\u9fff]', html))
            has_romaji_array = bool(re.search(r'\["[A-Z][a-z]+"(?:,\s*"[A-Z][a-z]+")+\]', html))
            if has_romaji_array and not has_kana and not has_kanji:
                issues.append("🔴 日文名使用罗马字，应使用漢字/かな/カタカナ")
    
    return {
        "pass": len(issues) == 0,
        "issues": issues,
        "score": 100 - len(issues) * 25
    }


# ─── 自检 ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    validator = AIQualityValidator()
    print("=== AI Quality Validator 自检 ===")
    print(f"  AI 可用: {'✅' if validator.available else '❌ (仅静态检查)'}")
    
    # 测试1: 好的HTML
    good_html = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script></head>
<body class="p-6 bg-zinc-950 text-zinc-100">
<div class="max-w-3xl mx-auto">
<input id="main-input" class="w-full" placeholder="Enter text...">
<button onclick="process()" class="btn-primary">Run</button>
<div id="output-area"></div>
</div>
<script>
function process() {
    const input = document.getElementById('main-input').value;
    if (!input) { document.getElementById('output-area').innerHTML = '<p class=text-red-400>Empty</p>'; return; }
    const words = input.match(/\\b\\w+\\b/g) || [];
    document.getElementById('output-area').innerHTML = `<div class=stat-card><div class=stat-value>${words.length}</div><div class=stat-label>Words</div></div>`;
}
</script>
</body>
</html>"""
    
    demand = {"name": "Word Counter", "name_zh": "单词计数器", "desc": "Count words in text"}
    
    # 静态检查
    print("\n  测试1: 好的HTML")
    issues = validator._static_check(good_html, demand)
    if issues:
        for i in issues:
            print(f"    ❌ {i}")
    else:
        print("    ✅ 静态检查通过")
    
    # 快速门禁
    print("\n  测试2: 快速门禁")
    result = quick_gate_check(good_html, demand)
    print(f"    {'✅' if result['pass'] else '❌'} 通过: {result['pass']}")
    print(f"    分数: {result['score']}")
    
    # 测试3: 坏的HTML
    print("\n  测试3: 坏的HTML")
    bad_html = "<html><body><p>hi</p><script>// TODO: add logic</script></body></html>"
    result = quick_gate_check(bad_html, {"name": "Bad Tool"})
    print(f"    {'✅' if result['pass'] else '❌'} 通过: {result['pass']}")
    print(f"    问题: {result['issues']}")
    
    print("\n✅ 自检完成")
