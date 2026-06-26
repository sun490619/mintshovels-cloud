#!/usr/bin/env python3
"""
🔒 MintShovels 编译前置死锁 (Build Safeguard)
==============================================
在每次部署前强制校验 index.html 中的工具数据纯净度。
只要检测到数据污染，立刻抛出 Error 并终止部署链。

校验规则：
  1. TOOLS 数组必须恰好包含 36 个精品手写工具
  2. 必须包含 shovel-001 ~ shovel-026（26个网页工具）
  3. 必须包含 script-001 ~ script-010（10个可下载脚本）
  4. getAllTools() 函数中严禁包含 AUTO_TOOLS 引用
  5. 工具 ID 不得重复、不得缺失、不得有多余

退出码：
  0 = 通过 ✅ 可以安全部署
  1 = 失败 🔴 数据污染，阻止部署
"""

import re
import sys
import json

INDEX_FILE = "index.html"
REQUIRED_SHOVELS = [f"shovel-{i:03d}" for i in range(1, 27)]   # 001-026
REQUIRED_SCRIPTS = [f"script-{i:03d}" for i in range(1, 11)]    # 001-010
REQUIRED_TOOLS = REQUIRED_SHOVELS + REQUIRED_SCRIPTS
EXPECTED_TOTAL = len(REQUIRED_TOOLS)  # 36

def fail(msg):
    print(f"\n🔴 编译死锁触发！{msg}")
    print("   部署已自动终止。请修复数据源后重试。")
    sys.exit(1)

def ok(msg):
    print(f"   ✅ {msg}")

def main():
    print("=" * 60)
    print("🔒 MintShovels 编译前置死锁校验")
    print("=" * 60)

    # 1. 读取 index.html
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    # 2. 检查 getAllTools 函数中是否还引用 AUTO_TOOLS (实际合并逻辑)
    func_start = html.find("function getAllTools()")
    if func_start == -1:
        fail("无法定位 getAllTools() 函数定义")
    
    # 找函数结束位置：下一个顶格 function 或下一个 // =====
    next_func = html.find("\nfunction ", func_start + 1)
    next_section = html.find("\n// ==========", func_start + 1)
    func_end = -1
    candidates = [p for p in [next_func, next_section] if p > 0]
    if candidates:
        func_end = min(candidates)
    
    func_body = html[func_start:func_end] if func_end > 0 else html[func_start:func_start+500]
    
    # 去除注释行后检查
    func_body_no_comments = "\n".join(
        line for line in func_body.split("\n") 
        if not line.strip().startswith("//")
    )
    
    # 真正的合并写法: [...AUTO_TOOLS, ...TOOLS]
    if "[...AUTO_TOOLS" in func_body_no_comments:
        fail("getAllTools() 函数中仍使用 [...AUTO_TOOLS, ...TOOLS] 合并！这是严重数据污染！")
    elif "AUTO_TOOLS" in func_body_no_comments:
        fail("getAllTools() 函数中仍包含 AUTO_TOOLS 代码引用！数据可能被污染！")
    elif "AUTO_TOOLS" in func_body:
        # 只在注释中提到，属于留档说明，通过但提示
        print("   ⚠️  INFO: getAllTools() 注释中提到 AUTO_TOOLS（仅留档，无实际引用）")
        ok("getAllTools() 纯净，AUTO_TOOLS 已完全切除")
    else:
        ok("getAllTools() 纯净，AUTO_TOOLS 已完全切除")

    # 3. 提取 TOOLS 数组中的所有 id 字段
    #    TOOLS 数组: 从 "const TOOLS = [" 到 "// ========== Auto-generated tools" 之前
    tools_start = html.find("const TOOLS = [")
    if tools_start == -1:
        fail("无法找到 TOOLS 数组定义")
    
    # TOOLS 数组结束标志：注释 "// ========== Auto-generated tools"
    auto_marker = html.find("// ========== Auto-generated tools", tools_start)
    if auto_marker == -1:
        fail("无法找到 TOOLS 数组结束标记 '// ========== Auto-generated tools'")
    
    # 从 TOOLS_end_marker 向前找最近的 ];
    tools_block_raw = html[tools_start:auto_marker]
    last_bracket = tools_block_raw.rfind("];")
    if last_bracket == -1:
        fail("TOOLS 区域内无法找到数组结束符 '];'")
    
    tools_block = tools_block_raw[:last_bracket + 2]
    
    # 提取所有 id 字段值
    ids = re.findall(r'id:\s*"([^"]+)"', tools_block)
    
    shovel_ids = [i for i in ids if i.startswith("shovel-")]
    script_ids = [i for i in ids if i.startswith("script-")]
    other_ids = [i for i in ids if not i.startswith("shovel-") and not i.startswith("script-")]
    
    print(f"\n📊 工具数量统计：")
    print(f"   shovel工具: {len(shovel_ids)} 个")
    print(f"   script工具: {len(script_ids)} 个")
    print(f"   其他ID: {len(other_ids)} 个")
    print(f"   总计: {len(ids)} 个")
    
    # 4. 校验总数
    if len(ids) != EXPECTED_TOTAL:
        fail(f"TOOLS 数组包含 {len(ids)} 个工具，预期恰好 {EXPECTED_TOTAL} 个！差值: {len(ids) - EXPECTED_TOTAL:+d}")
    ok(f"工具总数 = {EXPECTED_TOTAL}，精确匹配")
    
    # 5. 校验 shovel 完整性
    missing_shovels = [s for s in REQUIRED_SHOVELS if s not in shovel_ids]
    extra_shovels = [s for s in shovel_ids if s not in REQUIRED_SHOVELS]
    
    if missing_shovels:
        fail(f"缺少 shovel 工具: {missing_shovels}")
    if extra_shovels:
        fail(f"多出未知 shovel 工具: {extra_shovels}")
    ok(f"shovel 工具完整: {len(shovel_ids)}/{len(REQUIRED_SHOVELS)} 个逐一核对通过")
    
    # 6. 校验 script 完整性
    missing_scripts = [s for s in REQUIRED_SCRIPTS if s not in script_ids]
    extra_scripts = [s for s in script_ids if s not in REQUIRED_SCRIPTS]
    
    if missing_scripts:
        fail(f"缺少 script 工具: {missing_scripts}")
    if extra_scripts:
        fail(f"多出未知 script 工具: {extra_scripts}")
    ok(f"script 工具完整: {len(script_ids)}/{len(REQUIRED_SCRIPTS)} 个逐一核对通过")
    
    # 7. 校验无重复
    if len(ids) != len(set(ids)):
        duplicates = [i for i in ids if ids.count(i) > 1]
        fail(f"发现重复工具 ID: {list(set(duplicates))}")
    ok("无重复工具 ID")
    
    # 8. 检查是否有其他类型工具混入
    if other_ids:
        fail(f"发现非标准工具 ID 混入 TOOLS 数组: {other_ids}")
    ok("无外来工具 ID 混入")
    
    # 全部通过
    print("\n" + "=" * 60)
    print("🟢 全量校验通过！数据纯净，允许部署。")
    print(f"   精品手写工具: {EXPECTED_TOTAL} 个")
    print(f"   自动生成垃圾: 0 个（已物理切除）")
    print("=" * 60)
    
    # 输出校验报告 JSON
    report = {
        "pass": True,
        "total_tools": len(ids),
        "expected_total": EXPECTED_TOTAL,
        "shovel_count": len(shovel_ids),
        "script_count": len(script_ids),
        "missing": [],
        "extra": [],
        "duplicates": [],
        "auto_tools_referenced": False
    }
    with open("build_safeguard_report.json", "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    return 0

if __name__ == "__main__":
    main()
