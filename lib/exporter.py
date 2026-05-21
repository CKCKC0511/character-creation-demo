"""导出选中角色到 Excel —— stateless 版本。

接受前端发来的完整数据 payload（characters + 丰容结果 + 图片 URL），
fetch 图片 URL 把字节嵌入 Excel，返回 base64 编码后的 .xlsx 给前端下载。
"""

from __future__ import annotations

import base64
import io
import time
from typing import Any

import requests
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from PIL import Image as PILImage

EMBED_MAX_H_PX = 1024
EMBED_DISPLAY_H_PX = 480

HEADERS = [
    "#",
    "Original Name", "Original Gender", "Original Tags",
    "Original Tagline", "Original Opener",
    "New Name", "New Tags", "New Tagline (cha_set)", "New Opener (cha_set)",
    "Card Tagline", "Card Opener", "User Background",
    "Character Portrait", "User Portrait",
]


def _safe(s: Any) -> str:
    if s is None:
        return ""
    if isinstance(s, list):
        return ", ".join(map(str, s))
    return str(s)


def _resize_for_excel(img_bytes: bytes, max_h_px: int = EMBED_MAX_H_PX) -> bytes:
    with PILImage.open(io.BytesIO(img_bytes)) as im:
        im.load()
        w, h = im.size
        if h > max_h_px:
            ratio = max_h_px / h
            im = im.resize((int(w * ratio), int(h * ratio)), PILImage.LANCZOS)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf.getvalue()


def _fetch_image(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception:
        return None


def export_to_excel(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """rows 来自前端，每个元素结构:
    {
      "character": {...},                   # tipsy 抓回来的原始 character dict
      "enrich": {...} or null,              # enrich_character() 返回值
      "char_portrait_url": "...",           # 第一张角色立绘 URL（可空）
      "user_portrait_url": "...",           # 第一张用户立绘 URL（可空）
    }
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Characters"

    header_font = Font(bold=True, color="FFFFFFFF", size=11)
    header_fill = PatternFill("solid", fgColor="1f1f28")
    for col_i, name in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=col_i, value=name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)

    widths = [4, 22, 12, 28, 48, 48, 22, 28, 56, 56, 48, 48, 32, 36, 36]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 30

    row_h = 380

    for row_i, row in enumerate(rows, start=2):
        ch = row.get("character") or {}
        enrich = (row.get("enrich") or {}).get("result") or {}
        cha_set = enrich.get("cha_set") or {}
        card = enrich.get("card") or {}
        user_set = enrich.get("user_set") or {}

        values = [
            row_i - 1,
            _safe(ch.get("name", "")),
            _safe(ch.get("gender", "")),
            _safe(ch.get("tags", [])),
            _safe(ch.get("introduction", "")),
            _safe(ch.get("greeting", "")),
            _safe(cha_set.get("name", "")),
            _safe(cha_set.get("core_tags", [])),
            _safe(cha_set.get("tagline", "")),
            _safe(cha_set.get("opener", "")),
            _safe(card.get("tagline", "")),
            _safe(card.get("opener", "")),
            _safe(user_set.get("background", "")),
            "", "",
        ]
        for col_i, v in enumerate(values, start=1):
            cell = ws.cell(row=row_i, column=col_i, value=v)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        ws.row_dimensions[row_i].height = row_h

        for col_letter, key, col_i in (
            ("N", "char_portrait_url", 14),
            ("O", "user_portrait_url", 15),
        ):
            url = row.get(key)
            if not url:
                continue
            raw = _fetch_image(url)
            if not raw:
                ws.cell(row=row_i, column=col_i, value="[image fetch failed]")
                continue
            try:
                img_bytes = _resize_for_excel(raw)
                xli = XLImage(io.BytesIO(img_bytes))
                xli.height = EMBED_DISPLAY_H_PX
                xli.width = int(EMBED_DISPLAY_H_PX * 9 / 16)
                ws.add_image(xli, f"{col_letter}{row_i}")
            except Exception as e:
                ws.cell(row=row_i, column=col_i, value=f"[image error] {e}")

    buf = io.BytesIO()
    wb.save(buf)
    raw = buf.getvalue()
    b64 = base64.b64encode(raw).decode("ascii")
    ts = time.strftime("%Y%m%d_%H%M%S")
    return {
        "ok": True,
        "filename": f"characters_export_{ts}.xlsx",
        "content_b64": b64,
        "size": len(raw),
        "count": len(rows),
    }
