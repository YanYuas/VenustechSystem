# 生成 PWA 图标（启明星：奶油底 + 粉色五角星）
# 用法：backend/.venv/Scripts/python.exe scripts/gen_pwa_icons.py
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

FRONTEND_PUBLIC = Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "icons"
BG = (255, 251, 245, 255)      # --bg-page 奶油
STAR = (255, 143, 163, 255)    # --primary 粉
RING = (255, 217, 122, 255)    # --butter 金


def star_points(cx: float, cy: float, outer: float, inner: float) -> list[tuple[float, float]]:
    pts = []
    for i in range(10):
        r = outer if i % 2 == 0 else inner
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def make(size: int, maskable: bool) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG)
    d = ImageDraw.Draw(img)
    # 安全区：maskable 图标内容缩进 20%
    pad = int(size * (0.22 if maskable else 0.10))
    cx = cy = size / 2
    outer = (size - 2 * pad) / 2
    # 底部金环（升起的星轨意象）
    ring_w = max(2, size // 48)
    d.arc([cx - outer, cy - outer * 0.2, cx + outer, cy + outer * 1.2],
          start=200, end=340, fill=RING, width=ring_w)
    d.polygon(star_points(cx, cy - size * 0.02, outer * 0.62, outer * 0.26), fill=STAR)
    return img


def main() -> None:
    FRONTEND_PUBLIC.mkdir(parents=True, exist_ok=True)
    for s in (192, 512):
        make(s, maskable=False).save(FRONTEND_PUBLIC / f"icon-{s}.png")
    make(512, maskable=True).save(FRONTEND_PUBLIC / "maskable-512.png")
    make(180, maskable=False).save(FRONTEND_PUBLIC / "apple-touch-icon.png")
    print("icons written to", FRONTEND_PUBLIC)


if __name__ == "__main__":
    main()
