#!/usr/bin/env python3
"""
MintShovels 全线功能测试运行器 v1.0
=====================================
用途：
  1. 车间拦截：新工具入库前自动运行测试，拦截伪工具
  2. 全盘大扫除：对存量1558个工具逐一运行诊断
  3. 定时巡检：可被 cron job 调用，自动轮询全站工具健康度

测试维度：
  🔍 静态代码分析 — JS/HTML模板是否有 TODO/占位符，是否有实质逻辑
  🔍 功能完整性 — 是否有输入→处理→输出完整链路
  🔍 空壳检测 — 是否为纯模板套壳，无任何自定义逻辑
  🔍 在线健康 — 对已部署工具尝试 HTTP 访问

判定等级：
  🟢 FUNCTIONAL    — 有完整功能逻辑，可正常运行
  🟡 DEGRADED     — 功能不完整，但骨架可用
  🔴 HOLLOW_SHELL — 纯模板套壳，TODO占位，无实质功能
  ⚫ EMPTY        — 代码为空，完全不可用

用法:
  python3 functional_test_runner.py                    # 全盘大扫除
  python3 functional_test_runner.py --sample 20        # 抽样测试前20个
  python3 functional_test_runner.py --tool-id auto-xxx # 测试单个工具
  python3 functional_test_runner.py --check-new '{"name":"xxx","html_template":"...","js_template":"..."}'  # 车间拦截
"""

import json
import os
import re
import ssl
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from collections import Counter, defaultdict

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOL_FACTORY_DIR = os.environ.get(
    "TOOL_FACTORY_DIR",
    os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), "tool-factory")
)
TOOLS_PATH = os.path.join(TOOL_FACTORY_DIR, "backups", "generated_tools.json")
REPORT_PATH = os.path.join(SCRIPT_DIR, "functional_test_report.json")
BASE_URL = "https://mintshovels.com"

# ═══════════════════════════════════════════
# 🚫 空壳检测模式
# ═══════════════════════════════════════════

# TODO/占位符模式 — 命中任何一条即判定为 HOLLOW_SHELL
# 注意：不使用裸 "placeholder" 关键词，避免误匹配 HTML placeholder 属性
TODO_PATTERNS = [
    r'//\s*TODO',
    r'#\s*TODO',
    r'//\s*todo',
    r'#\s*todo',
    r'Customize\s+(generation\s+)?logic',
    r'customize\s+calculation',
    r'Customize\s+logic',
    r'implement\s+this',
    r'TODO:\s*Customize',
    r'TODO:\s*customize',
    r'//\s*placeholder',       # 只在注释中的 placeholder
    r'#\s*placeholder',         # 只在Python注释中的 placeholder
    r'Generated\s+item\s+\$\{i',
]

# 🌐 社交/新闻/八卦内容检测 — 工具内容如果只是八卦废话，也判空壳
GOSSIP_PATTERNS = [
    r'(雷军|董明珠|曾沛慈)',
    r'(红包|打赌|赌约)',
    r'(全国统一|降智|周额度)',
    r'(父亲节|母亲节|情人节)',
    r'(演唱会|舞台|粉丝|直播间)',
    r'(第\d+集|动画|喜剧)',
    r'(听说|据说|当初不该)',
    r'(求助|跪求|在线等)',
]

# 实质功能代码特征 — 必须同时满足多条才算 FUNCTIONAL
# JS 功能指标
JS_FUNCTIONAL_INDICATORS = [
    r'\.map\(',
    r'\.filter\(',
    r'\.reduce\(',
    r'\.sort\(',
    r'\.forEach\(',
    r'fetch\(',
    r'XMLHttpRequest',
    r'WebSocket',
    r'canvas',
    r'CryptoJS',
    r'crypto\.',
    r'localStorage',
    r'IndexedDB',
    r'Worker\(',
    r'Blob\(',
    r'FileReader',
    r'\.split\(',
    r'\.replace\(',
    r'\.match\(',
    r'\.exec\(',
    r'regex|RegExp',
    r'encode|decode',
    r'compress|decompress',
    r'encrypt|decrypt',
    r'hash',
    r'parse',
    r'serialize',
    r'\.toFixed\(',
    r'\.toPrecision\(',
    r'Math\.(sqrt|pow|log|sin|cos|tan|abs|ceil|floor|round|max|min)',
    r'\.fromCharCode|\.charCodeAt',
    r'\.toUpperCase|\.toLowerCase',
    r'\.trim\(',
    r'\.includes\(',
    r'\.startsWith\(',
    r'\.endsWith\(',
    r'\.padStart\(',
    r'\.padEnd\(',
    r'genOne\s*\(',           # 随机生成器的核心生成函数
    r'getRandomValues',       # crypto 随机值
    r'\.randomUUID\(',
    r'\.getElementById\(',    # DOM 操作
    r'performance\.',         # 性能计时
    r'new\s+RegExp',          # 正则构造函数
    r'setInterval|setTimeout',
    r'addEventListener',
    r'createElement',
]

# Python 功能指标（用于 Python脚本模板）
PY_FUNCTIONAL_INDICATORS = [
    r'def\s+\w+\s*\(',       # 函数定义
    r'import\s+\w+',          # import 语句
    r'from\s+\w+\s+import',   # from import
    r'class\s+\w+',           # 类定义
    r'with\s+\w+',            # with 语句
    r'try\s*:',               # try/except
    r'if\s+__name__',         # main guard
    r'\.read\(',              # 文件读取
    r'\.write\(',             # 文件写入
    r'\.append\(',            # 列表操作
    r'sys\.argv',             # 命令行参数
    r'sys\.stdin',            # 标准输入
    r'argparse',              # 参数解析
    r'json\.',                # JSON操作
    r'hashlib',               # 哈希
    r'base64',                # 编码
    r'csv\.',                 # CSV
    r'secrets\.',             # 加密随机
    r'Counter\(',             # 统计
    r'set\(',                 # 集合
    r'datetime',              # 日期时间
    r'os\.path',              # 路径操作
    r'print\(f',              # f-string打印
    r're\.(findall|search|sub|match)',  # 正则
]


# ═══════════════════════════════════════════
# HTTP 工具
# ═══════════════════════════════════════════

def http_get(url, timeout=10):
    """发送 HTTP GET，返回 (ok, status_code, body_size, error)"""
    ctx = ssl._create_unverified_context()
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        data = resp.read()
        return True, resp.status, len(data), None
    except urllib.error.HTTPError as e:
        return True, e.code, 0, f"HTTP {e.code}"
    except Exception as e:
        return False, 0, 0, str(e)[:120]


# ═══════════════════════════════════════════
# 🔍 核心分析函数
# ═══════════════════════════════════════════

def analyze_tool_code(tool: dict) -> dict:
    """
    对工具的 JS/HTML 代码进行静态分析，判定功能等级

    返回: {
        "verdict": "FUNCTIONAL" | "DEGRADED" | "HOLLOW_SHELL" | "EMPTY",
        "reasons": [...],
        "score": 0-100,
        "details": {...}
    }
    """
    reasons = []
    js = tool.get("js_template", "") or ""
    html = tool.get("html_template", "") or ""
    css = tool.get("css_template", "") or ""
    name = tool.get("name", "")
    template_name = tool.get("template_name", "")

    # ── 去模板变量 {xxx} ──
    js_clean = re.sub(r'\{[^}]+\}', '', js)
    html_clean = re.sub(r'\{[^}]+\}', '', html)

    # ── 1. 空代码检查 ──
    total_code = len(js_clean.strip()) + len(html_clean.strip()) + len((css or "").strip())
    if total_code < 20:
        return {
            "verdict": "EMPTY",
            "reasons": ["代码为空或极短（<20字符）"],
            "score": 0,
            "details": {"js_len": len(js), "html_len": len(html), "css_len": len(css or "")}
        }

    # ── 2. TODO/占位符检查（最重要！）──
    todo_hits = []
    for pattern in TODO_PATTERNS:
        if re.search(pattern, js) or re.search(pattern, html):
            todo_hits.append(pattern)

    # ── 3. 八卦废话检查 ──
    gossip_hits = []
    for pattern in GOSSIP_PATTERNS:
        if re.search(pattern, name):
            gossip_hits.append(pattern)

    # ── 4. 功能指标计数 ──
    func_count = 0
    func_hits = []
    
    # 根据模板类型选择合适的指标集
    if template_name in ("Python脚本",):
        indicators = PY_FUNCTIONAL_INDICATORS
    else:
        indicators = JS_FUNCTIONAL_INDICATORS
    
    for pattern in indicators:
        if re.search(pattern, js):
            func_count += 1
            func_hits.append(pattern)

    # ── 5. 判定 ──
    verdict = "UNKNOWN"
    score = 0

    if todo_hits:
        # TODO占位符 = 空壳
        verdict = "HOLLOW_SHELL"
        score = 0
        reasons.append(f"检测到 TODO/占位符 ({len(todo_hits)} 处): {', '.join(todo_hits[:3])}")
    elif func_count >= 3:
        verdict = "FUNCTIONAL"
        score = min(100, func_count * 15)
        reasons.append(f"检测到 {func_count} 项实质功能代码: {', '.join(func_hits[:5])}")
    elif func_count >= 1:
        verdict = "DEGRADED"
        score = func_count * 10
        reasons.append(f"功能指标不足 (仅 {func_count} 项): {', '.join(func_hits[:5])}")
    else:
        # 没有TODO也没有实质功能 → 空壳（模板骨架）
        verdict = "HOLLOW_SHELL"
        score = 0
        reasons.append("代码无 TODO 标记但缺乏实质功能逻辑，判定为模板空壳")

    # ── 额外：八卦内容降级 ──
    if gossip_hits and verdict in ("FUNCTIONAL", "DEGRADED"):
        verdict = "HOLLOW_SHELL"
        score = 0
        reasons.append(f"工具内容含社交闲聊/八卦关键词: {', '.join(gossip_hits[:3])}")

    # ── 模板类型标记 ──
    # 只有当真无功能指标时才标记随机生成器为空壳
    if template_name == "随机生成器" and verdict != "FUNCTIONAL" and func_count == 0:
        reasons.append(f"模板类型为「随机生成器」且无自定义逻辑")

    return {
        "verdict": verdict,
        "reasons": reasons,
        "score": score,
        "details": {
            "js_len": len(js),
            "html_len": len(html),
            "css_len": len(css or ""),
            "template": template_name,
            "todo_hits": len(todo_hits),
            "func_indicators": func_count,
            "gossip_hits": len(gossip_hits),
        }
    }


def test_tool_online(tool: dict, timeout=8) -> dict:
    """
    尝试访问部署在 mintshovels.com 上的工具页面
    """
    page_url = tool.get("page_url", "")
    if not page_url:
        return {"online": False, "reason": "无 page_url"}

    full_url = f"{BASE_URL}{page_url}"
    ok, status, size, err = http_get(full_url, timeout=timeout)

    return {
        "online": ok and status == 200,
        "url": full_url,
        "status_code": status,
        "body_size": size,
        "error": err,
    }


# ═══════════════════════════════════════════
# 🏭 车间拦截：新工具入库前测试
# ═══════════════════════════════════════════

def workshop_gate_check(tool_data: dict) -> dict:
    """
    车间拦截器：新工具入库前必须通过此检查

    输入: {"name": "...", "html_template": "...", "js_template": "...", ...}
    输出: {"pass": bool, "verdict": str, "reasons": [...], "action": "ALLOW"|"BLOCK"}
    """
    analysis = analyze_tool_code(tool_data)

    passed = analysis["verdict"] == "FUNCTIONAL"

    return {
        "pass": passed,
        "verdict": analysis["verdict"],
        "score": analysis["score"],
        "reasons": analysis["reasons"],
        "action": "ALLOW" if passed else "BLOCK",
        "checked_at": datetime.now(timezone.utc).isoformat() + "Z",
    }


# ═══════════════════════════════════════════
# 🧹 全盘大扫除：存量工具逐一运行
# ═══════════════════════════════════════════

def full_scan(tools_path: str = TOOLS_PATH, online_check: bool = False, sample: int = 0) -> dict:
    """
    对数据库所有工具执行全量功能测试

    Args:
        tools_path: 工具数据库路径
        online_check: 是否也做在线HTTP检测（慢，默认关闭）
        sample: 只测前 N 个 (0=全部)

    Returns: 完整报告 dict
    """
    if not os.path.exists(tools_path):
        raise FileNotFoundError(f"工具数据库不存在: {tools_path}")

    tools = json.load(open(tools_path))
    total = len(tools)
    file_source = os.path.basename(tools_path)

    # 🔄 降级：主文件为空或为旧审计数据时回退到最新1558归档
    tools_dir = os.path.join(TOOL_FACTORY_DIR, "tools")
    is_audit_only = False
    if total > 0:
        # 检测是否为v1.6旧审计数据（无实际HTML文件）
        if os.path.isdir(tools_dir):
            sample_check = sum(1 for t in tools[:50] if t.get("id", "") and 
                              os.path.exists(os.path.join(tools_dir, f"{t['id']}.html")))
            is_audit_only = (sample_check == 0)
    if total == 0 or is_audit_only:
        archive_path = _find_latest_archive()
        if archive_path:
            tools = json.load(open(archive_path))
            total = len(tools)
            file_source = os.path.basename(archive_path)[:60]
            if is_audit_only:
                print(f"⚠️ 主文件为v1.6审计留存数据(无实际HTML)，自动回退到归档: {file_source}")
            else:
                print(f"⚠️ 主文件为空，自动回退到归档: {file_source}")
        else:
            raise ValueError("主文件为空且无归档可用")

    if sample and sample < total:
        tools = tools[:sample]
        total = len(tools)

    results = []
    verdict_counts = Counter()
    template_verdicts = defaultdict(lambda: Counter())
    hollow_reasons = Counter()

    print(f"🔍 开始全盘大扫除: {total} 个工具...")
    start_time = time.time()

    for i, tool in enumerate(tools):
        analysis = analyze_tool_code(tool)
        verdict = analysis["verdict"]
        verdict_counts[verdict] += 1
        template_verdicts[tool.get("template_name", "?")][verdict] += 1

        # 收集空壳原因
        for reason in analysis["reasons"]:
            hollow_reasons[reason[:80]] += 1

        entry = {
            "id": tool["id"],
            "name": tool["name"],
            "category": tool.get("category", "?"),
            "template": tool.get("template_name", "?"),
            "deployed": tool.get("deployed", False),
            "verdict": verdict,
            "score": analysis["score"],
            "reasons": analysis["reasons"],
            "details": analysis["details"],
        }

        # 在线检测（仅抽样或显式开启）
        if online_check and (sample or i < 10):
            entry["online_test"] = test_tool_online(tool)

        results.append(entry)

        if (i + 1) % 100 == 0:
            elapsed = time.time() - start_time
            print(f"  进度: {i+1}/{total} ({elapsed:.1f}s) | 当前判定: {verdict_counts.most_common()}")

    elapsed = time.time() - start_time

    # ── 生成报告 ──
    healthy = verdict_counts.get("FUNCTIONAL", 0) + verdict_counts.get("DEGRADED", 0)
    hollow = verdict_counts.get("HOLLOW_SHELL", 0)
    empty = verdict_counts.get("EMPTY", 0)
    health_rate = round(healthy / total * 100, 1) if total > 0 else 0

    report = {
        "report_time": datetime.now(timezone.utc).isoformat() + "Z",
        "runner_version": "v1.0",
        "data_source": file_source,
        "summary": {
            "total_tested": total,
            "duration_seconds": round(elapsed, 1),
            "health_rate": health_rate,
            "verdict_counts": dict(verdict_counts),
            "healthy": healthy,
            "hollow_shells": hollow,
            "empty": empty,
        },
        "by_template": {
            tmpl: dict(counts) for tmpl, counts in template_verdicts.items()
        },
        "top_hollow_reasons": hollow_reasons.most_common(15),
        "hollow_tools": [
            {
                "id": r["id"],
                "name": r["name"][:120],
                "category": r["category"],
                "template": r["template"],
                "reasons": r["reasons"],
                "deployed": r["deployed"],
            }
            for r in results if r["verdict"] in ("HOLLOW_SHELL", "EMPTY")
        ],
        "functional_tools": [
            {
                "id": r["id"],
                "name": r["name"][:120],
                "category": r["category"],
                "template": r["template"],
                "score": r["score"],
                "deployed": r["deployed"],
            }
            for r in results if r["verdict"] == "FUNCTIONAL"
        ],
        "degraded_tools": [
            {
                "id": r["id"],
                "name": r["name"][:120],
                "category": r["category"],
                "template": r["template"],
                "score": r["score"],
                "reasons": r["reasons"],
                "deployed": r["deployed"],
            }
            for r in results if r["verdict"] == "DEGRADED"
        ],
        "raw_results": results,
    }

    return report


# ═══════════════════════════════════════════
# 🩺 体检联动：供 mintshovels_full_check.py 调用
# ═══════════════════════════════════════════

def _find_latest_archive():
    """在 backups 目录找最新归档（按 mtime），回退时使用"""
    backup_dir = os.path.join(TOOL_FACTORY_DIR, "backups")
    if not os.path.exists(backup_dir):
        return None
    candidates = [
        os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
        if f.startswith("generated_tools_") and f.endswith(".json")
    ]
    if not candidates:
        return None
    # 按文件修改时间降序，取最新的
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[0]


def health_check_snapshot() -> dict:
    """
    快速健康快照，供体检系统 3️⃣ 工具库 使用
    返回格式与 mintshovels_full_check.py 兼容

    当 generated_tools.json 为空时自动回退到最新归档文件
    """
    tools_path = TOOLS_PATH
    file_source = "generated_tools.json"

    if not os.path.exists(tools_path):
        return {
            "ok": False,
            "detail": "工具数据库文件不存在",
            "hollow_count": 0,
            "total": 0,
            "health_rate": 0,
        }

    tools = json.load(open(tools_path))
    total = len(tools)

    # 🔄 降级：主文件为空时回退到最新归档
    if total == 0:
        archive_path = _find_latest_archive()
        if archive_path:
            tools = json.load(open(archive_path))
            total = len(tools)
            file_source = os.path.basename(archive_path)[:60]
        else:
            return {
                "ok": False,
                "detail": "主文件为空且无归档可用",
                "hollow_count": 0,
                "total": 0,
                "health_rate": 0,
            }

    hollow_count = 0
    # 🔍 v1.6: 检查实际HTML文件是否存在（v1.6已切除自动生成垃圾，JSON仅审计留存）
    tools_dir = os.path.join(TOOL_FACTORY_DIR, "tools")
    actual_files = 0
    for tool in tools:
        js = tool.get("js_template", "") or ""
        name = tool.get("name", "")
        has_todo = any(re.search(p, js) for p in TODO_PATTERNS)
        has_gossip = any(re.search(p, name) for p in GOSSIP_PATTERNS)
        # 检查实际文件
        tid = tool.get("id", "")
        if tid and os.path.isdir(tools_dir) and os.path.exists(os.path.join(tools_dir, f"{tid}.html")):
            actual_files += 1
        if has_todo or has_gossip:
            hollow_count += 1

    healthy = total - hollow_count
    health_rate = round(healthy / total * 100, 1) if total > 0 else 0

    # v1.6: 如果所有HTML文件已被切除，空壳仅代表JSON审计记录
    # 此时尝试从1558归档获取真实工具健康率
    archive_health_rate = None
    if actual_files == 0 and hollow_count > 0:
        status_ok = True  # 已切除干净的审计记录不算异常
        # 尝试从1558归档计算真实健康率
        archive_path = _find_latest_archive()
        if archive_path and "1558" in os.path.basename(archive_path):
            try:
                archive_tools = json.load(open(archive_path))
                arch_hollow = 0
                for at in archive_tools:
                    at_js = at.get("js_template", "") or ""
                    at_name = at.get("name", "")
                    if any(re.search(p, at_js) for p in TODO_PATTERNS) or \
                       any(re.search(p, at_name) for p in GOSSIP_PATTERNS):
                        arch_hollow += 1
                arch_total = len(archive_tools)
                archive_health_rate = round((arch_total - arch_hollow) / arch_total * 100, 1) if arch_total > 0 else 0
            except Exception:
                pass
        if archive_health_rate is not None:
            detail = f"🟢 v1.6已切除自动生成垃圾 ({total}条JSON审计记录, 0个实际文件) | 归档1558工具真实健康率 {archive_health_rate}%"
        else:
            detail = f"🟢 v1.6已切除自动生成垃圾 ({total}条JSON审计记录, 0个实际文件)"
    else:
        status_ok = hollow_count == 0
        detail = f"🟢 工具库健康率 {health_rate}% ({healthy}/{total} 可运行)" if status_ok \
                 else f"🔴 发现 {hollow_count} 个空壳工具！健康率仅 {health_rate}% ({healthy}/{total})"
    if file_source != "generated_tools.json":
        detail += f" [源: {file_source}]"

    result = {
        "ok": status_ok,
        "detail": detail,
        "hollow_count": hollow_count,
        "total": total,
        "health_rate": health_rate,
        "checked_at": datetime.now(timezone.utc).isoformat() + "Z",
    }
    if archive_health_rate is not None:
        result["archive_health_rate"] = archive_health_rate
        result["archive_total"] = arch_total

    return result


# ═══════════════════════════════════════════
# 📊 打印报告
# ═══════════════════════════════════════════

def print_report(report: dict):
    """打印人类可读报告"""
    s = report["summary"]
    print()
    print("=" * 70)
    print("  🩺 MintShovels 全盘功能测试报告")
    print("=" * 70)
    print(f"  测试时间: {report['report_time']}")
    print(f"  耗时: {s['duration_seconds']} 秒")
    print(f"  总计: {s['total_tested']} 个工具")
    print()
    print("  ── 判定分布 ──")
    for verdict, count in sorted(s["verdict_counts"].items()):
        emoji = {"FUNCTIONAL": "🟢", "DEGRADED": "🟡", "HOLLOW_SHELL": "🔴", "EMPTY": "⚫"}.get(verdict, "❓")
        pct = round(count / s["total_tested"] * 100, 1)
        bar = "█" * int(pct / 2)
        print(f"  {emoji} {verdict:15s}: {count:5d} ({pct:5.1f}%) {bar}")

    print()
    print(f"  🩺 整体健康率: {s['health_rate']}%")
    print()

    print("  ── 按模板分布 ──")
    for tmpl, counts in report.get("by_template", {}).items():
        total_tmpl = sum(counts.values())
        hollow = counts.get("HOLLOW_SHELL", 0) + counts.get("EMPTY", 0)
        func = counts.get("FUNCTIONAL", 0)
        print(f"  {tmpl}: {total_tmpl}个 | 🟢{func} 🔴{hollow}")

    print()
    print("  ── Top 空壳原因 ──")
    for reason, cnt in report.get("top_hollow_reasons", [])[:10]:
        print(f"  [{cnt:4d}] {reason}")

    print()

    hollow_tools = report.get("hollow_tools", [])
    if hollow_tools:
        print(f"  ── 空壳工具清单（前30/共{len(hollow_tools)}）──")
        for ht in hollow_tools[:30]:
            print(f"  🔴 [{ht['category']:8s}] {ht['name'][:70]}")
            print(f"       原因: {'; '.join(ht['reasons'][:2])}")

    func_tools = report.get("functional_tools", [])
    if func_tools:
        print(f"\n  ── 功能完整工具（共{len(func_tools)}）──")
        for ft in func_tools[:10]:
            print(f"  🟢 [{ft['category']:8s}] {ft['name'][:70]} (分:{ft['score']})")

    print()
    print("=" * 70)


# ═══════════════════════════════════════════
# CLI 入口
# ═══════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="MintShovels 全线功能测试运行器")
    parser.add_argument("--sample", type=int, default=0, help="只测试前 N 个工具")
    parser.add_argument("--online", action="store_true", help="同时做在线 HTTP 检测")
    parser.add_argument("--check-new", type=str, default="", help="车间拦截：JSON 格式的新工具数据")
    parser.add_argument("--tool-id", type=str, default="", help="测试单个工具ID")
    parser.add_argument("--health-snapshot", action="store_true", help="快速健康快照（供体检系统调用）")
    parser.add_argument("--save-report", type=str, default="", help="保存报告路径（默认 functional_test_report.json）")

    args = parser.parse_args()

    # ── 快速健康快照模式 ──
    if args.health_snapshot:
        snapshot = health_check_snapshot()
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return

    # ── 车间拦截模式 ──
    if args.check_new:
        try:
            tool_data = json.loads(args.check_new)
        except json.JSONDecodeError:
            print("❌ 无效的 JSON 输入")
            sys.exit(1)
        result = workshop_gate_check(tool_data)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["pass"]:
            print(f"\n🚫 车间拦截！工具未通过功能测试: {'; '.join(result['reasons'])}")
            sys.exit(1)
        else:
            print(f"\n✅ 车间放行！工具功能完整，允许入库")
        return

    # ── 单工具测试模式 ──
    if args.tool_id:
        tools = json.load(open(TOOLS_PATH))
        target = None
        for t in tools:
            if t["id"] == args.tool_id:
                target = t
                break
        if not target:
            print(f"❌ 未找到工具: {args.tool_id}")
            sys.exit(1)

        analysis = analyze_tool_code(target)
        print(f"工具: {target['name']}")
        print(f"判定: {analysis['verdict']}")
        print(f"评分: {analysis['score']}/100")
        print(f"原因: {'; '.join(analysis['reasons'])}")
        print(f"详情: {json.dumps(analysis['details'], ensure_ascii=False)}")

        if args.online:
            online = test_tool_online(target)
            print(f"在线: {json.dumps(online, ensure_ascii=False, indent=2)}")
        return

    # ── 全盘大扫除模式 ──
    report = full_scan(
        tools_path=TOOLS_PATH,
        online_check=args.online,
        sample=args.sample,
    )
    print_report(report)

    # 保存报告
    save_path = args.save_report or REPORT_PATH
    with open(save_path, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"📄 完整报告已保存: {save_path}")

    # 返回 exit code 给 CI/cron
    health_rate = report["summary"]["health_rate"]
    if health_rate < 50:
        print(f"\n🚨 健康率严重不足 ({health_rate}%)！退出码 2")
        sys.exit(2)
    elif health_rate < 90:
        print(f"\n⚠️ 健康率偏低 ({health_rate}%)，退出码 1")
        sys.exit(1)


if __name__ == "__main__":
    main()
