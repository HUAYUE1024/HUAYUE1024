"""Tiny typesetting engine: shape text with HarfBuzz, emit SVG <path>s via fontTools.

Rendering text as outlines means the README looks identical on every OS —
no dependency on whatever fonts the viewer happens to have installed.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONTS = Path(__file__).with_name("fonts")


def _num(v: float) -> str:
    s = f"{v:.1f}"
    return s[:-2] if s.endswith(".0") else s


class Font:
    def __init__(self, file: str, **axes: float):
        path = FONTS / file
        self.tt = TTFont(path)
        self.upm = self.tt["head"].unitsPerEm
        loc = {k: v for k, v in axes.items()} if "fvar" in self.tt else {}
        self.glyphs = self.tt.getGlyphSet(location=loc or None)
        self.order = self.tt.getGlyphOrder()
        self.hb = hb.Font(hb.Face(hb.Blob.from_file_path(str(path))))
        if loc:
            self.hb.set_variations(loc)

    def _shape(self, text: str):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {"kern": True, "liga": True, "calt": True})
        return buf.glyph_infos, buf.glyph_positions

    def width(self, text: str, size: float, tracking: float = 0) -> float:
        if not text:
            return 0.0
        _, pos = self._shape(text)
        return sum(p.x_advance + tracking * self.upm for p in pos) * size / self.upm - tracking * size

    def path(self, text: str, size: float, x: float, y: float, tracking: float = 0) -> str:
        if not text:
            return ""
        infos, pos = self._shape(text)
        s = size / self.upm
        pen_x, out = 0.0, []
        for info, p in zip(infos, pos):
            pen = SVGPathPen(self.glyphs, ntos=_num)
            t = (s, 0, 0, -s, x + (pen_x + p.x_offset) * s, y - p.y_offset * s)
            self.glyphs[self.order[info.codepoint]].draw(TransformPen(pen, t))
            out.append(pen.getCommands())
            pen_x += p.x_advance + tracking * self.upm
        return "".join(out)


@lru_cache(maxsize=None)
def font(file: str, **axes: float) -> Font:
    return Font(file, **axes)


def text(f: Font, s: str, size: float, x: float, y: float, *, anchor: str = "start",
         tracking: float = 0, max_w: float | None = None, **attrs) -> tuple[str, float]:
    """Return (<path .../>, rendered width). anchor: start | middle | end."""
    w = f.width(s, size, tracking)
    if max_w and w > max_w:
        size *= max_w / w
        w = max_w
    if anchor == "middle":
        x -= w / 2
    elif anchor == "end":
        x -= w
    a = " ".join(f'{k.rstrip("_").replace("_", "-")}="{v}"' for k, v in attrs.items())
    return f'<path d="{f.path(s, size, x, y, tracking)}" {a}/>', w


_CJK_RE = re.compile(r"([\u2e80-\u9fff\uff00-\uffef]+)")


def mixed_text(latin_f: Font, cjk_f: Font, s: str, size: float, x: float, y: float, *,
               cjk_scale: float = 0.94, tracking: float = 0.02, **attrs) -> tuple[str, float]:
    """Shape mixed Latin + CJK text into a single SVG <path>."""
    parts = [p for p in _CJK_RE.split(s) if p]
    cx, d_parts = x, []
    for p in parts:
        is_cjk = bool(_CJK_RE.match(p))
        f = cjk_f if is_cjk else latin_f
        sz = size * cjk_scale if is_cjk else size
        tr = tracking * 1.4 if is_cjk else tracking
        d_parts.append(f.path(p, sz, cx, y, tr))
        cx += f.width(p, sz, tr) + (size * 0.04 if len(parts) > 1 else 0)
    a = " ".join(f'{k.rstrip("_").replace("_", "-")}="{v}"' for k, v in attrs.items())
    return f'<path d="{"".join(d_parts)}" {a}/>', cx - x
