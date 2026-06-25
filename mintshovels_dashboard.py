#!/usr/bin/env python3
"""
MintShovels 数据管家 v3 — 全面升级版
=====================================
用法:
  python3 mintshovels_dashboard.py           # 终端 + HTML 看板
  python3 mintshovels_dashboard.py --email   # + 发邮件
  python3 mintshovels_dashboard.py --all     # 全部

升级亮点:
  ✅ Bing + Clarity 数据接入
  ✅ 历史数据持久化 + 周环比对比
  ✅ 交叉数据诊断（GA4 vs CF 覆盖、缓存、SEO）
  ✅ 增强 HTML 看板：环比箭头、交叉洞察、SEO 评分
  ✅ SMTP 邮件替代 sendmail
"""

import json, os, sys, smtplib, subprocess
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from data_engine import *

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "mintshovels_config.json")
OUTPUT_HTML = os.path.join(SCRIPT_DIR, "dashboard.html")


# ═══════════════════════════════════════════
# HTML 看板
# ═══════════════════════════════════════════

def _wow_badge(wow: dict) -> str:
    """环比徽章 HTML"""
    if wow["dir"] == "up":
        return f'<span class="wow up">{wow["text"]}</span>'
    elif wow["dir"] == "down":
        return f'<span class="wow down">{wow["text"]}</span>'
    return ''


def _status_icon(status: str) -> str:
    if status == "ok": return "🟢"
    if status.startswith("error") or status.startswith("network"):
        return "🔴"
    return "⚪"


def generate_html_dashboard(data: dict = None, config: dict = None) -> str:
    """生成 v3 HTML 看板"""
    if config is None: config = load_config()
    if data is None:
        data = fetch_all(config)
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cf = data.get("cf", {})
    ga4 = data.get("ga4", {})
    gsc = data.get("gsc", {})
    bing = data.get("bing", {})
    clarity = data.get("clarity", {})
    diags = data.get("diagnostics", [])
    
    # 历史环比
    history = load_history()
    snaps = history.get("snapshots", [])
    prev_cf_uv = sum(s.get("cf_uv", 0) for s in snaps[-14:-7]) if len(snaps) >= 14 else 0
    prev_ga4_users = sum(s.get("ga4_users", 0) for s in snaps[-14:-7]) if len(snaps) >= 14 else 0
    prev_gsc_clicks = sum(s.get("gsc_clicks", 0) for s in snaps[-14:-7]) if len(snaps) >= 14 else 0
    
    cf_wow = calc_wow(cf.get("uv", 0), prev_cf_uv)
    ga4_wow = calc_wow(ga4.get("today_users", 0), prev_ga4_users // 7 if prev_ga4_users > 0 else 0)
    gsc_wow = calc_wow(gsc.get("total_clicks", 0), prev_gsc_clicks)
    
    cards = ""
    
    # ═══ 摘要卡片 ═══
    cf_ok = cf.get("status") == "ok"
    ga4_ok = ga4.get("status") == "ok"
    gsc_ok = gsc.get("status") == "ok"
    bing_ok = bing.get("status") == "ok"
    
    cards += '<div class="summary-row">'
    cards += f'<div class="summary-card">{"🟢" if cf_ok else "🔴"}<div class="sval">{_wow_badge(cf_wow)}</div><div class="slbl">Cloudflare</div></div>'
    cards += f'<div class="summary-card">{"🟢" if ga4_ok else "🔴"}<div class="sval">{_wow_badge(ga4_wow)}</div><div class="slbl">GA4</div></div>'
    cards += f'<div class="summary-card">{"🟢" if gsc_ok else "⚪"}<div class="sval">{_wow_badge(gsc_wow)}</div><div class="slbl">GSC</div></div>'
    cards += f'<div class="summary-card">{"🟢" if bing.get("status")=="ok" else "⚪"}<div class="sval"></div><div class="slbl">Bing</div></div>'
    cards += '</div>'
    
    # ═══ Cloudflare 卡片 ═══
    if cf_ok:
        cards += f'''
        <div class="card green">
            <div class="card-header">🌐 Cloudflare 近7天 {_wow_badge(cf_wow)}</div>
            <div class="card-body cols4">
                <div class="metric"><span class="value">{cf['uv']:,}</span><span class="label">独立访客</span></div>
                <div class="metric"><span class="value">{cf['requests']:,}</span><span class="label">总请求</span></div>
                <div class="metric"><span class="value">{cf['pageviews']:,}</span><span class="label">页面浏览</span></div>
                <div class="metric"><span class="value">{cf['bandwidth_mb']}MB</span><span class="label">带宽</span></div>
            </div>
            <div class="card-stats">
                <span>📊 日均 {cf.get('avg_daily_uv','-')} 访客</span>
                <span>📦 缓存率 {cf['cached_pct']}%</span>
                <span>🔒 SSL {cf.get('ssl_pct','-')}%</span>
                <span>📈 趋势 {"↗上升" if cf.get('trend')=="up" else "↘下降" if cf.get('trend')=="down" else "→平稳"}</span>
            </div>
            <div class="card-footer">
                今日: {cf['today_uv']:,} 访客 · {cf['today_pageviews']:,} 浏览 · {cf['today_mb']}MB
            </div>
        </div>'''
        
        # 趋势图
        if cf.get("daily") and len(cf["daily"]) >= 2:
            max_uv = max(d["uv"] for d in cf["daily"])
            bars = "".join(
                f'<div class="bar-col"><div class="bar" style="height:{int(d["uv"]/max(max_uv,1)*100)}px" '
                f'title="{d["date"]}: {d["uv"]}访客 | {d["requests"]}请求"></div>'
                f'<span class="bar-label">{d["date"][5:]}</span></div>'
                for d in cf["daily"]
            )
            cards += f'<div class="card"><div class="card-header">📊 7日访客趋势</div><div class="chart-bars">{bars}</div></div>'
    else:
        cards += f'<div class="card red"><div class="card-header">🌐 Cloudflare</div><div class="card-body"><p class="note">{cf.get("status")}</p></div></div>'
    
    # ═══ GA4 卡片 ═══
    if ga4_ok and ga4.get("daily"):
        latest = ga4["daily"][-1]
        totals = ga4.get("totals", {})
        cards += f'''
        <div class="card blue">
            <div class="card-header">📈 GA4 今日 {_wow_badge(ga4_wow)}</div>
            <div class="card-body cols4">
                <div class="metric"><span class="value">{latest.get("activeUsers",0)}</span><span class="label">活跃用户</span></div>
                <div class="metric"><span class="value">{latest.get("sessions",0)}</span><span class="label">会话</span></div>
                <div class="metric"><span class="value">{latest.get("pageViews",0)}</span><span class="label">浏览</span></div>
                <div class="metric"><span class="value">{latest.get("avgDuration",0)}s</span><span class="label">均时长</span></div>
            </div>
            <div class="card-stats">
                <span>🚪 跳出率 {latest.get("bounceRate",0):.0f}%</span>
                <span>📱 {"手机" if ga4.get("device_breakdown",{}).get("mobile","") else "—"}</span>
            </div>
            <div class="card-footer">
                7天共 {totals.get("activeUsers",0):,} 用户 · {totals.get("pageViews",0):,} 浏览 · {totals.get("sessions",0):,} 会话
            </div>
        </div>'''
        
        # 来源
        if ga4.get("top_sources"):
            src_html = "".join(
                f'<tr><td>{s["source"]}</td><td class="right">{s["users"]}</td></tr>'
                for s in ga4["top_sources"][:5]
            )
            cards += f'<div class="card"><div class="card-header">🌍 流量来源 Top 5</div><table class="mini-table"><tbody>{src_html}</tbody></table></div>'
    else:
        cards += f'<div class="card red"><div class="card-header">📈 GA4</div><div class="card-body"><p class="note">{ga4.get("status")}</p><p class="note small">{ga4.get("detail","")}</p></div></div>'
    
    # ═══ GSC 卡片 ═══
    if gsc_ok:
        queries_html = "".join(
            f'<tr><td>"{q["query"]}"</td><td class="right">{q["clicks"]}</td><td class="right">{q["impressions"]}</td></tr>'
            for q in (gsc.get("top_queries") or [])[:5]
        )
        cards += f'''
        <div class="card purple">
            <div class="card-header">🔍 Google 搜索 近7天 {_wow_badge(gsc_wow)}</div>
            <div class="card-body cols3">
                <div class="metric"><span class="value">{gsc.get("total_clicks",0):,}</span><span class="label">点击</span></div>
                <div class="metric"><span class="value">{gsc.get("total_impressions",0):,}</span><span class="label">展示</span></div>
                <div class="metric"><span class="value">{gsc.get("avg_ctr",0):.1f}%</span><span class="label">CTR</span></div>
            </div>
            {"<div class=\"card-footer\"><table class=\"mini-table\"><tbody>" + queries_html + "</tbody></table></div>" if queries_html else ""}
        </div>'''
    else:
        st = gsc.get("status",""); st_text = st
        if st == "network_ssl": st_text = "🔒 网络限制"
        cards += f'<div class="card purple"><div class="card-header">🔍 GSC</div><div class="card-body"><p class="note">{st_text}</p><p class="note small">{gsc.get("detail","数据链路正常")}</p></div></div>'
    
    # ═══ Bing 卡片 ═══
    if bing_ok:
        if bing.get("queries"):
            bq_html = "".join(
                f'<tr><td>"{q["query"]}"</td><td class="right">{q["clicks"]}</td></tr>'
                for q in bing["queries"][:5]
            )
            cards += f'''
            <div class="card purple" style="border-left-color: #f59e0b;">
                <div class="card-header">🔎 Bing 搜索</div>
                <div class="card-body cols2">
                    <div class="metric"><span class="value">{bing["total_clicks"]:,}</span><span class="label">点击</span></div>
                    <div class="metric"><span class="value">{bing["total_impressions"]:,}</span><span class="label">展示</span></div>
                </div>
                {"<div class=\"card-footer\"><table class=\"mini-table\"><tbody>" + bq_html + "</tbody></table></div>" if bq_html else ""}
            </div>'''
        else:
            cards += f'<div class="card" style="border-left: 4px solid #f59e0b;"><div class="card-header">🔎 Bing 搜索</div><div class="card-body"><p class="note">✅ 已连接 · 暂无数据 (新站收录中)</p></div></div>'
    elif bing.get("status") == "not_configured":
        pass  # 不显示
    
    # ═══ 诊断卡片 ═══
    if diags:
        diag_html = "".join(
            f'''<div class="diag-item diag-{d["severity"]}">
                <div class="diag-title">{d["severity"]} {d["title"]}</div>
                <div class="diag-detail">{d["detail"]}</div>
                <div class="diag-action">🔧 {d["action"]}</div>
            </div>'''
            for d in diags
        )
        cards += f'<div class="card"><div class="card-header">🩺 系统诊断 ({len(diags)}项)</div>{diag_html}</div>'
    
    # ═══ SEO 健康评分 ═══
    seo_score, seo_items = _calc_seo_score(cf, ga4, gsc)
    seo_html = "".join(
        f'<div class="seo-item {"pass" if i["pass"] else "fail"}">{"✅" if i["pass"] else "❌"} {i["label"]}</div>'
        for i in seo_items
    )
    score_color = "#4ade80" if seo_score >= 70 else "#f59e0b" if seo_score >= 40 else "#f87171"
    cards += f'''<div class="card"><div class="card-header">🎯 SEO 健康评分</div>
        <div class="score-circle" style="background:{score_color}">{seo_score}</div>
        <div class="seo-grid">{seo_html}</div></div>'''
    
    # ═══ Clarity 链接 ═══
    if clarity.get("status") == "ok":
        cards += f'<div class="card"><div class="card-header">📹 用户行为录屏</div><div class="card-body"><a href="{clarity["dashboard_url"]}" class="link-btn" target="_blank">打开 Clarity 看板 →</a></div></div>'
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>MintShovels · 数据看板</title>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", sans-serif;
            background: #f0f2f5; color: #1a1a2e; padding: 16px; max-width: 500px; margin: 0 auto;
            -webkit-font-smoothing: antialiased;
        }}
        .header {{ text-align: center; padding: 20px 0 12px; }}
        .header h1 {{ font-size: 24px; font-weight: 700;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }}
        .header .time {{ font-size: 13px; color: #888; margin-top: 4px; }}
        .summary-row {{ display: flex; gap: 8px; margin-bottom: 14px; }}
        .summary-card {{ flex:1; background:#fff; border-radius:14px; padding:10px 8px;
            text-align:center; box-shadow: 0 1px 6px rgba(0,0,0,0.05); font-size:12px; }}
        .summary-card .sval {{ font-size:16px; font-weight:700; }}
        .summary-card .slbl {{ font-size:10px; color:#888; margin-top:2px; }}
        .wow {{ font-size:11px; border-radius:8px; padding:1px 6px; }}
        .wow.up {{ background:#dcfce7; color:#16a34a; }}
        .wow.down {{ background:#fef2f2; color:#dc2626; }}
        .card {{ background:#fff; border-radius:16px; padding:16px; margin-bottom:12px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06); }}
        .card.green {{ border-left: 4px solid #4ade80; }}
        .card.blue {{ border-left: 4px solid #60a5fa; }}
        .card.purple {{ border-left: 4px solid #a78bfa; }}
        .card.red {{ border-left: 4px solid #f87171; }}
        .card-header {{ font-size:15px; font-weight:600; margin-bottom:12px; color:#374151; }}
        .card-body {{ display:grid; gap:8px; }}
        .card-body.cols4 {{ grid-template-columns: 1fr 1fr 1fr 1fr; }}
        .card-body.cols3 {{ grid-template-columns: 1fr 1fr 1fr; }}
        .card-body.cols2 {{ grid-template-columns: 1fr 1fr; }}
        .metric {{ text-align:center; padding:4px 2px; }}
        .metric .value {{ display:block; font-size:24px; font-weight:700; color:#1f2937; line-height:1.2; }}
        .metric .label {{ font-size:11px; color:#9ca3af; margin-top:2px; }}
        .card-stats {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:8px; padding-top:8px;
            border-top:1px solid #f3f4f6; font-size:11px; color:#6b7280; }}
        .card-footer {{ margin-top:10px; padding-top:10px; border-top:1px solid #f3f4f6;
            font-size:12px; color:#6b7280; }}
        .note {{ font-size:13px; color:#6b7280; line-height:1.5; }}
        .note.small {{ font-size:11px; color:#9ca3af; }}
        .mini-table {{ width:100%; border-collapse:collapse; font-size:12px; }}
        .mini-table td {{ padding:4px 0; border-bottom:1px solid #f9fafb; }}
        .mini-table td.right {{ text-align:right; color:#6b7280; }}
        .mini-table tr:last-child td {{ border-bottom:none; }}
        .chart-bars {{ display:flex; align-items:flex-end; gap:4px; height:110px; padding:4px 0; }}
        .bar-col {{ flex:1; display:flex; flex-direction:column; align-items:center; height:100%; justify-content:flex-end; }}
        .bar {{ width:100%; max-width:38px; background:linear-gradient(180deg,#60a5fa,#3b82f6);
            border-radius:4px 4px 0 0; min-height:3px; }}
        .bar-label {{ font-size:9px; color:#9ca3af; margin-top:3px; white-space:nowrap; }}
        .diag-item {{ padding:8px 0; border-bottom:1px dashed #e5e7eb; }}
        .diag-item:last-child {{ border-bottom:none; }}
        .diag-title {{ font-size:13px; font-weight:600; }}
        .diag-detail {{ font-size:12px; color:#6b7280; margin:4px 0; line-height:1.5; }}
        .diag-action {{ font-size:11px; color:#2563eb; background:#eff6ff; padding:4px 8px; border-radius:6px; line-height:1.5; }}
        .seo-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:6px; margin-top:10px; }}
        .seo-item {{ font-size:12px; padding:4px 8px; border-radius:6px; }}
        .seo-item.pass {{ background:#f0fdf4; color:#16a34a; }}
        .seo-item.fail {{ background:#fef2f2; color:#dc2626; }}
        .score-circle {{ width:60px; height:60px; border-radius:50%; display:flex;
            align-items:center; justify-content:center; color:#fff; font-size:24px; font-weight:700;
            margin:8px auto; }}
        .link-btn {{ display:inline-block; padding:8px 16px; background:#667eea; color:#fff;
            border-radius:8px; text-decoration:none; font-size:13px; }}
        .footer {{ text-align:center; padding:20px 0; font-size:11px; color:#bbb; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🛠️ MintShovels 数据管家 v3</h1>
        <div class="time">更新时间: {now}</div>
    </div>
    {cards}
    <div class="footer">MintShovels Data Agent v3 · 自动生成于 {now}</div>
</body>
</html>"""
    
    return html


def _calc_seo_score(cf: dict, ga4: dict, gsc: dict) -> tuple:
    """计算 SEO 健康评分 (0-100)"""
    items = []
    score = 50  # 基础分
    
    # 有搜索展示
    has_impressions = gsc.get("total_impressions", 0) > 0
    items.append({"label": "Google 已收录", "pass": has_impressions})
    if has_impressions: score += 10
    
    # CTR
    ctr = gsc.get("avg_ctr", 0) or 0
    ctr_ok = ctr >= 2
    items.append({"label": f"搜索CTR {ctr:.1f}%", "pass": ctr_ok})
    if ctr_ok: score += 10
    
    # 跳出率
    br = ga4.get("today_bounce", 0) or ga4.get("totals", {}).get("bounceRate", 0)
    br_ok = isinstance(br, (int, float)) and br < 70
    items.append({"label": f"跳出率 {br:.0f}%", "pass": br_ok})
    if br_ok: score += 10
    
    # 停留时长
    dur = ga4.get("today_duration", 0) or ga4.get("totals", {}).get("avgDuration", 0)
    dur_ok = isinstance(dur, (int, float)) and dur > 30
    items.append({"label": f"停留时长 {dur:.0f}s", "pass": dur_ok})
    if dur_ok: score += 10
    
    # 移动端友好
    mobile_ok = ga4.get("device_breakdown", {}).get("mobile", 0) > 0
    items.append({"label": "有移动端访客", "pass": mobile_ok})
    if mobile_ok: score += 5
    
    # 缓存
    cached_ok = cf.get("cached_pct", 0) > 50
    items.append({"label": f"缓存率 {cf.get('cached_pct',0)}%", "pass": cached_ok})
    if cached_ok: score += 5
    
    return min(score, 100), items


# ═══════════════════════════════════════════
# 终端报告
# ═══════════════════════════════════════════

def print_terminal_report(data: dict = None, config: dict = None):
    if config is None: config = load_config()
    if data is None:
        data = fetch_all(config)
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cf, ga4, gsc, bing, diags = data["cf"], data["ga4"], data["gsc"], data["bing"], data["diagnostics"]
    
    print(f"\n{'='*60}")
    print(f"  🛠️  MintShovels 数据管家 v3 — {now}")
    print(f"{'='*60}")
    
    # Cloudflare
    if cf.get("status") == "ok":
        trend = "↗" if cf.get("trend")=="up" else "↘" if cf.get("trend")=="down" else "→"
        print(f"\n🌐 Cloudflare 近7天 {trend}")
        print(f"   UV: {cf['uv']:,}  |  请求: {cf['requests']:,}  |  浏览: {cf['pageviews']:,}  |  带宽: {cf['bandwidth_mb']}MB")
        print(f"   缓存: {cf['cached_pct']}%  |  SSL: {cf.get('ssl_pct','-')}%  |  日均: {cf.get('avg_daily_uv','-')} 访客")
        print(f"   今日: {cf['today_uv']:,} 访客 · {cf['today_pageviews']:,} 浏览 · {cf['today_mb']}MB")
    else:
        print(f"\n🌐 Cloudflare: ⚠️ {cf.get('status')}")
    
    # GA4
    if ga4.get("status") == "ok" and ga4.get("daily"):
        l = ga4["daily"][-1]; t = ga4.get("totals", {})
        print(f"\n📈 GA4 今日 ({l['date']})")
        print(f"   用户: {l['activeUsers']}  |  会话: {l['sessions']}  |  浏览: {l['pageViews']}  |  跳出率: {l['bounceRate']}%  |  均时长: {l['avgDuration']}s")
        print(f"   7天: {t.get('activeUsers',0):,} 用户 · {t.get('pageViews',0):,} 浏览 · {t.get('sessions',0):,} 会话")
        if ga4.get("top_sources"):
            srcs = ", ".join(f"{s['source']}({s['users']})" for s in ga4["top_sources"][:3])
            print(f"   来源: {srcs}")
    else:
        print(f"\n📈 GA4: ⚠️ {ga4.get('status')}")
    
    # GSC
    if gsc.get("status") == "ok":
        print(f"\n🔍 GSC 近7天")
        print(f"   点击: {gsc['total_clicks']:,}  |  展示: {gsc['total_impressions']:,}  |  CTR: {gsc.get('avg_ctr',0):.1f}%")
        if gsc.get("top_queries"):
            print(f"   🔑 热门搜索:")
            for q in gsc["top_queries"][:5]:
                print(f"      \"{q['query']}\" → {q['clicks']}点击 / {q['impressions']}展示")
    else:
        st = gsc.get("status","")
        print(f"\n🔍 GSC: {'🔒 网络限制' if st=='network_ssl' else f'⚠️ {st}'}")
    
    # Bing
    if bing.get("status") == "ok":
        if bing.get("queries"):
            print(f"\n🔎 Bing 搜索")
            print(f"   点击: {bing['total_clicks']:,}  |  展示: {bing['total_impressions']:,}")
            for q in bing["queries"][:3]:
                print(f"   \"{q['query']}\" → {q['clicks']}点击")
        else:
            print(f"\n🔎 Bing 搜索: ✅ 已连接 (暂无数据，新站正常)")
    elif bing.get("status") != "not_configured":
        print(f"\n🔎 Bing 搜索: ⚠️ {bing.get('status')}")
    
    # 诊断
    if diags:
        print(f"\n🩺 系统诊断 ({len(diags)}项)")
        for d in diags:
            print(f"   {d['severity']} {d['title']}")
            print(f"      {d['detail']}")
            print(f"   🔧 {d['action']}")
    
    print(f"\n{'='*60}\n")


# ═══════════════════════════════════════════
# 邮件发送 (SMTP)
# ═══════════════════════════════════════════

def send_email_report(data: dict, config: dict):
    """SMTP 发送 HTML 邮件"""
    to_email = config["notifications"].get("email_to", "")
    if not to_email:
        print("❌ 未配置收件邮箱")
        return False
    
    subject = f"📊 MintShovels 数据日报 - {datetime.now().strftime('%m/%d %H:%M')}"
    html = generate_html_dashboard(data, config)
    
    msg = MIMEMultipart("alternative")
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["From"] = f"MintShovels Agent <{to_email}>"
    msg.attach(MIMEText(f"MintShovels 数据报告\n{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n请在支持 HTML 的客户端查看。", "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    
    # 方式1: SMTP (推荐)
    smtp_config = config.get("notifications", {}).get("smtp", {})
    if smtp_config.get("host"):
        try:
            server = smtplib.SMTP(smtp_config["host"], smtp_config.get("port", 587), timeout=15)
            server.starttls()
            server.login(smtp_config["user"], smtp_config["password"])
            server.sendmail(smtp_config["user"], to_email, msg.as_string())
            server.quit()
            print(f"✅ SMTP 邮件已发送到 {to_email}")
            return True
        except Exception as e:
            print(f"❌ SMTP 失败: {e}")
    
    # 方式2: sendmail (macOS 备用)
    try:
        p = subprocess.Popen(["/usr/sbin/sendmail", "-t", "-oi"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate(msg.as_bytes())
        if p.returncode == 0:
            print(f"✅ sendmail 已发送到 {to_email}")
            return True
        else:
            print(f"❌ sendmail 失败: {stderr.decode()}")
            return False
    except Exception as e:
        print(f"❌ 邮件异常: {e}")
        return False


# ═══════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="MintShovels 数据管家 v3")
    parser.add_argument("--email", action="store_true")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--now", action="store_true", help="立即执行 + 发邮件")
    args = parser.parse_args()
    
    config = load_config()
    
    # 抓取数据
    data = fetch_all(config)
    
    # 默认: 终端显示
    if not args.email and not args.html and not args.all and not args.now:
        print_terminal_report(data, config)
        return
    
    if args.html or args.all or args.now:
        print("🔄 生成 HTML 看板...")
        html = generate_html_dashboard(data, config)
        with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✅ 看板: {OUTPUT_HTML}")
        print(f"   浏览器打开: file://{OUTPUT_HTML}")
    
    if args.email or args.all or args.now:
        send_email_report(data, config)
    
    if args.all:
        print_terminal_report(data, config)


if __name__ == "__main__":
    main()
