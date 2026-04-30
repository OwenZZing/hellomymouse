"""Generate a cute telescope icon for Hypothesis Maker."""
from PIL import Image, ImageDraw, ImageFont
import math, os

def make_icon(size: int) -> Image.Image:
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size

    # ── Background: rounded square, deep navy ──────────────────
    r = s // 6
    bg = (15, 25, 60, 255)        # deep navy
    d.rounded_rectangle([0, 0, s-1, s-1], radius=r, fill=bg)

    # ── Stars (small dots scattered in background) ──────────────
    stars = [
        (0.12, 0.18), (0.25, 0.10), (0.70, 0.12), (0.85, 0.20),
        (0.82, 0.70), (0.15, 0.75), (0.55, 0.85), (0.40, 0.92),
        (0.92, 0.45), (0.08, 0.50),
    ]
    for (fx, fy) in stars:
        x, y = int(fx * s), int(fy * s)
        sr = max(1, s // 64)
        d.ellipse([x-sr, y-sr, x+sr, y+sr], fill=(220, 230, 255, 200))

    # ── Telescope body ─────────────────────────────────────────
    # Diagonal tube: lower-left → upper-right
    cx, cy = s * 0.50, s * 0.52   # pivot (eyepiece end)
    angle = -38                    # degrees from horizontal

    def rot(px, py, ox, oy, deg):
        rad = math.radians(deg)
        dx, dy = px - ox, py - oy
        return (ox + dx*math.cos(rad) - dy*math.sin(rad),
                oy + dx*math.sin(rad) + dy*math.cos(rad))

    # Main barrel (thick trapezoid: narrow at eyepiece, wide at objective)
    barrel_len = s * 0.44
    ew = s * 0.075   # eyepiece half-width
    ow = s * 0.115   # objective half-width
    ox, oy = cx + barrel_len, cy  # objective center (before rotation)

    pts = [
        rot(cx - ew*0.6, cy - ew, cx, cy, angle),
        rot(cx - ew*0.6, cy + ew, cx, cy, angle),
        rot(ox,          oy + ow, cx, cy, angle),
        rot(ox,          oy - ow, cx, cy, angle),
    ]
    d.polygon(pts, fill=(100, 160, 240, 255))  # sky blue barrel

    # Barrel highlight stripe (lighter edge)
    pts_hi = [
        rot(cx - ew*0.5, cy - ew + 1, cx, cy, angle),
        rot(cx - ew*0.5, cy - ew*0.4, cx, cy, angle),
        rot(ox,          oy - ow + s*0.018, cx, cy, angle),
        rot(ox,          oy - ow + 1, cx, cy, angle),
    ]
    d.polygon(pts_hi, fill=(170, 210, 255, 160))

    # Objective lens cap (circle at big end)
    obj_cx, obj_cy = rot(ox, oy, cx, cy, angle)
    lens_r = ow * 1.05
    d.ellipse([obj_cx-lens_r, obj_cy-lens_r, obj_cx+lens_r, obj_cy+lens_r],
              fill=(50, 90, 180, 255), outline=(180, 210, 255, 255),
              width=max(1, s//80))
    # Lens glare dot
    glare_r = lens_r * 0.25
    d.ellipse([obj_cx - lens_r*0.35 - glare_r,
               obj_cy - lens_r*0.35 - glare_r,
               obj_cx - lens_r*0.35 + glare_r,
               obj_cy - lens_r*0.35 + glare_r],
              fill=(200, 230, 255, 200))

    # Eyepiece (small cylinder at narrow end)
    ep_cx, ep_cy = rot(cx, cy, cx, cy, angle)
    ep_r = ew * 0.85
    d.ellipse([ep_cx-ep_r, ep_cy-ep_r, ep_cx+ep_r, ep_cy+ep_r],
              fill=(60, 80, 140, 255), outline=(130, 170, 230, 255),
              width=max(1, s//80))

    # Band ring on barrel (decoration)
    band_fx = 0.55
    bx = cx + barrel_len * band_fx
    bw_half = ew + (ow - ew) * band_fx
    bpts = [
        rot(bx - s*0.018, by - bw_half - s*0.008, cx, cy, angle)
        for (bx, by) in [(bx, cy)]
    ]
    b1 = [
        rot(bx - s*0.018, cy - bw_half - s*0.01, cx, cy, angle),
        rot(bx - s*0.018, cy + bw_half + s*0.01, cx, cy, angle),
        rot(bx + s*0.018, cy + bw_half + s*0.01, cx, cy, angle),
        rot(bx + s*0.018, cy - bw_half - s*0.01, cx, cy, angle),
    ]
    d.polygon(b1, fill=(70, 110, 200, 255))

    # ── Tripod legs ────────────────────────────────────────────
    # Pivot point on barrel bottom
    piv = rot(cx + barrel_len * 0.45, cy, cx, cy, angle)
    bottom_y = s * 0.91
    leg_color = (80, 100, 160, 255)
    lw = max(1, s // 48)
    legs = [piv[0] - s*0.18, piv[0], piv[0] + s*0.14]
    for lx in legs:
        d.line([piv, (lx, bottom_y)], fill=leg_color, width=lw)
    # Foot bar
    d.line([(legs[0], bottom_y), (legs[2], bottom_y)], fill=leg_color, width=lw)

    # ── Sparkle star near objective lens ──────────────────────
    def sparkle(sx, sy, sr, color):
        for a in range(0, 360, 45):
            rad = math.radians(a)
            length = sr if a % 90 == 0 else sr * 0.55
            x2 = sx + math.cos(rad) * length
            y2 = sy + math.sin(rad) * length
            d.line([(sx, sy), (x2, y2)], fill=color, width=max(1, s//90))

    sparkle(int(obj_cx + s*0.12), int(obj_cy - s*0.10),
            s * 0.055, (255, 240, 130, 230))

    return img


def build_ico(out_path: str):
    sizes = [16, 32, 48, 64, 128, 256]
    frames = [make_icon(sz) for sz in sizes]
    frames[0].save(
        out_path,
        format='ICO',
        sizes=[(sz, sz) for sz in sizes],
        append_images=frames[1:],
    )
    print(f'Saved: {out_path}')


if __name__ == '__main__':
    out = os.path.join(os.path.dirname(__file__), 'icon.ico')
    build_ico(out)
