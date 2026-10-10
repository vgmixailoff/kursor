#!/usr/bin/env python3
"""Render inline diagrams from Gemini INLINE*_ONIMAGE strings.

Not a text poster: architecture / columns / stats / rows that fill 16:9.
Optional maya_pro badge on inlines only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from excalibur_blog_cover_brand_watermark import load_cfg, make_badge  # noqa: E402

INK = (22, 22, 22)
BG = (245, 241, 232)
PANEL = (24, 24, 24)
CREAM = (252, 249, 243)
ACCENT = (176, 72, 32)
MUTED = (90, 86, 80)
WHITE = (255, 255, 255)

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
)


def project_root() -> Path:
    env_root = os.environ.get("EXCALIBUR_PROJECT_ROOT", "").strip()
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parents[1]


def _lines_from_onimage(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[\n|;•·]+", text or "") if p.strip()]
    if len(parts) == 1 and "—" in parts[0]:
        parts = [p.strip() for p in parts[0].split("—") if p.strip()]
    return parts[:8] or ["факт"]


def _font(size: int, *, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = FONT_CANDIDATES if bold else (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        *FONT_CANDIDATES,
    )
    for path in paths:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _text_w(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return max(1, bbox[2] - bbox[0])


def _text_h(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return max(1, bbox[3] - bbox[1])


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    raw = re.sub(r"\s+", " ", (text or "").strip())
    if not raw:
        return [""]
    words = raw.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        piece = word
        while _text_w(draw, piece, font) > max_width and len(piece) > 1:
            cut = max(1, len(piece) // 2)
            while cut > 1 and _text_w(draw, piece[:cut], font) > max_width:
                cut -= 1
            chunk = piece[:cut]
            trial = (current + " " + chunk).strip() if current else chunk
            if current and _text_w(draw, trial, font) > max_width:
                lines.append(current)
                current = chunk
            else:
                current = trial
            piece = piece[cut:]
        trial = (current + " " + piece).strip() if current else piece
        if _text_w(draw, trial, font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = piece
    if current:
        lines.append(current)
    return lines or [raw]


def choose_layout(lines: list[str]) -> str:
    title = (lines[0] if lines else "").casefold()
    blob = " ".join(lines).casefold()
    if any(token in title for token in ("ограничен", "беты", "лимит", "нюанс")):
        return "rows"
    if any(
        token in blob
        for token in ("процент", "кратн", "×", "x6", "30%", "шести", "самоотчет")
    ):
        return "stats"
    if any(token in title for token in ("архитектур", "схема")) or (
        "координатор" in blob and "субагент" in blob
    ):
        return "architecture"
    if any(token in blob for token in ("паттерн", "сценари")):
        return "columns"
    return "rows"


_STAT_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (
        re.compile(r"\+?\s*30\s*%|\bтридцат\w*(?:\s+процент\w*)?", re.I),
        "+30%",
        "принятых пулл-реквестов",
    ),
    (
        re.compile(r"×\s*6|\bx6\b|шестикратн\w*", re.I),
        "×6",
        "ускорение для основных пользователей",
    ),
    (
        re.compile(
            r"20\s*[–\-]\s*100|(?:от\s+)?двадцат\w*\s+до\s+ста(?:\s+задач\w*)?",
            re.I,
        ),
        "20–100",
        "задач в день",
    ),
)


def _rest_caption(item: str, match: re.Match[str], fallback: str) -> str:
    rest = (item[: match.start()] + " " + item[match.end() :]).strip()
    rest = re.sub(r"\s+", " ", rest)
    rest = rest.strip(" :,;.–—-")
    rest = re.sub(r"\s+(на|от|до|в|для)$", "", rest, flags=re.I)
    rest = re.sub(r"^(на|от|до|в|для)\s+", "", rest, flags=re.I)
    if re.match(r"^(ное|ые|ый|ая|ых|ов|ами)\b", rest, flags=re.I):
        return fallback
    if match.end() - match.start() > max(18, int(len(item) * 0.45)):
        return fallback
    if len(rest) >= 12:
        return rest[0].upper() + rest[1:]
    return fallback


def extract_stats(items: list[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    used: set[int] = set()
    for pattern, number, fallback in _STAT_RULES:
        for idx, item in enumerate(items):
            if idx in used:
                continue
            match = pattern.search(item)
            if not match:
                continue
            out.append((number, _rest_caption(item, match, fallback)))
            used.add(idx)
            break
    for idx, item in enumerate(items):
        if idx in used:
            continue
        if len(out) >= 3:
            break
        head = re.match(
            r"^([+\-×xX]?\s*\d+(?:\s*[–\-]\s*\d+)?\s*%?)\s+(.*)$", item
        )
        if head and head.group(2).strip():
            out.append((head.group(1).replace(" ", ""), head.group(2).strip()))
        else:
            out.append((item[:12], item))
    return out[:3]


def split_heading(item: str, default: str) -> tuple[str, str]:
    raw = (item or "").strip()
    if not raw:
        return default, ""
    dashed = re.match(r"^([^:–—]{2,28})\s*[:–—]\s+(.+)$", raw)
    if dashed:
        return dashed.group(1).strip(), dashed.group(2).strip()
    words = raw.split()
    if len(words) >= 2 and words[0].casefold() in {"общая", "shared"}:
        return " ".join(words[:2]), " ".join(words[2:])
    if len(words) >= 2 and len(words[0]) <= 18:
        return words[0], " ".join(words[1:])
    return default, raw


def _draw_wrapped_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    box: tuple[int, int, int, int],
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    align: str = "left",
    valign: str = "center",
    max_lines: int = 5,
) -> None:
    x0, y0, x1, y1 = box
    max_w = max(40, x1 - x0)
    lines = wrap_text(draw, text, font, max_w)[:max_lines]
    line_h = _text_h(draw, "Ag", font) + 8
    total_h = line_h * len(lines)
    if valign == "top":
        y = y0
    else:
        y = y0 + max(0, (y1 - y0 - total_h) // 2)
    for line in lines:
        width = _text_w(draw, line, font)
        if align == "center":
            x = x0 + max(0, (max_w - width) // 2)
        else:
            x = x0
        draw.text((x, y), line, fill=fill, font=font)
        y += line_h


def _round_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int],
) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def _arrow_down(draw: ImageDraw.ImageDraw, x: int, y0: int, y1: int) -> None:
    draw.line((x, y0, x, y1 - 12), fill=ACCENT, width=5)
    draw.polygon([(x - 10, y1 - 14), (x + 10, y1 - 14), (x, y1)], fill=ACCENT)


def _render_node(
    draw: ImageDraw.ImageDraw,
    item: str,
    *,
    default: str,
    box: tuple[int, int, int, int],
    fill: tuple[int, int, int],
) -> None:
    heading, rest = split_heading(item, default)
    _round_rect(draw, box, 16, fill)
    head_font = _font(26)
    body_font = _font(20, bold=False)
    x0, y0, x1, y1 = box
    head_box = (x0 + 18, y0 + 16, x1 - 18, y0 + 70)
    _draw_wrapped_block(
        draw,
        heading,
        box=head_box,
        font=head_font,
        fill=WHITE,
        align="center",
        max_lines=2,
    )
    if rest:
        _draw_wrapped_block(
            draw,
            rest,
            box=(x0 + 18, y0 + 78, x1 - 18, y1 - 16),
            font=body_font,
            fill=(235, 230, 222),
            align="center",
            valign="top",
            max_lines=4,
        )


def _render_architecture(
    draw: ImageDraw.ImageDraw,
    items: list[str],
    *,
    width: int,
    height: int,
    header_h: int,
) -> None:
    pad = 48
    top = header_h + 24
    coord_h = 132
    coord = (pad + 80, top, width - pad - 80, top + coord_h)
    bottom_top = coord[3] + 56
    box_h = height - pad - bottom_top
    mid = width // 2
    left = (pad, bottom_top, mid - 18, bottom_top + box_h)
    right = (mid + 18, bottom_top, width - pad, bottom_top + box_h)
    left_cx = (left[0] + left[2]) // 2
    right_cx = (right[0] + right[2]) // 2
    fork_y = coord[3] + 20
    draw.line((width // 2, coord[3], width // 2, fork_y), fill=ACCENT, width=5)
    draw.line((left_cx, fork_y, right_cx, fork_y), fill=ACCENT, width=5)
    _arrow_down(draw, left_cx, fork_y, bottom_top)
    _arrow_down(draw, right_cx, fork_y, bottom_top)
    _render_node(
        draw,
        items[0] if items else "Координатор",
        default="Координатор",
        box=coord,
        fill=PANEL,
    )
    _render_node(
        draw,
        items[1] if len(items) > 1 else "Субагенты",
        default="Субагенты",
        box=left,
        fill=ACCENT,
    )
    _render_node(
        draw,
        items[2] if len(items) > 2 else "Общая память",
        default="Общая память",
        box=right,
        fill=PANEL,
    )


def _render_columns(
    draw: ImageDraw.ImageDraw,
    items: list[str],
    *,
    width: int,
    height: int,
    header_h: int,
) -> None:
    pad = 40
    top = header_h + 28
    n = max(1, min(3, len(items) or 1))
    while len(items) < n:
        items.append("")
    gap = 20
    usable = width - pad * 2 - gap * (n - 1)
    col_w = usable // n
    bottom = height - pad
    fonts = _font(24)
    for i in range(n):
        x0 = pad + i * (col_w + gap)
        x1 = x0 + col_w
        _round_rect(draw, (x0, top, x1, bottom), 18, PANEL if i != 1 else ACCENT)
        num_font = _font(48)
        num = str(i + 1)
        nw = _text_w(draw, num, num_font)
        draw.text((x0 + (col_w - nw) // 2, top + 24), num, fill=WHITE, font=num_font)
        _draw_wrapped_block(
            draw,
            items[i],
            box=(x0 + 18, top + 100, x1 - 18, bottom - 24),
            font=fonts,
            fill=WHITE,
            align="center",
            max_lines=6,
        )


def _render_stats(
    draw: ImageDraw.ImageDraw,
    items: list[str],
    *,
    width: int,
    height: int,
    header_h: int,
) -> None:
    stats = extract_stats(items)
    if not stats:
        stats = [(str(i + 1), line) for i, line in enumerate(items[:3])]
    pad = 40
    top = header_h + 28
    n = len(stats)
    gap = 20
    usable = width - pad * 2 - gap * (n - 1)
    col_w = usable // n
    bottom = height - pad
    for i, (number, caption) in enumerate(stats):
        x0 = pad + i * (col_w + gap)
        x1 = x0 + col_w
        _round_rect(draw, (x0, top, x1, bottom), 18, PANEL)
        draw.rectangle((x0, top, x0 + 10, bottom), fill=ACCENT)
        num_font = _font(56)
        cap_font = _font(22, bold=False)
        _draw_wrapped_block(
            draw,
            number,
            box=(x0 + 24, top + 36, x1 - 18, top + 160),
            font=num_font,
            fill=WHITE,
            align="left",
            max_lines=2,
        )
        _draw_wrapped_block(
            draw,
            caption,
            box=(x0 + 24, top + 180, x1 - 22, bottom - 28),
            font=cap_font,
            fill=(230, 226, 218),
            align="left",
            max_lines=5,
        )


def _render_rows(
    draw: ImageDraw.ImageDraw,
    items: list[str],
    *,
    width: int,
    height: int,
    header_h: int,
) -> None:
    pad = 40
    top = header_h + 24
    bottom = height - pad
    n = max(1, min(4, len(items) or 1))
    items = items[:n]
    gap = 16
    row_h = (bottom - top - gap * (n - 1)) // n
    body_font = _font(26)
    num_font = _font(34)
    for i, item in enumerate(items):
        y0 = top + i * (row_h + gap)
        y1 = y0 + row_h
        _round_rect(draw, (pad, y0, width - pad, y1), 16, CREAM)
        draw.rectangle((pad, y0, pad + 14, y1), fill=ACCENT)
        num = str(i + 1)
        draw.text((pad + 36, y0 + 18), num, fill=ACCENT, font=num_font)
        _draw_wrapped_block(
            draw,
            item,
            box=(pad + 88, y0 + 16, width - pad - 28, y1 - 16),
            font=body_font,
            fill=INK,
            align="left",
            max_lines=4,
        )


def _paste_brand_badge(img: Image.Image, width: int) -> Image.Image:
    try:
        badge = make_badge(project_root(), load_cfg(project_root()))
    except Exception:
        return img
    target_w = min(210, max(150, int(width * 0.18)))
    ratio = target_w / max(1, badge.width)
    badge = badge.resize(
        (target_w, max(1, int(badge.height * ratio))),
        Image.Resampling.LANCZOS,
    )
    img_rgba = img.convert("RGBA")
    img_rgba.paste(badge, (width - badge.width - 16, 16), badge)
    return img_rgba.convert("RGB")


def render_fact_card(
    lines: list[str],
    *,
    out_path: Path,
    width: int = 1200,
    height: int = 675,
    badge_path: Path | None = None,
    with_badge: bool = False,
    layout: str | None = None,
) -> str:
    clean = [ln.strip() for ln in lines if str(ln).strip()]
    title = clean[0] if clean else "Схема"
    items = clean[1:] or clean
    kind = layout or choose_layout(clean)

    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)
    header_h = 92
    draw.rectangle((0, 0, width, header_h), fill=PANEL)
    title_font = _font(34)
    wrapped_title = wrap_text(draw, title, title_font, width - 260)
    y = 22
    for line in wrapped_title[:2]:
        draw.text((36, y), line, fill=WHITE, font=title_font)
        y += _text_h(draw, line, title_font) + 6

    if kind == "architecture":
        _render_architecture(
            draw, items, width=width, height=height, header_h=header_h
        )
    elif kind == "columns":
        _render_columns(
            draw, items, width=width, height=height, header_h=header_h
        )
    elif kind == "stats":
        _render_stats(draw, items, width=width, height=height, header_h=header_h)
    else:
        _render_rows(draw, items, width=width, height=height, header_h=header_h)

    if with_badge or (badge_path and badge_path.is_file()):
        img = _paste_brand_badge(img, width)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    return kind


def inject_inline_figures(html: str, panels: list[dict]) -> str:
    """Replace data-slot=inline_N figures; park after a paragraph, not next to screens."""
    out = html
    for panel in panels:
        slot = panel["slot"]
        src = panel["src"]
        alt = escape(panel["alt"], quote=True)
        pat = re.compile(
            rf'<figure\s+(?=[^>]*\bdata-slot="{re.escape(slot)}")[^>]*>[\s\S]*?</figure>\s*',
            re.I,
        )
        figure = (
            f'\n<figure class="inline-visual" data-slot="{slot}">\n'
            f'<img src="{src}" alt="{alt}" />\n'
            f"<figcaption>{alt}</figcaption>\n"
            f"</figure>\n"
        )
        # Writer may place a semantic slot next to the paragraph it explains.
        # Keep that placement instead of guessing from heading numbers.
        if pat.search(out):
            out = pat.sub(lambda _: figure, out, count=1)
            continue
        h2s = list(re.finditer(r"</h2>", out, flags=re.I))
        idx = panel.get("after_h2_index")
        if isinstance(idx, int) and 0 <= idx < len(h2s):
            pos = h2s[idx].end()
            after = out[pos:]
            para = re.search(r"</p>", after, flags=re.I)
            if para:
                pos = pos + para.end()
            out = out[:pos] + figure + out[pos:]
        else:
            # No matching section: still keep the visual by its explanation,
            # never after the article's concluding paragraph.
            para = re.search(r"</p>", out, flags=re.I)
            if para:
                out = out[:para.end()] + figure + out[para.end():]
            else:
                out = figure + out
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--article-dir", required=True)
    ap.add_argument("--inject-html", action="store_true")
    ap.add_argument("--with-badge", action="store_true", help="maya_pro badge on inlines")
    ap.add_argument("--slot", default="", help="render only inline_N (fallback for one AI visual)")
    ap.add_argument("--root", default=".")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    article_dir = Path(args.article_dir)
    if not article_dir.is_absolute():
        article_dir = (root / article_dir).resolve()

    gemini_path = article_dir / "gemini-article.json"
    cover_text_path = article_dir / "cover" / "cover-text.json"
    onimage: dict[str, str] = {}
    alts: dict[str, str] = {}
    if gemini_path.is_file():
        g = json.loads(gemini_path.read_text(encoding="utf-8"))
        for i in range(1, 5):
            on = str(g.get(f"INLINE{i}_ONIMAGE") or "").strip()
            if on:
                onimage[f"inline_{i}"] = on
                alts[f"inline_{i}"] = str(g.get(f"INLINE{i}_ALT") or on[:80]).strip()
    elif cover_text_path.is_file():
        ct = json.loads(cover_text_path.read_text(encoding="utf-8"))
        onimage = {k: str(v) for k, v in (ct.get("inline_onimage") or {}).items() if v}
        alts = {k: str(v) for k, v in (ct.get("inline_alts") or {}).items() if v}
        if not onimage:
            for k, labels in (ct.get("inline_labels") or {}).items():
                if isinstance(labels, list) and labels:
                    onimage[k] = "\n".join(str(x) for x in labels)

    if not onimage:
        # A useful screenshot can carry the point better than a diagram.
        # Do not invent a fact card merely to satisfy an image count.
        print(json.dumps({"status": "SKIP", "reason": "no INLINE*_ONIMAGE"}, ensure_ascii=False))
        return 0
    if args.slot:
        if args.slot not in onimage:
            print(json.dumps({"status": "FAIL", "errors": [f"{args.slot} missing"]}, ensure_ascii=False))
            return 1
        onimage = {args.slot: onimage[args.slot]}

    panels: list[dict] = []
    cover_dir = article_dir / "cover"
    for i, (slot, text) in enumerate(sorted(onimage.items())):
        n = slot.split("_")[-1]
        out_name = f"inline-{n.zfill(2)}.png"
        out_path = cover_dir / out_name
        kind = render_fact_card(
            _lines_from_onimage(text),
            out_path=out_path,
            with_badge=bool(args.with_badge),
        )
        panels.append(
            {
                "slot": slot,
                "src": f"cover/{out_name}",
                "alt": alts.get(slot) or text[:80],
                "after_h2_index": i,
                "layout": kind,
                "file": str(out_path),
            }
        )
        print(f"OK {out_path} layout={kind}")

    if args.inject_html:
        html_path = article_dir / "article.html"
        html = html_path.read_text(encoding="utf-8")
        html_path.write_text(inject_inline_figures(html, panels), encoding="utf-8")
        print("OK injected inline figures")

    report = {"status": "PASS", "panels": panels, "count": len(panels)}
    (cover_dir / "inline-fact-cards.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": "PASS", "count": len(panels)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
