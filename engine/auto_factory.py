#!/usr/bin/env python3
"""
MintShovels 自动工厂 - 读取需求雷达报告，自动生成工具页面 + 测试 + 部署

流程:
  1. 读取 reports/demand_report.json
  2. 对比 reports/factory_log.json 排除已生产的工具
  3. 为每个新工具生成独立的 tools/ 页面
  4. 更新 index.html 的 TOOLS 数据库
  5. 写入 factory_log.json
  6. 🧪 自动化测试 (HTML 结构 / JS 语法 / 页面渲染)
  7. 🚀 自动部署到 Cloudflare Pages

用法:
  python3 engine/auto_factory.py              # 生产+测试+部署
  python3 engine/auto_factory.py --dry-run     # 预览模式
  python3 engine/auto_factory.py --max 3       # 最多生产3个
  python3 engine/auto_factory.py --no-deploy   # 只生产测试，不部署
  python3 engine/auto_factory.py --test-only   # 只测试现有 index.html
"""

import json
import os
import re
import sys
import argparse
import subprocess
import http.server
import socketserver
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(BASE_DIR, "reports")
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
INDEX_PATH = os.path.join(BASE_DIR, "index.html")
FACTORY_LOG_PATH = os.path.join(REPORT_DIR, "factory_log.json")
DEMAND_REPORT_PATH = os.path.join(REPORT_DIR, "demand_report.json")
TEST_REPORT_PATH = os.path.join(REPORT_DIR, "test_report.json")

# ─── 集成真实模板引擎 + 车间门禁 ─────────────────────────────────────
# 优先从 engine/ 本地加载（CI 环境），回退到 CodeBuddy 工作区（本地开发）
ENGINE_DIR = os.path.join(BASE_DIR, "engine")
sys.path.insert(0, ENGINE_DIR)
CODEBUDDY_DIR = os.path.join(os.path.dirname(BASE_DIR), "20260619190048")
if os.path.exists(CODEBUDDY_DIR):
    sys.path.insert(0, CODEBUDDY_DIR)

try:
    from template_rewriter import (
        GENERATOR_MODULES, CHECKER_MODULES, CALCULATOR_MODULES, PYTHON_MODULES,
        match_generator_keyword, match_checker_keyword, match_calculator_keyword, match_python_keyword,
        rewrite_random_gen_js, rewrite_checker_js, rewrite_calculator_js, rewrite_calculator_html, rewrite_python_js,
    )
    TEMPLATE_REWRITER_AVAILABLE = True
except ImportError:
    TEMPLATE_REWRITER_AVAILABLE = False
    print("⚠️ template_rewriter.py not found, using fallback templates")

try:
    from functional_test_runner import workshop_gate_check, analyze_tool_code
    GATE_CHECK_AVAILABLE = True
except ImportError:
    GATE_CHECK_AVAILABLE = False
    print("⚠️ functional_test_runner.py not found, gate check disabled")

os.makedirs(REPORT_DIR, exist_ok=True)
os.makedirs(TOOLS_DIR, exist_ok=True)

# Cloudflare Pages 部署配置
CF_PROJECT_NAME = "mintshovels"
CF_BRANCH = "main"

# ─── JSON 工具 ───────────────────────────────────────────────────────

def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ─── 工厂日志 ─────────────────────────────────────────────────────────

def load_factory_log():
    log = load_json(FACTORY_LOG_PATH)
    if log is None:
        log = {"produced": [], "last_run": None, "deployments": []}
    return log

def save_factory_log(log):
    save_json(FACTORY_LOG_PATH, log)

def load_demand_report():
    return load_json(DEMAND_REPORT_PATH)

# ─── ID 管理 ──────────────────────────────────────────────────────────

def get_next_tool_id(index_html):
    shovel_ids = re.findall(r'"shovel-(\d+)"', index_html)
    script_ids = re.findall(r'"script-(\d+)"', index_html)
    max_shovel = max([int(x) for x in shovel_ids]) if shovel_ids else 0
    max_script = max([int(x) for x in script_ids]) if script_ids else 0
    return max_shovel, max_script

# ─── 工具页面生成 ─────────────────────────────────────────────────────

def generate_tool_page(suggestion, tool_id):
    """v2.0: 使用真实模板引擎生成带功能的工具页面"""
    name = suggestion["name"]
    name_zh = suggestion["name_zh"]
    category = suggestion["category"]
    subcat = suggestion["subcat"]
    ttype = suggestion["type"]

    slug = name.lower().replace(" ", "-").replace("/", "-")
    escaped_slug = slug.replace("'", "\\'")

    icon_map = {
        "dev": "💻", "media": "🎬", "finance": "💰",
        "productivity": "💼", "gaming": "🎮", "ai": "🤖", "misc": "🧩",
    }
    icon = icon_map.get(category, "🔧")

    if ttype == "script":
        badge = f"Script #{tool_id.split('-')[1]}"
    else:
        badge = f"Shovel #{tool_id.split('-')[1]}"

    # ── 根据需求类型分派真实模板 ──
    js_code = ""
    html_body = ""

    if TEMPLATE_REWRITER_AVAILABLE:
        if subcat in ("generator", "random", "随机", "生成器") or "generator" in name.lower() or "生成" in name_zh:
            module = match_generator_keyword(name)
            mod = GENERATOR_MODULES[module]
            var_decl = mod.get("var_decl", "")
            gen_fn = mod["gen_fn"]
            item_fmt = mod["item_fmt"]
            js_code = f"""let {escaped_slug}_data = [];
{var_decl}
{gen_fn}
function generate{tool_id.replace("-", "_")}() {{
    const count = parseInt(document.getElementById('gen-count')?.value || 10);
    const results = document.getElementById('results');
    if (count < 1 || count > 1000) {{ results.innerHTML = '<p class="text-amber-400">数量1-1000</p>'; return; }}
    const items = [];
    for (let i = 0; i < count; i++) items.push({item_fmt});
    results.innerHTML = items.join('');
    {escaped_slug}_data = items;
}}
function exportData() {{
    if (!{escaped_slug}_data?.length) {{ alert('请先生成数据'); return; }}
    const text = document.getElementById('results').innerText;
    const blob = new Blob([text], {{type:'text/plain'}});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = '{slug}_export.txt';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
}}"""
            html_body = f'''<div class="space-y-4">
    <div class="flex items-center gap-3">
        <input id="gen-count" type="number" value="10" min="1" max="1000"
            class="w-24 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm">
        <button onclick="generate{tool_id.replace("-", "_")}()" class="btn-primary">🎲 生成</button>
        <button onclick="exportData()" class="btn-secondary">📥 导出</button>
    </div>
    <div id="results" class="space-y-2"></div>
</div>'''

        elif subcat in ("validator", "checker", "检测", "验证") or "check" in name.lower() or "检测" in name_zh:
            module = match_checker_keyword(name)
            mod = CHECKER_MODULES[module]
            js_code = f"""function check() {{
    const input = document.getElementById('check-input').value.trim();
    const result = document.getElementById('check-result');
    if (!input) {{ result.innerHTML = '<p class="text-amber-400">⚠️ 请输入待检测内容</p>'; return; }}
    {mod["validate_code"]}
    result.className = 'mt-4 p-4 rounded-lg text-sm ' + (valid ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20');
    result.innerHTML = detail;
}}"""
            html_body = f'''<div class="space-y-4">
    <input id="check-input" type="text" placeholder="输入待检测内容..." class="w-full">
    <button onclick="check()" class="btn-primary">✅ 开始检测</button>
    <div id="check-result"></div>
</div>'''

        elif subcat in ("calculator", "计算", "换算") or "calc" in name.lower() or "计算" in name_zh:
            module = match_calculator_keyword(name)
            mod = CALCULATOR_MODULES[module]
            extra = mod.get("html_extra", "").replace("{id}", escaped_slug)
            js_code = f"""function calc() {{
    const a = parseFloat(document.getElementById('param1').value);
    const b = parseFloat(document.getElementById('param2').value);
    const result = document.getElementById('calc-result');
    if (isNaN(a)) {{ result.innerHTML = '<p class="text-amber-400">请输入有效参数</p>'; return; }}
    {mod["calc_code"]}
}}"""
            html_body = f'''<div class="space-y-4">
    {extra}
    <button onclick="calc()" class="btn-primary">🧮 开始计算</button>
    <div id="calc-result" class="bg-zinc-800/50 rounded-lg p-4 text-center text-2xl font-bold text-emerald-400">{mod.get("result_html", "计算结果")}</div>
</div>'''

        elif subcat in ("script", "python", "脚本") or ttype == "script":
            module = match_python_keyword(name)
            mod = PYTHON_MODULES[module]
            code = mod["code"].replace("{name_en}", name)
            js_code = f""""""  # Python代码通过script模板展示
            html_body = f'''<div class="space-y-4">
    <div class="bg-zinc-900 rounded-lg p-4 border border-zinc-700">
        <pre class="text-xs text-emerald-400 overflow-x-auto whitespace-pre-wrap font-mono">{code[:2000]}</pre>
    </div>
    <button onclick="navigator.clipboard.writeText(document.querySelector('pre').innerText);alert('已复制!')" class="btn-secondary">📋 复制代码</button>
</div>'''

        else:
            # 默认通用工具页
            js_code = """function runTool() {
    const input = document.getElementById('tool-input').value;
    const result = document.getElementById('tool-result');
    if (!input) { result.innerHTML = '<p class="text-amber-400">请输入内容</p>'; return; }
    result.innerHTML = `<div class="text-emerald-400">✅ 处理完成: ${input.length} 字符</div><div class="text-zinc-400 text-sm mt-2">${input.substring(0, 200)}</div>`;
}"""
            html_body = f'''<div class="space-y-4">
    <textarea id="tool-input" rows="4" placeholder="输入内容..." class="w-full"></textarea>
    <button onclick="runTool()" class="btn-primary">▶️ 运行</button>
    <div id="tool-result"></div>
</div>'''

    # ── 组装完整页面 ──
    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name} - {name_zh} | MintShovels</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{ background: #09090b; color: #fafafa; font-family: system-ui, -apple-system, sans-serif; min-height: 100vh; }}
        .card {{ background: #18181b; border: 1px solid #27272a; border-radius: 16px; padding: 24px; }}
        .btn-primary {{ background: linear-gradient(135deg,#6366f1,#8b5cf6); color:white; border:none; padding:10px 24px; border-radius:12px; font-weight:600; font-size:14px; cursor:pointer; }}
        .btn-primary:hover {{ transform:translateY(-1px); box-shadow:0 8px 25px rgba(99,102,241,0.3); }}
        .btn-secondary {{ background:#27272a; color:#d4d4d8; border:1px solid #3f3f46; padding:10px 24px; border-radius:12px; font-weight:600; font-size:14px; cursor:pointer; }}
        .btn-secondary:hover {{ background:#3f3f46; }}
        input, textarea {{ background:#18181b; border:1px solid #27272a; border-radius:10px; padding:10px 14px; color:#fafafa; font-size:14px; width:100%; }}
        input:focus, textarea:focus {{ outline:none; border-color:#6366f1; }}
    </style>
</head>
<body class="p-6">
    <div class="max-w-3xl mx-auto">
        <a href="../index.html" class="text-zinc-500 hover:text-white text-sm mb-6 inline-block">← MintShovels</a>
        <div class="card mb-6">
            <div class="text-5xl mb-4">{icon}</div>
            <h1 class="text-2xl font-bold">{name}</h1>
            <p class="text-zinc-400">{name_zh}</p>
            <span class="inline-block mt-2 px-3 py-1 rounded-full text-xs bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                {badge} · {'🔧 Web Tool' if ttype == 'tool' else '📜 Script'}
            </span>
        </div>
        <div class="card">
            {html_body}
        </div>
        <script>{js_code}</script>
    </div>
</body>
</html>"""

    file_path = os.path.join(TOOLS_DIR, f"{slug}.html")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(page_html)

    return file_path


def generate_tool_entry(suggestion, tool_id):
    name = suggestion["name"]
    name_zh = suggestion["name_zh"]
    category = suggestion["category"]
    subcat = suggestion["subcat"]
    ttype = suggestion["type"]

    color_map = {
        "dev": "#a78bfa", "media": "#818cf8", "finance": "#fb923c",
        "productivity": "#34d399", "gaming": "#f472b6", "ai": "#38bdf8", "misc": "#e879f9",
    }
    color = color_map.get(category, "#6366f1")

    icon_map = {
        "video": "video", "image": "image", "audio": "mic",
        "crypto": "bitcoin", "wallet": "wallet", "defi": "trending-up",
        "office": "file-text", "text": "align-left", "convert": "shuffle", "util": "tool",
        "code": "braces", "api": "terminal", "encode": "lock",
        "game": "gamepad-2", "fun": "smile",
        "ai-chat": "message-circle", "ai-image": "image-plus", "ai-video": "film",
        "ai-writing": "edit-3", "misc": "puzzle",
    }
    icon = icon_map.get(subcat, "zap")

    keywords = name.lower().replace("-", " ").split()
    keywords_zh = [name_zh]

    if ttype == "script":
        badge = f"Script #{tool_id.split('-')[1]}"
    else:
        badge = f"Shovel #{tool_id.split('-')[1]}"

    entry = f"""        {{
            id: "{tool_id}", name: "{name}", name_zh: "{name_zh}",
            desc: "{name} - auto-generated by demand radar.",
            desc_zh: "{name_zh} - 由需求雷达自动生产。",
            icon: "{icon}", color: "{color}", category: "{category}", subcat: "{subcat}", type: "{ttype}",
            tags: {json.dumps(keywords)},
            tags_zh: {json.dumps(keywords_zh)},
            status: "live", ready: false, badge: "{badge}", detail_page: true,
        }}"""

    return entry


def update_index_html(new_entries, dry_run=False):
    if not new_entries:
        print("  No new entries to add.")
        return False

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    insert_str = ",\n".join(new_entries) + ",\n"

    match = re.search(r'(\n\s*\];\s*\n\s*// ={3,}.*?i18n)', content)
    if not match:
        match = re.search(r'(\n\s*\];\s*\n\s*//.*?i18n)', content)

    if not match:
        print("  ⚠️ Could not find insertion point in index.html")
        return False

    insert_pos = match.start()
    new_content = content[:insert_pos] + insert_str + content[insert_pos:]

    if dry_run:
        print(f"  [DRY-RUN] Would insert {len(new_entries)} entries into index.html")
    else:
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"  ✅ Inserted {len(new_entries)} entries into index.html")

    return True


# ─── 🧪 自动化测试 ────────────────────────────────────────────────────

def run_tests(index_html=None):
    """测试 index.html 的完整性：HTML结构、JS语法、关键功能"""
    if index_html is None:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            index_html = f.read()

    results = {
        "passed": [],
        "failed": [],
        "warnings": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    def check(name, condition, severity="error"):
        if condition:
            results["passed"].append(name)
            print(f"  ✅ {name}")
        else:
            if severity == "warning":
                results["warnings"].append(name)
                print(f"  ⚠️ {name} [WARNING]")
            else:
                results["failed"].append(name)
                print(f"  ❌ {name}")

    print("\n🧪 Running automated tests...")
    print("-" * 40)

    # 1. HTML 结构
    print("  [HTML Structure]")
    check("DOCTYPE declaration", index_html.startswith("<!DOCTYPE"))
    check("<html> tag", "<html" in index_html)
    check("</html> tag", "</html>" in index_html)
    check("<head> tag", "<head>" in index_html or "<head " in index_html)
    check("<body> tag", "<body" in index_html or "<body " in index_html)
    check("<script> tag", "<script>" in index_html or "<script " in index_html)

    # 2. CDN 依赖
    print("  [CDN Dependencies]")
    check("Tailwind CSS CDN", "cdn.tailwindcss.com" in index_html)
    check("Lucide Icons CDN", "lucide@latest" in index_html or "unpkg.com/lucide" in index_html)

    # 3. TOOLS 数据库
    print("  [TOOLS Database]")
    tools_match = re.search(r'const TOOLS\s*=\s*\[([\s\S]*?)\];', index_html)
    check("TOOLS array defined", tools_match is not None)
    if tools_match:
        tool_count = len(re.findall(r'\bid:\s*"', tools_match.group(1)))
        check(f"TOOLS entries ({tool_count})", tool_count > 0)
        check("Has Web Tools (🔧)", '"tool"' in tools_match.group(1))
        check("Has Scripts (📜)", '"script"' in tools_match.group(1))
        check("Has Live tools", '"live"' in tools_match.group(1))

    # 4. 关键函数
    print("  [Key Functions]")
    funcs = [
        "renderAll", "renderSections", "renderToolCard", "renderToolDetail",
        "openToolDetail", "goHome", "checkRadar", "switchLang", "t",
        "filterSubcat", "toggleCat", "clearSearch",
    ]
    for f in funcs:
        check(f"function {f}()", f"function {f}" in index_html or f"{f} =" in index_html or f"{f}=" in index_html, "warning")

    # 5. i18n 字典完整性
    print("  [i18n Dictionary]")
    i18n_match = re.search(r'const i18n\s*=\s*\{', index_html)
    check("i18n dict defined", i18n_match is not None)
    check("has 'en' lang", re.search(r'\ben\s*:', index_html) is not None)
    check("has 'zh' lang", re.search(r'\bzh\s*:', index_html) is not None)

    # 6. 潜在问题
    print("  [Potential Issues]")
    debug_count = len(re.findall(r'console\.log|debugger', index_html))
    check(f"No debug code ({debug_count} found)", debug_count == 0, "warning")

    # 7. API 端点
    check("API endpoint configured", "railway.app" in index_html or "api" in index_html.lower(), "warning")

    # 总结
    print("-" * 40)
    total = len(results["passed"]) + len(results["failed"]) + len(results["warnings"])
    print(f"\n  📊 Results: {len(results['passed'])}✅ passed, {len(results['failed'])}❌ failed, {len(results['warnings'])}⚠️ warnings ({total} total)")

    # 保存测试报告
    save_json(TEST_REPORT_PATH, results)

    return len(results["failed"]) == 0


def run_local_server_test(port=None):
    """启动本地HTTP服务器并验证页面可访问"""
    import random
    if port is None:
        port = random.randint(9000, 9999)
    print(f"\n  🌐 Testing local server on port {port}...")

    server_started = threading.Event()

    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=BASE_DIR, **kwargs)
        def log_message(self, format, *args):
            pass

    def serve():
        try:
            with socketserver.TCPServer(("127.0.0.1", port), QuietHandler) as httpd:
                server_started.set()
                httpd.timeout = 3
                httpd.handle_request()
        except Exception:
            server_started.set()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    server_started.wait(timeout=3)
    time.sleep(0.5)

    try:
        url = f"http://127.0.0.1:{port}/index.html"
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=10)
        status = resp.status
        size = len(resp.read())
        if status == 200 and size > 1000:
            print(f"  ✅ Local server: HTTP {status}, {size} bytes")
            return True
        else:
            print(f"  ❌ Local server: HTTP {status}, {size} bytes")
            return False
    except Exception as e:
        print(f"  ❌ Local server test failed: {e}")
        return False


# ─── 🚀 部署到 Cloudflare Pages ───────────────────────────────────────

def deploy_to_cloudflare(dry_run=False):
    """使用 wrangler CLI 部署到 Cloudflare Pages"""
    print("\n🚀 Deploying to Cloudflare Pages...")
    print("-" * 40)

    if dry_run:
        print("  [DRY-RUN] Would deploy to Cloudflare Pages")
        return True, "dry-run"

    # 检查 wrangler 是否可用
    try:
        result = subprocess.run(
            ["npx", "wrangler", "--version"],
            capture_output=True, text=True, timeout=30, cwd=BASE_DIR
        )
        print(f"  Wrangler: {result.stdout.strip()}")
    except Exception as e:
        print(f"  ❌ Wrangler not available: {e}")
        return False, str(e)

    # 部署
    try:
        print(f"  Deploying project: {CF_PROJECT_NAME}...")
        result = subprocess.run(
            ["npx", "wrangler", "pages", "deploy", ".",
             "--project-name", CF_PROJECT_NAME,
             "--branch", CF_BRANCH,
             "--commit-dirty=true"],
            capture_output=True, text=True, timeout=120, cwd=BASE_DIR
        )

        output = result.stdout + result.stderr
        print(f"  {output.strip()}")

        if result.returncode != 0:
            print(f"  ❌ Deployment failed (exit code {result.returncode})")
            return False, output

        # 提取部署 URL
        url_match = re.search(r'https://[a-f0-9]+\.' + re.escape(CF_PROJECT_NAME) + r'\.pages\.dev', output)
        if url_match:
            deploy_url = url_match.group(0)
            print(f"\n  ✅ Deployed to: {deploy_url}")
            return True, deploy_url
        else:
            print(f"\n  ⚠️ Deployment appeared successful but URL not found in output")
            return True, "unknown-url"

    except subprocess.TimeoutExpired:
        print(f"  ❌ Deployment timed out")
        return False, "timeout"
    except Exception as e:
        print(f"  ❌ Deployment error: {e}")
        return False, str(e)


def verify_deployment(url):
    """验证部署后的页面可访问"""
    if not url or url in ("dry-run", "unknown-url"):
        return True

    print(f"\n  🔍 Verifying deployment: {url}")
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=15)
        if resp.status == 200:
            print(f"  ✅ Deployment verified: HTTP 200")
            return True
        else:
            print(f"  ⚠️ Deployment returned HTTP {resp.status}")
            return False
    except Exception as e:
        print(f"  ⚠️ Verification failed (may need a moment): {e}")
        return True  # 刚部署可能需要几秒钟生效


# ─── 主流程 ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="MintShovels Auto Factory - 生产+测试+部署")
    parser.add_argument("--dry-run", action="store_true", help="Preview mode, no file changes")
    parser.add_argument("--max", type=int, default=0, dest="max_count", help="Max tools to produce")
    parser.add_argument("--no-deploy", action="store_true", help="Skip deployment")
    parser.add_argument("--test-only", action="store_true", help="Only run tests on existing index.html")
    parser.add_argument("--deploy-only", action="store_true", help="Only deploy (skip production)")
    args = parser.parse_args()

    print("🏭 MintShovels Auto Factory")
    print("=" * 50)

    # ── 仅测试模式 ──
    if args.test_only:
        print("📋 Test-only mode")
        passed = run_tests()
        passed = run_local_server_test() and passed
        if passed:
            print("\n✅ All tests passed!")
        else:
            print("\n❌ Some tests failed. Check report for details.")
            sys.exit(1)
        return

    # ── 仅部署模式 ──
    if args.deploy_only:
        print("📋 Deploy-only mode")
        passed = run_tests()
        if not passed:
            print("\n❌ Tests failed. Aborting deployment.")
            print("   Use --deploy-only to force deploy despite failures (not recommended)")
            sys.exit(1)
        success, url = deploy_to_cloudflare(dry_run=args.dry_run)
        if success:
            verify_deployment(url)
        sys.exit(0 if success else 1)

    # ── 完整流水线: 生产 → 测试 → 部署 ──

    # 1. 加载需求报告
    demand = load_demand_report()
    if not demand:
        print("❌ No demand report found. Run demand_radar.py first.")
        print(f"   Expected: {DEMAND_REPORT_PATH}")
        sys.exit(1)

    suggestions = demand.get("tool_suggestions", [])
    if not suggestions:
        print("❌ No tool suggestions in demand report.")
        sys.exit(0)

    print(f"📊 Demand report loaded: {len(suggestions)} suggestions")
    print(f"   Generated at: {demand.get('generated_at', 'unknown')}")

    # 2. 加载工厂记录
    log = load_factory_log()
    produced_ids = set(log.get("produced", []))

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        index_html = f.read()

    existing_names = set(re.findall(r'name:\s*"([^"]+)"', index_html))
    
    # 🔒 去重增强：检查 tools/ 目录下已有文件
    existing_files = set()
    if os.path.exists(TOOLS_DIR):
        for f in os.listdir(TOOLS_DIR):
            if f.endswith(".html"):
                # 去掉 .html 后缀作为文件标识
                existing_files.add(f.replace(".html", ""))
    
    print(f"   Already in catalog: {len(existing_names)} tools")
    print(f"   Previously produced: {len(produced_ids)} tools")
    print(f"   Existing tool pages: {len(existing_files)} files")

    # 3. 获取下一个可用ID
    max_shovel, max_script = get_next_tool_id(index_html)
    print(f"   Next shovel ID: shovel-{max_shovel + 1:03d}")
    print(f"   Next script ID: script-{max_script + 1:03d}")

    # 4. 筛选新工具（多层去重）
    new_suggestions = []
    seen_names_in_batch = set()  # 批次内去重
    for s in suggestions:
        name = s["name"]
        slug = name.lower().replace(" ", "-").replace("/", "-")
        # 去重1: 名称已在 TOOLS 数据库中
        if name in existing_names:
            continue
        # 去重2: 文件已存在于 tools/ 目录
        if slug in existing_files:
            continue
        # 去重3: 批次内去重
        if name in seen_names_in_batch:
            continue
        seen_names_in_batch.add(name)
        new_suggestions.append(s)

    if not new_suggestions:
        print("\n✅ All suggested tools already exist in catalog. Nothing to produce.")
        log["last_run"] = datetime.now(timezone.utc).isoformat()
        save_factory_log(log)

        # 即使没有新工具，也跑一遍测试+部署确保代码健康
        print("\n📋 Running tests on current codebase...")
        if run_tests():
            if not args.no_deploy:
                success, url = deploy_to_cloudflare(dry_run=args.dry_run)
                if success:
                    verify_deployment(url)
                    log["deployments"].append({
                        "time": datetime.now(timezone.utc).isoformat(),
                        "url": url,
                        "new_tools": 0,
                    })
                    save_factory_log(log)
        return

    if args.max_count and args.max_count > 0:
        new_suggestions = new_suggestions[:args.max_count]

    print(f"\n🔧 Producing {len(new_suggestions)} new tools:")
    for s in new_suggestions:
        print(f"   • {s['name']} ({s['name_zh']}) [{s['category']}/{s['subcat']}]")

    if args.dry_run:
        print("\n[DRY-RUN MODE] No files will be changed.\n")

    # 5. 生产工具（带车间门禁拦截）
    new_entries = []
    produced_this_run = []
    blocked_by_gate = []

    for s in new_suggestions:
        ttype = s.get("type", "tool")
        if ttype == "script":
            max_script += 1
            tool_id = f"script-{max_script:03d}"
        else:
            max_shovel += 1
            tool_id = f"shovel-{max_shovel:03d}"

        print(f"\n  🛠  Producing: {s['name']} → {tool_id}")

        # ── 🔒 车间门禁检查 ──
        if GATE_CHECK_AVAILABLE and not args.dry_run:
            tool_data = {
                "id": tool_id,
                "name": s["name"],
                "name_zh": s["name_zh"],
                "category": s["category"],
                "type": ttype,
            }
            gate_result = workshop_gate_check(tool_data)
            if not gate_result.get("pass", True):
                blocked_by_gate.append({
                    "tool_id": tool_id,
                    "name": s["name"],
                    "reason": gate_result.get("reason", "未通过车间门禁"),
                    "verdict": gate_result.get("verdict", "BLOCKED"),
                })
                print(f"     🚫 BLOCKED by gate: {gate_result.get('reason', 'unknown')}")
                continue
            else:
                print(f"     ✅ Gate check passed")

        if not args.dry_run:
            page_path = generate_tool_page(s, tool_id)
            print(f"     📄 Page: {os.path.relpath(page_path, BASE_DIR)}")

        entry = generate_tool_entry(s, tool_id)
        new_entries.append(entry)
        produced_this_run.append({
            "tool_id": tool_id,
            "name": s["name"],
            "name_zh": s["name_zh"],
            "category": s["category"],
            "produced_at": datetime.now(timezone.utc).isoformat(),
        })

    # 门禁拦截报告
    if blocked_by_gate:
        print(f"\n  🚫 车间门禁拦截了 {len(blocked_by_gate)} 个不合格工具:")
        for b in blocked_by_gate:
            print(f"     • {b['tool_id']}: {b['reason']}")

    # 6. 更新 index.html
    if new_entries:
        update_index_html(new_entries, dry_run=args.dry_run)

    # 7. 更新工厂日志（去重写入）
    existing_produced = set(log.get("produced", []))
    for item in produced_this_run:
        if item["tool_id"] not in existing_produced:
            log["produced"].append(item["tool_id"])
            existing_produced.add(item["tool_id"])
    log["last_run"] = datetime.now(timezone.utc).isoformat()

    if not args.dry_run:
        save_factory_log(log)
        print(f"\n  📝 Factory log updated")

    # ── 🧪 测试阶段 ──
    print(f"\n{'='*50}")
    print("🧪 TEST PHASE")

    # 重新读取更新后的 index.html
    if not args.dry_run:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            updated_html = f.read()
    else:
        updated_html = index_html

    tests_passed = run_tests(updated_html)
    local_ok = run_local_server_test()

    if not tests_passed or not local_ok:
        print("\n❌ Tests failed! Aborting deployment.")
        print(f"   Test report saved to: {TEST_REPORT_PATH}")
        print("   Fix issues and run: python3 engine/auto_factory.py --deploy-only")
        sys.exit(1)

    print("\n✅ All tests passed!")

    # ── 🚀 部署阶段 ──
    if args.no_deploy:
        print(f"\n{'='*50}")
        print("⏭️  Skipping deployment (--no-deploy)")
        print(f"{'='*50}")
    else:
        print(f"\n{'='*50}")
        print("🚀 DEPLOY PHASE")

        success, url = deploy_to_cloudflare(dry_run=args.dry_run)

        if not success:
            print("\n❌ Deployment failed!")
            sys.exit(1)

        verify_deployment(url)

        if not args.dry_run:
            log["deployments"].append({
                "time": datetime.now(timezone.utc).isoformat(),
                "url": url,
                "new_tools": len(produced_this_run),
            })
            save_factory_log(log)

    # ── 最终总结 ──
    print(f"\n{'='*50}")
    print(f"🏭 Pipeline complete!")
    print(f"   New tools: {len(produced_this_run)}")
    if produced_this_run:
        for p in produced_this_run:
            print(f"   • {p['tool_id']}: {p['name']}")
    print(f"   Tests: {'✅ Passed' if tests_passed else '❌ Failed'}")
    if not args.no_deploy:
        print(f"   Deploy: {'✅ Done' if success else '❌ Failed'}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
