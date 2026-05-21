"""POST /api/export | GET /api/export/candidates"""

from api._lib.exporter import export_to_excel, list_candidates
from api._lib.handler import make_handler


def _post(body, _query):
    cids = body.get("character_ids") or []
    if not isinstance(cids, list) or not cids:
        return 400, {"error": "character_ids required"}
    result = export_to_excel(cids)
    return 200, result


def _get(query):
    return 200, {"candidates": list_candidates()}


handler = make_handler(on_post=_post, on_get=_get)
