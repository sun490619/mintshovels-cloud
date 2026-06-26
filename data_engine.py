#!/usr/bin/env python3
"""
MintShovels 统一数据引擎 v3
============================
所有数据源的统一抓取层 + 持久化 + 环比 + 诊断
"""

import json, os, ssl, urllib.request, urllib.error
from datetime import datetime, timedelta, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "mintshovels_config.json")
HISTORY_PATH = os.path.join(SCRIPT_DIR, "analytics_history.json")


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)

def resolve_path(p: str) -> str:
    return p if os.path.isabs(p) else os.path.join(SCRIPT_DIR, p)

# ═══════ 历史数据 ═══════
def load_history() -> dict:
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError, Exception) as e:
            print(f"⚠️ 历史数据读取失败，将使用空快照: {e}")
    return {"snapshots": []}

def save_snapshot(data: dict):
    history = load_history()
    today = datetime.now().strftime("%Y-%m-%d")
    history["snapshots"] = [s for s in history["snapshots"] if s.get("date") != today]
    history["snapshots"].append({
        "date": today, "timestamp": datetime.now().isoformat(),
        "cf_uv": data.get("cf",{}).get("uv",0),
        "cf_requests": data.get("cf",{}).get("requests",0),
        "cf_pageviews": data.get("cf",{}).get("pageviews",0),
        "cf_bandwidth_mb": data.get("cf",{}).get("bandwidth_mb",0),
        "cf_cached_pct": data.get("cf",{}).get("cached_pct",0),
        "ga4_users": data.get("ga4",{}).get("today_users",0),
        "ga4_sessions": data.get("ga4",{}).get("today_sessions",0),
        "ga4_bounce": data.get("ga4",{}).get("today_bounce",0),
        "gsc_clicks": data.get("gsc",{}).get("total_clicks",0),
        "gsc_impressions": data.get("gsc",{}).get("total_impressions",0),
        "bing_clicks": data.get("bing",{}).get("total_clicks",0),
    })
    history["snapshots"] = history["snapshots"][-90:]
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def calc_wow(cur: float, prev: float) -> dict:
    """周环比"""
    if prev == 0:
        if cur == 0: return {"pct": 0, "dir": "flat", "text": "—"}
        return {"pct": 100, "dir": "up", "text": "新增"}
    pct = round((cur - prev) / prev * 100, 1)
    if pct > 5: return {"pct": pct, "dir": "up", "text": f"↑{abs(pct)}%"}
    elif pct < -5: return {"pct": pct, "dir": "down", "text": f"↓{abs(pct)}%"}
    return {"pct": pct, "dir": "flat", "text": "—"}

def get_previous_week_sum(key: str) -> float:
    """获取上周同期数据总和"""
    history = load_history()
    snaps = history.get("snapshots", [])
    if len(snaps) < 7: return 0
    return sum(s.get(key, 0) for s in snaps[-14:-7])

def get_previous_7d(keys: list) -> float:
    """获取上周同期的总和"""
    return sum(get_previous_week_sum(k) for k in keys)

# ═══════ 1. Cloudflare ═══════
def fetch_cloudflare(config: dict, days: int = 7) -> dict:
    result = {"status": "pending", "uv": 0, "requests": 0, "pageviews": 0,
              "bandwidth_mb": 0, "cached_pct": 0, "ssl_pct": 0, "threats": 0,
              "today_uv": 0, "today_requests": 0, "today_pageviews": 0, "today_mb": 0,
              "daily": [], "avg_daily_uv": 0, "avg_daily_pv": 0, "trend": "flat"}
    token = config["cloudflare"].get("analytics_token", config["cloudflare"]["api_token"])
    zone_id = config["cloudflare"]["zone_id"]
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=days+1)).strftime('%Y-%m-%d')
        q = {"query": f"""{{ viewer {{ zones(filter: {{zoneTag: "{zone_id}"}}) {{
          httpRequests1dGroups(limit: {days+2}, filter: {{date_geq: "{since}"}}) {{
            dimensions {{ date }}
            sum {{ requests bytes pageViews cachedRequests encryptedRequests }}
            uniq {{ uniques }}
          }} }} }} }}"""}
        req = urllib.request.Request('https://api.cloudflare.com/client/v4/graphql',
            data=json.dumps(q).encode(),
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read())
        if d.get('data') and d['data']['viewer']['zones']:
            groups = d['data']['viewer']['zones'][0].get('httpRequests1dGroups', [])
            if groups:
                result["status"] = "ok"; result["daily"] = []
                tr, tu, tp, tb, tc, ts = 0,0,0,0,0,0
                for g in sorted(groups, key=lambda x: x['dimensions']['date']):
                    s, u = g['sum'], g['uniq']
                    day = {"date": g['dimensions']['date'], "requests": s.get('requests',0),
                           "uv": u.get('uniques',0), "pageviews": s.get('pageViews',0),
                           "mb": round(s.get('bytes',0)/1024/1024,1),
                           "cached": s.get('cachedRequests',0), "ssl": s.get('encryptedRequests',0)}
                    result["daily"].append(day); tr+=day["requests"]; tu+=day["uv"]
                    tp+=day["pageviews"]; tb+=s.get('bytes',0); tc+=day["cached"]; ts+=day["ssl"]
                result["requests"]=tr; result["uv"]=tu; result["pageviews"]=tp
                result["bandwidth_mb"]=round(tb/1024/1024,1)
                result["cached_pct"]=round(tc/max(tr,1)*100,1)
                result["ssl_pct"]=round(ts/max(tr,1)*100,1)
                td = result["daily"][-1] if result["daily"] else {}
                result["today_uv"]=td.get("uv",0); result["today_requests"]=td.get("requests",0)
                result["today_pageviews"]=td.get("pageviews",0); result["today_mb"]=td.get("mb",0)
                n = len(result["daily"])
                if n: result["avg_daily_uv"]=round(tu/n,1); result["avg_daily_pv"]=round(tp/n,1)
                if n>=3:
                    h=n//2; fh=sum(d_["uv"] for d_ in result["daily"][:h])
                    sh_=sum(d_["uv"] for d_ in result["daily"][h:])
                    result["trend"]="up" if sh_>fh*1.1 else ("down" if sh_<fh*0.9 else "flat")
        elif 'errors' in d: result["status"] = f"error: {d['errors'][0].get('message','')[:100]}"
        else: result["status"] = "no_data"
    except Exception as e: result["status"] = f"error: {e}"
    return result

# ═══════ 2. GA4 ═══════
def fetch_ga4(config: dict, days: int = 7) -> dict:
    result = {"status": "pending", "daily": [], "totals": {},
              "today_users": 0, "today_sessions": 0, "today_bounce": 0,
              "today_duration": 0, "today_pageviews": 0,
              "top_pages": [], "top_sources": [], "device_breakdown": {}}
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        with open(resolve_path(config["ga4"]["credentials_file"])) as f:
            sa = json.load(f)
        creds = service_account.Credentials.from_service_account_info(
            sa, scopes=["https://www.googleapis.com/auth/analytics.readonly"])
        creds.refresh(Request())
        pid = config["ga4"]["property_id"]
        today = datetime.now().strftime('%Y-%m-%d')
        start = (datetime.now()-timedelta(days=days)).strftime('%Y-%m-%d')
        ctx = ssl._create_unverified_context() if hasattr(ssl,'_create_unverified_context') else None

        payload = {"dateRanges":[{"startDate":start,"endDate":today}],
            "metrics":[{"name":"activeUsers"},{"name":"sessions"},{"name":"screenPageViews"},
                       {"name":"averageSessionDuration"},{"name":"bounceRate"}],
            "dimensions":[{"name":"date"}], "orderBys":[{"dimension":{"dimensionName":"date"}}]}
        req = urllib.request.Request(f'https://analyticsdata.googleapis.com/v1beta/{pid}:runReport',
            data=json.dumps(payload).encode(),
            headers={'Authorization':f'Bearer {creds.token}','Content-Type':'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            d = json.loads(r.read())
        result["status"]="ok"; result["daily"]=[]
        totals={"activeUsers":0,"sessions":0,"pageViews":0,"avgDuration":0,"bounceRate":0}; rc=0
        for row in (d.get("rows") or []):
            date=row["dimensionValues"][0]["value"]; v=row["metricValues"]
            e={"date":date,"activeUsers":int(v[0]["value"]),"sessions":int(v[1]["value"]),
               "pageViews":int(v[2]["value"]),"avgDuration":round(float(v[3]["value"]),1),
               "bounceRate":round(float(v[4]["value"])*100,1)}
            result["daily"].append(e)
            for k in totals: totals[k]+=e[k]; rc+=1
        if rc>0: totals["avgDuration"]=round(totals["avgDuration"]/rc,1); totals["bounceRate"]=round(totals["bounceRate"]/rc,1)
        result["totals"]=totals
        if result["daily"]:
            l=result["daily"][-1]; result["today_users"]=l["activeUsers"]; result["today_sessions"]=l["sessions"]
            result["today_bounce"]=l["bounceRate"]; result["today_duration"]=l["avgDuration"]; result["today_pageviews"]=l["pageViews"]
        # 来源
        try:
            sp={"dateRanges":[{"startDate":start,"endDate":today}],"metrics":[{"name":"activeUsers"}],
                "dimensions":[{"name":"sessionSource"}],"limit":10,
                "orderBys":[{"metric":{"metricName":"activeUsers"},"desc":True}]}
            req2=urllib.request.Request(f'https://analyticsdata.googleapis.com/v1beta/{pid}:runReport',
                data=json.dumps(sp).encode(),headers={'Authorization':f'Bearer {creds.token}','Content-Type':'application/json'},method='POST')
            with urllib.request.urlopen(req2, timeout=20, context=ctx) as r2:
                sd=json.loads(r2.read())
            result["top_sources"]=[{"source":r_["dimensionValues"][0]["value"],"users":int(r_["metricValues"][0]["value"])} for r_ in (sd.get("rows")or[])]
        except Exception:
            pass  # 来源数据非关键，拉取失败不影响主流程
        # 设备
        try:
            dp={"dateRanges":[{"startDate":start,"endDate":today}],"metrics":[{"name":"activeUsers"}],"dimensions":[{"name":"deviceCategory"}]}
            req3=urllib.request.Request(f'https://analyticsdata.googleapis.com/v1beta/{pid}:runReport',
                data=json.dumps(dp).encode(),headers={'Authorization':f'Bearer {creds.token}','Content-Type':'application/json'},method='POST')
            with urllib.request.urlopen(req3, timeout=20, context=ctx) as r3:
                dd=json.loads(r3.read())
            result["device_breakdown"]={r_["dimensionValues"][0]["value"]:int(r_["metricValues"][0]["value"]) for r_ in (dd.get("rows")or[])}
        except Exception:
            pass  # 设备数据非关键
        # 热门页面
        try:
            pp={"dateRanges":[{"startDate":start,"endDate":today}],"metrics":[{"name":"screenPageViews"}],
                "dimensions":[{"name":"pagePath"}],"limit":10,
                "orderBys":[{"metric":{"metricName":"screenPageViews"},"desc":True}]}
            req4=urllib.request.Request(f'https://analyticsdata.googleapis.com/v1beta/{pid}:runReport',
                data=json.dumps(pp).encode(),headers={'Authorization':f'Bearer {creds.token}','Content-Type':'application/json'},method='POST')
            with urllib.request.urlopen(req4, timeout=20, context=ctx) as r4:
                pd=json.loads(r4.read())
            result["top_pages"]=[{"path":r_["dimensionValues"][0]["value"],"views":int(r_["metricValues"][0]["value"])} for r_ in (pd.get("rows")or[])]
        except Exception:
            pass  # 热门页面数据非关键
    except ImportError: result["status"]="need_install"
    except urllib.error.URLError as e: result["status"]=f"network_error: {e.reason}"
    except Exception as e: result["status"]=f"error: {e}"
    return result

# ═══════ 3. GSC ═══════
def fetch_gsc(config: dict, days: int = 7) -> dict:
    result = {"status":"pending","total_clicks":0,"total_impressions":0,"avg_ctr":0,"avg_position":0,
              "top_queries":[],"top_pages":[],"daily":[],"detail":""}
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        with open(resolve_path(config["gsc"]["credentials_file"])) as f:
            sa = json.load(f)
        creds = service_account.Credentials.from_service_account_info(
            sa, scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
        creds.refresh(Request())
        site = config["gsc"]["site_url"]
        ed = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        sd = (datetime.now(timezone.utc)-timedelta(days=days)).strftime("%Y-%m-%d")
        ctx = ssl._create_unverified_context() if hasattr(ssl,'_create_unverified_context') else None
        cp = json.dumps({"startDate":sd,"endDate":ed,"dimensions":["query"],"rowLimit":20}).encode()
        req = urllib.request.Request(f'https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query',
            data=cp, headers={'Authorization':f'Bearer {creds.token}','Content-Type':'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=20, context=ctx) as r:
            d = json.loads(r.read())
        rows = d.get("rows",[])
        result["status"]="ok"; result["total_clicks"]=sum(r_["clicks"] for r_ in rows)
        result["total_impressions"]=sum(r_["impressions"] for r_ in rows)
        result["top_queries"]=[{"query":r_["keys"][0],"clicks":r_["clicks"],"impressions":r_["impressions"]} for r_ in sorted(rows,key=lambda x:x.get("clicks",0),reverse=True)[:10]]
        if result["total_impressions"]>0: result["avg_ctr"]=round(result["total_clicks"]/result["total_impressions"]*100,2)
        if result["total_impressions"]==0: result["detail"]="暂无搜索数据，网站刚开始收录中"
        # 按日
        try:
            dp=json.dumps({"startDate":sd,"endDate":ed,"dimensions":["date"],"rowLimit":days+1}).encode()
            req2=urllib.request.Request(f'https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query',
                data=dp,headers={'Authorization':f'Bearer {creds.token}','Content-Type':'application/json'},method='POST')
            with urllib.request.urlopen(req2, timeout=20, context=ctx) as r2:
                dd=json.loads(r2.read())
            result["daily"]=[{"date":r_["keys"][0],"clicks":r_["clicks"],"impressions":r_["impressions"]} for r_ in sorted(dd.get("rows",[]),key=lambda x:x["keys"][0])]
        except Exception:
            pass  # 每日GSC数据非关键
    except ImportError: result["status"]="need_install"
    except urllib.error.URLError as e:
        rs = str(e.reason) if hasattr(e,'reason') else str(e)
        result["status"]="network_ssl" if 'SSL' in rs else f"network_error: {e}"
        result["detail"]="Google API SSL握手失败，网络环境限制" if 'SSL' in rs else str(e)
    except Exception as e: result["status"]=f"error: {e}"
    return result

# ═══════ 4. Bing ═══════
def fetch_bing(config: dict) -> dict:
    result = {"status":"pending","total_clicks":0,"total_impressions":0,"queries":[]}
    ak = config.get("bing",{}).get("api_key","")
    su = config.get("bing",{}).get("site_url","")
    if not ak or "YOUR_" in ak: result["status"]="not_configured"; return result
    try:
        # Bing Webmaster API 使用 apikey 作为 URL 查询参数，不是 Bearer Token
        url = f"https://ssl.bing.com/webmaster/api.svc/json/GetQueryStats?siteUrl={urllib.parse.quote(su)}&apikey={ak}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
        qs = d.get("d",[]) or []
        result["queries"]=[{"query":q.get("Query",""),"clicks":q.get("Clicks",0),"impressions":q.get("Impressions",0)} for q in qs[:10]]
        result["total_clicks"]=sum(q.get("Clicks",0) for q in qs)
        result["total_impressions"]=sum(q.get("Impressions",0) for q in qs)
        result["status"]="ok"
    except Exception as e: result["status"]=f"error: {e}"
    return result

# ═══════ 5. Clarity ═══════
def fetch_clarity(config: dict) -> dict:
    result = {"status":"pending","project_id":"","dashboard_url":""}
    pid = config.get("clarity",{}).get("project_id","")
    if not pid or "XXXXXXXXXX" in pid: result["status"]="not_configured"; return result
    result["project_id"]=pid; result["dashboard_url"]=f"https://clarity.microsoft.com/projects/{pid}/dashboard"
    result["status"]="ok"; result["detail"]="需在网页端查看热力图和录屏"
    return result

# ═══════ 6. 诊断引擎 ═══════
def run_diagnostics(cf: dict, ga4: dict, gsc: dict) -> list:
    diags = []
    # GA4 vs CF 覆盖
    if cf.get("status")=="ok" and ga4.get("status")=="ok":
        cf_uv=cf.get("uv",0); ga4_u=ga4.get("totals",{}).get("activeUsers",0)
        if cf_uv>50:
            if ga4_u==0:
                diags.append({"severity":"🔴","title":"GA4 可能未部署","detail":f"CF检测{cf_uv}访客，GA4显示0用户","action":"检查网站所有页面的 GA4 gtag 代码，或使用 Cloudflare Zaraz 服务端加载"})
            elif ga4_u/cf_uv<0.2:
                diags.append({"severity":"🟡","title":f"GA4覆盖率仅{ga4_u/cf_uv*100:.0f}%","detail":f"CF {cf_uv}UV vs GA4 {ga4_u}用户，可能广告拦截器阻止了GA4","action":"考虑用 Cloudflare Zaraz 做服务端 GA4 事件发送"})
    # 缓存
    if cf.get("status")=="ok":
        cp=cf.get("cached_pct",0)
        if cp<20:
            diags.append({"severity":"🟡","title":f"缓存率仅{cp}%","detail":"大部分请求回源，拖慢速度","action":"Cloudflare→缓存规则：对 *.css,*.js,*.woff2 设Edge TTL=1月，对 /images/ 设标准缓存"})
    # SEO
    if gsc.get("status")=="ok":
        imp=gsc.get("total_impressions",0); clk=gsc.get("total_clicks",0)
        if imp==0:
            diags.append({"severity":"ℹ️","title":"GSC 0搜索数据","detail":"新站正常，谷歌需要几周收录","action":"提交sitemap→GSC、在社交媒体分享链接加速收录"})
        elif clk==0 and imp>0:
            diags.append({"severity":"🟡","title":"有展示无点击","detail":f"{imp}展示但0点击","action":"优化页面title和meta description"})
    # 跳出率
    if ga4.get("status")=="ok":
        br=ga4.get("today_bounce",0) or ga4.get("totals",{}).get("bounceRate",0)
        if br>80:
            diags.append({"severity":"🟡","title":f"跳出率{br}%过高","detail":"用户停留时间短","action":"检查首屏加载速度、增加明确CTA按钮"})
    return diags

# ═══════ 7. 全量采集 ═══════
def fetch_all(config: dict = None) -> dict:
    if config is None: config = load_config()
    print("🔄 抓取 Cloudflare + GA4 + GSC + Bing...")
    cf = fetch_cloudflare(config)
    ga4 = fetch_ga4(config)
    gsc = fetch_gsc(config)
    bing = fetch_bing(config)
    clarity = fetch_clarity(config)
    result = {"timestamp": datetime.now().isoformat(), "cf": cf, "ga4": ga4,
              "gsc": gsc, "bing": bing, "clarity": clarity}
    result["diagnostics"] = run_diagnostics(cf, ga4, gsc)
    save_snapshot(result)
    return result

# ═══════ 8. 自动工厂触发器 ═══════
def trigger_auto_factory(dry_run=False, max_count=3):
    """
    数据引擎采集完成后，自动检测需求雷达报告中的新工具建议，
    如果存在尚未生产的新工具，触发 auto_factory 进行生产。
    
    内置去重：对比 index.html 已有工具名称，跳过已存在的工具。
    """
    demand_path = os.path.join(SCRIPT_DIR, "reports", "demand_report.json")
    factory_log_path = os.path.join(SCRIPT_DIR, "reports", "factory_log.json")
    
    if not os.path.exists(demand_path):
        print("📡 无需求雷达报告，跳过工厂触发")
        return {"triggered": False, "reason": "no_demand_report"}
    
    try:
        with open(demand_path, "r", encoding="utf-8") as f:
            demand = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️ 需求报告读取失败: {e}")
        return {"triggered": False, "reason": "demand_read_error"}
    
    suggestions = demand.get("tool_suggestions", [])
    if not suggestions:
        print("📡 需求报告无工具建议")
        return {"triggered": False, "reason": "no_suggestions"}
    
    # 读取 index.html 中已有工具名称（去重关键）
    index_path = os.path.join(SCRIPT_DIR, "index.html")
    existing_names = set()
    if os.path.exists(index_path):
        import re as _re
        with open(index_path, "r", encoding="utf-8") as f:
            html = f.read()
        existing_names = set(_re.findall(r'name:\s*"([^"]+)"', html))
    
    # 读取工厂日志中已生产的工具ID
    produced_ids = set()
    if os.path.exists(factory_log_path):
        try:
            with open(factory_log_path, "r", encoding="utf-8") as f:
                flog = json.load(f)
            produced_ids = set(flog.get("produced", []))
        except (json.JSONDecodeError, IOError):
            pass
    
    # 筛选真正新的工具建议（名称不在已有工具中）
    truly_new = []
    for s in suggestions:
        name = s.get("name", "")
        if name and name not in existing_names:
            # 额外去重：检查工厂日志是否已记录
            # 这里按名称去重，不按ID（ID在auto_factory里分配）
            truly_new.append(s)
    
    if not truly_new:
        print(f"✅ 所有 {len(suggestions)} 条建议的工具已存在于目录中，无需生产")
        return {"triggered": False, "reason": "all_exist", "suggestions_count": len(suggestions), "existing_count": len(existing_names)}
    
    print(f"\n🏭 数据引擎检测到 {len(truly_new)} 个新工具需求（共 {len(suggestions)} 条建议，{len(existing_names)} 个已存在）")
    for s in truly_new[:5]:
        print(f"   • {s.get('name', '?')} ({s.get('name_zh', '?')})")
    
    if dry_run:
        print("[DRY-RUN] 跳过实际生产")
        return {"triggered": True, "dry_run": True, "new_count": len(truly_new)}
    
    # 触发 auto_factory
    try:
        import subprocess as _sp
        factory_script = os.path.join(SCRIPT_DIR, "engine", "auto_factory.py")
        cmd = ["python3", factory_script, "--max", str(min(max_count, len(truly_new))), "--no-deploy"]
        result = _sp.run(cmd, capture_output=True, text=True, timeout=120, cwd=SCRIPT_DIR)
        output = result.stdout + result.stderr
        print(output[:2000])
        
        produced = [line.strip() for line in output.split("\n") if "Producing:" in line]
        return {
            "triggered": True,
            "new_count": len(truly_new),
            "produced_this_run": len(produced),
            "factory_output": output[-500:],
        }
    except _sp.TimeoutExpired:
        print("❌ 工厂触发超时")
        return {"triggered": False, "reason": "factory_timeout"}
    except Exception as e:
        print(f"❌ 工厂触发失败: {e}")
        return {"triggered": False, "reason": str(e)}


def full_pipeline():
    """
    完整数据流水线: 采集 → 诊断 → 工厂触发
    供定时任务或健康检查调用
    """
    print("=" * 50)
    print("🔬 MintShovels 数据引擎 + 自动工厂")
    print("=" * 50)
    
    # 阶段1: 全量数据采集
    data = fetch_all()
    
    # 阶段2: 诊断
    diags = data.get("diagnostics", [])
    issues = [d for d in diags if d["severity"] in ("🔴", "🟡")]
    print(f"\n📊 诊断: {len(diags)}条, {len(issues)}个需关注")
    for d in issues:
        print(f"  {d['severity']} {d['title']}: {d['action']}")
    
    # 阶段3: 自动工厂触发
    factory_result = trigger_auto_factory(dry_run=False, max_count=3)
    
    # 汇总
    data["factory"] = factory_result
    summary_path = os.path.join(SCRIPT_DIR, "reports", "pipeline_summary.json")
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    except IOError:
        pass
    
    print(f"\n{'='*50}")
    print(f"✅ 全流程完成")
    print(f"{'='*50}")
    return data


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        # 完整流水线模式
        data = full_pipeline()
    elif len(sys.argv) > 1 and sys.argv[1] == "--factory":
        # 仅工厂触发模式
        result = trigger_auto_factory(dry_run="--dry-run" in sys.argv, max_count=3)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 默认：仅数据采集
        data = fetch_all()
        print(json.dumps({k: v if k!="diagnostics" else f"{len(v)}条诊断" for k,v in data.items()}, ensure_ascii=False, indent=2))
