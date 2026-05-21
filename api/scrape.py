"""POST /api/scrape — 同步抓取一批角色，写入 KV。"""

import time

from api._lib.handler import make_handler
from api._lib.scraper import scrape
from api._lib.storage import kv_flush_pattern, kv_set_json


def _post(body, _query):
    feed = (body.get("feed") or "weekly").strip()
    if feed not in ("popular", "weekly", "new", "featured", "recommend"):
        feed = "weekly"
    try:
        count = max(1, min(int(body.get("count") or 20), 60))
    except Exception:
        count = 20
    gender = (body.get("gender") or "male").strip().lower()
    if gender not in ("male", "female", "other", ""):
        gender = "male"
    nsfw = bool(body.get("nsfw", True))

    items = scrape(
        feed=feed, count=count, gender=gender or None,
        nsfw=nsfw, language_code="",
    )

    # 启动新一批爬取时，清掉旧的丰容/产物索引（图片对象不删，让 Blob 自己过期）
    kv_flush_pattern("enriched:*")

    kv_set_json("characters", items)
    kv_set_json("characters_meta", {"scraped_at": time.time(), "feed": feed, "gender": gender})

    return 200, {"ok": True, "count": len(items), "feed": feed, "gender": gender}


handler = make_handler(on_post=_post)
