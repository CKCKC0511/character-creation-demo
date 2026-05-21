"""Vercel Python serverless handler 工具：封装 BaseHTTPRequestHandler 样板。

Vercel Python runtime 要求每个 api/*.py 暴露一个 `handler(BaseHTTPRequestHandler)` 类，
这里提供工具函数让业务函数可以只关心 (method, body) -> (status, json)。
"""

from __future__ import annotations

import json
import traceback
from http.server import BaseHTTPRequestHandler
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse


def make_handler(
    *,
    on_post: Callable[[dict[str, Any], dict[str, Any]], tuple[int, Any]] | None = None,
    on_get: Callable[[dict[str, Any]], tuple[int, Any]] | None = None,
):
    """生成一个 Vercel Python handler 类。

    on_post(body_json, query) -> (status, dict)
    on_get(query) -> (status, dict)
    """

    class H(BaseHTTPRequestHandler):
        def _write_json(self, status: int, payload: Any) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(data)

        def _query(self) -> dict[str, str]:
            q = parse_qs(urlparse(self.path).query)
            return {k: v[0] for k, v in q.items()}

        def do_OPTIONS(self):  # noqa: N802
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self):  # noqa: N802
            if not on_get:
                self._write_json(405, {"error": "method not allowed"})
                return
            try:
                status, body = on_get(self._query())
            except Exception as e:
                traceback.print_exc()
                self._write_json(500, {"error": f"{type(e).__name__}: {e}"})
                return
            self._write_json(status, body)

        def do_POST(self):  # noqa: N802
            if not on_post:
                self._write_json(405, {"error": "method not allowed"})
                return
            length = int(self.headers.get("content-length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw or b"{}")
            except Exception:
                body = {}
            try:
                status, resp = on_post(body, self._query())
            except Exception as e:
                traceback.print_exc()
                self._write_json(500, {"error": f"{type(e).__name__}: {e}"})
                return
            self._write_json(status, resp)

    return H
