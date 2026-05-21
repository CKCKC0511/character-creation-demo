from api._lib.handler import make_handler
from api._lib.storage import kv_get_json


def _get(query):
    items = kv_get_json("characters") or []
    meta = kv_get_json("characters_meta") or {}
    return 200, {
        "items": items,
        "count": len(items),
        "scraped_at": meta.get("scraped_at"),
        "feed": meta.get("feed"),
    }


handler = make_handler(on_get=_get)
