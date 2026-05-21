"""tipsy.chat 角色抓取（同步版本，可在 60s serverless 函数内完成）。

和原 tipsy/scrape_tipsy.py 的差别：
  - 不接 subprocess、不接 argparse
  - 抓完后写入 KV (key='characters'，JSON list)
  - 单次默认抓 20 个，配 page_size=50 大概率 1~2 页 search 即够
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Iterable

import requests

PUBLIC_LIST_URL = "https://api.tipsy.chat/api/v1/character/get/public_list"
RECOMMEND_URL = "https://api.tipsy.chat/api/v1/recommend_feed/list"
SITE_BASE = "https://tipsy.chat"

SORTING_MAP = {
    "popular": "Popular",
    "weekly": "WeeklyPicks",
    "new": "New",
    "featured": "Featured",
    "featured7d": "Featured7D",
    "featured1d": "Featured1D",
}

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Platform": "web",
    "Origin": SITE_BASE,
    "Referer": SITE_BASE + "/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}


def _normalize(char: dict[str, Any], creator: dict[str, Any] | None = None) -> dict[str, Any]:
    if not char:
        return {}
    tags = char.get("tags") or []
    tag_names = [t.get("alias") or t.get("desc") for t in tags if isinstance(t, dict)]
    tag_names = [t for t in tag_names if t]
    cid = char.get("character_id", "")
    return {
        "character_id": cid,
        "name": char.get("nickname", ""),
        "gender": char.get("gender", ""),
        "tags": tag_names,
        "tag_ids": char.get("tag_ids") or [],
        "introduction": char.get("introduction", ""),
        "greeting": char.get("greeting", ""),
        "image_url": char.get("image_url") or "",
        "face_url": char.get("face_url") or "",
        "animated_image_url": char.get("animated_image_url") or "",
        "source_url": f"{SITE_BASE}/chat/{cid}" if cid else "",
        "is_nsfw": bool(char.get("nsfw", False)),
        "lang": char.get("lang", ""),
        "creator_nickname": (creator or {}).get("nickname", "") if creator else "",
    }


def _fetch_public_list(
    session: requests.Session,
    *,
    sorting: str,
    page: int,
    size: int,
    nsfw: bool,
    language_code: str,
    tag_ids: list[str],
    gender: str | None,
) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {
        "sorting": sorting,
        "size": size,
        "page": page,
        "tag_ids": tag_ids,
        "nsfw": nsfw,
        "language_code": language_code,
    }
    if gender:
        payload["gender"] = gender
    r = session.post(PUBLIC_LIST_URL, json=payload, headers=DEFAULT_HEADERS, timeout=20)
    r.raise_for_status()
    body = r.json()
    if body.get("code") != 0:
        raise RuntimeError(f"tipsy API non-zero: {body}")
    items = body.get("data", {}).get("list", []) or []
    out = []
    for it in items:
        char = it.get("character") or {}
        if not char:
            continue
        out.append(_normalize(char, it.get("creator")))
    return out


def _fetch_recommend(
    session: requests.Session,
    *,
    page: int,
    size: int,
    nsfw: bool,
    language_code: str,
    tag_ids: list[str],
    session_id: str,
) -> list[dict[str, Any]]:
    payload = {
        "size": size,
        "nsfw": nsfw,
        "language_code": language_code,
        "tag_ids": tag_ids,
        "session_id": session_id,
        "page": page,
    }
    r = session.post(RECOMMEND_URL, json=payload, headers=DEFAULT_HEADERS, timeout=20)
    r.raise_for_status()
    body = r.json()
    if body.get("code") != 0:
        raise RuntimeError(f"tipsy API non-zero: {body}")
    items = body.get("data", {}).get("list", []) or []
    out = []
    for it in items:
        if it.get("type") != "character":
            continue
        data = it.get("data") or {}
        char = data.get("character") or {}
        if not char:
            continue
        out.append(_normalize(char, data.get("creator")))
    return out


def scrape(
    *,
    feed: str = "weekly",
    count: int = 20,
    gender: str | None = "male",
    nsfw: bool = True,
    language_code: str = "",
    tag_ids: list[str] | None = None,
    page_size: int = 50,
    max_pages: int = 8,
    delay: float = 0.3,
) -> list[dict[str, Any]]:
    """同步抓取，返回归一化后的角色列表。本地按 gender 过滤。"""
    session = requests.Session()
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    rec_session_id = str(uuid.uuid4())

    for page in range(max_pages):
        if feed == "recommend":
            items = _fetch_recommend(
                session, page=page, size=page_size, nsfw=nsfw,
                language_code=language_code, tag_ids=tag_ids or [],
                session_id=rec_session_id,
            )
        else:
            items = _fetch_public_list(
                session, sorting=SORTING_MAP.get(feed, "Popular"),
                page=page, size=page_size, nsfw=nsfw,
                language_code=language_code, tag_ids=tag_ids or [],
                gender=None,  # 不在 API 侧过滤；本地筛
            )
        if not items:
            break
        for ch in items:
            cid = ch.get("character_id")
            if not cid or cid in seen:
                continue
            if gender and ch.get("gender") != gender:
                continue
            seen.add(cid)
            out.append(ch)
            if len(out) >= count:
                return out
        time.sleep(delay)
    return out
