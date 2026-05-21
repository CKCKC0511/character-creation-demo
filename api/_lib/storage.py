"""Vercel Blob + KV (Upstash Redis REST) 存储封装。

环境变量（Vercel 自动注入）:
  BLOB_READ_WRITE_TOKEN   - Vercel Blob 写入 token
  KV_REST_API_URL         - Upstash REST endpoint
  KV_REST_API_TOKEN       - Upstash bearer token
"""

from __future__ import annotations

import json
import os
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Vercel Blob
# ---------------------------------------------------------------------------

BLOB_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN", "")
BLOB_API = "https://blob.vercel-storage.com"


def blob_put(pathname: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """上传到 Blob，返回公开 URL。pathname 形如 'portraits/character/xxx.png'。"""
    if not BLOB_TOKEN:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN not set")

    headers = {
        "authorization": f"Bearer {BLOB_TOKEN}",
        "x-content-type": content_type,
        # 关闭随机后缀，让相同 pathname 直接覆盖
        "x-add-random-suffix": "0",
    }
    r = requests.put(f"{BLOB_API}/{pathname}", data=data, headers=headers, timeout=45)
    r.raise_for_status()
    body = r.json()
    return body.get("url") or body.get("downloadUrl") or ""


def blob_get(url: str) -> bytes:
    """从 Blob 公开 URL 读回数据。"""
    r = requests.get(url, timeout=45)
    r.raise_for_status()
    return r.content


# ---------------------------------------------------------------------------
# Vercel KV (Upstash Redis REST)
# ---------------------------------------------------------------------------

KV_URL = os.environ.get("KV_REST_API_URL", "").rstrip("/")
KV_TOKEN = os.environ.get("KV_REST_API_TOKEN", "")


def _kv(*command: Any) -> Any:
    if not KV_URL or not KV_TOKEN:
        raise RuntimeError("KV_REST_API_URL / KV_REST_API_TOKEN not set")
    headers = {"Authorization": f"Bearer {KV_TOKEN}", "Content-Type": "application/json"}
    body = list(command)
    r = requests.post(KV_URL, json=body, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json().get("result")


def kv_set_json(key: str, value: Any) -> None:
    _kv("SET", key, json.dumps(value, ensure_ascii=False))


def kv_get_json(key: str) -> Any:
    raw = _kv("GET", key)
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return raw


def kv_del(key: str) -> None:
    _kv("DEL", key)


def kv_keys(pattern: str) -> list[str]:
    res = _kv("KEYS", pattern)
    return res or []


def kv_flush_pattern(pattern: str) -> int:
    keys = kv_keys(pattern)
    n = 0
    for k in keys:
        kv_del(k)
        n += 1
    return n
