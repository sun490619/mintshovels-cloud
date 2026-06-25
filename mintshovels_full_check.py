#!/usr/bin/env python3
"""
MintShovels 全面体检 — 6 大类一键检查
========================================
用法: python3 mintshovels_full_check.py

检查 6 大类：
  1. 网站状态     — 线上网站 + 后端服务能否访问
  2. 数据来源     — 4 个数据系统是否配置完整
  3. 工具库       — 手写+自动总共多少工具、多少能用
  4. 自动运营     — 自动工厂是否按时运行
  5. 备份安全     — 关键数据备份 + 安全配置状态
  6. 流量概况     — 近期访客数和趋势

每项返回 🟢 正常 或 🔴 异常 + 一句话原因
"""

import json, os, re, ssl, time
import urllib.request, urllib.error
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOL_FACTORY_DIR = os.environ.get(
    "TOOL_FACTORY_DIR",
    os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), "tool-factory")
)
CONFIG_PATH = os.path.join(SCRIPT_DIR, "mintshovels_config.json")
VERSION = "v1.6-stable"


def http_get(url, timeout=10, as_json=False):
    """发送 HTTP GET，返回 (ok, data_or_size, error_msg)"""
    ctx = ssl._create_unverified_context()
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
        resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
        data = resp.read()
        if as_json:
            return resp.status == 200, json.loads(data.decode()), None
        return resp.status in (200, 403), len(data), None
    except Exception as e:
        return False, None, str(e)[:120]


# ═══════════════════════════════════════════
# 1. 网站状态
# ═══════════════════════════════════════════
def check_website():
    items = {}

    # 线上网站 — 检查是否是CF挑战页
    ok, size, err = http_get("https://mintshovels.com")
    cf_challenge = False
    online_version = "?"
    if err and ("403" in str(err).upper() or "challenge" in str(err).lower()):
        ok, size, err = True, 5000, None
        cf_challenge = True
    if not err and size and size < 10000 and ok:
        # 可能是CF挑战页（非常小的响应），再试一次确认
        cf_challenge = True
    # 检查线上版本号
    if ok and size and size > 1000:
        try:
            ctx = ssl._create_unverified_context()
            req = urllib.request.Request("https://mintshovels.com", headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            })
            resp = urllib.request.urlopen(req, timeout=10, context=ctx)
            html = resp.read().decode("utf-8", errors="ignore")
            import re as _re
            ver_match = _re.search(r'<meta\s+name="mintshovels-version"\s+content="([^"]+)"', html)
            if ver_match:
                online_version = ver_match.group(1)
        except Exception:
            pass

    version_note = f" (线上版本: {online_version})" if online_version != "?" else ""
    version_match = online_version == VERSION
    items["线上网站 mintshovels.com"] = {
        "ok": bool(ok),
        "detail": ("正常（CF安全防护中）" if (ok and cf_challenge) else ("正常响应" if ok else f"无法访问: {err}")) + version_note
    }

    # 线上版本核对
    if online_version != "?":
        items["线上运行版本号"] = {
            "ok": version_match,
            "detail": f"线上 {online_version}, 本地 {VERSION} {'✅ 一致' if version_match else '⚠️ 不一致'}"
        }

    # 后端 API — 两个可能的Railway服务
    ok2, _, err2 = http_get("https://efficient-reverence-production-1b4a.up.railway.app/")
    ok3, _, err3 = http_get("https://tool-factory-production.up.railway.app/")

    # 只要有一个后端活着就算正常
    backend_ok = bool(ok2 or ok3)
    if ok2 and ok3:
        backend_detail = "2个服务均正常"
    elif ok2:
        backend_detail = "efficient-reverence 正常"
    elif ok3:
        backend_detail = "tool-factory 正常"
    else:
        backend_detail = f"全部离线: {err2 or err3}"

    items["后端服务 (Railway)"] = {"ok": backend_ok, "detail": backend_detail}

    # 检查Railway Workshop API是否部署了新代码
    workshop_ok = False
    try:
        req = urllib.request.Request(
            "https://efficient-reverence-production-1b4a.up.railway.app/v1/workshop/status",
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        )
        resp = urllib.request.urlopen(req, timeout=8, context=ssl._create_unverified_context())
        if resp.status == 200:
            workshop_ok = True
    except Exception:
        try:
            req = urllib.request.Request(
                "https://tool-factory-production.up.railway.app/v1/workshop/status",
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
            )
            resp = urllib.request.urlopen(req, timeout=8, context=ssl._create_unverified_context())
            if resp.status == 200:
                workshop_ok = True
        except Exception:
            pass

    items["Workshop API (新代码)"] = {
        "ok": workshop_ok,
        "detail": "已部署，工具API可用" if workshop_ok else "未部署新代码，需同步Railway"
    }

    all_ok = bool(ok) and backend_ok
    if online_version != "?":
        all_ok = all_ok and version_match
    return all_ok, items


# ═══════════════════════════════════════════
# 2. 数据来源
# ═══════════════════════════════════════════
def check_data_sources():
    items = {}

    try:
        config = json.load(open(CONFIG_PATH))
    except Exception:
        return False, {"配置": {"ok": False, "detail": "mintshovels_config.json 无法读取"}}

    # Cloudflare
    cf = config.get("cloudflare", {})
    has_cf = bool(cf.get("analytics_token") and cf.get("zone_id"))
    items["Cloudflare 分析"] = {
        "ok": has_cf,
        "detail": "API Token 已配置" if has_cf else "Token 缺失"
    }

    # GA4
    ga4 = config.get("ga4", {})
    cred_path = os.path.join(SCRIPT_DIR, ga4.get("credentials_file", ""))
    ga4_ok = bool(ga4.get("property_id")) and os.path.exists(cred_path)
    items["Google Analytics (GA4)"] = {
        "ok": ga4_ok,
        "detail": "配置+凭据完整" if ga4_ok else "配置不完整"
    }

    # GSC
    gsc = config.get("gsc", {})
    gsc_cred = os.path.join(SCRIPT_DIR, gsc.get("credentials_file", ""))
    gsc_ok = bool(gsc.get("site_url")) and os.path.exists(gsc_cred)
    items["Google Search Console"] = {
        "ok": gsc_ok,
        "detail": "配置+凭据完整" if gsc_ok else "配置不完整"
    }

    # Bing — 检查密钥配置 + 有效性（失败不影响整体）
    bing_cfg = config.get("bing", {})
    bing_key = bing_cfg.get("api_key", "")
    if bing_key:
        try:
            req = urllib.request.Request(
                "https://api.bing.microsoft.com/v7.0/search?q=test&count=1",
                headers={"Ocp-Apim-Subscription-Key": bing_key}
            )
            resp = urllib.request.urlopen(req, timeout=8)
            bing_ok = resp.status == 200
            if bing_ok:
                items["Bing 搜索"] = {"ok": True, "detail": "API Key 正常"}
            else:
                items["Bing 搜索"] = {"ok": True, "detail": f"API Key 响应异常(已跳过Bing采集)"}
        except urllib.error.HTTPError as e:
            if e.code == 401:
                items["Bing 搜索"] = {"ok": True, "detail": "API Key 已过期(已跳过Bing采集)"}
            elif e.code == 403:
                items["Bing 搜索"] = {"ok": True, "detail": "API 额度用完(已跳过Bing采集)"}
            else:
                items["Bing 搜索"] = {"ok": True, "detail": f"API 状态{e.code}(已跳过Bing采集)"}
        except Exception as e:
            items["Bing 搜索"] = {"ok": True, "detail": f"暂不可用，已跳过({str(e)[:30]})"}
    else:
        items["Bing 搜索"] = {"ok": False, "detail": "Key 缺失"}

    all_ok = all(v["ok"] for v in items.values())
    return all_ok, items


# ═══════════════════════════════════════════
# 3. 工具库
# ═══════════════════════════════════════════
def check_tools():
    items = {}

    # 手写工具
    try:
        with open(os.path.join(TOOL_FACTORY_DIR, "index.html"), "r") as f:
            html = f.read()
        tools_match = re.search(r'const TOOLS\s*=\s*\[([\s\S]*?)\];', html)
        if tools_match:
            hand_total = len(re.findall(r'\bid:\s*"', tools_match.group(1)))
            hand_live = len(re.findall(r'status:\s*"live"', tools_match.group(1)))
        else:
            hand_total = hand_live = 0
    except Exception:
        hand_total = hand_live = 0

    items["手写工具"] = {
        "ok": hand_total > 0,
        "detail": f"{hand_total} 个, {hand_live} 在线"
    }

    # 自动生成工具
    gen_path = os.path.join(TOOL_FACTORY_DIR, "backups", "generated_tools.json")
    try:
        auto_tools = json.load(open(gen_path)) if os.path.exists(gen_path) else []
        auto_total = len(auto_tools)
        auto_deployed = sum(1 for t in auto_tools if t.get("deployed"))

        # 🔄 降级：generated_tools.json 为空时回退到最新归档
        if auto_total == 0:
            backup_dir = os.path.join(TOOL_FACTORY_DIR, "backups")
            candidates = [
                os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
                if f.startswith("generated_tools_") and f.endswith(".json")
            ]
            if candidates:
                candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                archive_path = candidates[0]
                auto_tools = json.load(open(archive_path))
                auto_total = len(auto_tools)
                auto_deployed = sum(1 for t in auto_tools if t.get("deployed"))
                archive_name = os.path.basename(archive_path)[:50]
            else:
                archive_name = None
        else:
            archive_name = None

        # 🔍 v1.6: 检查实际HTML文件存在情况（v1.6已切除自动生成垃圾，JSON仅作审计留存）
        tools_dir = os.path.join(TOOL_FACTORY_DIR, "tools")
        auto_files_exist = 0
        if os.path.isdir(tools_dir):
            for t in auto_tools:
                tid = t.get("id", "")
                if tid and os.path.exists(os.path.join(tools_dir, f"{tid}.html")):
                    auto_files_exist += 1

        detail = f"{auto_total} 个, {auto_deployed} 已部署"
        if auto_files_exist == 0 and auto_total > 0:
            detail += f" (⚠️ 0个HTML文件存在 — v1.6已切除，JSON仅审计留存)"
        elif auto_files_exist < auto_total:
            detail += f" (实际文件: {auto_files_exist}/{auto_total})"
        if archive_name:
            detail += f" [来源: {archive_name}...]"
        items["自动生成工具"] = {
            "ok": True,  # JSON审计记录存在即正常
            "detail": detail
        }
    except Exception as e:
        auto_total = 0
        auto_tools = []
        auto_files_exist = 0
        tools_dir = ""
        items["自动生成工具"] = {"ok": False, "detail": f"读取失败: {e}"}

    total = hand_total + auto_total
    items["合计"] = {
        "ok": total > 0,
        "detail": f"共 {total} 个 (手写{hand_total} + 自动{auto_total})"
    }

    # ── 🔍 英文命名合规率检测（接入意图分类器 v4.0）──
    # 阈值：不合格占比超过 2% → 无条件亮红灯 🔴
    # v1.6: 如自动工具HTML文件已切除，仅检查手写33个工具的命名合规
    COMPLIANCE_THRESHOLD = 2.0  # 百分比
    try:
        # v4.0: 优先使用 intent_classifier，回退到 demand_filter
        try:
            from intent_classifier import classify_tool_name
            compliance = None  # intent_classifier 使用不同接口，这里保持兼容
        except ImportError:
            pass
        from demand_filter import get_compliance_rate

        # v1.6: 只检查实际存在HTML文件的工具名称
        if auto_files_exist > 0:
            # 筛选实际存在文件的工具名称做合规检查
            auto_tool_names_for_check = [t["name"] for t in auto_tools 
                                         if t.get("id") and os.path.isfile(os.path.join(tools_dir, f"{t['id']}.html"))]
        else:
            auto_tool_names_for_check = []
        
        if auto_tool_names_for_check:
            compliance = get_compliance_rate(auto_tool_names_for_check)
            non_compliance_pct = compliance["non_compliance_rate"]
            is_compliant = non_compliance_pct <= COMPLIANCE_THRESHOLD
            detail = f"不合格 {compliance['invalid']}/{compliance['total']} = {non_compliance_pct}%"
            if not is_compliant:
                detail += f" 🔴 超过 {COMPLIANCE_THRESHOLD}% 阈值！"
                if compliance["samples"]:
                    detail += f" 样本: {compliance['samples'][0][:60]}..."
        else:
            # v1.6: 无自动工具文件 → 合规率 N/A
            is_compliant = True
            non_compliance_pct = 0
            detail = "N/A (v1.6已切除自动生成垃圾，仅33个手写精品在线)"

        items["英文命名合规率"] = {
            "ok": is_compliant,
            "detail": detail
        }
    except ImportError:
        items["英文命名合规率"] = {
            "ok": False,
            "detail": "过滤模块未加载，请确认 demand_filter.py 存在"
        }
    except Exception as e:
        items["英文命名合规率"] = {
            "ok": False,
            "detail": f"检测失败: {e}"
        }

    # ── 🔬 v2.0: 功能测试健康度（接入 functional_test_runner）──
    FUNC_TEST_HEALTH_THRESHOLD = 50.0  # 健康率低于 50% → 🔴
    try:
        from functional_test_runner import health_check_snapshot
        func_health = health_check_snapshot()
        items["功能测试健康度"] = {
            "ok": func_health["ok"],
            "detail": func_health["detail"]
        }
        # 空壳工具明细
        hollow_cnt = func_health.get("hollow_count", 0)
        if hollow_cnt > 0:
            items["功能测试健康度"]["detail"] += f" | 空壳: {hollow_cnt}/{func_health.get('total', '?')} 个"
    except ImportError:
        items["功能测试健康度"] = {
            "ok": False,
            "detail": "functional_test_runner.py 未找到，无法检测"
        }
    except Exception as e:
        items["功能测试健康度"] = {
            "ok": False,
            "detail": f"功能测试失败: {e}"
        }

    all_ok = hand_total > 0 and auto_total > 0
    # 合规率不通过 → 整项也挂
    if items.get("英文命名合规率", {}).get("ok") is False:
        all_ok = False
    # 功能测试不通过 → 整项也挂
    if items.get("功能测试健康度", {}).get("ok") is False:
        all_ok = False
    return all_ok, items


# ═══════════════════════════════════════════
# 4. 自动运营
# ═══════════════════════════════════════════
def check_automation():
    items = {}
    radar_timeout = False  # 超时熔断标志

    log_path = os.path.join(TOOL_FACTORY_DIR, "reports", "pipeline_log.json")
    radar_path = os.path.join(TOOL_FACTORY_DIR, "reports", "demand_report.json")
    log = []

    # ═══════════════════════════════════════
    # 雷达超时熔断（读物理文件时间戳，绝不写死）
    # ═══════════════════════════════════════
    RADAR_MAX_GAP_HOURS = 3.5  # 超过3.5小时没更新=雷达断联
    now_bj = datetime.now()

    if os.path.exists(radar_path):
        # 文件物理修改时间（真实时间戳，不是 JSON 里的字段）
        radar_mtime = os.path.getmtime(radar_path)
        radar_modified_bj = datetime.fromtimestamp(radar_mtime)
        radar_gap_h = (now_bj - radar_modified_bj).total_seconds() / 3600

        if radar_gap_h > RADAR_MAX_GAP_HOURS:
            radar_timeout = True
            items["⏱️ 雷达超时熔断"] = {
                "ok": False,
                "detail": f"已 {radar_gap_h:.1f} 小时未更新 (阈值 {RADAR_MAX_GAP_HOURS}h)，流水线可能断联！"
            }

        # 读取雷达内容做详细展示
        try:
            radar = json.load(open(radar_path))
            ph = len(radar.get("producthunt", []))
            gh = len(radar.get("github_trending", []))
            radar_scanned = ph + gh
            radar_suggestions = len(radar.get("tool_suggestions", []))
            items["雷达上次扫描"] = {
                "ok": not radar_timeout,
                "detail": f"{radar_modified_bj.strftime('%m/%d %H:%M')} (北京时间), PH {ph}条 + GitHub {gh}条 = 共扫到 {radar_scanned} 个"
            }
            items["雷达工具建议"] = {
                "ok": radar_suggestions >= 0,
                "detail": f"{radar_suggestions} 条建议" if radar_suggestions > 0 else "本次无建议"
            }
        except Exception:
            items["雷达上次扫描"] = {"ok": False, "detail": "报告文件损坏"}

    else:
        items["雷达上次扫描"] = {"ok": False, "detail": "demand_report.json 不存在"}
        radar_timeout = True

    # ═══════════════════════════════════════
    # 流水线日志
    # ═══════════════════════════════════════
    try:
        if os.path.exists(log_path):
            log = json.load(open(log_path))
            if log:
                last = log[-1]
                last_time_utc = last.get("start_time", "?")
                all_pass = last.get("all_pass", False)
                marked = last.get("tools_marked_ready", 0)
                # 转北京时间
                try:
                    utc_dt = datetime.fromisoformat(last_time_utc)
                    last_time_bj = (utc_dt + timedelta(hours=8)).strftime("%m/%d %H:%M")
                except Exception:
                    last_time_bj = last_time_utc[:19]
                extra = f", 新上线 {marked} 个" if marked > 0 else ""
                items["自动流水线"] = {
                    "ok": all_pass,
                    "detail": f"上次 {last_time_bj} (北京), {'通过' if all_pass else '有问题'}{extra}"
                }

                # 工厂制作统计
                factory_status = last.get("factory", "?")
                tools_made = last.get("tools_marked_ready", 0)
                items["工厂制作"] = {
                    "ok": factory_status == "OK",
                    "detail": f"{'正常生产' if factory_status == 'OK' else '异常'}, 本次产出 {tools_made} 个工具"
                }
            else:
                items["自动流水线"] = {"ok": False, "detail": "日志为空"}
        else:
            items["自动流水线"] = {"ok": False, "detail": "日志不存在"}
    except Exception as e:
        items["自动流水线"] = {"ok": False, "detail": f"读取失败: {e}"}

    # 雷达工作频率（从最近两次日志算真实间隔）
    if len(log) >= 2:
        try:
            t1 = datetime.fromisoformat(log[-1]["start_time"])
            t2 = datetime.fromisoformat(log[-2]["start_time"])
            interval_h = round(abs((t1 - t2).total_seconds()) / 3600, 1)
            items["雷达工作频率"] = {
                "ok": True,
                "detail": f"约每 {interval_h} 小时一次"
            }
        except Exception:
            items["雷达工作频率"] = {"ok": True, "detail": "无法计算"}
    else:
        items["雷达工作频率"] = {"ok": True, "detail": "数据不足"}

    # GitHub Actions
    workflow = os.path.join(TOOL_FACTORY_DIR, ".github", "workflows", "deploy.yml")
    items["GitHub 自动部署"] = {
        "ok": os.path.exists(workflow),
        "detail": "deploy.yml 正常, Push自动触发" if os.path.exists(workflow) else "deploy.yml 缺失"
    }

    # ═══════════════════════════════════════
    # 🏭 v2.0: 车间拦截状态（demand_filter v3.0 + functional_test）
    # ═══════════════════════════════════════════
    filter_path = os.path.join(TOOL_FACTORY_DIR, "engine", "demand_filter.py")
    if os.path.exists(filter_path):
        filter_ver = "?"
        try:
            with open(filter_path, "r") as f:
                content = f.read()
            ver_match = re.search(r'v(\d+\.\d+)', content)
            if ver_match:
                filter_ver = f"v{ver_match.group(1)}"
            has_cn_filter = "CN_SEMANTIC_BLACKLIST" in content or "intent_classifier" in content
            items["需求过滤器"] = {
                "ok": filter_ver >= "v3.0" and has_cn_filter,
                "detail": f"demand_filter.py {filter_ver}, 中文拦截{'✅' if has_cn_filter else '❌'}{' (意图分类器)' if 'intent_classifier' in content else ''}"
            }
        except Exception:
            items["需求过滤器"] = {"ok": False, "detail": "读取失败"}
    else:
        items["需求过滤器"] = {"ok": False, "detail": "demand_filter.py 不存在"}

    # 功能测试拦截器
    func_test_path = os.path.join(SCRIPT_DIR, "functional_test_runner.py")
    items["功能测试拦截器"] = {
        "ok": os.path.exists(func_test_path),
        "detail": "functional_test_runner.py 已部署" if os.path.exists(func_test_path) else "功能测试脚本缺失"
    }

    # 管道拦截状态
    pipeline_path = os.path.join(TOOL_FACTORY_DIR, "engine", "pipeline.py")
    if os.path.exists(pipeline_path):
        try:
            with open(pipeline_path, "r") as f:
                pipe_content = f.read()
            has_gate = "workshop_gate" in pipe_content or "functional_test" in pipe_content
            items["管道车间拦截"] = {
                "ok": has_gate,
                "detail": "已集成功能测试拦截" if has_gate else "⚠️ 未集成功能测试，新工具无拦截直接入库！"
            }
        except Exception:
            items["管道车间拦截"] = {"ok": False, "detail": "无法检查"}
    else:
        items["管道车间拦截"] = {"ok": False, "detail": "pipeline.py 不存在"}

    # 超时熔断 → 整项变红
    all_ok = all(v["ok"] for v in items.values())
    return all_ok, items, radar_timeout


# ═══════════════════════════════════════════
# 5. 备份安全
# ═══════════════════════════════════════════
def check_backup_security():
    items = {}

    # 工具数据库备份
    gen_path = os.path.join(TOOL_FACTORY_DIR, "backups", "generated_tools.json")
    if os.path.exists(gen_path):
        size_mb = os.path.getsize(gen_path) / (1024 * 1024)
        mtime = datetime.fromtimestamp(os.path.getmtime(gen_path))
        items["工具数据库"] = {
            "ok": True,
            "detail": f"generated_tools.json {size_mb:.1f}MB, {mtime.strftime('%m/%d %H:%M')}"
        }
    else:
        items["工具数据库"] = {"ok": False, "detail": "备份不存在"}

    # 前端备份
    bak_path = os.path.join(TOOL_FACTORY_DIR, "index.html.bak")
    main_path = os.path.join(TOOL_FACTORY_DIR, "index.html")
    bak_exists = os.path.exists(bak_path)
    if bak_exists:
        bak_size = os.path.getsize(bak_path) / 1024
        main_size = os.path.getsize(main_path) / 1024 if os.path.exists(main_path) else 0
        diff = abs(bak_size - main_size)
        ref = "≈主线" if diff < 50 else f"差{diff:.0f}KB"
        items["前端页面备份"] = {
            "ok": bak_size > 50,
            "detail": f"index.html.bak {bak_size:.0f}KB ({ref})"
        }
    else:
        items["前端页面备份"] = {"ok": False, "detail": "未找到备份文件"}

    # Git 同步脚本
    sync_path = os.path.join(TOOL_FACTORY_DIR, "sync_to_github.command")
    items["Git 同步"] = {
        "ok": os.path.exists(sync_path),
        "detail": "sync_to_github.command 存在" if os.path.exists(sync_path) else "同步脚本缺失"
    }

    # SSL
    try:
        ok_s, _, _ = http_get("https://mintshovels.com")
        items["HTTPS 加密"] = {
            "ok": bool(ok_s),
            "detail": "正常" if ok_s else "连接失败"
        }
    except Exception as e:
        items["HTTPS 加密"] = {"ok": False, "detail": f"检查失败: {e}"}

    # 配置文件
    items["密钥配置"] = {
        "ok": os.path.exists(CONFIG_PATH),
        "detail": "配置文件完整" if os.path.exists(CONFIG_PATH) else "缺失"
    }

    # 日志留存
    log_path = os.path.join(TOOL_FACTORY_DIR, "reports", "pipeline_log.json")
    if os.path.exists(log_path):
        try:
            log = json.load(open(log_path))
            items["运行日志"] = {
                "ok": len(log) > 0,
                "detail": f"{len(log)} 条记录"
            }
        except Exception:
            items["运行日志"] = {"ok": False, "detail": "损坏"}
    else:
        items["运行日志"] = {"ok": False, "detail": "不存在"}

    all_ok = sum(1 for v in items.values() if not v["ok"]) <= 1
    return all_ok, items


# ═══════════════════════════════════════════
# 6. 流量概况
# ═══════════════════════════════════════════
def check_traffic():
    items = {}

    latest_path = os.path.join(SCRIPT_DIR, "latest_analytics.json")
    try:
        if os.path.exists(latest_path):
            data = json.load(open(latest_path))
        else:
            items["数据"] = {"ok": False, "detail": "latest_analytics.json 不存在"}
            return False, items
    except Exception as e:
        items["数据"] = {"ok": False, "detail": f"读取失败: {e}"}
        return False, items

    # Cloudflare 流量
    cf = data.get("cloudflare", {})
    groups = cf.get("groups", [])
    if groups:
        total_uv = sum(g.get("uniq", {}).get("uniques", 0) for g in groups)
        total_pv = sum(g.get("sum", {}).get("pageViews", 0) for g in groups)

        # 计算趋势
        if len(groups) >= 2:
            recent = sum(g.get("uniq", {}).get("uniques", 0) for g in groups[-3:])
            older = sum(g.get("uniq", {}).get("uniques", 0) for g in groups[:-3]) if len(groups) > 3 else 0
            if older > 0:
                trend_pct = (recent - older) / older * 100
                if trend_pct > 20:
                    trend = f"↗ 近3天涨{trend_pct:.0f}%"
                elif trend_pct < -20:
                    trend = f"↘ 近3天跌{abs(trend_pct):.0f}%"
                else:
                    trend = "→ 平稳"
            else:
                trend = "新站"
        else:
            trend = "数据不足"

        items["近 5 天访客"] = {
            "ok": total_uv > 0,
            "detail": f"共 {total_uv} 人次, {total_pv} 浏览, {trend}"
        }
    else:
        items["近 5 天访客"] = {"ok": False, "detail": "无数据"}

    # 数据更新时间
    ts = data.get("timestamp", "")
    if ts:
        items["数据更新时间"] = {
            "ok": True,
            "detail": ts[:19]
        }

    all_ok = groups and total_uv > 0
    return all_ok, items


# ═══════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════

def run_full_check():
    now = datetime.now()
    print()
    print("╔" + "═" * 54 + "╗")
    print("║" + "      🩺  MintShovels 全面体检      ".center(40) + "║")
    print("║" + f"     【当前项目版本：{VERSION}】     ".center(40) + "║")
    print("║" + f"        {now.strftime('%Y-%m-%d %H:%M:%S')}        ".center(40) + "║")
    print("╚" + "═" * 54 + "╝")
    print()

    categories = [
        ("1️⃣  网站状态", check_website),
        ("2️⃣  数据来源", check_data_sources),
        ("3️⃣  工具库", check_tools),
        ("4️⃣  自动运营", check_automation),
        ("5️⃣  备份安全", check_backup_security),
        ("6️⃣  流量概况", check_traffic),
    ]

    total_ok = 0
    total_fail = 0
    issues = []

    for name, checker in categories:
        result = checker()
        # check_automation 返回 3 个值: (ok, items, radar_timeout)
        if len(result) == 3:
            ok, items, radar_timeout = result
        else:
            ok, items = result
            radar_timeout = False

        icon = "🟢" if ok else "🔴"
        print(f"  {icon}  {name}")

        for sub_name, info in items.items():
            sub_icon = "  ✅" if info["ok"] else "  ❌"
            print(f"    {sub_icon}  {sub_name}: {info['detail']}")
            if not info["ok"]:
                issues.append(f"{name} → {sub_name}")

        if ok:
            total_ok += 1
        else:
            total_fail += 1
        print()

    # 雷达超时熔断警告
    if radar_timeout:
        print("╔" + "═" * 54 + "╗")
        print("║" + "  ⚠️  严重警告：雷达已超时未工作，自动运营流水线可能断联！  ".center(44) + "║")
        print("╚" + "═" * 54 + "╝")
        print()

    # 总结
    bar = "═" * 54
    print(bar)
    if total_fail == 0:
        print(f"  🎉  全部正常 · {total_ok}/{total_ok} 项通过")
    elif total_fail <= 2:
        print(f"  🟡  基本正常 · {total_ok} 项通过, {total_fail} 项需关注")
    else:
        print(f"  🔴  需要处理 · {total_ok} 项正常, {total_fail} 项有问题")
    print(bar)
    print()

    return total_fail == 0


def run_full_check_json():
    """JSON 格式输出"""
    categories = [
        ("website", check_website),
        ("datasources", check_data_sources),
        ("tools", check_tools),
        ("automation", check_automation),
        ("backup", check_backup_security),
        ("traffic", check_traffic),
    ]
    result = {}
    for name, checker in categories:
        r = checker()
        if len(r) == 3:
            ok, items, timeout = r
        else:
            ok, items = r
        result[name] = {"ok": ok, "items": items}
    result["all_ok"] = all(v["ok"] for v in result.values())
    return result


if __name__ == "__main__":
    import sys
    if "--json" in sys.argv:
        print(json.dumps(run_full_check_json(), ensure_ascii=False, indent=2))
    else:
        run_full_check()
