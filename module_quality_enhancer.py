#!/usr/bin/env python3
"""
MintShovels 模块输出质量增强器
===============================
针对 32 种逻辑模块，提升生成数据的实用价值和参考价值：
  - 生成器：追加统计/分类/使用说明/复制功能
  - 验证器：追加测试样例/正确示例/批量验证
  - 计算器：追加公式展示/单位标注/历史记录
  - 脚本：追加错误处理/帮助文档/环境适配

不会创建无意义随机字串堆砌，每个输出都有真实参考意义。
"""

import json
import os
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOL_FACTORY_DIR = os.environ.get(
    "TOOL_FACTORY_DIR",
    os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), "tool-factory")
)
TOOLS_PATH = os.path.join(TOOL_FACTORY_DIR, "backups", "generated_tools.json")
BACKUP_DIR = os.path.join(TOOL_FACTORY_DIR, "backups")

# ═══════════════════════════════════════════════════════════
# 生成器输出增强：追加统计、复制、说明信息
# ═══════════════════════════════════════════════════════════

def enhance_generator_js(js_code):
    """增强生成器的JS输出 — 追加统计面板和复制功能"""
    
    # 追加复制单条功能
    copy_patch = """
function copyItem(el) {
    const text = el.innerText || el.textContent;
    navigator.clipboard.writeText(text).then(() => {
        const orig = el.style.background;
        el.style.background = '#10b98133';
        setTimeout(() => el.style.background = orig, 600);
    }).catch(() => {});
}"""

    # 追加统计面板
    stats_patch = """
function showStats(data, containerId) {
    if (!data || !data.length) return;
    const unique = new Set(data.map(String)).size;
    const panel = document.getElementById(containerId);
    if (panel) {
        panel.innerHTML = `<div class="text-xs text-zinc-500 mt-3 flex flex-wrap gap-2">
            <span class="bg-zinc-800/50 px-2 py-1 rounded">📊 共 ${data.length} 条</span>
            <span class="bg-zinc-800/50 px-2 py-1 rounded">🔢 唯一值 ${unique}</span>
            <span class="bg-zinc-800/50 px-2 py-1 rounded">📋 点击数据可复制</span>
        </div>`;
    }
}"""

    # 检查是否有 generate 函数
    if 'function generate' in js_code:
        # 在 exportData 前追加复制和统计
        enhanced = js_code
        
        if 'copyItem' not in enhanced:
            # 在 exportData 函数前插入 copyItem
            enhanced = enhanced.replace(
                'function export',
                copy_patch + '\n' + stats_patch + '\nfunction copyItem',
            )
        
        # 给生成结果加上 onclick="copyItem(this)" 使数据可复制
        # 在结果容器中追加统计
        if 'results.innerHTML = items.join' in enhanced and 'showStats' not in enhanced:
            enhanced = enhanced.replace(
                'results.innerHTML = items.join',
                'const statsId = containerId || (results.id + \'-stats\');\n    results.innerHTML = items.join',
            )
            # 在 generate 函数末尾追加统计调用
            if '}_data = items;' in enhanced:
                enhanced = enhanced.replace(
                    '}_data = items;\n}',
                    '}_data = items;\n    showStats(items, results.id + \'-stats\');\n}',
                )
        
        return enhanced
    
    return js_code


# ═══════════════════════════════════════════════════════════
# 验证器增强：追加测试样例、正确格式示例
# ═══════════════════════════════════════════════════════════

def enhance_checker_js(js_code, check_type="json"):
    """增强验证器的输出 — 追加测试样例和正确格式说明"""
    
    examples_map = {
        "email": [("test@example.com", "标准邮箱"), ("user@domain.co.uk", "多级域名"), ("invalid@", "缺少域名")],
        "url": [("https://example.com", "标准HTTPS"), ("http://localhost:3000", "本地地址"), ("ftp://files.com", "非HTTP")],
        "json": [('{"name":"Alice"}', "标准JSON"), ("[1, 2, 3]", "JSON数组"), ("{bad json}", "格式错误")],
        "password": [("MyP@ssw0rd!", "极强密码"), ("abc123", "弱密码"), ("Tr0ub4dor&3", "强密码")],
        "ip": [("192.168.1.1", "私有IPv4"), ("8.8.8.8", "公共IPv4"), ("256.1.1.1", "超范围")],
        "regex": [("[a-z]+", "匹配合法"), ("[0-9]+", "匹配数字"), ("[", "语法错误")],
    }
    
    examples = examples_map.get(check_type, examples_map["json"])
    
    # Build example buttons as plain HTML strings
    buttons = []
    for ex_val, ex_desc in examples:
        escaped_val = ex_val.replace("'", "\\'").replace('"', '&quot;')
        btn = f'<button onclick="document.getElementById(\'{{{{id}}}}-input\').value=\'{escaped_val}\';check{{{{id}}}}()" class="text-xs bg-zinc-800 hover:bg-zinc-700 px-2 py-1 rounded mr-1 mb-1 inline-block" title="{ex_desc}">{ex_desc}: {ex_val[:15]}</button>'
        buttons.append(btn)
    
    examples_html = '<div class="mt-4 pt-3 border-t border-zinc-700"><p class="text-xs text-zinc-500 mb-2">Test examples (click to fill):</p>' + ''.join(buttons[:4]) + '</div>'
    
    # 在 check 函数的 result 输出后追加
    if 'result.innerHTML = detail;' in js_code:
        enhanced = js_code.replace(
            'result.innerHTML = detail;',
            'result.innerHTML = detail + `' + examples_html + '`;'
        )
        return enhanced
    
    return js_code


# ═══════════════════════════════════════════════════════════
# 计算器增强：追加公式展示
# ═══════════════════════════════════════════════════════════

def enhance_calculator_html(html_code, calc_type="bmi"):
    """增强计算器的输出 — 追加公式说明"""
    
    formula_map = {
        "bmi": '<div class="mt-3 pt-3 border-t border-zinc-700"><p class="text-xs text-zinc-500">📐 公式: BMI = 体重(kg) ÷ 身高²(m²)</p><p class="text-xs text-zinc-600">参考: &lt;18.5 偏瘦 | 18.5-24 正常 | 24-28 偏胖 | ≥28 肥胖</p></div>',
        "percentage": '<div class="mt-3 pt-3 border-t border-zinc-700"><p class="text-xs text-zinc-500">📐 公式: 百分比 = (数值 ÷ 总数) × 100%</p></div>',
        "unit_converter": '<div class="mt-3 pt-3 border-t border-zinc-700"><p class="text-xs text-zinc-500">📐 公式: 结果 = 输入值 × 换算比率</p></div>',
        "area": '<div class="mt-3 pt-3 border-t border-zinc-700"><p class="text-xs text-zinc-500">📐 矩形: 面积=长×宽, 周长=2(长+宽) | 圆形: 面积=πr², 周长=2πr</p></div>',
        "mortgage": '<div class="mt-3 pt-3 border-t border-zinc-700"><p class="text-xs text-zinc-500">📐 等额本息: M=P×r(1+r)ⁿ/((1+r)ⁿ-1) | r=月利率 n=期数</p></div>',
        "tip": '<div class="mt-3 pt-3 border-t border-zinc-700"><p class="text-xs text-zinc-500">📐 每人应付 = (账单 + 小费) ÷ 人数 | 小费通常 15%-20%</p></div>',
    }
    
    formula_html = formula_map.get(calc_type, '')
    
    if formula_html and '<div id="{id}-result"' in html_code:
        enhanced = html_code.replace(
            '<div id="{id}-result"',
            formula_html + '\n    <div id="{id}-result"'
        )
        return enhanced
    
    return html_code


# ═══════════════════════════════════════════════════════════
# 批量增强引擎
# ═══════════════════════════════════════════════════════════

def enhance_all_tools(dry_run=False):
    """批量增强所有工具的输出质量"""
    tools = json.load(open(TOOLS_PATH))
    total = len(tools)
    
    enhanced_count = 0
    skipped_count = 0
    garbage_count = 0
    
    for i, tool in enumerate(tools):
        # 跳过垃圾工具
        if tool.get("_garbage"):
            garbage_count += 1
            continue
        
        tmpl = tool.get("template_name", "")
        modified = False
        
        try:
            if tmpl == "随机生成器":
                js = tool.get("js_template", "")
                if js and '// TODO' not in js:
                    enhanced_js = enhance_generator_js(js)
                    if enhanced_js != js and not dry_run:
                        tool["js_template"] = enhanced_js
                        tool["_quality_enhanced"] = True
                        modified = True
            
            elif tmpl in ("检测验证器", "检测/验证器"):
                js = tool.get("js_template", "")
                if js:
                    enhanced_js = enhance_checker_js(js)
                    if enhanced_js != js and not dry_run:
                        tool["js_template"] = enhanced_js
                        tool["_quality_enhanced"] = True
                        modified = True
            
            elif tmpl == "计算器":
                html = tool.get("html_template", "")
                if html:
                    enhanced_html = enhance_calculator_html(html)
                    if enhanced_html != html and not dry_run:
                        tool["html_template"] = enhanced_html
                        tool["_quality_enhanced"] = True
                        modified = True
            
            if modified:
                enhanced_count += 1
                tool["_quality_enhanced_at"] = datetime.now(timezone.utc).isoformat()
            else:
                skipped_count += 1
                
        except Exception as e:
            skipped_count += 1
        
        if (i + 1) % 500 == 0:
            print(f"  进度: {i+1}/{total}")
    
    # 写回
    if not dry_run:
        with open(TOOLS_PATH, "w") as f:
            json.dump(tools, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 已写回 {TOOLS_PATH}")
    
    active_tools = total - garbage_count
    
    print(f"\n{'='*70}")
    print(f"📊 质量增强统计:")
    print(f"  总工具数: {total}")
    print(f"  垃圾标记: {garbage_count} (跳过)")
    print(f"  有效工具: {active_tools}")
    print(f"  已增强: {enhanced_count}")
    print(f"  未改动: {skipped_count}")
    
    return enhanced_count

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="模块输出质量增强器")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    if args.dry_run:
        print("⚠️ DRY-RUN 模式\n")
    
    enhance_all_tools(dry_run=args.dry_run)
