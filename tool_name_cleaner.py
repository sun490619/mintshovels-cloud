#!/usr/bin/env python3
"""
MintShovels 存量工具名称清洗器 v2.0
====================================
v2.0 修正：
  - 垃圾检测只用硬模式（名人/新闻/游戏/地名/广告），不用意图分类器重判
  - 意图分类器仅用于新需求雷达，不用于已有工具
  - 命名清理：去Random前缀 + 去尾缀 + 修复中英缝合
"""

import json, re, sys, os
from collections import Counter
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOL_FACTORY_DIR = os.environ.get(
    "TOOL_FACTORY_DIR",
    os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), "tool-factory")
)
TOOLS_PATH = os.path.join(TOOL_FACTORY_DIR, "backups", "generated_tools.json")
BACKUP_DIR = os.path.join(TOOL_FACTORY_DIR, "backups")

# ═══════════════════════════════════════════════════════════
# 硬模式垃圾检测（不依赖意图分类器）
# ═══════════════════════════════════════════════════════════

GARBAGE_PATTERNS = [
    # 名人/人物
    (r'(张靓颖|雷军|董明珠|曾沛慈|马斯克|特朗普|拜登|Putin|Zelensky|Xi Jinping)', "含名人"),
    # 新闻句式
    (r'(新闻|快讯|头条|突发|报道|最新消息|breaking news|just in|leaked|revealed)', "新闻标题"),
    # 八卦/社交闲聊
    (r'(打赌|赌约|后悔|不该|道歉|对不起|降智|降麻了|周额度|额度.*增|听说|据说)', "社交闲聊"),
    # 娱乐直播
    (r'(主播|直播间|粉丝.*狂|演唱会|舞台|综艺|第.*集|喜剧|动画|票房|box office|opening weekend)', "娱乐内容"),
    # 购物/商品
    (r'(paper towels|toilet paper|laundry detergent|gift card|礼品卡|family rolls|regular rolls)', "商品描述"),
    # 破解/广告
    (r'(出.*协议源码|通杀|破解|免费送|加微信|QQ群)', "广告/破解"),
    # 纯游戏名 (不是工具)
    (r'\b(cyberpunk\s*2077|fruit shooter|dungeon|dragon.*quest|celestial.*quest)\b', "游戏名称"),
    # 纯社交平台名
    (r'^(小红书[\s_]|淘宝[\s_]|抖音[\s_]|快手[\s_]|微博[\s_]|知乎[\s_])', "社交平台关键词"),
    # 纯地名
    (r'^(Cape cod|Boston|New York|London|Paris|Tokyo|Sydney)$', "纯地名"),
    # 无意义短词 (名字清洗后为空)
    (r'^[a-zA-Z]{1,2}$', "名称过短"),
]

def is_garbage_tool(tool):
    """硬模式垃圾检测"""
    name = tool.get("name", "")
    name_zh = tool.get("name_zh", "")
    combined = f"{name} {name_zh}"
    
    for pattern, reason in GARBAGE_PATTERNS:
        if re.search(pattern, combined, re.I):
            return True, reason
    
    return False, ""


# ═══════════════════════════════════════════════════════════
# 命名规范化
# ═══════════════════════════════════════════════════════════

def clean_tool_name(tool):
    """清洗工具名称"""
    name = tool.get("name", "")
    name_zh = tool.get("name_zh", "")
    tmpl = tool.get("template_name", "随机生成器")
    changes = []
    
    new_name = name
    new_name_zh = name_zh
    
    # ── 1. 去 "Random " 前缀 ──
    if re.match(r'^Random\s+', new_name, re.I):
        new_name = re.sub(r'^Random\s+', '', new_name, flags=re.IGNORECASE).strip()
        changes.append("去Random前缀")
    
    # ── 2. 去英文工具尾缀 ──
    english_suffixes = [
        r'\s+Generator$', r'\s+Checker$', r'\s+Calculator$', 
        r'\s+Tool$', r'\s+Script$', r'\s+Converter$',
        r'\s+Validator$', r'\s+Analyzer$',
    ]
    for pattern in english_suffixes:
        if re.search(pattern, new_name, re.I):
            label = re.search(pattern, new_name, re.I).group().strip()
            new_name = re.sub(pattern, '', new_name, flags=re.IGNORECASE).strip()
            changes.append(f"去尾缀:{label}")
            break  # 只去掉一个尾缀
    
    # ── 3. 去中文尾缀 ──
    chinese_suffixes = [
        r'\s*生成器$', r'\s*验证器$', r'\s*计算器$',
        r'\s*工具$', r'\s*脚本$', r'\s*转换器$',
    ]
    for pattern in chinese_suffixes:
        if re.search(pattern, new_name_zh):
            label = re.search(pattern, new_name_zh).group().strip()
            new_name_zh = re.sub(pattern, '', new_name_zh).strip()
            changes.append(f"去中文尾缀:{label}")
            break
    
    # ── 4. 中英缝合修复 ──
    if new_name:
        has_cn = bool(re.search(r'[\u4e00-\u9fff]', new_name))
        has_en = bool(re.search(r'[a-zA-Z]{3,}', new_name))
        if has_cn and has_en:
            # 提取中文部分作为主名
            cn_parts = re.findall(r'[\u4e00-\u9fff]+', new_name)
            if cn_parts and len(''.join(cn_parts)) >= 2:
                new_name = ''.join(cn_parts)
                changes.append("中英缝合修复")
    
    # ── 5. 确保不为空 ──
    if not new_name or len(new_name.strip()) < 2:
        if new_name_zh and len(new_name_zh.strip()) >= 2:
            new_name = new_name_zh.strip()
            changes.append("从name_zh恢复")
        else:
            new_name = f"Tool #{tool.get('id', '?')[-6:]}"
            changes.append("生成默认名")
    
    if not new_name_zh or len(new_name_zh.strip()) < 2:
        new_name_zh = new_name.strip()
    
    # ── 6. 根据模板类型追加合适后缀 ──
    suffix_map = {
        "随机生成器": ("生成器", "Generator"),
        "检测验证器": ("验证器", "Checker"),
        "检测/验证器": ("验证器", "Checker"),
        "计算器": ("计算器", "Calculator"),
        "Python脚本": ("工具", "Tool"),
    }
    
    suffix_info = suffix_map.get(tmpl)
    if suffix_info:
        zh_suffix = suffix_info[0]
        name_zh_final = new_name_zh.strip()
        if not name_zh_final.endswith(zh_suffix):
            name_zh_final = f"{name_zh_final}{zh_suffix}"
        
        name_final = new_name.strip()
        
        was_modified = len(changes) > 0
        return name_final, name_zh_final, was_modified, changes
    
    was_modified = len(changes) > 0
    return new_name.strip(), new_name_zh.strip(), was_modified, changes


# ═══════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════

def clean_all_tools(dry_run=False):
    tools = json.load(open(TOOLS_PATH))
    total = len(tools)
    print(f"📊 加载 {total} 个工具\n")

    stats = {"total": total, "cleaned": 0, "garbage": 0, "unchanged": 0}
    garbage_list = []
    cleanup_log = []
    
    for i, tool in enumerate(tools):
        name = tool.get("name", "")
        tool_id = tool.get("id", "")
        
        # 垃圾检测
        is_garbage, reason = is_garbage_tool(tool)
        if is_garbage:
            stats["garbage"] += 1
            if not dry_run:
                tool["_garbage"] = True
                tool["_garbage_reason"] = reason
                tool["_garbage_at"] = datetime.now(timezone.utc).isoformat()
            garbage_list.append({"id": tool_id, "name": name[:60], "reason": reason})
            continue
        
        # 名称清洗
        new_name, new_name_zh, modified, changes = clean_tool_name(tool)
        
        if modified:
            stats["cleaned"] += 1
            if not dry_run:
                tool["name"] = new_name
                tool["name_zh"] = new_name_zh
                tool["_name_cleaned"] = True
                tool["_name_cleaned_at"] = datetime.now(timezone.utc).isoformat()
            cleanup_log.append({
                "id": tool_id,
                "old_name": name[:60],
                "new_name": new_name[:60],
                "new_name_zh": new_name_zh[:40],
                "changes": changes,
            })
        else:
            stats["unchanged"] += 1
        
        if (i + 1) % 500 == 0:
            print(f"  进度: {i+1}/{total}")
    
    # 写回
    if not dry_run:
        backup_path = os.path.join(BACKUP_DIR, f"generated_tools_pre_name_clean_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(backup_path, "w") as f:
            json.dump(json.load(open(TOOLS_PATH)), f, ensure_ascii=False, indent=2)
        print(f"\n💾 备份: {os.path.basename(backup_path)}")
        
        with open(TOOLS_PATH, "w") as f:
            json.dump(tools, f, ensure_ascii=False, indent=2)
        print(f"✅ 已写回 {TOOLS_PATH}")
    
    # 统计
    active = total - stats["garbage"]
    print(f"\n{'='*70}")
    print(f"📊 清洗统计:")
    print(f"  总工具: {total}")
    print(f"  名称优化: {stats['cleaned']} ({stats['cleaned']/total*100:.1f}%)")
    print(f"  垃圾标记: {stats['garbage']}")
    print(f"  无需修改: {stats['unchanged']}")
    print(f"  有效工具: {active}")
    
    if garbage_list:
        print(f"\n🗑 垃圾标记 (前15):")
        for g in garbage_list[:15]:
            print(f"  {g['id']}: '{g['name']}' → {g['reason']}")
    
    if cleanup_log:
        print(f"\n✨ 名称优化 (前15):")
        for log in cleanup_log[:15]:
            print(f"  {log['id']}: '{log['old_name']}' → '{log['new_name']}' [{log['new_name_zh']}]")
    
    # 保存账本
    ledger_path = os.path.join(BACKUP_DIR, "name_cleanup_ledger.json")
    with open(ledger_path, "w") as f:
        json.dump({"cleaned_at": datetime.now(timezone.utc).isoformat(), "stats": stats, "garbage": garbage_list, "changes": cleanup_log}, f, ensure_ascii=False, indent=2)
    print(f"\n📋 清洗账本: {os.path.basename(ledger_path)}")
    
    return stats, garbage_list, cleanup_log


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="存量工具名称清洗器 v2.0")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if args.dry_run:
        print("⚠️ DRY-RUN 模式\n")
    clean_all_tools(dry_run=args.dry_run)
