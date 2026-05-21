"""Vercel Python entrypoint — 单 Flask app。

部署关键约定：
- 文件放在项目根目录，文件名为 app.py，导出顶级 `app` 变量；Vercel 会自动作为 WSGI 入口。
- 静态前端放在 `static/`，Flask 自带 static_folder 机制把它一起打进 lambda 包；
  访问 `/` → `static/index.html`。
- 业务依赖都同步执行；ARK 文本/图片调用都在 60s 内完成（Hobby 默认 5min 上限够用）。
"""

from __future__ import annotations

import os
import sys
import time

from flask import Flask, jsonify, request, send_from_directory

# 让 lib/ 包能被 import
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)

from lib.exporter import export_to_excel, list_candidates  # noqa: E402
from lib.generation import (  # noqa: E402
    enrich_character,
    gen_character_portrait,
    gen_user_portrait,
)
from lib.scraper import scrape  # noqa: E402
from lib.storage import (  # noqa: E402
    kv_flush_pattern,
    kv_get_json,
    kv_set_json,
)

STATIC_DIR = os.path.join(_ROOT, "static")

app = Flask(
    __name__,
    static_folder=STATIC_DIR,
    static_url_path="",
)


# ---------------------------------------------------------------------------
# 静态前端
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


# ---------------------------------------------------------------------------
# /api/characters
# ---------------------------------------------------------------------------

@app.route("/api/characters", methods=["GET"])
def api_characters():
    items = kv_get_json("characters") or []
    meta = kv_get_json("characters_meta") or {}
    return jsonify({
        "items": items,
        "count": len(items),
        "scraped_at": meta.get("scraped_at"),
        "feed": meta.get("feed"),
    })


# ---------------------------------------------------------------------------
# /api/scrape
# ---------------------------------------------------------------------------

@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    body = request.get_json(silent=True) or {}
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

    kv_flush_pattern("enriched:*")
    kv_set_json("characters", items)
    kv_set_json("characters_meta", {
        "scraped_at": time.time(), "feed": feed, "gender": gender,
    })

    return jsonify({"ok": True, "count": len(items), "feed": feed, "gender": gender})


# ---------------------------------------------------------------------------
# /api/tags
# ---------------------------------------------------------------------------

import requests as _requests  # noqa: E402

TIPSY_TAGS_URL = "https://api.tipsy.chat/api/v1/character/tags"
TIPSY_HEADERS = {
    "Content-Type": "application/json",
    "Platform": "web",
    "Origin": "https://tipsy.chat",
    "Referer": "https://tipsy.chat/",
    "User-Agent": "Mozilla/5.0 Chrome/120 Safari/537.36",
}


@app.route("/api/tags", methods=["GET"])
def api_tags():
    nsfw = request.args.get("nsfw", "0") in ("1", "true", "True")
    try:
        r = _requests.post(
            TIPSY_TAGS_URL, json={"nsfw": nsfw},
            headers=TIPSY_HEADERS, timeout=12,
        )
        r.raise_for_status()
        tags = r.json().get("data", {}).get("tags", []) or []
        slim = [
            {"tag_id": t.get("tag_id"), "desc": t.get("desc"), "alias": t.get("alias")}
            for t in tags
        ]
        slim.sort(key=lambda t: t.get("desc") or "")
        return jsonify(slim)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# /api/enriched
# ---------------------------------------------------------------------------

@app.route("/api/enriched", methods=["GET"])
def api_enriched():
    cid = (request.args.get("cid") or "").strip()
    if not cid:
        return jsonify({"error": "cid required"}), 400
    data = kv_get_json(f"enriched:{cid}")
    return jsonify({"exists": bool(data), "data": data})


# ---------------------------------------------------------------------------
# /api/generate/enrich
# ---------------------------------------------------------------------------

@app.route("/api/generate/enrich", methods=["POST"])
def api_generate_enrich():
    body = request.get_json(silent=True) or {}
    cid = (body.get("character_id") or "").strip()
    if not cid:
        return jsonify({"error": "character_id required"}), 400
    items = kv_get_json("characters") or []
    ch = next((c for c in items if c.get("character_id") == cid), None)
    if not ch:
        return jsonify({"error": f"character {cid} not found"}), 404
    result = enrich_character(ch)
    return jsonify({"ok": True, "result": result})


# ---------------------------------------------------------------------------
# /api/generate/portrait_character
# ---------------------------------------------------------------------------

@app.route("/api/generate/portrait_character", methods=["POST"])
def api_generate_portrait_character():
    body = request.get_json(silent=True) or {}
    cid = (body.get("character_id") or "").strip()
    prompt = (body.get("prompt") or "").strip()
    if not cid or not prompt:
        return jsonify({"error": "character_id and prompt required"}), 400
    items = kv_get_json("characters") or []
    ch = next((c for c in items if c.get("character_id") == cid), None)
    if not ch:
        return jsonify({"error": f"character {cid} not found"}), 404
    ref = ch.get("image_url") or ch.get("face_url") or ch.get("animated_image_url") or None
    result = gen_character_portrait(character_id=cid, prompt=prompt, reference_url=ref)
    key = f"char_portraits:{cid}"
    history = kv_get_json(key) or []
    history.insert(0, result)
    history = history[:8]
    kv_set_json(key, history)
    return jsonify({"ok": True, "result": result})


# ---------------------------------------------------------------------------
# /api/generate/portrait_user
# ---------------------------------------------------------------------------

@app.route("/api/generate/portrait_user", methods=["POST"])
def api_generate_portrait_user():
    body = request.get_json(silent=True) or {}
    prompt = (body.get("prompt") or "").strip()
    cid = (body.get("character_id") or "").strip()
    if not prompt:
        return jsonify({"error": "prompt required"}), 400
    result = gen_user_portrait(prompt=prompt, character_id=cid or None)
    if cid:
        key = f"user_portraits:{cid}"
        history = kv_get_json(key) or []
        history.insert(0, result)
        history = history[:8]
        kv_set_json(key, history)
    return jsonify({"ok": True, "result": result})


# ---------------------------------------------------------------------------
# /api/export
# ---------------------------------------------------------------------------

@app.route("/api/export", methods=["GET", "POST"])
def api_export():
    if request.method == "GET":
        return jsonify({"candidates": list_candidates()})
    body = request.get_json(silent=True) or {}
    cids = body.get("character_ids") or []
    if not isinstance(cids, list) or not cids:
        return jsonify({"error": "character_ids required"}), 400
    return jsonify(export_to_excel(cids))
