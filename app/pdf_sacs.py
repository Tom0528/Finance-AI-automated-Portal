"""
SACS PDF Generator – Simple Automated Cashflow System
Matches the visual layout from the reference screenshots.
"""
import io
import math
import os
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white, black

_HERE = os.path.dirname(os.path.abspath(__file__))
_IMG  = os.path.join(_HERE, "static", "images")

IMG_DOLLAR  = os.path.join(_IMG, "dollar_sign.jpg")
IMG_DOCS    = os.path.join(_IMG, "piled_docs.png")
IMG_PIG     = os.path.join(_IMG, "piggy_bank.png")

# Navy RGB components for pig-background replacement
_NAVY_RGB = (26, 58, 107)


def _processed_pig():
    """Return path to a pig image whose white background is replaced with navy."""
    out = os.path.join(_IMG, "piggy_bank_navy.png")
    if os.path.exists(out):
        return out
    try:
        from PIL import Image, ImageChops
        img = Image.open(IMG_PIG).convert("RGBA")
        r, g, b, a = img.split()
        hi = lambda v: 255 if v > 215 else 0
        wm = ImageChops.multiply(
                ImageChops.multiply(r.point(hi), g.point(hi)), b.point(hi))
        nr = Image.new('L', img.size, _NAVY_RGB[0])
        ng = Image.new('L', img.size, _NAVY_RGB[1])
        nb = Image.new('L', img.size, _NAVY_RGB[2])
        Image.merge('RGBA', (
            Image.composite(nr, r, wm),
            Image.composite(ng, g, wm),
            Image.composite(nb, b, wm),
            a,
        )).save(out)
        return out
    except Exception:
        return IMG_PIG


def _processed_docs():
    """Return path to the docs image with the black bottom bar cropped out."""
    out = os.path.join(_IMG, "piled_docs_clean.png")
    if os.path.exists(out):
        return out
    try:
        from PIL import Image
        img = Image.open(IMG_DOCS)
        w, h = img.size
        img.crop((0, 0, w, int(h * 0.91))).save(out)
        return out
    except Exception:
        return IMG_DOCS


def _processed_dollar():
    """Return path to the dollar sign as a JPEG (no alpha, guaranteed white background)."""
    out = os.path.join(_IMG, "dollar_sign_white.jpg")
    if os.path.exists(out):
        return out
    try:
        from PIL import Image
        img = Image.open(IMG_DOLLAR).convert("RGBA")
        # Composite onto a solid white canvas, then save as JPEG (no transparency)
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])   # paste using alpha as mask
        bg.save(out, format="JPEG", quality=95)
        return out
    except Exception:
        return IMG_DOLLAR


def _pig_aspect(pig_path):
    """Return the (width, height) of the pig image to maintain aspect ratio at given height."""
    try:
        from PIL import Image
        iw, ih = Image.open(pig_path).size
        return iw / ih if ih else 1.0
    except Exception:
        return 1.0

# ── Brand colours ──────────────────────────────────────────────────────────────
GREEN       = HexColor("#3A8731")
RED         = HexColor("#CC3A2A")
NAVY        = HexColor("#1A3A6B")
LIGHT_BLUE  = HexColor("#5B9BD5")
DARK_NAVY   = HexColor("#0D1F45")
ARROW_RED   = HexColor("#D94F3C")
ARROW_BLUE  = HexColor("#4A90D9")
LABEL_GREEN = HexColor("#2E7D32")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fmt(val):
    try:    return f"${float(val):,.0f}"
    except: return "$0"


def _draw_circle(c, cx, cy, r, fill_color, stroke_color=None, stroke_width=2.2):
    """Filled circle with optional border."""
    c.setFillColor(fill_color)
    if stroke_color:
        c.setStrokeColor(stroke_color)
        c.setLineWidth(stroke_width)
        c.circle(cx, cy, r, fill=1, stroke=1)
    else:
        c.setStrokeColor(fill_color)
        c.circle(cx, cy, r, fill=1, stroke=0)


def _draw_amount_box(c, cx, cy, w, h, fill_color, text, font_size=13):
    c.setFillColor(white)
    c.roundRect(cx - w/2, cy - h/2, w, h, 4, fill=1, stroke=0)
    c.setFillColor(fill_color)
    c.setFont("Helvetica-Bold", font_size)
    c.drawCentredString(cx, cy - font_size * 0.35, text)


def _chord_line(c, cx, cy, r, y_offset, color=black, lw=1.5):
    """Draw a horizontal chord inside circle at y = cy - r + y_offset."""
    floor_y = cy - r + y_offset
    d = abs(cy - floor_y)
    if d >= r: return
    half = math.sqrt(r * r - d * d)
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    c.setDash([])
    c.line(cx - half, floor_y, cx + half, floor_y)


def _arrowhead(c, tip_x, tip_y, angle_deg, size, color):
    """Filled arrowhead at tip_x,tip_y pointing in angle_deg direction."""
    a = math.radians(angle_deg)
    bx = tip_x - size * math.cos(a)
    by = tip_y - size * math.sin(a)
    hw = size * 0.82
    perp = math.radians(angle_deg + 90)
    lx = bx + hw * math.cos(perp);  ly = by + hw * math.sin(perp)
    rx = bx - hw * math.cos(perp);  ry = by - hw * math.sin(perp)
    p = c.beginPath()
    p.moveTo(tip_x, tip_y);  p.lineTo(lx, ly);  p.lineTo(rx, ry);  p.close()
    c.setFillColor(color)
    c.drawPath(p, fill=1, stroke=0)


def _straight_arrow(c, x1, y1, x2, y2, fill_color, stroke_color=None,
                    shaft_w=0.12, head_w=0.22, head_len=0.20):
    """Straight (non-bent) filled arrow from (x1,y1) to (x2,y2)."""
    dx = x2 - x1;  dy = y2 - y1
    length = math.sqrt(dx * dx + dy * dy)
    if length < 0.001: return
    ux = dx / length;  uy = dy / length
    nx = -uy;          ny =  ux       # perpendicular (90° CCW)

    sw = shaft_w  * inch / 2
    hw = head_w   * inch / 2
    hl = head_len * inch

    se_x = x2 - ux * hl;  se_y = y2 - uy * hl   # shaft end (arrowhead base)

    p = c.beginPath()
    p.moveTo(x1  + nx*sw,  y1  + ny*sw)
    p.lineTo(se_x + nx*sw, se_y + ny*sw)
    p.lineTo(se_x + nx*hw, se_y + ny*hw)
    p.lineTo(x2,            y2)
    p.lineTo(se_x - nx*hw, se_y - ny*hw)
    p.lineTo(se_x - nx*sw, se_y - ny*sw)
    p.lineTo(x1  - nx*sw,  y1  - ny*sw)
    p.close()

    c.setFillColor(fill_color)
    if stroke_color:
        c.setStrokeColor(stroke_color)
        c.setLineWidth(1.0)
        c.drawPath(p, fill=1, stroke=1)
    else:
        c.drawPath(p, fill=1, stroke=0)


def _outlined_h_arrow(c, x1, x2, y, border_color,
                      label="", sublabel="", thickness=0.27):
    """White-filled outlined horizontal arrow; label drawn inside the body."""
    t   = thickness * inch
    ahl = 0.28 * inch
    ahh = 0.24 * inch
    shaft_end = x2 - ahl

    p = c.beginPath()
    p.moveTo(x1,         y - t/2)
    p.lineTo(shaft_end,  y - t/2)
    p.lineTo(shaft_end,  y - ahh)
    p.lineTo(x2,         y)
    p.lineTo(shaft_end,  y + ahh)
    p.lineTo(shaft_end,  y + t/2)
    p.lineTo(x1,         y + t/2)
    p.close()
    c.setFillColor(white)
    c.setStrokeColor(border_color)
    c.setLineWidth(1.8)
    c.drawPath(p, fill=1, stroke=1)

    if label:
        c.setFillColor(border_color)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString((x1 + shaft_end) / 2, y - 4, label)
    if sublabel:
        c.setFillColor(HexColor("#555555"))
        c.setFont("Helvetica-Oblique", 7.5)
        c.drawCentredString((x1 + x2) / 2, y - t/2 - 0.15 * inch, sublabel)


def _circle_clip_path(cx, cy, r):
    """Return a ReportLab path that approximates a circle (for clipPath)."""
    from reportlab.pdfgen.pathobject import PDFPathObject
    k = 0.5522847498 * r
    p = PDFPathObject()
    p.moveTo(cx + r, cy)
    p.curveTo(cx + r, cy + k,  cx + k, cy + r,  cx,     cy + r)
    p.curveTo(cx - k, cy + r,  cx - r, cy + k,  cx - r, cy)
    p.curveTo(cx - r, cy - k,  cx - k, cy - r,  cx,     cy - r)
    p.curveTo(cx + k, cy - r,  cx + r, cy - k,  cx + r, cy)
    p.close()
    return p


def _draw_image_clipped(c, img_path, cx, cy, r, img_x, img_y, img_w, img_h):
    """Draw an image clipped to a circle boundary."""
    if not os.path.exists(img_path):
        return
    c.saveState()
    p = _circle_clip_path(cx, cy, r)
    c.clipPath(p, stroke=0, fill=0)
    c.drawImage(img_path, img_x, img_y, width=img_w, height=img_h, mask='auto')
    c.restoreState()


def _outlined_l_arrow(c, start_x, start_y, end_x, end_y,
                      border_color, thickness=0.24, label=""):
    """White-filled outlined L-arrow (DOWN then RIGHT); label inside horizontal part."""
    t   = thickness * inch
    ahl = 0.22 * inch
    ahh = 0.20 * inch
    cx   = start_x;  cy = end_y;  se = end_x - ahl

    p = c.beginPath()
    p.moveTo(cx - t/2, start_y)
    p.lineTo(cx + t/2, start_y)
    p.lineTo(cx + t/2, cy + t/2)
    p.lineTo(se,        cy + t/2)
    p.lineTo(se,        cy + ahh)
    p.lineTo(end_x,     cy)
    p.lineTo(se,        cy - ahh)
    p.lineTo(se,        cy - t/2)
    p.lineTo(cx - t/2,  cy - t/2)
    p.close()

    c.setFillColor(white)
    c.setStrokeColor(border_color)
    c.setLineWidth(1.8)
    c.drawPath(p, fill=1, stroke=1)

    if label:
        mid_x = (cx + se) / 2
        c.setFillColor(border_color)
        c.setFont("Helvetica-Bold", 9)
        c.drawCentredString(mid_x, cy - 4, label)


# ── Page 1 ─────────────────────────────────────────────────────────────────────

def draw_page1(c, data):
    W, H = landscape(letter)

    c.setFillColor(white);  c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setStrokeColor(NAVY);  c.setLineWidth(2)
    c.rect(0.25*inch, 0.25*inch, W - 0.5*inch, H - 0.5*inch, fill=0, stroke=1)

    # ── Header (client name only, no date) ──
    c.setFillColor(NAVY);  c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(W/2, H - 0.65*inch, "Simple Automated Cashflow System (SACS)")
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(W/2, H - 1.0*inch, data.get("client_name", ""))

    # ── Header corner icons ──
    dlr_sz  = 1.00 * inch
    docs_sz = 1.05 * inch
    dlr_x   = 0.38 * inch
    dlr_y   = H - 0.62 * inch - dlr_sz   # lowered (was 0.36)
    docs_x  = W - 0.38 * inch - docs_sz
    docs_y  = H - 0.62 * inch - docs_sz  # lowered (was 0.36)
    # Dollar sign: JPEG with solid white bg (no alpha); also draw white rect underneath as safety
    dlr_clean = _processed_dollar()
    if os.path.exists(dlr_clean):
        c.setFillColor(white)
        c.rect(dlr_x, dlr_y, dlr_sz, dlr_sz, fill=1, stroke=0)
        c.drawImage(dlr_clean, dlr_x, dlr_y, width=dlr_sz, height=dlr_sz)
    # Docs: cropped (no black bar), drawn with auto mask for any transparency
    docs_clean = _processed_docs()
    if os.path.exists(docs_clean):
        c.drawImage(docs_clean, docs_x, docs_y,
                    width=docs_sz, height=docs_sz, mask='auto')

    # ── Circle positions ──
    inflow_cx  = W * 0.24;   inflow_cy  = H * 0.52;  inflow_r  = 1.38 * inch
    outflow_cx = W * 0.73;   outflow_cy = H * 0.52;  outflow_r = 1.38 * inch
    reserve_cx = W * 0.485;  reserve_cy = H * 0.23;  reserve_r = 1.18 * inch

    # ── INFLOW circle – with BLACK BORDER ──
    _draw_circle(c, inflow_cx, inflow_cy, inflow_r, GREEN, stroke_color=black)
    c.setFillColor(white);  c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(inflow_cx, inflow_cy + 0.38*inch, "INFLOW")
    _draw_amount_box(c, inflow_cx, inflow_cy - 0.05*inch,
                     1.55*inch, 0.42*inch, GREEN, _fmt(data.get("inflow", 0)))
    # Horizontal chord line above "$1,000 Floor" label
    _chord_line(c, inflow_cx, inflow_cy, inflow_r, y_offset=0.42*inch, color=black)
    c.setFillColor(white);  c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(inflow_cx, inflow_cy - inflow_r + 0.20*inch, "$1,000 Floor")

    # ── Salary labels – left-aligned, above INFLOW ──
    c1_sal  = data.get("client1_salary", 0)
    c2_sal  = data.get("client2_salary", 0)
    c1_name = data.get("client1_first", "Client 1")
    c2_name = data.get("client2_first", "Client 2")
    lbl_x = 0.70 * inch
    c.setFillColor(LABEL_GREEN);  c.setFont("Helvetica-Bold", 10.5)
    if c1_sal and c2_sal:
        c.drawString(lbl_x, inflow_cy + inflow_r + 0.44*inch,
                     f"{_fmt(c1_sal)} \u2013 {c1_name}")
        c.drawString(lbl_x, inflow_cy + inflow_r + 0.26*inch,
                     f"{_fmt(c2_sal)} \u2013 {c2_name}")
    elif c1_sal:
        c.drawString(lbl_x, inflow_cy + inflow_r + 0.32*inch,
                     f"{_fmt(c1_sal)} \u2013 {c1_name}")

    # ── Green straight diagonal arrow – short, solid, black border ──
    # Tip stops just outside the INFLOW circle (small gap so it doesn't overlap border).
    arr_len  = 0.42 * inch
    arr_gap  = 0.13 * inch                            # gap between tip and circle edge
    tip_r    = inflow_r + arr_gap                     # tip is arr_gap outside the circle
    tip_x    = inflow_cx + tip_r * math.cos(math.radians(135))
    tip_y    = inflow_cy + tip_r * math.sin(math.radians(135))
    from_x   = tip_x + arr_len * math.cos(math.radians(135))
    from_y   = tip_y + arr_len * math.sin(math.radians(135))
    _straight_arrow(c, from_x, from_y, tip_x, tip_y,
                    GREEN, stroke_color=black, shaft_w=0.13, head_w=0.34, head_len=0.18)

    # ── OUTFLOW circle – with BLACK BORDER ──
    _draw_circle(c, outflow_cx, outflow_cy, outflow_r, RED, stroke_color=black)
    c.setFillColor(white);  c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(outflow_cx, outflow_cy + 0.38*inch, "OUTFLOW")
    _draw_amount_box(c, outflow_cx, outflow_cy - 0.05*inch,
                     1.55*inch, 0.42*inch, RED, _fmt(data.get("outflow", 0)))
    # Horizontal chord line above "$1,000 Floor" label
    _chord_line(c, outflow_cx, outflow_cy, outflow_r, y_offset=0.42*inch, color=black)
    c.setFillColor(white);  c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(outflow_cx, outflow_cy - outflow_r + 0.20*inch, "$1,000 Floor")

    # ── "X = Monthly Expenses" label + single black L-bracket arrow to $12,000 ──
    # Fix 6: more right margin – start text just outside circle right edge
    msg_x     = outflow_cx + outflow_r + 0.08 * inch
    msg_y_top = outflow_cy + outflow_r + 0.44 * inch
    msg_y_bot = msg_y_top - 0.18 * inch
    c.setFillColor(black);  c.setFont("Helvetica-Bold", 10.5)
    c.drawString(msg_x, msg_y_top, "X = Monthly")
    c.drawString(msg_x, msg_y_bot, "Expenses")

    # Fix 4: vertical shaft starts from bottom-centre of "Expenses" word
    exp_w = c.stringWidth("Expenses", "Helvetica-Bold", 10.5)
    brk_x = msg_x + exp_w / 2                               # centre of "Expenses"

    # Bracket arrow down then left into OUTFLOW to $12,000 box
    box_cy    = outflow_cy - 0.05 * inch
    # Gap between arrowhead and $12,000 box (arrow stops before touching box)
    arr_tip_x = outflow_cx + 1.55 * inch / 2 + 0.22 * inch
    brk_end_x = arr_tip_x + 0.13 * inch  # horizontal segment ends here (arrowhead base)

    c.setStrokeColor(black);  c.setLineWidth(1.6);  c.setDash([])
    # Vertical: starts with a small gap below "Expenses" text (not touching it)
    c.line(brk_x, msg_y_bot - 0.10*inch, brk_x, box_cy)
    # Horizontal: from vertical shaft right to arrowhead base
    c.line(brk_x, box_cy, brk_end_x, box_cy)
    _arrowhead(c, arr_tip_x, box_cy, 180, 0.13*inch, black)  # ← thicker arrowhead pointing LEFT

    # ── PRIVATE RESERVE circle ──
    _draw_circle(c, reserve_cx, reserve_cy, reserve_r, NAVY)
    # Pig image – white BG → navy, aspect-ratio-correct, clipped to lower portion
    pig_path   = _processed_pig()
    pig_aspect = _pig_aspect(pig_path)
    pig_h      = reserve_r * 0.80                  # smaller – fits well inside circle
    pig_w      = pig_h * pig_aspect                # honour original w:h ratio
    # cap width so it doesn't exceed circle diameter
    if pig_w > reserve_r * 1.80:
        pig_w = reserve_r * 1.80
        pig_h = pig_w / pig_aspect
    _draw_image_clipped(c, pig_path,
                        reserve_cx, reserve_cy, reserve_r,
                        img_x=reserve_cx - pig_w / 2,
                        img_y=reserve_cy - reserve_r + 0.08 * inch,
                        img_w=pig_w, img_h=pig_h)
    c.setFillColor(white);  c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(reserve_cx, reserve_cy + 0.52*inch, "PRIVATE")
    c.drawCentredString(reserve_cx, reserve_cy + 0.30*inch, "RESERVE")
    c.setFont("Helvetica", 8)
    c.drawCentredString(reserve_cx, reserve_cy + 0.08*inch, "[ High-Yield Savings ]")

    # ── Outlined red arrow: INFLOW → OUTFLOW  (shorter, text inside) ──
    arrow_y  = (inflow_cy + outflow_cy) / 2
    arrow_x1 = inflow_cx  + inflow_r  + 0.22 * inch   # shortened (was 0.04)
    arrow_x2 = outflow_cx - outflow_r - 0.22 * inch   # shortened (was 0.04)
    _outlined_h_arrow(c, arrow_x1, arrow_x2, arrow_y, ARROW_RED,
                      label=f"X = {_fmt(data.get('outflow', 0))}/month*",
                      sublabel="Automated transfer on the 28th")

    # ── Outlined blue L-arrow: starts from bottom-centre of INFLOW with a gap ──
    l_sx = inflow_cx                          # vertical shaft at INFLOW circle centre x
    l_sy = inflow_cy - inflow_r - 0.12 * inch # gap below circle bottom
    l_ex = reserve_cx - reserve_r - 0.04 * inch
    l_ey = reserve_cy
    _outlined_l_arrow(c, l_sx, l_sy, l_ex, l_ey, ARROW_BLUE,
                      thickness=0.20,
                      label=f"{_fmt(data.get('excess', 0))}/mo*")

    # ── Footer: MONTHLY | CASHFLOW with vertical dashed line through the gap ──
    c.setFont("Helvetica-Bold", 12)
    monthly_w  = c.stringWidth("MONTHLY",  "Helvetica-Bold", 12)
    space_w    = c.stringWidth(" ",         "Helvetica-Bold", 12)
    cashflow_w = c.stringWidth("CASHFLOW", "Helvetica-Bold", 12)
    total_w    = monthly_w + space_w + cashflow_w
    start_x    = W / 2 - total_w / 2
    gap_x      = start_x + monthly_w + space_w / 2   # centre of the space between words

    footer_y = 0.52 * inch
    c.setFillColor(NAVY)
    c.drawString(start_x,                        footer_y, "MONTHLY")
    c.drawString(start_x + monthly_w + space_w,  footer_y, "CASHFLOW")

    # Vertical dashed line precisely between the two words
    dash_top = reserve_cy - reserve_r - 0.05 * inch
    dash_bot = 0.32 * inch
    c.setStrokeColor(NAVY);  c.setDash([4, 3]);  c.setLineWidth(1)
    c.line(gap_x, dash_top, gap_x, dash_bot)
    c.setDash([])


# ── Page 2 ─────────────────────────────────────────────────────────────────────

def draw_page2(c, data):
    W, H = landscape(letter)

    c.setFillColor(white);  c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setStrokeColor(NAVY);  c.setLineWidth(2)
    c.rect(0.25*inch, 0.25*inch, W - 0.5*inch, H - 0.5*inch, fill=0, stroke=1)

    # ── Header (client name only, no date) ──
    c.setFillColor(NAVY);  c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(W/2, H - 0.65*inch, "Simple Automated Cashflow System (SACS)")
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(W/2, H - 1.0*inch, data.get("client_name", ""))

    # Dashed vertical centre divider
    c.setStrokeColor(HexColor("#AAAAAA"));  c.setDash([6, 4]);  c.setLineWidth(1.2)
    c.line(W/2, H - 1.6*inch, W/2, 1.5*inch)
    c.setDash([])

    fica_cx = W * 0.30;  inv_cx = W * 0.70;  circ_cy = H * 0.50;  r = 1.45 * inch

    # FICA circle
    _draw_circle(c, fica_cx, circ_cy, r, LIGHT_BLUE)
    c.setFillColor(white);  c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(fica_cx, circ_cy + 0.38*inch, "FICA")
    c.drawCentredString(fica_cx, circ_cy + 0.15*inch, "ACCOUNT")
    _draw_amount_box(c, fica_cx, circ_cy - 0.20*inch, 1.6*inch, 0.42*inch,
                     LIGHT_BLUE, _fmt(data.get("private_reserve_balance", 0)))
    c.setFillColor(HexColor("#444444"));  c.setFont("Helvetica", 8.5)
    c.drawCentredString(fica_cx, circ_cy - r - 0.22*inch,
                        "6X Monthly Expenses + Deductibles")
    c.setFont("Helvetica-Bold", 9);  c.setFillColor(NAVY)
    c.drawCentredString(fica_cx, circ_cy - r - 0.40*inch,
                        f"Target: {_fmt(data.get('private_reserve_target', 0))}")

    # Investment circle
    _draw_circle(c, inv_cx, circ_cy, r, DARK_NAVY)
    c.setFillColor(white);  c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(inv_cx, circ_cy + 0.38*inch, "INVESTMENT")
    c.drawCentredString(inv_cx, circ_cy + 0.15*inch, "ACCOUNT")
    _draw_amount_box(c, inv_cx, circ_cy - 0.20*inch, 1.6*inch, 0.42*inch,
                     DARK_NAVY, _fmt(data.get("schwab_investment_balance", 0)))
    c.setFillColor(HexColor("#444444"));  c.setFont("Helvetica", 8.5)
    c.drawCentredString(inv_cx, circ_cy - r - 0.22*inch, "Remainder")

    # Double-headed arrow between circles
    ax1 = fica_cx + r + 0.08*inch;  ax2 = inv_cx - r - 0.08*inch;  ay = circ_cy
    t = 0.12*inch;  ah = 0.22*inch;  ahh = 0.18*inch
    c.setFillColor(ARROW_BLUE)
    c.rect(ax1 + ah, ay - t/2, ax2 - ax1 - 2*ah, t, fill=1, stroke=0)
    for tip_x, base_x in [(ax1, ax1 + ah), (ax2, ax2 - ah)]:
        p = c.beginPath()
        p.moveTo(tip_x, ay);  p.lineTo(base_x, ay + ahh);  p.lineTo(base_x, ay - ahh)
        p.close();  c.drawPath(p, fill=1, stroke=0)

    # Footer
    c.setFillColor(NAVY);  c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(W/2, 0.72*inch, "LONG TERM  CASHFLOW")
    c.setFont("Helvetica-Oblique", 10);  c.setFillColor(ARROW_BLUE)
    c.drawCentredString(W/2, 0.50*inch, "(Magnified Private Reserve Cashflow)")


# ── Public entry point ─────────────────────────────────────────────────────────

def generate_sacs_pdf(client, report):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=landscape(letter))
    data = {
        "client_name":    client["display_name"],
        "client1_first":  client.get("client1_first", ""),
        "client2_first":  client.get("client2_first", ""),
        "client1_salary": client.get("client1_salary", 0),
        "client2_salary": client.get("client2_salary", 0),
        "inflow":         report.get("inflow", 0),
        "outflow":        report.get("outflow", 0),
        "excess":         report.get("excess", 0),
        "private_reserve_balance":   report.get("private_reserve_balance", 0),
        "schwab_investment_balance": report.get("schwab_investment_balance", 0),
        "private_reserve_target":    report.get("private_reserve_target", 0),
    }
    draw_page1(c, data)
    c.showPage()
    draw_page2(c, data)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()
