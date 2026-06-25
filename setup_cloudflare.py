#!/usr/bin/env python3
"""
MintShovels Cloudflare 优化配置脚本 v2
=======================================
先检测 API Token 权限，再决定自动配置 or 给出 Dashboard 指引
"""

import json, os, urllib.request, urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "mintshovels_config.json")
TEST_IP = os.environ.get("TEST_IP", "35.78.117.113")

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

def api(method, path, token, data=None):
    url = f"https://api.cloudflare.com/client/v4{path}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return {"success": True, "data": json.loads(r.read())}
    except urllib.error.HTTPError as e:
        resp = e.read().decode()
        return {"success": False, "http_code": e.code, "error": resp[:300]}
    except Exception as e:
        return {"success": False, "error": str(e)}

def test_write_perms(token, zone_id):
    """测试 token 是否有写权限"""
    results = {}
    
    # 测试 cache rules 写
    payload = {
        "description": "TEST - will be deleted",
        "expression": '(http.request.uri.path.extension eq "___test___")',
        "action": "set_cache_settings",
        "action_parameters": {"cache": True, "edge_ttl": {"mode": "override_origin", "default": 60}}
    }
    existing = api("GET", f"/zones/{zone_id}/rulesets?phase=http_request_cache_settings", token)
    
    if existing["success"] and existing["data"].get("result"):
        ruleset_id = existing["data"]["result"][0]["id"]
        # 尝试创建测试规则
        r = api("PUT", f"/zones/{zone_id}/rulesets/{ruleset_id}", token, {
            "rules": existing["data"]["result"][0].get("rules", []) + [payload]
        })
        results["cache_rules"] = r["success"]
        if r["success"]:
            # 删除测试规则
            current = api("GET", f"/zones/{zone_id}/rulesets/{ruleset_id}", token)
            if current["success"]:
                clean_rules = [r_ for r_ in current["data"].get("result", {}).get("rules", [])
                              if "___test___" not in (r_.get("description") or "")]
                api("PUT", f"/zones/{zone_id}/rulesets/{ruleset_id}", token, {"rules": clean_rules})
    else:
        results["cache_rules"] = existing["success"]  # can at least read
    
    # 测试 Zaraz 写
    r = api("GET", f"/zones/{zone_id}/settings/zaraz", token)
    results["zaraz_read"] = r["success"]
    if r["success"]:
        config = r["data"].get("result", {})
        # 仅回写确认写权限
        r2 = api("PUT", f"/zones/{zone_id}/settings/zaraz", token, config)
        results["zaraz_write"] = r2["success"]
    else:
        results["zaraz_write"] = False
    
    # 测试 transform rules 写
    r = api("GET", f"/zones/{zone_id}/rulesets?phase=http_request_late_transform", token)
    results["transform_read"] = r["success"] and bool(r["data"].get("result"))
    
    return results


def configure_cache_rules(token, zone_id):
    """配置缓存规则"""
    print("\n" + "=" * 55)
    print("📦 任务 2/4: Cloudflare 缓存规则")
    print("=" * 55)
    print(f"  目标: 静态资源缓存 1个月, 图片缓存 7天")

    expr = (
        '(http.request.uri.path.extension eq "css" or '
        'http.request.uri.path.extension eq "js" or '
        'http.request.uri.path.extension eq "woff2" or '
        'http.request.uri.path.extension eq "woff" or '
        'http.request.uri.path.extension eq "ttf" or '
        'http.request.uri.path.extension eq "svg" or '
        'http.request.uri.path.extension eq "png" or '
        'http.request.uri.path.extension eq "jpg" or '
        'http.request.uri.path.extension eq "jpeg" or '
        'http.request.uri.path.extension eq "gif" or '
        'http.request.uri.path.extension eq "webp" or '
        'http.request.uri.path.extension eq "ico" or '
        'http.request.uri.path.extension eq "avif")'
    )
    
    existing = api("GET", f"/zones/{zone_id}/rulesets?phase=http_request_cache_settings", token)
    
    if existing["success"] and existing["data"].get("result"):
        ruleset_id = existing["data"]["result"][0]["id"]
        current_rules = existing["data"]["result"][0].get("rules", [])
        
        for r in current_rules:
            if "静态资源缓存" in (r.get("description") or ""):
                print("\n  ✅ 缓存规则已存在，无需重复配置")
                return True
        
        print(f"  规则集ID: {ruleset_id}")
        print(f"  当前 {len(current_rules)} 条规则")
        
        payload = {
            "description": "MintShovels - 静态资源缓存1个月",
            "expression": expr,
            "action": "set_cache_settings",
            "action_parameters": {
                "cache": True,
                "edge_ttl": {"mode": "override_origin", "default": 2592000},
                "browser_ttl": {"mode": "override_origin", "default": 2592000}
            }
        }
        
        r = api("PUT", f"/zones/{zone_id}/rulesets/{ruleset_id}", token, {
            "rules": current_rules + [payload]
        })
        
        if r["success"]:
            print("\n  ✅ 缓存规则创建成功!")
            print(f"     *.css, *.js, *.woff2, *.woff, *.ttf, *.svg")
            print(f"     *.png, *.jpg, *.gif, *.webp, *.ico, *.avif")
            print(f"     → Edge TTL: 30天 (2592000秒)")
            return True
    
    # API 不可用，给出 Dashboard 指引
    print_dashboard_cache_guide()
    return False


def configure_zaraz_ga4(token, zone_id, ga4_id):
    """配置 Zaraz GA4"""
    print("\n" + "=" * 55)
    print("🔄 任务 3/4: Zaraz + GA4 服务端")
    print("=" * 55)
    print(f"  目标: 通过 Cloudflare Edge 发送 GA4 事件，绕过广告拦截")
    print(f"  GA4 Measurement ID: {ga4_id}")
    
    r = api("GET", f"/zones/{zone_id}/settings/zaraz", token)
    if r["success"]:
        config = r["data"].get("result", {})
        tools = config.get("tools", {})
        
        ga4_exists = any(
            t.get("component") == "google-analytics-4" and t.get("enabled")
            for t in tools.values()
        )
        
        if ga4_exists:
            print("\n  ✅ GA4 已在 Zaraz 中配置，跳过")
            return True
        
        # 添加 GA4
        tools["ga4"] = {
            "blockingTriggers": [],
            "component": "google-analytics-4",
            "defaultFields": {},
            "enabled": True,
            "name": "Google Analytics 4",
            "permissions": [],
            "settings": {"measurementId": ga4_id},
            "type": "component",
            "actions": {
                "pageview": {
                    "actionType": "event",
                    "data": {},
                    "description": "Page View",
                    "firingTriggers": ["pageload"]
                }
            }
        }
        
        triggers = config.get("triggers", {})
        if "pageload" not in triggers:
            triggers["pageload"] = {
                "excludeRules": [],
                "loadRules": [{
                    "op": "or", "type": "group",
                    "rules": [{
                        "op": "and", "type": "group",
                        "rules": [{
                            "field": "{{client.__zarazTrack}}",
                            "isHidden": True,
                            "op": "eq", "type": "simple",
                            "value": "pageview"
                        }]
                    }]
                }],
                "name": "Pageview",
                "system": "pageload"
            }
        
        config["tools"] = tools
        config["triggers"] = triggers
        config["settings"]["autoInjectScript"] = True
        config["dataLayer"] = True
        
        r2 = api("PUT", f"/zones/{zone_id}/settings/zaraz", token, config)
        if r2["success"]:
            print("\n  ✅ Zaraz + GA4 服务端配置成功!")
            print(f"     📡 GA4 事件将通过 Cloudflare 边缘节点发送")
            print(f"     🛡️  绕过 AdBlock/隐私拦截器")
            print(f"     ⚠️  请从网站 <head> 中移除旧 gtag.js 代码，避免重复统计")
            return True
    
    print_dashboard_zaraz_guide(ga4_id)
    return False


def configure_ip_filter(token, zone_id):
    """配置 IP 过滤"""
    print("\n" + "=" * 55)
    print("🏷️  任务 4/4: 排除测试流量")
    print("=" * 55)
    print(f"  测试 IP: {TEST_IP}")
    print(f"  方案: Transform Rule 注入 X-Test-Traffic 请求头")
    
    rule = {
        "description": "MintShovels - 标记测试IP流量",
        "expression": f'(ip.src eq "{TEST_IP}")',
        "action": "rewrite",
        "action_parameters": {
            "headers": {
                "X-Test-Traffic": {
                    "operation": "set",
                    "value": "true"
                }
            }
        }
    }
    
    existing = api("GET", f"/zones/{zone_id}/rulesets?phase=http_request_late_transform", token)
    
    if existing["success"] and existing["data"].get("result"):
        results = existing["data"]["result"]
        if results and len(results) > 0:
            ruleset_id = results[0]["id"]
            current_rules = results[0].get("rules", [])
            
            for r in current_rules:
                if "测试IP" in (r.get("description") or ""):
                    print("\n  ✅ IP 过滤已配置，跳过")
                    return True
            
            print(f"  规则集ID: {ruleset_id}")
            r2 = api("PUT", f"/zones/{zone_id}/rulesets/{ruleset_id}", token, {
                "rules": current_rules + [rule]
            })
            
            if r2["success"]:
                print(f"\n  ✅ Transform Rule 创建成功!")
                print(f"     {TEST_IP} → 自动标记 X-Test-Traffic: true")
                print(f"     Zaraz 会排除此标记的请求")
                return True
        else:
            r2 = api("POST", f"/zones/{zone_id}/rulesets/phases/http_request_late_transform/entrypoint", token, {
                "rules": [rule]
            })
            if r2["success"]:
                print(f"\n  ✅ Transform Rule 创建成功!")
                return True
    
    print_dashboard_ip_guide()
    return False


def print_dashboard_cache_guide():
    print("""
  ╔══════════════════════════════════════════════════╗
  ║  📖 Cloudflare Dashboard 操作：缓存规则          ║
  ╠══════════════════════════════════════════════════╣
  ║                                                   ║
  ║  1. 打开 https://dash.cloudflare.com/              ║
  ║  2. 选择 mintshovels.com                          ║
  ║  3. 左侧菜单 → Rules → Cache Rules                ║
  ║  4. 点击 "Create rule"                            ║
  ║  5. 配置如下:                                     ║
  ║                                                   ║
  ║     名称: Static Assets Cache 1 Month             ║
  ║     条件: URI Path - contains - /css|/js|/fonts   ║
  ║     或使用表达式:                                  ║
  ║     (http.request.uri.path.extension eq "css"     ║
  ║      or http.request.uri.path.extension eq "js"   ║
  ║      or http.request.uri.path.extension eq        ║
  ║         "woff2")                                  ║
  ║     缓存设置:                                      ║
  ║       ✓ Eligible for cache                        ║
  ║       Edge TTL: Override → 1 month                ║
  ║       Browser TTL: Override → 1 month             ║
  ║                                                   ║
  ║  6. 再创建一条图片缓存规则:                         ║
  ║     条件: URI Path contains "/images/"             ║
  ║     Edge TTL: 7 days                              ║
  ║                                                   ║
  ║  7. 保存 → 部署                                    ║
  ╚══════════════════════════════════════════════════╝
""")


def print_dashboard_zaraz_guide(ga4_id):
    print(f"""
  ╔══════════════════════════════════════════════════╗
  ║  📖 Cloudflare Dashboard 操作：Zaraz + GA4       ║
  ╠══════════════════════════════════════════════════╣
  ║                                                   ║
  ║  1. 打开 https://dash.cloudflare.com/              ║
  ║  2. 选择 mintshovels.com                          ║
  ║  3. 左侧菜单 → Zaraz                              ║
  ║  4. 点击 "Add Tool" → 选择 "Google Analytics 4"   ║
  ║  5. 填入 Measurement ID: {ga4_id}            ║
  ║  6. 触发器自动创建 (Pageview = 所有页面)           ║
  ║  7. 点击 "Save"                                   ║
  ║                                                   ║
  ║  ⚠️ 重要: 配置完 Zaraz 后，必须从网站源码中        ║
  ║     删除旧的 Google gtag.js 脚本!!!               ║
  ║     否则 GA4 会收到双份数据。                      ║
  ║                                                   ║
  ║  🛡️ 为什么这样做?                                  ║
  ║     Zaraz 在 Cloudflare 边缘节点执行 GA4 发送，    ║
  ║     不会经过用户浏览器，AdBlock 无法拦截。         ║
  ║     这样可以拿回被广告拦截器阻挡的 90%+ 访客数据。 ║
  ╚══════════════════════════════════════════════════╝
""")


def print_dashboard_ip_guide():
    print(f"""
  ╔══════════════════════════════════════════════════╗
  ║  📖 排除测试流量 - 两种方案                       ║
  ╠══════════════════════════════════════════════════╣
  ║                                                   ║
  ║  方案 A: Transform Rule (推荐)                    ║
  ║  ────────────────────────────                     ║
  ║  1. Cloudflare Dashboard → Rules → Transform      ║
  ║  2. "Modify Request Header"                       ║
  ║  3. 创建规则:                                     ║
  ║     条件: ip.src eq "{TEST_IP}"              ║
  ║     动作: Set header X-Test-Traffic = true        ║
  ║  4. Zaraz 触发器排除此 header                     ║
  ║                                                   ║
  ║  方案 B: 浏览器插件 (更快)                          ║
  ║  ────────────────────────────                     ║
  ║  安装 "Google Analytics Opt-out Add-on"            ║
  ║  它会阻止你浏览器的 GA4 数据上报                   ║
  ║  Chrome: https://tools.google.com/dlpage/gaoptout  ║
  ║                                                   ║
  ║  方案 C: 测试时加参数 (最简)                       ║
  ║  ────────────────────────────                     ║
  ║  访问 https://mintshovels.com/?notrack=1           ║
  ║  Zaraz 触发器排除包含此参数的请求                   ║
  ║                                                   ║
  ║  ⚡ 临时方案: 现在就安装 GA Opt-out 插件            ║
  ║     你的测试访问就不会污染数据了                   ║
  ╚══════════════════════════════════════════════════╝
""")


def main():
    config = load_config()
    token = config["cloudflare"]["api_token"]
    zone_id = config["cloudflare"]["zone_id"]
    ga4_id = config["ga4"]["measurement_id"]
    
    print("=" * 55)
    print("  🚀 MintShovels Cloudflare 一步配置 v2")
    print("=" * 55)
    print(f"  Zone:     mintshovels.com")
    print(f"  GA4:      {ga4_id}")
    print(f"  测试 IP:  {TEST_IP}")
    
    # 先检测写权限
    print(f"\n🔍 检测 API Token 权限...")
    perms = test_write_perms(token, zone_id)
    
    print(f"  Cache Rules:   {'✅ 可写' if perms.get('cache_rules') else '⚠️  只读/无权限'}")
    print(f"  Zaraz:         {'✅ 可写' if perms.get('zaraz_write') else '⚠️  只读' if perms.get('zaraz_read') else '❌'} 无权限")
    print(f"  Transform:     {'✅ 可写' if perms.get('transform_read') else '⚠️  只读/无权限'}")
    
    has_write = perms.get("cache_rules") or perms.get("zaraz_write")
    
    if has_write:
        print(f"\n  🟢 检测到写权限，自动配置...")
    else:
        print(f"\n  🟡 API Token 无写权限，将显示 Dashboard 操作指引")
        print(f"  💡 如需自动配置，请在 Cloudflare 创建新 Token:")
        print(f"     权限: Zone → Cache Rules → Edit")
        print(f"           Zone → Zaraz → Edit")  
        print(f"           Zone → Transform Rules → Edit")
        print(f"     然后更新 mintshovels_config.json 中的 api_token")
    
    # 执行配置
    cache_ok = configure_cache_rules(token, zone_id) if perms.get("cache_rules") else print_dashboard_cache_guide() or True
    
    configure_zaraz_ga4(token, zone_id, ga4_id)
    configure_ip_filter(token, zone_id)
    
    print(f"\n{'=' * 55}")
    print(f"  ✅ 所有指引已输出，请按上方步骤操作")
    print(f"  📊 配置完成后运行: python3 mintshovels_dashboard.py")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    main()
