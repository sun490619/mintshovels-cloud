#!/usr/bin/env python3
"""
MintShovels 全自动数据管家
============================
功能：
  1. 每日简报：抓取 GA4 + GSC + Bing + Cloudflare 核心数据
  2. 每周深度报告 + 优化建议
  3. 异常报警（流量骤变、404/500 激增、转化率为零等）

使用方式：
  python3 mintshovels_monitor.py --mode daily      # 每日简报
  python3 mintshovels_monitor.py --mode weekly     # 每周深度报告
  python3 mintshovels_monitor.py --mode alert      # 异常检查（可配合 cron）

依赖：
  pip3 install google-analytics-data google-api-python-client requests

配置：
  复制 config.example.json 为 config.json 并填入你的凭据
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

# ============================================================
# 配置加载
# ============================================================

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "mintshovels_config.json")

DEFAULT_CONFIG = {
    "site_url": "https://mintshovels.com",
    "site_name": "MintShovels",
    # Google Analytics 4
    "ga4": {
        "property_id": "properties/XXXXXXXXXX",  # 格式: properties/123456789
        "measurement_id": "G-XXXXXXXXXX",         # 用于前端追踪
        "credentials_file": "ga4_service_account.json"  # Google Cloud 服务账号 JSON
    },
    # Google Search Console
    "gsc": {
        "site_url": "sc-domain:mintshovels.com",  # 域名级属性
        "credentials_file": "ga4_service_account.json"  # 可复用 GA4 的服务账号
    },
    # Bing Webmaster Tools
    "bing": {
        "api_key": "YOUR_BING_API_KEY",
        "site_url": "https://mintshovels.com"
    },
    # Microsoft Clarity
    "clarity": {
        "project_id": "XXXXXXXXXX"
    },
    # Cloudflare (GraphQL Analytics API)
    "cloudflare": {
        "api_token": "YOUR_CF_API_TOKEN",
        "zone_id": "YOUR_CF_ZONE_ID",
        "account_id": "YOUR_CF_ACCOUNT_ID"
    },
    # 报警阈值
    "alerts": {
        "traffic_drop_pct": 50,          # 流量相比昨日下降超过 50% 报警
        "traffic_spike_pct": 300,        # 流量暴增 300% 报警
        "error_rate_threshold": 0.05,    # 错误率超过 5% 报警
        "zero_conversion": True,         # 有流量但转化率为 0 报警
        "check_interval_hours": 6
    },
    # 通知方式 (可选: slack, email, telegram)
    "notifications": {
        "slack_webhook": "",
        "email_to": "",
        "telegram_bot_token": "",
        "telegram_chat_id": ""
    }
}


CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve_path(path: str) -> str:
    """如果路径是相对路径，则相对于脚本所在目录解析"""
    if not os.path.isabs(path):
        return os.path.join(CONFIG_DIR, path)
    return path


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        print(f"[!] 配置文件不存在，创建默认配置: {CONFIG_PATH}")
        with open(CONFIG_PATH, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        print("[!] 请编辑配置文件填入真实凭据后重新运行")
        sys.exit(1)
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
    # 将凭据文件路径转为绝对路径
    for section in ["ga4", "gsc"]:
        if "credentials_file" in config.get(section, {}):
            config[section]["credentials_file"] = _resolve_path(config[section]["credentials_file"])
    return config


# ============================================================
# 数据抓取
# ============================================================

def fetch_ga4_data(config: dict, days: int = 1) -> dict:
    """通过 GA4 Data API 抓取流量数据"""
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange, Dimension, Metric, RunReportRequest
        )
    except ImportError:
        return {"error": "请先安装: pip3 install google-analytics-data"}

    credentials_file = config["ga4"]["credentials_file"]
    if not os.path.exists(credentials_file):
        return {"error": f"服务账号文件不存在: {credentials_file}"}

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_file
    client = BetaAnalyticsDataClient()
    property_id = config["ga4"]["property_id"]
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    results = {}

    # 1. 总览：活跃用户、新用户、浏览量、平均时长
    request = RunReportRequest(
        property=property_id,
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="newUsers"),
            Metric(name="screenPageViews"),
            Metric(name="averageSessionDuration"),
            Metric(name="bounceRate"),
        ],
    )
    response = client.run_report(request)
    if response.rows:
        row = response.rows[0]
        results["active_users"] = int(row.metric_values[0].value)
        results["new_users"] = int(row.metric_values[1].value)
        results["page_views"] = int(row.metric_values[2].value)
        results["avg_session_sec"] = round(float(row.metric_values[3].value), 1)
        results["bounce_rate"] = round(float(row.metric_values[4].value) * 100, 1)

    # 2. 热门页面 Top 10
    request = RunReportRequest(
        property=property_id,
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name="pagePath")],
        metrics=[Metric(name="screenPageViews")],
        limit=10,
        order_bys=[{"metric": {"metric_name": "screenPageViews"}, "desc": True}],
    )
    response = client.run_report(request)
    results["top_pages"] = [
        {"path": row.dimension_values[0].value, "views": int(row.metric_values[0].value)}
        for row in (response.rows or [])
    ]

    # 3. 流量来源
    request = RunReportRequest(
        property=property_id,
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name="sessionSource")],
        metrics=[Metric(name="activeUsers")],
        limit=10,
        order_bys=[{"metric": {"metric_name": "activeUsers"}, "desc": True}],
    )
    response = client.run_report(request)
    results["top_sources"] = [
        {"source": row.dimension_values[0].value, "users": int(row.metric_values[0].value)}
        for row in (response.rows or [])
    ]

    return results


def fetch_gsc_data(config: dict, days: int = 1) -> dict:
    """通过 GSC API 抓取搜索关键词数据"""
    try:
        from googleapiclient.discovery import build
        from google.oauth2 import service_account
    except ImportError:
        return {"error": "请先安装: pip3 install google-api-python-client"}

    credentials_file = config["gsc"]["credentials_file"]
    if not os.path.exists(credentials_file):
        return {"error": f"服务账号文件不存在: {credentials_file}"}

    credentials = service_account.Credentials.from_service_account_file(
        credentials_file, scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
    )
    service = build("webmasters", "v3", credentials=credentials)
    site_url = config["gsc"]["site_url"]
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    results = {}

    # 搜索查询 Top 20
    try:
        response = service.searchanalytics().query(
            siteUrl=site_url,
            body={
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": ["query"],
                "rowLimit": 20,
            },
        ).execute()
        results["top_queries"] = [
            {"query": row["keys"][0], "clicks": row.get("clicks", 0), "impressions": row.get("impressions", 0)}
            for row in (response.get("rows", []))
        ]
    except Exception as e:
        results["top_queries"] = []
        results["gsc_error"] = str(e)

    # 汇总统计
    try:
        response = service.searchanalytics().query(
            siteUrl=site_url,
            body={
                "startDate": start_date,
                "endDate": end_date,
                "rowLimit": 1,
            },
        ).execute()
        if response.get("rows"):
            row = response["rows"][0]
            results["total_clicks"] = row.get("clicks", 0)
            results["total_impressions"] = row.get("impressions", 0)
            results["avg_ctr"] = round(row.get("ctr", 0) * 100, 2)
            results["avg_position"] = round(row.get("position", 0), 1)
    except Exception:
        pass

    return results


def fetch_bing_data(config: dict) -> dict:
    """通过 Bing Webmaster API 抓取搜索数据"""
    api_key = config["bing"]["api_key"]
    site_url = config["bing"]["site_url"]
    if api_key == "YOUR_BING_API_KEY":
        return {"error": "Bing API Key 未配置"}

    results = {}
    try:
        # Bing 搜索关键词
        req = urllib.request.Request(
            f"https://ssl.bing.com/webmaster/api.svc/json/GetQueryStats?"
            f"q={urllib.parse.quote(site_url)}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            results["queries"] = [
                {"query": q.get("Query", ""), "clicks": q.get("Clicks", 0)}
                for q in (data.get("d", []) or [])[:10]
            ]
    except Exception as e:
        results["error"] = str(e)

    return results


def fetch_cloudflare_analytics(config: dict, hours: int = 24) -> dict:
    """通过 Cloudflare GraphQL API 抓取站点统计"""
    token = config["cloudflare"]["api_token"]
    zone_id = config["cloudflare"]["zone_id"]
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    query = f"""
    {{
      viewer {{
        zones(filter: {{ zoneTag: "{zone_id}" }}) {{
          httpRequests1hGroups(
            limit: 100
            filter: {{
              datetime_geq: "{start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}",
              datetime_lt: "{end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            }}
          ) {{
            dimensions {{ datetime }}
            sum {{
              requests
              bytes
              threats
              cachedRequests
              encryptedRequests
            }}
            uniq {{
              uniques  # 独立访客
            }}
          }}
        }}
      }}
    }}
    """

    try:
        req = urllib.request.Request(
            "https://api.cloudflare.com/client/v4/graphql",
            data=json.dumps({"query": query}).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            if data.get("errors"):
                return {"error": str(data["errors"])}
            groups = (
                data.get("data", {})
                .get("viewer", {})
                .get("zones", [{}])[0]
                .get("httpRequests1hGroups", [])
            )
            total_requests = sum(g["sum"]["requests"] for g in groups)
            total_bytes = sum(g["sum"]["bytes"] for g in groups)
            total_threats = sum(g["sum"]["threats"] for g in groups)
            total_cached = sum(g["sum"]["cachedRequests"] for g in groups)
            total_unique = sum(g["uniq"]["uniques"] for g in groups)
            return {
                "requests": total_requests,
                "unique_visitors": total_unique,
                "bandwidth_mb": round(total_bytes / (1024 * 1024), 2),
                "threats_blocked": total_threats,
                "cached_pct": round(total_cached / max(total_requests, 1) * 100, 1),
            }
    except Exception as e:
        return {"error": str(e)}


def fetch_error_rates(config: dict) -> dict:
    """检查 Cloudflare 中 404/500 等错误率"""
    token = config["cloudflare"]["api_token"]
    zone_id = config["cloudflare"]["zone_id"]
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=24)

    query = f"""
    {{
      viewer {{
        zones(filter: {{ zoneTag: "{zone_id}" }}) {{
          httpRequests1hGroups(
            limit: 100
            filter: {{
              datetime_geq: "{start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}",
              datetime_lt: "{end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}",
              clientRequestHTTPHost: "mintshovels.com"
            }}
          ) {{
            dimensions {{ clientRequestPath, edgeResponseStatus }}
            sum {{ requests }}
          }}
        }}
      }}
    }}
    """

    try:
        req = urllib.request.Request(
            "https://api.cloudflare.com/client/v4/graphql",
            data=json.dumps({"query": query}).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            if data.get("errors"):
                return {"error": str(data["errors"])}
            groups = (
                data.get("data", {})
                .get("viewer", {})
                .get("zones", [{}])[0]
                .get("httpRequests1hGroups", [])
            )

            total = sum(g["sum"]["requests"] for g in groups)
            errors_404 = sum(
                g["sum"]["requests"] for g in groups
                if str(g["dimensions"].get("edgeResponseStatus", "")) == "404"
            )
            errors_500 = sum(
                g["sum"]["requests"] for g in groups
                if str(g["dimensions"].get("edgeResponseStatus", "")).startswith("5")
            )

            return {
                "total_requests": total,
                "404_count": errors_404,
                "5xx_count": errors_500,
                "error_rate": round((errors_404 + errors_500) / max(total, 1) * 100, 2),
                "top_404_pages": [
                    {
                        "path": g["dimensions"].get("clientRequestPath", ""),
                        "count": g["sum"]["requests"],
                    }
                    for g in sorted(groups, key=lambda x: x["sum"]["requests"], reverse=True)
                    if str(g["dimensions"].get("edgeResponseStatus", "")) == "404"
                ][:5],
            }
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# 报告生成
# ============================================================

def generate_daily_report(config: dict) -> str:
    """生成每日大白话简报"""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y年%m月%d日")

    lines = []
    lines.append(f"📊 MintShovels 数据日报 — {date_str}")
    lines.append("=" * 50)

    # ---- Cloudflare 数据 ----
    cf = fetch_cloudflare_analytics(config, hours=24)
    if "error" not in cf:
        lines.append("")
        lines.append("🌐 Cloudflare 站点统计 (近24小时)")
        lines.append(f"   • 独立访客: {cf['unique_visitors']} 人")
        lines.append(f"   • 总请求数: {cf['requests']}")
        lines.append(f"   • 带宽消耗: {cf['bandwidth_mb']} MB")
        lines.append(f"   • 缓存命中率: {cf['cached_pct']}%")
        lines.append(f"   • 威胁拦截: {cf['threats_blocked']} 次")

    # ---- GA4 数据 ----
    ga4 = fetch_ga4_data(config, days=1)
    if "error" not in ga4:
        lines.append("")
        lines.append("📈 Google Analytics 4 (今日)")
        lines.append(f"   • 活跃用户: {ga4.get('active_users', '?')}")
        lines.append(f"   • 新用户: {ga4.get('new_users', '?')}")
        lines.append(f"   • 页面浏览量: {ga4.get('page_views', '?')}")
        lines.append(f"   • 平均停留: {ga4.get('avg_session_sec', '?')} 秒")
        lines.append(f"   • 跳出率: {ga4.get('bounce_rate', '?')}%")

        if ga4.get("top_pages"):
            lines.append("")
            lines.append("   🔥 热门页面 Top 5:")
            for p in ga4["top_pages"][:5]:
                lines.append(f"      {p['path']} — {p['views']} 次浏览")

    # ---- GSC 数据 ----
    gsc = fetch_gsc_data(config, days=1)
    if "error" not in gsc and gsc.get("top_queries"):
        lines.append("")
        lines.append("🔍 Google 搜索 (今日)")
        lines.append(f"   • 总点击: {gsc.get('total_clicks', '?')}")
        lines.append(f"   • 总展示: {gsc.get('total_impressions', '?')}")
        lines.append(f"   • 平均排名: {gsc.get('avg_position', '?')}")

        lines.append("")
        lines.append("   🔑 带来点击的关键词:")
        clicked = [q for q in gsc["top_queries"] if q["clicks"] > 0][:10]
        if clicked:
            for q in clicked:
                lines.append(f"      \"{q['query']}\" — {q['clicks']} 次点击")
        else:
            lines.append("      (暂无点击数据，GSC 数据有 1-2 天延迟)")

    # ---- Bing 数据 ----
    bing = fetch_bing_data(config)
    if "error" not in bing and bing.get("queries"):
        lines.append("")
        lines.append("🔎 Bing 搜索")
        for q in bing["queries"][:5]:
            lines.append(f"   • \"{q['query']}\" — {q['clicks']} 次点击")

    # ---- 优化建议 ----
    lines.append("")
    lines.append("💡 今日优化建议")
    suggestions = _generate_suggestions(ga4, gsc, cf)
    if suggestions:
        for i, s in enumerate(suggestions, 1):
            lines.append(f"   {i}. {s}")
    else:
        lines.append("   (数据积累中，建议将在有足够数据后生成)")

    lines.append("")
    lines.append("— MintShovels 数据管家自动生成")
    return "\n".join(lines)


def generate_weekly_report(config: dict) -> str:
    """生成每周深度报告"""
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y年%m月%d日")

    lines = []
    lines.append(f"📊 MintShovels 数据周报 — {date_str}")
    lines.append("=" * 50)

    # GA4 周数据
    ga4 = fetch_ga4_data(config, days=7)
    if "error" not in ga4:
        lines.append("")
        lines.append("📈 本周 GA4 数据概览")
        lines.append(f"   • 活跃用户: {ga4.get('active_users', '?')}")
        lines.append(f"   • 新用户: {ga4.get('new_users', '?')}")
        lines.append(f"   • 页面浏览量: {ga4.get('page_views', '?')}")
        lines.append(f"   • 跳出率: {ga4.get('bounce_rate', '?')}%")

        if ga4.get("top_pages"):
            lines.append("")
            lines.append("   🏆 本周热门页面 Top 10:")
            for p in ga4["top_pages"][:10]:
                lines.append(f"      {p['views']:>5} → {p['path']}")

        if ga4.get("top_sources"):
            lines.append("")
            lines.append("   🌍 流量来源 Top 5:")
            for s in ga4["top_sources"][:5]:
                lines.append(f"      {s['source']}: {s['users']} 用户")

    # GSC 周数据
    gsc = fetch_gsc_data(config, days=7)
    if "error" not in gsc:
        lines.append("")
        lines.append("🔍 本周 Google 搜索")
        lines.append(f"   • 总点击: {gsc.get('total_clicks', '?')}")
        lines.append(f"   • 总展示: {gsc.get('total_impressions', '?')}")
        lines.append(f"   • 平均排名: {gsc.get('avg_position', '?')}")
        lines.append(f"   • 平均点击率: {gsc.get('avg_ctr', '?')}%")

        if gsc.get("top_queries"):
            lines.append("")
            lines.append("   🔑 热门搜索词 Top 20:")
            for i, q in enumerate(gsc["top_queries"][:20], 1):
                lines.append(f"      {i:2}. \"{q['query']}\" — 点击:{q['clicks']} 展示:{q['impressions']}")

    # Cloudflare 周数据
    cf = fetch_cloudflare_analytics(config, hours=168)
    if "error" not in cf:
        lines.append("")
        lines.append("🌐 本周 Cloudflare 统计")
        lines.append(f"   • 独立访客: {cf['unique_visitors']}")
        lines.append(f"   • 总请求: {cf['requests']}")
        lines.append(f"   • 缓存率: {cf['cached_pct']}%")

    # 优化建议
    lines.append("")
    lines.append("💡 本周网站优化建议")
    suggestions = _generate_suggestions(ga4, gsc, cf, weekly=True)
    if suggestions:
        for i, s in enumerate(suggestions, 1):
            lines.append(f"   {i}. {s}")
    else:
        lines.append("   (数据积累中)")

    lines.append("")
    lines.append("— MintShovels 数据管家自动生成")
    return "\n".join(lines)


def _generate_suggestions(ga4: dict, gsc: dict, cf: dict, weekly: bool = False) -> list:
    """基于数据生成大白话优化建议"""
    suggestions = []

    # 1. 跳出率过高 → 改进页面体验
    bounce = ga4.get("bounce_rate", 0)
    if isinstance(bounce, (int, float)) and bounce > 70:
        suggestions.append(
            f"跳出率高达 {bounce}%，说明访客打开页面就跑了。"
            "建议检查首页加载速度、首屏内容是否吸引人，或增加搜索框让用户快速找到需要的工具。"
        )

    # 2. 高展示低点击 → 优化标题和描述
    if gsc.get("avg_ctr") and gsc["avg_ctr"] < 2:
        suggestions.append(
            f"搜索展示量不错但点击率只有 {gsc['avg_ctr']}%，"
            "建议优化页面标题(title)和描述(meta description)，让它们在搜索结果中更吸引点击。"
        )

    # 3. 缓存率低 → 检查缓存策略
    if cf.get("cached_pct") is not None and cf["cached_pct"] < 50:
        suggestions.append(
            f"Cloudflare 缓存命中率仅 {cf['cached_pct']}%，"
            "建议检查和优化 _headers 文件中的缓存规则，对静态资源设置更长的缓存时间。"
        )

    # 4. 平均排名靠后
    if gsc.get("avg_position") and gsc["avg_position"] > 20:
        suggestions.append(
            f"Google 搜索平均排名第 {gsc['avg_position']} 名，"
            "建议挑选搜索量较大但排名在 8-15 的关键词重点优化对应页面内容。"
        )

    # 5. 新用户占比过高但回访低
    new_users = ga4.get("new_users", 0)
    active_users = ga4.get("active_users", 0)
    if active_users > 100 and new_users > 0:
        new_ratio = new_users / max(active_users, 1) * 100
        if new_ratio > 90:
            suggestions.append(
                f"新用户占比 {new_ratio:.0f}%，但回访用户很少。"
                "建议增加收藏引导或让工具有保存/分享功能，提高用户回头率。"
            )

    # 6. 平均停留时间过短
    avg_sec = ga4.get("avg_session_sec", 0)
    if isinstance(avg_sec, (int, float)) and avg_sec < 30 and active_users > 10:
        suggestions.append(
            f"用户平均只停留 {avg_sec} 秒，说明内容不够粘人。"
            "建议在工具页面增加使用示例、教程或相关工具推荐，延长停留时间。"
        )

    return suggestions[:3]  # 最多 3 条


# ============================================================
# 异常报警
# ============================================================

def check_alerts(config: dict) -> list:
    """检查异常指标，返回报警列表"""
    alerts_list = []
    thresholds = config.get("alerts", {})

    cf = fetch_cloudflare_analytics(config, hours=24)
    if "error" in cf:
        return alerts_list

    # 1. 检查错误率
    errors = fetch_error_rates(config)
    if "error" not in errors:
        error_rate = errors.get("error_rate", 0)
        if error_rate > thresholds.get("error_rate_threshold", 0.05) * 100:
            alerts_list.append({
                "level": "🔴 严重",
                "title": f"错误率飙升到 {error_rate}%",
                "detail": (
                    f"近 24 小时请求 {errors['total_requests']} 次，"
                    f"其中 404 错误 {errors['404_count']} 次，5xx 错误 {errors['5xx_count']} 次。\n"
                    f"最常见的 404 页面: {errors.get('top_404_pages', [])}"
                ),
                "fix": (
                    "1. 检查 Railway 后端是否正常运行\n"
                    "2. 检查 sitemap.xml 中是否有失效链接\n"
                    "3. 设置 301 重定向修复高频 404 页面"
                ),
            })

    # 2. 流量异常
    unique_now = cf.get("unique_visitors", 0)
    cf_prev = fetch_cloudflare_analytics(config, hours=48)
    # 估算昨日同期流量 (简单用比例算)
    if "error" not in cf_prev and unique_now > 0:
        prev_unique = cf_prev.get("unique_visitors", 0) - unique_now
        if prev_unique > 10:
            change_pct = abs(unique_now - prev_unique / 2) / max(prev_unique / 2, 1) * 100
            if unique_now < prev_unique / 2 * (1 - thresholds.get("traffic_drop_pct", 50) / 100):
                alerts_list.append({
                    "level": "🟡 警告",
                    "title": f"流量大幅下降",
                    "detail": (
                        f"今日独立访客 {unique_now}，较昨日同期 ({prev_unique//2}) 下降明显。"
                    ),
                    "fix": (
                        "1. 检查网站是否可正常访问\n"
                        "2. 查看 GSC 是否有索引/抓取问题\n"
                        "3. 确认搜索引擎排名是否有剧烈变动"
                    ),
                })

    return alerts_list


def send_alert(config: dict, alert: dict):
    """发送报警通知"""
    notif = config.get("notifications", {})

    message = (
        f"{alert['level']} | {alert['title']}\n\n"
        f"{alert['detail']}\n\n"
        f"🔧 建议修复方案:\n{alert['fix']}"
    )

    # Slack
    if notif.get("slack_webhook"):
        try:
            req = urllib.request.Request(
                notif["slack_webhook"],
                data=json.dumps({"text": message}).encode(),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
            print("✅ Slack 通知已发送")
        except Exception as e:
            print(f"⚠️ Slack 通知失败: {e}")

    # Telegram
    if notif.get("telegram_bot_token") and notif.get("telegram_chat_id"):
        try:
            url = (
                f"https://api.telegram.org/bot{notif['telegram_bot_token']}"
                f"/sendMessage?chat_id={notif['telegram_chat_id']}"
                f"&text={urllib.parse.quote(message)}"
            )
            urllib.request.urlopen(url, timeout=10)
            print("✅ Telegram 通知已发送")
        except Exception as e:
            print(f"⚠️ Telegram 通知失败: {e}")

    # 控制台输出
    print(f"\n{'='*50}")
    print(message)
    print(f"{'='*50}\n")


# ============================================================
# GSC + GA4 关联检查
# ============================================================

def check_gsc_ga4_link(config: dict):
    """检查 GSC 和 GA4 是否已关联"""
    print("\n📋 GSC↔GA4 关联状态检查")
    print("-" * 30)
    print("请在浏览器中手动确认：")
    print("  1. 打开 https://analytics.google.com/")
    print("  2. 进入 mintshovels.com 的 GA4 属性")
    print("  3. 左下角「管理」→「产品关联」→「Search Console 关联」")
    print("  4. 确认 mintshovels.com 已在关联列表中")
    print()
    print("如果未关联：点击「添加关联」→ 选择 GSC 中的 mintshovels.com → 选择对应的数据流 → 保存")
    print("-" * 30)


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="MintShovels 全自动数据管家")
    parser.add_argument(
        "--mode", choices=["daily", "weekly", "alert", "check-link"],
        default="daily", help="运行模式: daily(每日简报) / weekly(周报) / alert(异常检查) / check-link(关联检查)"
    )
    parser.add_argument(
        "--output", "-o", help="输出到文件"
    )
    parser.add_argument(
        "--silent", action="store_true", help="静默模式 (alert 模式无异常时不输出)"
    )
    args = parser.parse_args()

    config = load_config()

    if args.mode == "daily":
        report = generate_daily_report(config)
        print(report)
        if args.output:
            with open(args.output, "w") as f:
                f.write(report)

    elif args.mode == "weekly":
        report = generate_weekly_report(config)
        print(report)
        if args.output:
            with open(args.output, "w") as f:
                f.write(report)

    elif args.mode == "alert":
        alerts = check_alerts(config)
        if alerts:
            for alert in alerts:
                send_alert(config, alert)
        elif not args.silent:
            print("✅ 一切正常，无异常报警")

    elif args.mode == "check-link":
        check_gsc_ga4_link(config)


if __name__ == "__main__":
    main()
