"""POST /api/generate/portrait_character — 同步生成一张角色立绘。"""

import time

from api._lib.generation import gen_character_portrait
from api._lib.handler import make_handler
from api._lib.storage import kv_get_json, kv_set_json


def _post(body, _query):
    cid = (body.get("character_id") or "").strip()
    prompt = (body.get("prompt") or "").strip()
    if not cid or not prompt:
        return 400, {"error": "character_id and prompt required"}

    items = kv_get_json("characters") or []
    ch = next((c for c in items if c.get("character_id") == cid), None)
    if not ch:
        return 404, {"error": f"character {cid} not found"}

    ref = ch.get("image_url") or ch.get("face_url") or ch.get("animated_image_url") or None
    result = gen_character_portrait(character_id=cid, prompt=prompt, reference_url=ref)

    # 维护索引：character_portraits:<cid> → list[result]
    key = f"char_portraits:{cid}"
    history = kv_get_json(key) or []
    history.insert(0, result)
    history = history[:8]
    kv_set_json(key, history)

    return 200, {"ok": True, "result": result}


handler = make_handler(on_post=_post)
