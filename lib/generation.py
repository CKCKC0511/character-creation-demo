"""丰容（chat）+ 生图（seedream）调用，stateless 版本。

不写任何外部存储，所有结果直接返回给调用方，由前端持有。

环境变量:
  ARK_API_KEY, ARK_BASE_URL, ARK_TEXT_MODEL, ARK_IMAGE_MODEL
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import requests
from openai import OpenAI

from .prompts import ENRICH_SYSTEM_PROMPT, build_enrich_user_message

ARK_API_KEY = os.environ.get("ARK_API_KEY", "")
ARK_BASE_URL = os.environ.get("ARK_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3")
TEXT_MODEL = os.environ.get("ARK_TEXT_MODEL", "seed-sc-260215")
IMAGE_MODEL = os.environ.get("ARK_IMAGE_MODEL", "seedream-5-0-260128")


def _client() -> OpenAI:
    return OpenAI(api_key=ARK_API_KEY, base_url=ARK_BASE_URL)


def _strip_codefence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```\s*$", "", s)
    return s.strip()


def enrich_character(character: dict[str, Any]) -> dict[str, Any]:
    cid = character.get("character_id") or ""
    user_msg = build_enrich_user_message(character)

    resp = _client().chat.completions.create(
        model=TEXT_MODEL,
        messages=[
            {"role": "system", "content": ENRICH_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.95,
    )
    raw = resp.choices[0].message.content or ""
    clean = _strip_codefence(raw)
    try:
        parsed = json.loads(clean)
    except Exception:
        parsed = {"_raw": clean, "_error": "model did not return valid JSON"}

    return {
        "source_character_id": cid,
        "source_name": character.get("name", ""),
        "model": TEXT_MODEL,
        "generated_at": time.time(),
        "result": parsed,
    }


def _call_image_api(
    prompt: str,
    *,
    reference_url: str | None = None,
    size: str = "1440x2560",
) -> str:
    """调 seedream image API，返回 ARK 临时 URL（约 1 小时有效）。"""
    url = ARK_BASE_URL.rstrip("/") + "/images/generations"
    body: dict[str, Any] = {
        "model": IMAGE_MODEL,
        "prompt": prompt,
        "size": size,
        "response_format": "url",
        "watermark": False,
    }
    if reference_url:
        body["image"] = reference_url

    r = requests.post(
        url,
        json=body,
        headers={
            "Authorization": f"Bearer {ARK_API_KEY}",
            "Content-Type": "application/json",
        },
        timeout=55,
    )
    if not r.ok:
        raise RuntimeError(f"image API {r.status_code}: {r.text[:500]}")
    data = r.json().get("data") or []
    if not data:
        raise RuntimeError("image API returned empty data")
    item = data[0]
    img_url = item.get("url") if isinstance(item, dict) else None
    if not img_url:
        raise RuntimeError(f"unexpected response: {item!r}")
    return img_url


def gen_character_portrait(
    *, character_id: str, prompt: str, reference_url: str | None
) -> dict[str, Any]:
    if not prompt.strip():
        raise ValueError("prompt is required")
    img_url = _call_image_api(prompt, reference_url=reference_url)
    return {
        "character_id": character_id,
        "prompt": prompt,
        "reference_url": reference_url,
        "model": IMAGE_MODEL,
        "image_url": img_url,
        "generated_at": int(time.time()),
    }


def gen_user_portrait(*, prompt: str, character_id: str | None = None) -> dict[str, Any]:
    if not prompt.strip():
        raise ValueError("prompt is required")
    img_url = _call_image_api(prompt, reference_url=None)
    return {
        "character_id": character_id or "",
        "prompt": prompt,
        "model": IMAGE_MODEL,
        "image_url": img_url,
        "generated_at": int(time.time()),
    }
