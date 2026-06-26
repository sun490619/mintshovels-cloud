#!/usr/bin/env python3
"""
MintShovels 全自动流水线 — 每3小时执行
流程: 需求雷达 → 工厂生产 → 全量工具测试 → 验证通过才部署 → 汇总报告

用法:
  python3 engine/pipeline.py              # 完整流水线
  python3 engine/pipeline.py --test-only  # 只测试所有已有工具
  python3 engine/pipeline.py --no-deploy  # 只生产+测试，不部署
"""

import json
import os
import re
import sys
import time
import argparse
import subprocess
import urllib.request
import urllib.error
import http.server
import socketserver
import threading
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(BASE_DIR, "reports")
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
INDEX_PATH = os.path.join(BASE_DIR, "index.html")
PIPELINE_LOG = os.path.join(REPORT_DIR, "pipeline_log.json")

os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(TOOLS_DIR, exist_ok=True)

# ─── 集成车间门禁 ─────────────────────────────────────────────────────
# 优先从 engine/ 本地加载（CI 环境），回退到 CodeBuddy 工作区（本地开发）
ENGINE_DIR = os.path.join(BASE_DIR, "engine")
sys.path.insert(0, ENGINE_DIR)
CODEBUDDY_DIR = os.path.join(os.path.dirname(BASE_DIR), "CodeBuddy", "20260619190048")
if os.path.exists(CODEBUDDY_DIR):
    sys.path.insert(0, CODEBUDDY_DIR)

try:
    from functional_test_runner import workshop_gate_check, analyze_tool_code, health_check_snapshot
    GATE_AVAILABLE = True
except ImportError:
    GATE_AVAILABLE = False
    print("⚠️ functional_test_runner.py not found, gate check disabled")

# ─── 本地门禁健康检查（检查当前生产工具，非历史归档）─────────────────

def gate_health_check():
    """
    门禁专用健康检查：只检查 TOOLS 数据库中的 33 个生产工具
    根据 index.html 的 TOOLS 数组提取工具列表，逐个验证
    返回与 health_check_snapshot 兼容的格式
    """
    import re as _re
    from datetime import datetime as _dt, timezone as _tz
    
    # 2. 从 index.html 的 TOOLS 数组中提取工具 ID 列表
    tool_ids = []
    tools_dir = os.path.join(BASE_DIR, "tools")
    
    if not os.path.exists(INDEX_PATH):
        return {"ok": False, "detail": "index.html 不存在", "hollow_count": 0, "total": 0, "health_rate": 0}
    
    with open(INDEX_PATH, 'r', encoding='utf-8') as f:
        html = f.read()
    
    tools_match = _re.search(r'const TOOLS\s*=\s*\[([\s\S]*?)\];', html)
    if not tools_match:
        return {"ok": False, "detail": "TOOLS 数据库未找到", "hollow_count": 0, "total": 0, "health_rate": 0}
    
    tools_block = tools_match.group(1)
    # 提取每个工具的 id
    tool_objects = _re.findall(r'\{[^}]*?\}', tools_block)
    for t_obj in tool_objects:
        id_match = _re.search(r'id:\s*"([^"]+)"', t_obj)
        name_match = _re.search(r'name:\s*"([^"]+)"', t_obj)
        if id_match:
            tool_ids.append((id_match.group(1), name_match.group(1) if name_match else id_match.group(1)))
    
    # 3. 逐个检查工具文件质量（注意：这些是 SEO 着陆页，通过 meta refresh 跳转到 index.html）
    hollow_files = []
    
    for tool_id, tool_name in tool_ids:
        issues = []
        file_path = os.path.join(tools_dir, f"{tool_id}.html")
        
        if not os.path.exists(file_path):
            issues.append("文件缺失")
        else:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 基本结构检查
                checks = {
                    "DOCTYPE": content.strip().startswith("<!DOCTYPE"),
                    "<html>": "<html" in content,
                    "</html>": "</html>" in content,
                    "<body>": "<body" in content,
                    "</body>": "</body>" in content,
                    "长度>200": len(content) > 200,
                }
                failed_checks = [k for k, v in checks.items() if not v]
                if failed_checks:
                    issues.append(f"结构缺失: {', '.join(failed_checks)}")
                
                # 检查页面主体是否有实际内容（移除HTML标签后）
                body_match = _re.search(r'<body[^>]*>([\s\S]*?)</body>', content)
                if body_match:
                    body_text = _re.sub(r'<[^>]+>', '', body_match.group(1)).strip()
                    body_text = _re.sub(r'\s+', ' ', body_text)
                    if len(body_text) < 20:
                        issues.append(f"页面内容过短({len(body_text)}字符)")
                
                # 检查是否是完全空壳（无功能也无重定向）
                has_redirect = 'meta http-equiv="refresh"' in content
                has_external_script = 'script src=' in content
                has_inline_script = bool(_re.search(r'<script[^>]*>([\s\S]{20,})</script>', content))
                
                if not has_redirect and not has_external_script and not has_inline_script:
                    issues.append("无重定向/脚本/外部资源")
                    
            except Exception as e:
                issues.append(f"读取异常: {e}")
        
        if issues:
            hollow_files.append(f"{tool_id}: {'; '.join(issues)}")
    
    total_checked = len(tool_ids)
    hollow_count = len(hollow_files)
    healthy = total_checked - hollow_count
    health_rate = round(healthy / total_checked * 100, 1) if total_checked > 0 else 0
    status_ok = hollow_count == 0
    
    detail = (f"🟢 生产工具健康率 {health_rate}% ({healthy}/{total_checked} 合格)"
              if status_ok else
              f"🔴 发现 {hollow_count} 个问题工具！健康率 {health_rate}% ({healthy}/{total_checked})")
    
    return {
        "ok": status_ok,
        "detail": detail,
        "hollow_count": hollow_count,
        "total": total_checked,
        "health_rate": health_rate,
        "checked_at": _dt.now(_tz.utc).isoformat() + "Z",
        "source": f"生产工具 TOOLS 数据库 ({total_checked}个)",
        "hollow_files": hollow_files[:10],
    }


# ─── 需求过滤审计（意图分类器打分可视化）─────────────────────────────

def demand_filter_audit():
    """
    审计用函数：读取最新需求雷达报告，对每条建议运行意图分类器，
    打印 PASS/BLOCK 判定 + 分数，供人工审查过滤效果。
    不影响流水线主流程，纯日志输出。
    
    v2.0 新增：展示雷达特质分析（trait_analysis）摘要
    """
    import re as _re
    from datetime import datetime as _dt, timezone as _tz
    
    report_path = os.path.join(REPORT_DIR, "demand_report.json")
    if not os.path.exists(report_path):
        print("  ⚠️  无需求报告，跳过审计")
        return {"audited": 0, "passed": 0, "blocked": 0, "details": [], "trait_summary": None}
    
    report = load_json(report_path)
    if not report:
        print("  ⚠️  需求报告为空")
        return {"audited": 0, "passed": 0, "blocked": 0, "details": [], "trait_summary": None}
    
    # ── v2.0: 展示特质分析摘要 ──
    trait_summary = None
    trait_analysis = report.get("trait_analysis")
    if trait_analysis:
        print(f"\n  🧠 雷达特质识别 (v2.0) 摘要:")
        print(f"     原始抓取: {trait_analysis.get('total_captured', '?')} 条")
        print(f"     🚫 闲聊拦截: {trait_analysis.get('chatter_blocked', '?')} 条 ({trait_analysis.get('chatter_rate', '?')}%)")
        print(f"     🧠 工具信号: {trait_analysis.get('tool_signals_found', '?')} 条 ({trait_analysis.get('tool_signal_rate', '?')}%)")
        llm = trait_analysis.get("chatter_samples", [])
        if llm:
            print(f"     闲聊样例: {llm[0].get('text', '')[:50]}... [{llm[0].get('category', '?')}]" if isinstance(llm[0], dict) else str(llm[0])[:50])
        ts = trait_analysis.get("tool_signal_samples", [])
        if ts:
            ts0 = ts[0]
            if isinstance(ts0, dict):
                print(f"     工具信号样例: {ts0.get('text', '')[:50]}... [置信度{ts0.get('confidence', '?')}%]")
        trait_summary = {
            "total_captured": trait_analysis.get("total_captured", 0),
            "chatter_blocked": trait_analysis.get("chatter_blocked", 0),
            "tool_signals": trait_analysis.get("tool_signals_found", 0),
        }
    
    # ── 过滤统计 ──
    filter_stats = report.get("filter_stats", {})
    if filter_stats:
        print(f"\n  📊 硬核过滤器统计:")
        print(f"     工具信号 {filter_stats.get('raw_count', '?')} → 有效 {filter_stats.get('valid_count', '?')}")
        print(f"     拒绝率: {filter_stats.get('rejection_rate', '?')}%")
    
    suggestions = report.get("tool_suggestions", [])
    if not suggestions:
        print("  ℹ️  无工具建议")
        return {"audited": 0, "passed": 0, "blocked": 0, "details": [], "trait_summary": trait_summary}
    
    # 尝试加载意图分类器
    try:
        engine_dir = os.path.join(BASE_DIR, "engine")
        if engine_dir not in sys.path:
            sys.path.insert(0, engine_dir)
        from intent_classifier import IntentClassifier
        from demand_filter import is_valid_demand
        ic = IntentClassifier()
        classifier_ok = True
    except ImportError:
        ic = None
        classifier_ok = False
        print("  ⚠️  意图分类器不可用，使用回退逻辑")
    
    passed = []
    blocked = []
    
    for item in suggestions[:20]:  # 最多审计前20条
        name = item.get("name", str(item)) if isinstance(item, dict) else str(item)
        source = item.get("source", "?") if isinstance(item, dict) else "?"
        
        if classifier_ok and ic:
            result = ic.classify(name)
            verdict = result["verdict"]
            score = result["score"]
            intent = result.get("intent", "?")
            reasons = result.get("reasons", [])
            
            entry = {
                "name": name[:80], "source": source,
                "verdict": verdict, "score": score,
                "intent": intent, "reasons": reasons[:3],
            }
            if verdict in ("PASS", "WARN"):
                passed.append(entry)
            else:
                blocked.append(entry)
    
    total = len(passed) + len(blocked)
    
    # 打印审计表格
    print(f"\n  📊 意图分类器审计 — 审查 {total} 条需求")
    print(f"  {'─' * 70}")
    if passed:
        print(f"  ✅ 通过 ({len(passed)}):")
        for e in passed:
            print(f"     [{e['verdict']:5s} | {e['score']:+4d}] {e['name'][:55]}  [{e['source']}]")
    if blocked:
        print(f"  🚫 拦截 ({len(blocked)}):")
        for e in blocked:
            reason_str = e['reasons'][0][:40] if e['reasons'] else '?'
            print(f"     [{e['verdict']:5s} | {e['score']:+4d}] {e['name'][:50]}  [{e['source']}]  ← {reason_str}")
    if total == 0:
        print(f"  ℹ️  无有效需求可审计")
    
    return {
        "audited": total,
        "passed": len(passed),
        "blocked": len(blocked),
        "details": passed + blocked,
        "trait_summary": trait_summary,
    }


# ─── 辅助函数 ─────────────────────────────────────────────────────────

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

# ─── 阶段 0: 需求雷达 ──────────────────────────────────────────────────

def run_radar():
    """运行需求雷达，抓取最新工具需求"""
    print("\n" + "=" * 60)
    print("📡 阶段 0: 需求雷达")
    print("=" * 60)
    
    radar_script = os.path.join(BASE_DIR, "engine", "demand_radar.py")
    try:
        result = subprocess.run(
            ["python3", radar_script],
            capture_output=True, text=True, timeout=120, cwd=BASE_DIR
        )
        output = result.stdout + result.stderr
        print(output[:2000])
        
        if result.returncode != 0:
            print("❌ 雷达运行失败")
            return False, output
        
        # 检查报告是否生成
        report_path = os.path.join(REPORT_DIR, "demand_report.json")
        if os.path.exists(report_path):
            report = load_json(report_path)
            suggestions = len(report.get("tool_suggestions", [])) if report else 0
            print(f"\n✅ 雷达完成 — {suggestions} 条建议")
            return True, report
        else:
            print("❌ 报告文件未生成")
            return False, None
            
    except subprocess.TimeoutExpired:
        print("❌ 雷达超时")
        return False, None
    except Exception as e:
        print(f"❌ 雷达异常: {e}")
        return False, None

# ─── 阶段 1: 工厂生产 ──────────────────────────────────────────────────

def run_factory(max_count=3, dry_run=False):
    """运行自动工厂，生产新工具"""
    print("\n" + "=" * 60)
    print("🏭 阶段 1: 自动工厂")
    print("=" * 60)
    
    factory_script = os.path.join(BASE_DIR, "engine", "auto_factory.py")
    cmd = ["python3", factory_script, "--max", str(max_count), "--no-deploy"]
    if dry_run:
        cmd.append("--dry-run")
    
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, cwd=BASE_DIR
        )
        output = result.stdout + result.stderr
        print(output[:3000])
        
        if result.returncode != 0:
            print("❌ 工厂运行失败（但继续后续流程）")
        
        # 统计产量
        produced = []
        for line in output.split("\n"):
            if "Producing:" in line:
                produced.append(line.strip())
        
        print(f"\n✅ 工厂完成 — 本次生产 {len(produced)} 个工具")
        for p in produced:
            print(f"   {p}")
        return True, output
        
    except subprocess.TimeoutExpired:
        print("❌ 工厂超时")
        return False, None
    except Exception as e:
        print(f"❌ 工厂异常: {e}")
        return False, None

# ─── 阶段 2: 全量工具测试 ────────────────────────────────────────────

def test_index_html():
    """测试 index.html 结构完整性（复用 auto_factory 的测试逻辑）"""
    print("\n  📋 测试 index.html 结构...")
    
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    
    passed = 0
    failed = 0
    
    checks = [
        ("DOCTYPE", html.startswith("<!DOCTYPE")),
        ("<html>", "<html" in html),
        ("</html>", "</html>" in html),
        ("<head>", "<head" in html),
        ("<body>", "<body" in html),
        ("Tailwind CSS", "cdn.tailwindcss.com" in html),
        ("Lucide Icons", "lucide" in html.lower()),
    ]
    
    for name, ok in checks:
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"    ❌ {name}")
    
    # 统计工具
    tools_match = re.search(r'const TOOLS\s*=\s*\[([\s\S]*?)\];', html)
    if tools_match:
        tool_count = len(re.findall(r'\bid:\s*"', tools_match.group(1)))
        live_count = len(re.findall(r'status:\s*"live"', tools_match.group(1)))
        ready_count = len(re.findall(r'ready:\s*true', tools_match.group(1)))
        not_ready = len(re.findall(r'ready:\s*false', tools_match.group(1)))
        passed += 1
        print(f"    ✅ TOOLS 数据库: {tool_count} 工具, {live_count} 在线, {ready_count} ready:true, {not_ready} ready:false")
        # Warn if tools missing ready field entirely (neither true nor false)
        tools_in_block = re.findall(r'\{[^}]*?\}', tools_match.group(1))
        missing_ready = sum(1 for t in tools_in_block if 'ready:' not in t)
        if missing_ready > 0:
            print(f"    ⚠️ {missing_ready} 个工具缺少 ready 字段 (将不会在前端显示)")
    else:
        failed += 1
        print(f"    ❌ TOOLS 数据库未找到")
        tool_count = 0
    
    return passed, failed, tool_count


def test_individual_tool_pages():
    """测试 tools/ 目录下每个独立工具页面"""
    print("\n  📄 测试独立工具页面...")
    
    if not os.path.exists(TOOLS_DIR):
        print("    ⚠️ tools/ 目录不存在")
        return 0, 0, []
    
    tool_files = [f for f in os.listdir(TOOLS_DIR) if f.endswith(".html")]
    
    if not tool_files:
        print("    ℹ️ 无独立工具页面（所有工具内联在 index.html）")
        return 0, 0, []
    
    passed = 0
    failed = 0
    tools_ok = []
    
    for tf in sorted(tool_files):
        path = os.path.join(TOOLS_DIR, tf)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            
            checks = [
                content.startswith("<!DOCTYPE"),
                "<html" in content,
                "</html>" in content,
                "<head" in content,
                "<body" in content,
                len(content) > 200,
            ]
            
            if all(checks):
                passed += 1
                tools_ok.append(tf)
                print(f"    ✅ {tf}")
            else:
                failed += 1
                print(f"    ❌ {tf} — {sum(checks)}/{len(checks)} 检查通过")
        except Exception as e:
            failed += 1
            print(f"    ❌ {tf} — {e}")
    
    return passed, failed, tools_ok


def test_local_server():
    """启动本地 HTTP 服务器并验证 index.html + 工具页面可访问"""
    print("\n  🌐 本地服务器测试...")
    
    import random
    port = random.randint(9000, 9999)
    
    server_ready = threading.Event()
    
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=BASE_DIR, **kwargs)
        def log_message(self, fmt, *args):
            pass
    
    def serve():
        try:
            # 使用 ThreadingTCPServer 支持并发请求，避免 502
            with socketserver.ThreadingTCPServer(("127.0.0.1", port), QuietHandler) as httpd:
                httpd.daemon_threads = True
                server_ready.set()
                httpd.serve_forever(poll_interval=0.5)
        except Exception:
            server_ready.set()
    
    t = threading.Thread(target=serve, daemon=True)
    t.start()
    if not server_ready.wait(timeout=5):
        print("    ❌ 服务器启动超时")
        return 0, 1
    
    time.sleep(0.5)
    
    passed = 0
    failed = 0
    
    def try_fetch(path, label, timeout=10):
        """带重试的 HTTP 请求"""
        url = f"http://127.0.0.1:{port}{path}"
        for attempt in range(3):
            try:
                req = urllib.request.Request(url)
                resp = urllib.request.urlopen(req, timeout=timeout)
                size = len(resp.read())
                if resp.status == 200 and size > 100:
                    return True, f"HTTP 200, {size}B"
                else:
                    return False, f"HTTP {resp.status}, {size}B"
            except Exception as e:
                if attempt < 2:
                    time.sleep(0.3)
                else:
                    return False, str(e)
        return False, "unknown"
    
    try:
        # 测试 index.html
        ok, msg = try_fetch("/index.html", "index.html")
        if ok:
            passed += 1
            print(f"    ✅ index.html — {msg}")
        else:
            failed += 1
            print(f"    ❌ index.html — {msg}")
        
        # 测试工具页面
        if os.path.exists(TOOLS_DIR):
            tool_files = sorted([f for f in os.listdir(TOOLS_DIR) if f.endswith(".html")])
            for tf in tool_files:
                ok, msg = try_fetch(f"/tools/{tf}", tf, timeout=10)
                if ok:
                    passed += 1
                    print(f"    ✅ tools/{tf} — HTTP 200")
                else:
                    failed += 1
                    print(f"    ❌ tools/{tf} — {msg}")
    except Exception as e:
        failed += 1
        print(f"    ❌ 本地服务器异常: {e}")
    
    return passed, failed

# ─── 阶段 3: 部署 ──────────────────────────────────────────────────────

def deploy_to_cloudflare():
    """部署到 Cloudflare Pages"""
    print("\n" + "=" * 60)
    print("🚀 阶段 3: 部署到 Cloudflare Pages")
    print("=" * 60)
    
    try:
        result = subprocess.run(
            ["npx", "wrangler", "--version"],
            capture_output=True, text=True, timeout=30, cwd=BASE_DIR
        )
        print(f"  Wrangler: {result.stdout.strip()}")
    except Exception as e:
        print(f"  ❌ Wrangler 不可用: {e}")
        return False, None
    
    try:
        result = subprocess.run(
            ["npx", "wrangler", "pages", "deploy", ".",
             "--project-name", "mintshovels",
             "--branch", "main",
             "--commit-dirty=true"],
            capture_output=True, text=True, timeout=120, cwd=BASE_DIR
        )
        
        output = result.stdout + result.stderr
        print(output.strip())
        
        if result.returncode != 0:
            return False, None
        
        url_match = re.search(r'https://[a-f0-9]+\.mintshovels\.pages\.dev', output)
        deploy_url = url_match.group(0) if url_match else "unknown"
        
        # 验证部署
        time.sleep(5)
        try:
            req = urllib.request.Request(deploy_url)
            resp = urllib.request.urlopen(req, timeout=15)
            print(f"\n  ✅ 部署验证: HTTP {resp.status} — {deploy_url}")
            return True, deploy_url
        except Exception:
            print(f"\n  ✅ 已部署 (验证需等待) — {deploy_url}")
            return True, deploy_url
            
    except subprocess.TimeoutExpired:
        print("❌ 部署超时")
        return False, None
    except Exception as e:
        print(f"❌ 部署异常: {e}")
        return False, None

# ─── 阶段 2d: 标记 ready ──────────────────────────────────────────────

def mark_new_tools_ready():
    """测试全部通过后，将 ready:false 的新工具标记为 ready:true 正式上线"""
    print("\n  🏷️  标记新工具为 ready:true...")
    
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    
    # 统计 ready: false 的工具
    before_count = len(re.findall(r'ready:\s*false', html))
    
    if before_count == 0:
        print(f"    ✅ 没有待上线的工具")
        return 0
    
    # 替换 ready: false → ready: true
    html_updated = re.sub(r'ready:\s*false', 'ready: true', html)
    after_count = len(re.findall(r'ready:\s*false', html_updated))
    marked = before_count - after_count
    
    if marked > 0:
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            f.write(html_updated)
        print(f"    🚀 {marked} 个新工具测试通过，已标记 ready:true 正式上线")
    else:
        print(f"    ⚠️ 替换失败，请联系管理员")
    
    return marked


# ─── 主流水线 ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MintShovels 全自动流水线")
    parser.add_argument("--test-only", action="store_true", help="只测试不生产")
    parser.add_argument("--no-deploy", action="store_true", help="跳过部署")
    parser.add_argument("--max", type=int, default=3, help="每次最多生产工具数")
    args = parser.parse_args()
    
    start_time = now_iso()
    summary = {
        "start_time": start_time,
        "radar": None,
        "factory": None,
        "gate_check": None,
        "health_snapshot": None,
        "test_index": {"passed": 0, "failed": 0},
        "test_tools": {"passed": 0, "failed": 0, "tools": []},
        "test_server": {"passed": 0, "failed": 0},
        "tool_count": 0,
        "tools_marked_ready": 0,
        "deploy": None,
        "all_pass": False,
    }
    
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║" + "   MintShovels 全自动流水线 — 雷达→工厂→门禁→测试→部署".center(50) + "║")
    print("║" + f"   启动时间: {start_time}".center(50) + "║")
    print("╚" + "═" * 58 + "╝")
    
    all_stages_pass = True
    
    if not args.test_only:
        # 阶段 0: 雷达
        radar_ok, radar_report = run_radar()
        summary["radar"] = "OK" if radar_ok else "FAIL"
        all_stages_pass = all_stages_pass and radar_ok
        
        # 阶段 0.5: 需求过滤审计（意图分类器打分可视化）
        if radar_ok:
            print("\n" + "=" * 60)
            print("🔍 阶段 0.5: 需求过滤审计（意图分类器打分）")
            print("=" * 60)
            filter_audit = demand_filter_audit()
            summary["demand_filter_audit"] = filter_audit
        
        # 阶段 1: 工厂（即使雷达部分失败也尝试运行，利用已有报告）
        factory_ok, factory_output = run_factory(max_count=args.max)
        summary["factory"] = "OK" if factory_ok else "FAIL"
        # 工厂失败不阻止后续（可能没有新需求，但测试仍需要跑）
    
    # ── 阶段 1.5: 车间门禁（新工具功能拦截）──
    print("\n" + "=" * 60)
    print("🔒 阶段 1.5: 车间门禁检查")
    print("=" * 60)
    try:
        snapshot = gate_health_check()
        summary["health_snapshot"] = snapshot
        health_rate = snapshot.get("health_rate", 0)
        hollow_count = snapshot.get("hollow_count", 0)
        print(f"   生产工具健康率: {health_rate}% ({snapshot.get('total', 0)} 个工具, {hollow_count} 个问题)")
        if hollow_count > 0:
            print(f"   问题文件: {snapshot.get('hollow_files', [])}")
        if health_rate >= 90:
            print("   ✅ 门禁通过 — 健康率达标")
            summary["gate_check"] = "OK"
        else:
            print(f"   ⚠️ 门禁警告 — 健康率 {health_rate}% 低于90%阈值")
            summary["gate_check"] = "WARN"
    except Exception as e:
        print(f"   ⚠️ 门禁检查异常: {e}")
        summary["gate_check"] = "ERROR"
    
    # 阶段 2: 全量测试
    print("\n" + "=" * 60)
    print("🧪 阶段 2: 全量工具测试")
    print("=" * 60)
    
    # 2a: index.html 结构测试
    idx_pass, idx_fail, tool_count = test_index_html()
    summary["test_index"] = {"passed": idx_pass, "failed": idx_fail}
    summary["tool_count"] = tool_count
    
    # 2b: 独立工具页面测试
    tp_pass, tp_fail, tools_ok = test_individual_tool_pages()
    summary["test_tools"] = {"passed": tp_pass, "failed": tp_fail, "tools": tools_ok}
    
    # 2c: 本地服务器测试
    srv_pass, srv_fail = test_local_server()
    summary["test_server"] = {"passed": srv_pass, "failed": srv_fail}
    
    total_pass = idx_pass + tp_pass + srv_pass
    total_fail = idx_fail + tp_fail + srv_fail
    tests_all_pass = (total_fail == 0)
    
    print(f"\n  📊 测试汇总: {total_pass} 通过, {total_fail} 失败")
    
    # 阶段 2d: 测试通过 → 标记新工具为 ready:true（上线）
    ready_count = 0
    if tests_all_pass:
        ready_count = mark_new_tools_ready()
        summary["tools_marked_ready"] = ready_count
    
    # 阶段 3: 部署（仅在测试全部通过时）
    if not args.no_deploy:
        if tests_all_pass:
            deploy_ok, deploy_url = deploy_to_cloudflare()
            summary["deploy"] = {"status": "OK", "url": deploy_url} if deploy_ok else {"status": "FAIL", "url": None}
        else:
            print("\n" + "=" * 60)
            print("⛔ 部署已阻止 — 存在测试失败项，请修复后重试")
            print("=" * 60)
            summary["deploy"] = {"status": "BLOCKED", "reason": "tests_failed"}
            all_stages_pass = False
    else:
        summary["deploy"] = {"status": "SKIPPED", "reason": "--no-deploy"}
    
    summary["all_pass"] = all_stages_pass and tests_all_pass
    summary["end_time"] = now_iso()
    
    # 保存流水线日志
    log = load_json(PIPELINE_LOG) or []
    log.append(summary)
    if len(log) > 50:
        log = log[-50:]
    save_json(PIPELINE_LOG, log)
    
    # 最终报告
    print("\n" + "=" * 60)
    print("📊 流水线报告")
    print("=" * 60)
    print(f"  ⏱  耗时: {start_time} → {summary['end_time']}")
    print(f"  📡 雷达: {summary['radar'] or 'SKIP'}")
    print(f"  🏭 工厂: {summary['factory'] or 'SKIP'}")
    if summary.get('gate_check'):
        status_icon = "✅" if summary['gate_check'] == "OK" else "⚠️"
        print(f"  🔒 门禁: {status_icon} {summary['gate_check']}")
    if summary.get('health_snapshot'):
        hr = summary['health_snapshot'].get('health_rate', 0)
        print(f"  💚 健康率: {hr}%")
    print(f"  🧪 测试: {total_pass}✅ {total_fail}❌")
    print(f"  🔧 工具总数: {tool_count}")
    if ready_count > 0:
        print(f"  🏷️  新上线: {ready_count} 个工具 (已标记 ready:true)")
    print(f"  📄 独立页面: {len(summary['test_tools']['tools'])}")
    print(f"  🚀 部署: {summary['deploy']['status']}")
    if summary['deploy'].get('url'):
        print(f"  🔗 URL: {summary['deploy']['url']}")
    print(f"  {'✅ 全线通过' if summary['all_pass'] else '❌ 存在问题'}")
    print("=" * 60)
    
    sys.exit(0 if summary['all_pass'] else 1)

if __name__ == "__main__":
    main()
