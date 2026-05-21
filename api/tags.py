"""GET /api/tags?nsfw=0|1 — 代理 tipsy.chat 标签。"""

import requests

from api._lib.handler import make_handler

TIPSY_TAGS_URL = "https://api.tipsy.chat/api/v1/character/tags"
TIPSY_HEADERS = {
    "Content-Type": "application/json",
    "Platform": "web",
    "Origin": "https://tipsy.chat",
    "Referer": "https://tipsy.chat/",
    "User-Agent": "Mozilla/5.0 Chrome/120 Safari/537.36",
}


def _get(query):
    nsfw = query.get("nsfw", "0") in ("1", "true", "True")
    try:
        r = requests.post(TIPSY_TAGS_URL, json={"nsfw": nsfw}, headers=TIPSY_HEADERS, timeout=12)
        r.raise_for_status()
        tags = r.json().get("data", {}).get("tags", []) or []
        slim = [
            {"tag_id": t.get("tag_id"), "desc": t.get("desc"), "alias": t.get("alias")}
            for t in tags
        ]
        slim.sort(key=lambda t: t.get("desc") or "")
        return 200, slim
    except Exception as e:
        return 500, {"error": str(e)}


handler = make_handler(on_get=_get)
