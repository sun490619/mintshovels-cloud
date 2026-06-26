#!/usr/bin/env python3
"""
MintShovels Engine · 2号工厂
FastAPI Gateway + Zero-Log yt-dlp extractor + SearchLogger + Pain Point Radar Feed
"""

from __future__ import annotations

import os
import re
import uuid
import json
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl

from extract_common import extract, pick_best

app = FastAPI(title="MintShovels Engine", version="2.0.0")

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_session_store: Dict[str, dict] = {}
_radar_store: Dict[str, dict] = {}

# ── Pain Points 存储路径 ──
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(BASE_DIR, "reports")
PAIN_POINTS_PATH = os.path.join(REPORT_DIR, "pain_points.json")
SEARCH_LOG_PATH = os.path.join(REPORT_DIR, "search_log.json")
os.makedirs(REPORT_DIR, exist_ok=True)

_pain_points_lock = threading.Lock()


class ExtractRequest(BaseModel):
    url: HttpUrl


class ExtractResponse(BaseModel):
    status: str
    platform: str
    title: Optional[str] = None
    filename: Optional[str] = None
    download_url: Optional[str] = None


_PLATFORM_RE = {
    "x": re.compile(r'https?://(?:twitter\.com|x\.com)/\w+/status/\d+', re.I),
    "tiktok": re.compile(r'https?://(?:www\.)?tiktok\.com/@[^/]+/video/\d+', re.I),
    "youtube": re.compile(r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})', re.I),
}


def _detect_platform(url: str) -> Optional[str]:
    for plat, pat in _PLATFORM_RE.items():
        if pat.search(url):
            return plat
    return None


def _extract_info(url: str, platform: str) -> dict:
    return extract(url)


_X_RAPIDAPI_KEY = os.environ.get("X_RAPIDAPI_KEY", "")
_RAPIDAPI_HOST = os.environ.get("X_RAPIDAPI_HOST", "twitter-x.p.rapidapi.com")


def _x_rapidapi_fetch(tweet_url: str) -> dict:
    if not _X_RAPIDAPI_KEY:
        raise RuntimeError("RapidAPI X route not configured (X_RAPIDAPI_KEY missing)")
    import urllib.request, urllib.error
    endpoint = f"https://{_RAPIDAPI_HOST}/resolve"
    req = urllib.request.Request(
        endpoint,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-RapidAPI-Key": _X_RAPIDAPI_KEY,
            "X-RapidAPI-Host": _RAPIDAPI_HOST,
        },
        data=json.dumps({"url": tweet_url}).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"RapidAPI X route HTTP {e.code}: {body}")


_YDL_OPTS_BASE = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": False,
    "outtmpl": "-",
    "overwrites": False,
    "nopart": True,
    "updatetime": False,
    "format": "best[ext=mp4]/best",
    "geo_bypass": True,
}


def _build_streaming_response(direct_url: str, filename: str):
    from urllib.request import Request, urlopen
    req = Request(
        direct_url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "*/*",
        },
    )

    def _iter(chunk_size: int = 1024 * 512):
        with urlopen(req, timeout=30) as resp:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store, no-cache, must-revalidate",
        "Pragma": "no-cache",
    }
    return StreamingResponse(_iter(), media_type="application/octet-stream", headers=headers)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/v1/extract", response_model=ExtractResponse)
async def extract_endpoint(req: ExtractRequest):
    url = str(req.url)
    platform = _detect_platform(url)

    if not platform:
        _record_radar(url, reason="unsupported_platform")
        return JSONResponse({
            "status": "success",
            "platform": "unknown",
            "title": None,
            "filename": None,
            "download_url": None,
        })

    try:
        if platform == "x" and _X_RAPIDAPI_KEY:
            try:
                info = _x_rapidapi_fetch(url)
            except Exception as exc:
                return JSONResponse({"status": "error", "message": str(exc)}, status_code=502)
        else:
            info = _extract_info(url, platform)
    except Exception as exc:
        _record_radar(url, reason=str(exc))
        return JSONResponse({
            "status": "success",
            "platform": platform,
            "title": None,
            "filename": None,
            "download_url": None,
        })

    best = pick_best(info)
    if not best:
        _record_radar(url, reason="no_media")
        return JSONResponse({
            "status": "success",
            "platform": platform,
            "title": info.get("title"),
            "filename": None,
            "download_url": None,
        })

    session_id = str(uuid.uuid4())
    _session_store[session_id] = {
        "direct_url": best["url"],
        "filename": best["filename"],
    }
    return JSONResponse({
        "status": "success",
        "platform": platform,
        "title": info.get("title"),
        "filename": best["filename"],
        "download_url": f"/v1/stream/{session_id}",
    })


@app.get("/v1/stream/{session_id}")
def stream_media(session_id: str):
    record = _session_store.pop(session_id, None)
    if not record:
        raise HTTPException(status_code=404, detail="Session expired or not found")
    return _build_streaming_response(record["direct_url"], record["filename"])


def _record_radar(url: str, reason: str):
    _radar_store[url] = {
        "platform": _detect_platform(url) or "unknown",
        "reason": reason,
        "ts": datetime.utcnow().isoformat() + "Z",
    }


# ═══════════════════════════════════════════════════════════════
# 🧠 AI 助手商机捕手 — Pain Point 数据闭环
# ═══════════════════════════════════════════════════════════════

class PainPointRequest(BaseModel):
    """AI 机器人收集的用户痛点"""
    query: str                      # 用户原始搜索词
    conversation: List[dict] = []   # 对话历史 [{role, content}, ...]
    pain_summary: str = ""          # 机器人提炼的痛点摘要
    tool_idea: str = ""             # 机器人建议的工具名称
    category: str = ""              # 推测的分类
    source: str = "ai-assistant"    # 来源标识


class WishRequest(BaseModel):
    """用户许愿"""
    wish: str


class SearchLogRequest(BaseModel):
    """搜索日志"""
    query: str
    results: int = 0


def _load_pain_points() -> list:
    """加载已有痛点数据"""
    if os.path.exists(PAIN_POINTS_PATH):
        try:
            with open(PAIN_POINTS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def _save_pain_point(entry: dict):
    """保存单条痛点（线程安全）"""
    with _pain_points_lock:
        points = _load_pain_points()
        points.append(entry)
        # 去重：相同 query 保留最新的
        seen = {}
        deduped = []
        for p in reversed(points):
            key = p.get("query", "").strip().lower()
            if key and key not in seen:
                seen[key] = True
                deduped.append(p)
        deduped.reverse()
        with open(PAIN_POINTS_PATH, "w", encoding="utf-8") as f:
            json.dump(deduped, f, ensure_ascii=False, indent=2)


def _append_search_log(query: str, results: int = 0):
    """追加搜索日志"""
    entry = {
        "query": query,
        "results": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    logs = []
    if os.path.exists(SEARCH_LOG_PATH):
        try:
            with open(SEARCH_LOG_PATH, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    logs.append(entry)
    # 只保留最近200条
    logs = logs[-200:]
    with open(SEARCH_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


@app.post("/v1/pain-point")
async def collect_pain_point(req: PainPointRequest):
    """
    🧠 AI商机捕手 — 接收AI机器人收集的用户真实痛点
    
    这条数据会直接作为最高优先级原始需求回传雷达v2.0系统。
    """
    entry = {
        "query": req.query,
        "conversation": req.conversation,
        "pain_summary": req.pain_summary,
        "tool_idea": req.tool_idea,
        "category": req.category,
        "source": req.source,
        "priority": "highest",      # 🚨 最高优先级
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",        # pending → radar_processed → factory_built
    }
    
    _save_pain_point(entry)
    
    # 也同步到雷达内存存储
    _radar_store[f"pain:{req.query[:50]}"] = {
        "platform": "ai-assistant",
        "reason": "user_pain_point",
        "pain_summary": req.pain_summary,
        "tool_idea": req.tool_idea,
        "ts": datetime.utcnow().isoformat() + "Z",
    }
    
    return JSONResponse({
        "status": "received",
        "message": "✅ 痛点已捕获！系统将在下轮雷达扫描中优先处理您的需求。",
        "priority": "highest",
        "tool_idea": req.tool_idea,
    })


@app.post("/v1/wish")
async def submit_wish(req: WishRequest):
    """
    📝 用户许愿 — 快速提交工具需求
    """
    if not req.wish or len(req.wish.strip()) < 3:
        return JSONResponse({"status": "error", "message": "需求描述太短"}, status_code=400)
    
    entry = {
        "query": req.wish.strip(),
        "conversation": [{"role": "user", "content": req.wish.strip()}],
        "pain_summary": req.wish.strip(),
        "tool_idea": "",
        "category": "",
        "source": "wish-form",
        "priority": "high",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
    }
    
    _save_pain_point(entry)
    
    return JSONResponse({
        "status": "received",
        "message": "✅ 愿望已提交！我们会尽快处理。",
    })


@app.post("/v1/search-log")
async def log_search(req: SearchLogRequest):
    """
    🔍 搜索日志 — 记录用户搜索行为
    """
    if not req.query or len(req.query.strip()) < 1:
        return JSONResponse({"status": "ok"})
    
    _append_search_log(req.query.strip(), req.results)
    
    return JSONResponse({"status": "logged"})


@app.get("/v1/pain-points")
async def list_pain_points(limit: int = 20, source: str = ""):
    """
    📊 查询已收集的痛点列表（供调试/审计）
    """
    points = _load_pain_points()
    if source:
        points = [p for p in points if p.get("source") == source]
    points = sorted(points, key=lambda x: x.get("collected_at", ""), reverse=True)
    
    return JSONResponse({
        "total": len(points),
        "points": points[:limit],
    })


# ═══════════════════════════════════════════════════════════════
# 🏭 作坊工具接口 (供 index.html 加载动态工具)
# ═══════════════════════════════════════════════════════════════

class ToolEntry(BaseModel):
    id: str
    name: str
    name_zh: str
    desc: str
    desc_zh: str
    icon: str
    color: str
    category: str
    subcat: str
    type: str = "tool"
    tags: List[str] = []
    tags_zh: List[str] = []
    status: str = "live"
    ready: bool = True
    badge: str = ""
    detail_page: bool = True


@app.get("/v1/workshop/tools")
async def workshop_tools():
    """
    🏭 返回作坊生成的动态工具列表
    """
    # 从 reports/factory_log.json 读取已生产工具
    factory_log_path = os.path.join(REPORT_DIR, "factory_log.json")
    tools = []
    if os.path.exists(factory_log_path):
        try:
            with open(factory_log_path, "r", encoding="utf-8") as f:
                log = json.load(f)
            for entry in log:
                if entry.get("status") == "deployed":
                    tools.append({
                        "id": entry.get("id", ""),
                        "name": entry.get("name", ""),
                        "name_zh": entry.get("name_zh", ""),
                        "desc": entry.get("desc", ""),
                        "desc_zh": entry.get("desc_zh", ""),
                        "icon": entry.get("icon", "zap"),
                        "color": entry.get("color", "#6366f1"),
                        "category": entry.get("category", "utility"),
                        "subcat": entry.get("subcat", "tools"),
                        "type": entry.get("type", "tool"),
                        "tags": entry.get("tags", []),
                        "tags_zh": entry.get("tags_zh", []),
                        "status": "live",
                        "ready": True,
                        "badge": entry.get("badge", ""),
                        "detail_page": entry.get("detail_page", True),
                    })
        except (json.JSONDecodeError, IOError):
            pass
    return JSONResponse({"tools": tools, "count": len(tools)})
