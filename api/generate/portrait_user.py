"""POST /api/generate/portrait_user — 同步生成一张用户立绘（按角色配对）。"""

from api._lib.generation import gen_user_portrait
from api._lib.handler import make_handler
from api._lib.storage import kv_get_json, kv_set_json


def _post(body, _query):
    prompt = (body.get("prompt") or "").strip()
    cid = (body.get("character_id") or "").strip()
    if not prompt:
        return 400, {"error": "prompt required"}

    result = gen_user_portrait(prompt=prompt, character_id=cid or None)

    if cid:
        key = f"user_portraits:{cid}"
        history = kv_get_json(key) or []
        history.insert(0, result)
        history = history[:8]
        kv_set_json(key, history)

    return 200, {"ok": True, "result": result}


handler = make_handler(on_post=_post)
