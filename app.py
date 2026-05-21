"""Vercel Python entrypoint — stateless 单 Flask app。

设计要点：
- 不依赖任何 database / 对象存储；所有状态由前端持有，每次 fetch 必要时把上下文一并发来
- /api/scrape: 直接抓并返回 character list（前端缓存）
- /api/generate/*: 接受完整 character dict，调 ARK，返回结果（含 ARK 临时 URL）
- /api/export: 接受前端汇总好的 payload，组 Excel 返回 base64 让浏览器直接下载
"""

from __future__ import annotations

import os
import sys

from flask import Flask, jsonify, request, send_from_directory

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)

from lib.exporter import export_to_excel  # noqa: E402
from lib.generation import (  # noqa: E402
    enrich_character,
    gen_character_portrait,
    gen_user_portrait,
)
from lib.scraper import scrape  # noqa: E402

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
# /api/scrape — 同步抓取并返回（不持久化）
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

    return jsonify({
        "ok": True,
        "count": len(items),
        "feed": feed,
        "gender": gender,
        "items": items,
    })


# ---------------------------------------------------------------------------
# /api/tags — 仍然需要请求 tipsy 后端
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
# /api/generate/enrich — 接受完整 character dict
# ---------------------------------------------------------------------------

@app.route("/api/generate/enrich", methods=["POST"])
def api_generate_enrich():
    body = request.get_json(silent=True) or {}
    character = body.get("character") or {}
    if not character.get("character_id"):
        return jsonify({"error": "character with character_id required"}), 400
    result = enrich_character(character)
    return jsonify({"ok": True, "result": result})


# ---------------------------------------------------------------------------
# /api/generate/portrait_character — 接受 prompt + reference_url
# ---------------------------------------------------------------------------

@app.route("/api/generate/portrait_character", methods=["POST"])
def api_generate_portrait_character():
    body = request.get_json(silent=True) or {}
    cid = (body.get("character_id") or "").strip()
    prompt = (body.get("prompt") or "").strip()
    reference_url = (body.get("reference_url") or "").strip() or None
    if not cid or not prompt:
        return jsonify({"error": "character_id and prompt required"}), 400
    result = gen_character_portrait(
        character_id=cid, prompt=prompt, reference_url=reference_url,
    )
    return jsonify({"ok": True, "result": result})


# ---------------------------------------------------------------------------
# /api/generate/portrait_user — 接受 prompt
# ---------------------------------------------------------------------------

@app.route("/api/generate/portrait_user", methods=["POST"])
def api_generate_portrait_user():
    body = request.get_json(silent=True) or {}
    prompt = (body.get("prompt") or "").strip()
    cid = (body.get("character_id") or "").strip()
    if not prompt:
        return jsonify({"error": "prompt required"}), 400
    result = gen_user_portrait(prompt=prompt, character_id=cid or None)
    return jsonify({"ok": True, "result": result})


# ---------------------------------------------------------------------------
# /api/export — 接受前端汇总数据，返回 base64 .xlsx
# ---------------------------------------------------------------------------

@app.route("/api/export", methods=["POST"])
def api_export():
    body = request.get_json(silent=True) or {}
    rows = body.get("rows") or []
    if not isinstance(rows, list) or not rows:
        return jsonify({"error": "rows required (list of {character, enrich, char_portrait_url, user_portrait_url})"}), 400
    return jsonify(export_to_excel(rows))
