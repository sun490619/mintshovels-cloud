from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import re, logging, time
from typing import Optional, Dict
from datetime import datetime, timezone
import yt_dlp
import threading, time as _time
from fastapi.responses import HTMLResponse
import os as _os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mintshovels")

app = FastAPI(title="MintShovels Engine", version="1.6.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
)

# ---- 🏠 前端静态文件服务 ----
# 确保 API 路由优先于静态文件，所以先定义所有 API 路由，最后挂载静态文件
_STATIC_DIR = _os.path.dirname(_os.path.abspath(__file__))

class ExtractRequest(BaseModel):
    url: str

class SearchLogRequest(BaseModel):
    query: str
    lang: str = "en"

_PLATFORM_RE = {
    "x": re.compile(r"https?://(?:twitter\.com|x\.com)/\w+/status/\d+", re.I),
    "tiktok": re.compile(r"https?://(?:www\.)?tiktok\.com/@[^/]+/video/\d+", re.I),
    "youtube": re.compile(r"https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{11})", re.I),
}

# ---- Radar Store ----
_radar_store: Dict[str, dict] = {}
_radar_started_at: str = datetime.now(timezone.utc).isoformat()
_radar_total_scans: int = 0
_radar_fail_count: int = 0

def _read_radar_report():
    """读取最新 demand_report.json，返回报告摘要"""
    import json as _json
    report_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "reports", "demand_report.json")
    if not _os.path.exists(report_path):
        return None
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            return _json.load(f)
    except Exception:
        return None

def _record_radar(url: str, reason: str):
    global _radar_total_scans, _radar_fail_count
    _radar_total_scans += 1
    _radar_fail_count += 1
    _radar_store[url] = {
        "platform": _detect_platform(url) or "unknown",
        "reason": reason,
        "ts": datetime.now(timezone.utc).isoformat() + "Z",
    }

def _record_radar_ok():
    global _radar_total_scans
    _radar_total_scans += 1

_YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "format": "best[ext=mp4]/best",
    "geo_bypass": True,
    "noplaylist": True,
}

def _detect_platform(url: str) -> Optional[str]:
    for plat, pat in _PLATFORM_RE.items():
        if pat.search(url):
            return plat
    return None

@app.get("/api/status")
def root():
    """API 状态检查（移至 /api/status，根路径由前端 HTML 接管）"""
    return {"service": "MintShovels Engine", "version": "1.6.0", "status": "running"}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.post("/v1/extract")
def extract(req: ExtractRequest):
    url = req.url.strip()
    platform = _detect_platform(url)

    if not platform:
        _record_radar(url, reason="unsupported_platform")
        return JSONResponse({
            "status": "success",
            "platform": "unknown",
            "title": None,
            "filename": None,
            "direct_url": None,
        })

    try:
        with yt_dlp.YoutubeDL(_YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get("formats", [])
            
            best_format = None
            for f in formats:
                if f.get("ext") == "mp4" and f.get("url"):
                    best_format = f
                    break
            if not best_format and formats:
                best_format = formats[0]
            
            if best_format and best_format.get("url"):
                _record_radar_ok()
                ext = best_format.get("ext", "mp4")
                title = info.get("title") or "video"
                filename = title.replace("/", "_") + f".{ext}"
                
                return JSONResponse({
                    "status": "success",
                    "platform": platform,
                    "title": title,
                    "filename": filename,
                    "direct_url": best_format["url"],
                })

    except Exception as e:
        logger.error(f"Extract failed for {url}: {e}")
        _record_radar(url, reason=str(e))
        return JSONResponse({
            "status": "error",
            "platform": platform,
            "title": None,
            "filename": None,
            "direct_url": None,
            "error": str(e),
        })

    _record_radar(url, reason="no_media")
    return JSONResponse({
        "status": "success",
        "platform": platform,
        "title": None,
        "filename": None,
        "direct_url": None,
    })

# ---- Radar API ----
@app.get("/v1/radar")
def radar_status():
    """返回雷达系统运行状态 — 基于实际报告新鲜度判定"""
    uptime_seconds = (datetime.now(timezone.utc) - datetime.fromisoformat(_radar_started_at.replace("Z", "+00:00"))).total_seconds()
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    
    # 📡 读取实际雷达报告，判定真实状态
    report = _read_radar_report()
    radar_status = "idle"
    last_scan_time = None
    last_scan_count = 0
    total_signals = 0
    tool_signals = 0
    suggestions = 0
    
    if report:
        gen_at = report.get("generated_at", "")
        if gen_at:
            try:
                gen_dt = datetime.fromisoformat(gen_at.replace("Z", "+00:00"))
                age_minutes = (datetime.now(timezone.utc) - gen_dt).total_seconds() / 60
                last_scan_time = gen_at
                
                ta = report.get("trait_analysis", {})
                total_signals = ta.get("total_captured", 0)
                tool_signals = ta.get("tool_signals_found", 0)
                suggestions = len(report.get("tool_suggestions", []))
                
                # 4小时内 → patrolling, 12小时内 → standby, 超过 → idle
                if age_minutes < 240:
                    radar_status = "patrolling"
                    last_scan_count = tool_signals
                elif age_minutes < 720:
                    radar_status = "standby"
                    last_scan_count = tool_signals
                else:
                    radar_status = "idle"
                    last_scan_count = 0
            except Exception:
                pass
    
    # 统计各平台失败情况
    platform_stats = {}
    for entry in _radar_store.values():
        p = entry["platform"]
        if p not in platform_stats:
            platform_stats[p] = 0
        platform_stats[p] += 1
    
    # 附带搜索日志供前端 Workshop 雷达面板使用
    search_logs = [{
        "query": item["query"],
        "lang": item.get("lang", "en"),
        "ts": item["ts"],
        "type": "search",
    } for item in _search_log[-50:]]
    
    return {
        "status": radar_status,
        "started_at": _radar_started_at,
        "uptime_hours": hours,
        "uptime_minutes": minutes,
        "total_scans": _radar_total_scans,
        "fail_count": _radar_fail_count,
        "health_rate": round((1 - _radar_fail_count / max(_radar_total_scans, 1)) * 100, 1),
        "platform_stats": platform_stats,
        "recent_fails": dict(list(_radar_store.items())[-5:]),
        "search_logs": search_logs,
        # 🆕 实际雷达报告摘要
        "last_scan_time": last_scan_time,
        "last_scan_count": last_scan_count,
        "total_signals_captured": total_signals,
        "tool_signals_found": tool_signals,
        "tool_suggestions": suggestions,
    }

# ---- Search Log ----
_search_log: list = []

@app.post("/v1/search-log")
def search_log(req: SearchLogRequest):
    """记录未找到结果的搜索词，用于需求雷达"""
    entry = {
        "query": req.query,
        "lang": req.lang,
        "ts": datetime.now(timezone.utc).isoformat() + "Z",
    }
    _search_log.append(entry)
    # 只保留最近500条
    if len(_search_log) > 500:
        _search_log[:] = _search_log[-500:]
    logger.info(f"Search logged: {req.query}")
    return {"status": "logged", "total": len(_search_log)}

@app.get("/v1/search-log")
def get_search_log():
    """查看搜索日志（需求雷达）"""
    # 按出现次数排序
    from collections import Counter
    query_counts = Counter(item["query"] for item in _search_log)
    return {
        "total": len(_search_log),
        "top_queries": query_counts.most_common(20),
        "recent": _search_log[-20:],
    }

# ---- Tools Catalog ----
@app.get("/v1/tools")
def tools_catalog():
    """返回工具目录（前端也可直接渲染，此端点供外部调用）"""
    return {
        "count": 8,
        "tools": [
            {
                "id": "shovel-001",
                "name": "Multi-Platform Media Extractor",
                "name_zh": "多平台素材一键提取",
                "category": "video",
                "status": "live",
                "badge": "Shovel #001",
            },
            {
                "id": "shovel-002",
                "name": "Image Compressor",
                "name_zh": "图片批量压缩器",
                "category": "image",
                "status": "soon",
            },
            {
                "id": "shovel-003",
                "name": "Audio Transcriber",
                "name_zh": "音频转文字",
                "category": "audio",
                "status": "soon",
            },
            {
                "id": "shovel-004",
                "name": "PDF Toolkit",
                "name_zh": "PDF万能工具箱",
                "category": "office",
                "status": "soon",
            },
            {
                "id": "shovel-005",
                "name": "Crypto Wallet Tracker",
                "name_zh": "加密货币钱包追踪器",
                "category": "crypto",
                "status": "soon",
            },
            {
                "id": "shovel-006",
                "name": "QR Code Generator",
                "name_zh": "二维码批量生成器",
                "category": "misc",
                "status": "soon",
            },
            {
                "id": "shovel-007",
                "name": "Background Remover",
                "name_zh": "智能抠图去背景",
                "category": "image",
                "status": "soon",
            },
            {
                "id": "shovel-008",
                "name": "Text Diff Checker",
                "name_zh": "文本差异对比器",
                "category": "office",
                "status": "soon",
            },
        ],
    }

# ---- Workshop API (Auto Factory) ----
import os as _os
import json as _json
import uuid as _uuid

_GENERATED_TOOLS_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "backups", "generated_tools.json")
_workshop_queue: list = []
_workshop_generated_today: int = 0

def _load_generated_tools():
    """从备份文件加载生成工具列表"""
    if not _os.path.exists(_GENERATED_TOOLS_PATH):
        return []
    try:
        with open(_GENERATED_TOOLS_PATH, "r") as f:
            return _json.loads(f.read())
    except Exception:
        return []

@app.get("/v1/workshop/tools")
def workshop_tools(q: str = "", category: str = "", page: int = 1, limit: int = 5000):
    """返回 Workshop 已生成工具列表，支持搜索/分类/分页"""
    tools = _load_generated_tools()
    for t in tools:
        if "deployed" not in t:
            t["deployed"] = t.get("status") == "live"
    if q:
        ql = q.lower()
        tools = [t for t in tools if ql in (t.get("name","")+t.get("name_zh","")+t.get("keyword","")+(t.get("desc",""))).lower()]
    if category:
        tools = [t for t in tools if t.get("category") == category]
    total = len(tools)
    start = (page - 1) * limit
    paged = tools[start:start + limit]
    return {"total": total, "page": page, "limit": limit, "tools": paged}

@app.get("/v1/workshop/tools/{tool_id}")
def workshop_tool_detail(tool_id: str):
    """获取单个工具详情"""
    tools = _load_generated_tools()
    for t in tools:
        if t.get("id") == tool_id:
            if "deployed" not in t:
                t["deployed"] = t.get("status") == "live"
            return t
    raise HTTPException(status_code=404, detail="Tool not found")

@app.delete("/v1/workshop/tools/{tool_id}")
def workshop_tool_delete(tool_id: str):
    """删除一个工具"""
    tools = _load_generated_tools()
    filtered = [t for t in tools if t.get("id") != tool_id]
    if len(filtered) == len(tools):
        raise HTTPException(status_code=404, detail="Tool not found")
    with open(_GENERATED_TOOLS_PATH, "w") as f:
        _json.dump(filtered, f, ensure_ascii=False, indent=2)
    return {"status": "deleted", "id": tool_id, "remaining": len(filtered)}

@app.get("/v1/workshop/status")
def workshop_status():
    """Workshop 运行状态"""
    tools = _load_generated_tools()
    deployed = sum(1 for t in tools if t.get("deployed") or t.get("status") == "live")
    return {
        "active": True,
        "templates": 8,
        "total_generated": len(tools),
        "queue_size": len(_workshop_queue),
        "deployed": deployed,
        "tools_generated_today": _workshop_generated_today,
    }

@app.get("/v1/workshop/queue")
def workshop_queue():
    return {"total": len(_workshop_queue), "queue": _workshop_queue}

@app.post("/v1/workshop/queue")
async def workshop_add_to_queue(req: Request):
    body = await req.json()
    keyword = body.get("keyword", "").strip()
    template_id = body.get("template_id", "auto")
    lang = body.get("lang", "en")
    if not keyword:
        raise HTTPException(status_code=400, detail="keyword is required")
    entry = {
        "id": str(_uuid.uuid4())[:8],
        "keyword": keyword,
        "template_id": template_id,
        "lang": lang,
        "ts": datetime.now(timezone.utc).isoformat() + "Z",
    }
    _workshop_queue.append(entry)
    return {"status": "queued", "entry": entry}

@app.get("/v1/workshop/templates")
def workshop_templates():
    return {
        "templates": [
            {"id": "checker", "name": "检测器", "name_en": "Checker", "icon": "check-check", "type": "tool"},
            {"id": "generator", "name": "生成器", "name_en": "Generator", "icon": "dices", "type": "tool"},
            {"id": "converter", "name": "转换器", "name_en": "Converter", "icon": "arrow-left-right", "type": "tool"},
            {"id": "calculator", "name": "计算器", "name_en": "Calculator", "icon": "calculator", "type": "tool"},
            {"id": "formatter", "name": "格式化", "name_en": "Formatter", "icon": "terminal", "type": "tool"},
            {"id": "scraper", "name": "爬虫", "name_en": "Scraper", "icon": "check-check", "type": "script"},
            {"id": "validator", "name": "验证器", "name_en": "Validator", "icon": "check-check", "type": "tool"},
            {"id": "analyzer", "name": "分析器", "name_en": "Analyzer", "icon": "check-check", "type": "tool"},
        ]
    }

@app.post("/v1/workshop/tools/{tool_id}/deploy")
def workshop_deploy_tool(tool_id: str):
    tools = _load_generated_tools()
    found = False
    for t in tools:
        if t.get("id") == tool_id:
            t["deployed"] = True
            t["status"] = "live"
            t["deployed_at"] = datetime.now(timezone.utc).isoformat() + "Z"
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Tool not found")
    with open(_GENERATED_TOOLS_PATH, "w") as f:
        _json.dump(tools, f, ensure_ascii=False, indent=2)
    return {"status": "deployed", "id": tool_id}

@app.get("/v1/radar/risk-audit")
def radar_risk_audit():
    return {"pending": _radar_fail_count, "total_scanned": _radar_total_scans, "health_rate": round((1 - _radar_fail_count / max(_radar_total_scans, 1)) * 100, 1)}

@app.get("/v1/workshop/pipeline-status")
def workshop_pipeline_status():
    return {"status": "idle", "last_run": None, "next_run": None, "tools_this_cycle": 0}

# ---- 🏠 前端静态文件挂载（必须放在所有路由之后）----
# 挂载整个项目根目录为静态文件，index.html 会被自动作为首页
# API 路由优先级高于静态文件，所以不会互相干扰
app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
