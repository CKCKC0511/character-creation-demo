"""POST /api/generate/enrich — 同步丰容单个角色（body.character_id）。

注意：Hobby 60s 上限，批量丰容请前端拆成多个并发请求。
"""

from api._lib.generation import enrich_character
from api._lib.handler import make_handler
from api._lib.storage import kv_get_json


def _post(body, _query):
    cid = (body.get("character_id") or "").strip()
    if not cid:
        return 400, {"error": "character_id required"}

    items = kv_get_json("characters") or []
    ch = next((c for c in items if c.get("character_id") == cid), None)
    if not ch:
        return 404, {"error": f"character {cid} not found in current scrape"}

    result = enrich_character(ch)
    return 200, {"ok": True, "result": result}


handler = make_handler(on_post=_post)
