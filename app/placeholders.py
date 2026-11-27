"""On-brand placeholder artwork (SVG) and app icons (PNG), generated locally.

The shop never depends on external image hosting: ``python seed.py`` (re)writes
every image into ``app/static/img``. Each function returns an SVG string.
"""
from __future__ import annotations

import re
import struct
import unicodedata
import zlib
from pathlib import Path

IMG_DIR = Path(__file__).resolve().parent / "static" / "img"

GOLD = "#C9A227"
FONT = "Helvetica Neue, Helvetica, Arial, sans-serif"

# (highlight, shadow) colour pairs for metallic gradients.
METALS = {
    "goud": ("#F1D78A", "#A8861C"),
    "zilver": ("#F4F4F5", "#85858D"),
    "rose": ("#F3C9B1", "#A8714F"),
    "zwart": ("#5A5A63", "#141416"),
    "titanium": ("#CDD0D6", "#575B62"),
}


# --------------------------------------------------------------------------- #
# Building blocks
# --------------------------------------------------------------------------- #
def _is_dark(hex_color: str) -> bool:
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return (0.299 * r + 0.587 * g + 0.114 * b) < 140


def _metal(gid: str, metal: str) -> str:
    light, dark = METALS[metal]
    return (
        f'<linearGradient id="{gid}" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{light}"/><stop offset=".5" stop-color="{dark}"/>'
        f'<stop offset="1" stop-color="{light}"/></linearGradient>'
    )


def _canvas(body: str, defs: str = "") -> str:
    """Dark studio backdrop with a soft gold glow and floor shadow."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 800" width="800" height="800">'
        "<defs>"
        '<radialGradient id="bg" cx="50%" cy="38%" r="80%">'
        '<stop offset="0" stop-color="#26262B"/><stop offset="1" stop-color="#0B0B0C"/></radialGradient>'
        '<radialGradient id="glow" cx="50%" cy="50%" r="50%">'
        f'<stop offset="0" stop-color="{GOLD}" stop-opacity=".16"/>'
        f'<stop offset="1" stop-color="{GOLD}" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="sheen" cx="35%" cy="25%" r="75%">'
        '<stop offset="0" stop-color="#fff" stop-opacity=".14"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        f"{defs}</defs>"
        '<rect width="800" height="800" fill="url(#bg)"/>'
        '<circle cx="400" cy="400" r="330" fill="url(#glow)"/>'
        '<ellipse cx="400" cy="738" rx="210" ry="20" fill="#000" opacity=".5"/>'
        f"{body}</svg>"
    )


def _strap_piece(x: float, y: float, w: float, h: float, color: str, stitched: bool = True) -> str:
    svg = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="28" fill="{color}"/>'
    if stitched:
        svg += (
            f'<rect x="{x + 11}" y="{y + 11}" width="{w - 22}" height="{h - 22}" rx="20" fill="none" '
            'stroke="#fff" stroke-opacity=".16" stroke-width="2" stroke-dasharray="7 6"/>'
        )
    return svg


# --------------------------------------------------------------------------- #
# Products
# --------------------------------------------------------------------------- #
def analog_watch(
    metal: str = "goud",
    dial: str = "#111113",
    strap: str = "#18181B",
    hour: int = 10,
    minute: int = 9,
    chrono: bool = False,
    label: str = "AUTOMATIC",
) -> str:
    """Classic three-hand watch, optionally with chronograph sub-dials."""
    ink = METALS[metal][0] if _is_dark(dial) else "#27272A"
    parts = [
        _strap_piece(322, 40, 156, 240, strap),
        _strap_piece(322, 520, 156, 240, strap),
        '<rect x="602" y="376" width="38" height="48" rx="9" fill="url(#case)"/>',  # crown
        '<circle cx="400" cy="410" r="216" fill="#000" opacity=".35"/>',
        '<circle cx="400" cy="400" r="214" fill="url(#case)"/>',
        '<circle cx="400" cy="400" r="196" fill="#0A0A0B" opacity=".55"/>',
        f'<circle cx="400" cy="400" r="188" fill="{dial}"/>',
        '<circle cx="400" cy="400" r="188" fill="url(#sheen)"/>',
        f'<circle cx="400" cy="400" r="176" fill="none" stroke="{ink}" stroke-opacity=".25" '
        'stroke-width="1.5" stroke-dasharray="1.5 16.9"/>',
    ]
    for i in range(12):
        major = i % 3 == 0
        w, h = (9, 34) if major else (4, 20)
        parts.append(
            f'<rect x="{400 - w / 2}" y="228" width="{w}" height="{h}" rx="2" fill="{ink}" '
            f'transform="rotate({i * 30} 400 400)"/>'
        )
    parts.append(
        f'<text x="400" y="326" text-anchor="middle" font-family="{FONT}" font-size="17" '
        f'font-weight="600" letter-spacing="5" fill="{ink}">TIME SQUARE</text>'
    )
    parts.append(
        f'<text x="400" y="494" text-anchor="middle" font-family="{FONT}" font-size="11" '
        f'letter-spacing="4" fill="{ink}" opacity=".7">{label}</text>'
    )
    if chrono:
        for cx in (322, 478):
            parts.append(
                f'<circle cx="{cx}" cy="400" r="38" fill="#000" fill-opacity=".18" stroke="{ink}" '
                f'stroke-opacity=".5" stroke-width="2"/>'
                f'<rect x="{cx - 1.5}" y="370" width="3" height="32" rx="1.5" fill="{GOLD}" '
                f'transform="rotate({140 if cx < 400 else 250} {cx} 400)"/>'
            )
    hour_angle = (hour % 12) * 30 + minute * 0.5
    parts += [
        f'<rect x="393" y="292" width="14" height="122" rx="7" fill="{ink}" transform="rotate({hour_angle} 400 400)"/>',
        f'<rect x="396" y="236" width="8" height="178" rx="4" fill="{ink}" transform="rotate({minute * 6} 400 400)"/>',
        f'<rect x="398.5" y="226" width="3" height="214" rx="1.5" fill="{GOLD}" transform="rotate(200 400 400)"/>',
        '<circle cx="400" cy="400" r="13" fill="url(#case)"/>',
        f'<circle cx="400" cy="400" r="5" fill="{GOLD}"/>',
    ]
    return _canvas("".join(parts), _metal("case", metal))


def smart_watch(
    metal: str = "zwart",
    band: str = "#18181B",
    slim: bool = False,
    date: str = "VR 27 NOV",
    stat: str = "72 BPM",
    progress: float = 0.68,
) -> str:
    """Smartwatch (or slim fitness tracker) with a lit-up watch face."""
    w, h, rx, bw = (176, 330, 82, 124) if slim else (300, 364, 90, 184)
    x, y = 400 - w / 2, 400 - h / 2
    pad = 15
    sx, sy, sw, sh = x + pad, y + pad, w - 2 * pad, h - 2 * pad
    time_size, bar_w = (54, 96) if slim else (80, 176)
    parts = [
        _strap_piece(400 - bw / 2, 30, bw, y - 30 + 60, band, stitched=False),
        _strap_piece(400 - bw / 2, y + h - 60, bw, 770 - (y + h - 60), band, stitched=False),
        f'<rect x="{x + w - 8}" y="{400 - 74}" width="22" height="60" rx="10" fill="url(#case)"/>',
        f'<rect x="{x + w - 8}" y="{400 + 4}" width="18" height="40" rx="8" fill="url(#case)"/>',
        f'<rect x="{x}" y="{y + 10}" width="{w}" height="{h}" rx="{rx}" fill="#000" opacity=".35"/>',
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="url(#case)"/>',
        f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="{rx - 13}" fill="#050506"/>',
        f'<text x="400" y="{sy + sh * 0.27}" text-anchor="middle" font-family="{FONT}" '
        f'font-size="{14 if slim else 18}" font-weight="600" letter-spacing="3" fill="{GOLD}">{date}</text>',
        f'<text x="400" y="{sy + sh * 0.52}" text-anchor="middle" font-family="{FONT}" '
        f'font-size="{time_size}" font-weight="600" fill="#FAFAFA">10:09</text>',
        f'<circle cx="{400 - (34 if slim else 52)}" cy="{sy + sh * 0.66 - 6}" r="{5 if slim else 7}" fill="{GOLD}"/>',
        f'<text x="{400 - (22 if slim else 36)}" y="{sy + sh * 0.66}" font-family="{FONT}" '
        f'font-size="{14 if slim else 20}" fill="#D4D4D8">{stat}</text>',
        f'<rect x="{400 - bar_w / 2}" y="{sy + sh * 0.77}" width="{bar_w}" height="8" rx="4" fill="#27272A"/>',
        f'<rect x="{400 - bar_w / 2}" y="{sy + sh * 0.77}" width="{bar_w * progress}" height="8" rx="4" fill="{GOLD}"/>',
        f'<rect x="{sx}" y="{sy}" width="{sw}" height="{sh}" rx="{rx - 13}" fill="url(#sheen)"/>',
    ]
    return _canvas("".join(parts), _metal("case", metal))


def strap(color: str = "#8B5A2B", buckle: str = "zilver", stitched: bool = True, holes: int = 4) -> str:
    """A loose two-piece watch strap with buckle, shown at an angle."""
    parts = ['<g transform="rotate(-28 400 400)">']
    parts.append('<rect x="325" y="62" width="150" height="14" rx="7" fill="url(#case)"/>')  # spring bar
    parts.append(_strap_piece(340, 70, 120, 320, color, stitched))
    parts.append(_strap_piece(340, 420, 120, 320, color, stitched))
    parts.append('<rect x="340" y="420" width="120" height="320" rx="28" fill="#000" opacity=".12"/>')
    for i in range(holes):
        parts.append(f'<circle cx="400" cy="{540 + i * (150 / max(holes - 1, 1))}" r="7" fill="#0B0B0C" opacity=".8"/>')
    parts.append('<rect x="326" y="318" width="148" height="74" rx="18" fill="none" stroke="url(#case)" stroke-width="12"/>')
    parts.append('<rect x="396" y="318" width="8" height="84" rx="4" fill="url(#case)"/>')  # buckle pin
    parts.append('<rect x="334" y="444" width="132" height="22" rx="7" fill="#000" opacity=".28"/>')  # keeper
    parts.append("</g>")
    return _canvas("".join(parts), _metal("case", buckle))


def charger(metal: str = "zwart") -> str:
    """Magnetic charging puck with a USB-C cable."""
    parts = [
        '<path d="M400 470 C 400 620, 590 580, 600 790" fill="none" stroke="#2A2A2F" stroke-width="20" stroke-linecap="round"/>',
        '<circle cx="400" cy="412" r="172" fill="#000" opacity=".35"/>',
        '<circle cx="400" cy="400" r="170" fill="url(#case)"/>',
        '<circle cx="400" cy="400" r="142" fill="#121214"/>',
        '<circle cx="400" cy="400" r="142" fill="url(#sheen)"/>',
        f'<circle cx="400" cy="400" r="104" fill="none" stroke="{GOLD}" stroke-width="4" opacity=".85"/>',
        f'<rect x="372" y="372" width="56" height="56" fill="none" stroke="{GOLD}" stroke-width="7"/>',
        f'<rect x="392" y="392" width="16" height="16" fill="{GOLD}"/>',
    ]
    return _canvas("".join(parts), _metal("case", metal))


def watch_box() -> str:
    """Walnut storage box (top view) with six cushions."""
    defs = (
        '<linearGradient id="wood" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#8A5530"/><stop offset=".5" stop-color="#5A3419"/>'
        '<stop offset="1" stop-color="#7A4A28"/></linearGradient>'
    )
    metals = ["goud", "zilver", "zwart", "rose", "titanium", None]
    defs += "".join(_metal(f"m{i}", m) for i, m in enumerate(metals) if m)
    parts = [
        '<rect x="110" y="200" width="580" height="420" rx="34" fill="#000" opacity=".35"/>',
        '<rect x="110" y="190" width="580" height="420" rx="34" fill="url(#wood)"/>',
        '<rect x="138" y="218" width="524" height="364" rx="22" fill="#141416"/>',
    ]
    for i, metal in enumerate(metals):
        cx, cy = 157 + (i % 3) * 168, 234 + (i // 3) * 172
        parts.append(f'<rect x="{cx}" y="{cy}" width="150" height="160" rx="28" fill="#26262B"/>')
        if metal:
            mx, my = cx + 75, cy + 80
            parts.append(
                f'<circle cx="{mx}" cy="{my}" r="46" fill="url(#m{i})"/>'
                f'<circle cx="{mx}" cy="{my}" r="37" fill="#0F0F11"/>'
                f'<rect x="{mx - 2}" y="{my - 28}" width="4" height="30" rx="2" fill="#E4E4E7" transform="rotate(300 {mx} {my})"/>'
                f'<rect x="{mx - 1.5}" y="{my - 32}" width="3" height="34" rx="1.5" fill="#E4E4E7" transform="rotate(55 {mx} {my})"/>'
            )
    parts.append('<rect x="110" y="190" width="580" height="420" rx="34" fill="url(#sheen)"/>')
    return _canvas("".join(parts), defs)


# --------------------------------------------------------------------------- #
# Brand assets
# --------------------------------------------------------------------------- #
LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
    '<rect width="64" height="64" rx="14" fill="#0B0B0C"/>'
    f'<rect x="16" y="16" width="32" height="32" fill="none" stroke="{GOLD}" stroke-width="4.5"/>'
    f'<rect x="28" y="28" width="8" height="8" fill="{GOLD}"/></svg>'
)


def _png_icon(size: int) -> bytes:
    """Encode the logo (gold square-in-square on black) as a PNG, without Pillow."""
    gold, bg = bytes((201, 162, 39)), bytes((11, 11, 12))
    margin, stroke = round(size * 0.25), max(2, round(size * 0.07))
    c0, c1 = round(size * 0.4375), size - round(size * 0.4375)
    rows = []
    for y in range(size):
        row = bytearray(b"\x00")  # filter type "None"
        for x in range(size):
            outer = margin <= x < size - margin and margin <= y < size - margin
            inner = margin + stroke <= x < size - margin - stroke and margin + stroke <= y < size - margin - stroke
            centre = c0 <= x < c1 and c0 <= y < c1
            row += gold if (outer and not inner) or centre else bg
        rows.append(bytes(row))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
        + chunk(b"IEND", b"")
    )


# --------------------------------------------------------------------------- #
# File output
# --------------------------------------------------------------------------- #
def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def write_image(rel_path: str, content: str | bytes) -> str:
    """Write an image below static/img and return its path relative to /static."""
    path = IMG_DIR / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return f"img/{rel_path}"


def write_brand_assets() -> None:
    """Hero image, category tiles and app icons."""
    write_image("hero.svg", analog_watch("goud", "#0E0E10", "#141416"))
    write_image("categories/klassiek.svg", analog_watch("zilver", "#13233F", "#2A1B12", 1, 50, chrono=True, label="CHRONOGRAPH"))
    write_image("categories/smartwatch.svg", smart_watch("zwart", "#1F1F23"))
    write_image("categories/accessoire.svg", strap("#8B5A2B", "zilver"))
    write_image("icon.svg", LOGO_SVG)
    for size in (180, 192, 512):
        write_image(f"icon-{size}.png", _png_icon(size))
