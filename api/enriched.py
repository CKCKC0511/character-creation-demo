"""GET /api/enriched?cid=xxx — 单个角色的丰容结果。"""

from api._lib.handler import make_handler
from api._lib.storage import kv_get_json


def _get(query):
    cid = (query.get("cid") or "").strip()
    if not cid:
        return 400, {"error": "cid required"}
    data = kv_get_json(f"enriched:{cid}")
    return 200, {"exists": bool(data), "data": data}


handler = make_handler(on_get=_get)
