#!/usr/bin/env python3
"""
MintShovels 通用提取模块 · extract_common
供 engine/main.py (2号工厂) 使用
"""

from __future__ import annotations
from typing import Optional, List, Dict, Any

_YDL_OPTS_BASE = {
    "quiet": True,
    "no_warnings": True,
    "format": "best[ext=mp4]/best",
    "geo_bypass": True,
    "noplaylist": True,
}

def extract(url: str) -> dict:
    """从 URL 提取媒体信息"""
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL(_YDL_OPTS_BASE) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except Exception:
        return {"title": None, "formats": []}

def pick_best(info: dict) -> Optional[Dict[str, str]]:
    """从 info 中选出最佳的可下载格式"""
    formats = info.get("formats", [])
    if not formats:
        return None
    # 优选 mp4
    for f in formats:
        if f.get("ext") == "mp4" and f.get("url"):
            title = (info.get("title") or "video").replace("/", "_")
            return {
                "url": f["url"],
                "filename": f"{title}.{f.get('ext', 'mp4')}",
            }
    # 回退到第一个有 url 的格式
    for f in formats:
        if f.get("url"):
            title = (info.get("title") or "video").replace("/", "_")
            return {
                "url": f["url"],
                "filename": f"{title}.{f.get('ext', 'mp4')}",
            }
    return None
