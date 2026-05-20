"""
TCC PDF Generator – Total Client Chart (Net Worth)
Pixel-precise match to reference screenshot.
Page: US Letter Landscape  11 × 8.5 in
"""
import io
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, white, black

# ── Palette ───────────────────────────────────────────────────────────────────
CLIENT_GREEN = HexColor("#3A7A2F")
ACCT_BORDER  = HexColor("#888888")
GRAY_BOX     = HexColor("#555555")   # retirement boxes + liabilities summary – same shade
GRAY_BORDER  = HexColor("#333333")
TOTAL_BOX    = HexColor("#484848")   # NON RETIREMENT TOTAL (slightly lighter)
TAN_BOX      = HexColor("#D4C89A")   # liabilities itemised box
BORDER_GREEN = HexColor("#6AAF30")
TREE_LINE    = HexColor("#AAAAAA")   # connection lines / dividers
STALE_RED    = HexColor("#CC3333")
FOOTNOTE_BD  = HexColor("#555555")

# ── Page ──────────────────────────────────────────────────────────────────────
W = 11.0 * inch
H =  8.5 * inch

def _X(p): return W * p
def _Y(p): return H * (1.0 - p)   # top-% → ReportLab bottom-origin Y

# ── All positions as % of page (from top-left) ────────────────────────────────

# Grand Total box  (centred in page top)
_GT_CX = _X(0.493);  _GT_CY = _Y(0.087)      # 7.76"
_GT_W  = _X(0.120);  _GT_H  = H * 0.070       # 0.595"
_GT_BOT = _GT_CY - _GT_H / 2                  # 7.462"

# Oval row  (client ovals + LS summary box + retirement side-boxes)
# ← pushed down vs previous version to create proper gap below GT box
_OVL_CY = _Y(0.230)                            # 6.545" (was 0.148 = 7.24")
_C1_CX  = _X(0.291);  _C2_CX  = _X(0.696)
_OVL_RX = _X(0.075);  _OVL_RY = H * 0.068     # 0.578"
_OVL_TOP = _OVL_CY + _OVL_RY                   # 7.123"  ← gap from GT_BOT = 0.339" ✓

# Liabilities summary box  (same row / Y as ovals)
_LS_CX  = _X(0.495);  _LS_W  = _X(0.116);  _LS_H = H * 0.058
_LS_CY  = _OVL_CY     # explicitly the same row
_LS_TOP = _LS_CY + _LS_H / 2
_LS_BOT = _LS_CY - _LS_H / 2

# Retirement summary side-boxes  (same row)
_RB_W = _X(0.153);  _RB_H = H * 0.063
_C1RB_CX = _X(0.116);  _C2RB_CX = _X(0.877)

# Single centre-X used for ALL vertical spine segments (upper + lower must match)
_VLX    = _X(0.493)
_NR_CTR = _VLX      # ← same as _VLX so both halves form one continuous line

# Horizontal section divider (retirement / non-retirement)
_HLY = _Y(0.462)                               # 4.573"

# Retirement account ovals  (fixed metric sizes to prevent overlap)
_RET_ARX = 0.80 * inch
_RET_ARY = 0.57 * inch
_RET_CY  = _Y(0.368)                           # 5.372" (OVL_BOT – 0.15" gap – ARY)

# Fixed X column positions for retirement circles
_C1_RET_XS = [_X(0.118), _X(0.401)]
_C2_RET_XS = [_X(0.587), _X(0.741), _X(0.894)]

# Non-retirement account ovals  (fixed metric sizes)
_NR_ARX = 0.80 * inch
_NR_ARY = 0.58 * inch

# Non-ret column X positions
_NR_C1A = _X(0.109);  _NR_C1B = _X(0.289)
_NR_C2  = _X(0.747)
# _NR_CTR defined above (= _VLX) – Trust oval and spine share the same centre

# Non-ret Y reference slots  (2 rows for C1, 3 rows for C2)
# _NR_C2_Y1 pushed down so the top of the first C2 oval clears the divider line
_NR_C1_Y1 = _Y(0.580);  _NR_C1_Y2 = _Y(0.768)
_NR_C2_Y1 = _Y(0.544);  _NR_C2_Y2 = _Y(0.700);  _NR_C2_Y3 = _Y(0.845)

# Trust oval  (non-ret centre)
_TRUST_RX = _X(0.100);  _TRUST_RY = H * 0.112
_TRUST_CY = _Y(0.595)                          # 3.443"
_TRUST_TOP = _TRUST_CY + _TRUST_RY
_TRUST_BOT = _TRUST_CY - _TRUST_RY

# Liabilities itemised box
_LIAB_CX   = _X(0.487);  _LIAB_W  = _X(0.238)
_LIAB_BOT  = _Y(0.878)                         # 1.030"
_LIAB_H_REF = _Y(0.740) - _LIAB_BOT           # ref height for 7 items
_LIAB_HDR_H = 0.24 * inch
_LIAB_ROW_H = (_LIAB_H_REF - _LIAB_HDR_H) / 7

# NON RETIREMENT TOTAL box
_NRT_CX = _X(0.488);  _NRT_W = _X(0.154);  _NRT_H = H * 0.063
_NRT_BOT = 0.12 * inch
_NRT_TOP = _NRT_BOT + _NRT_H

# Page margins (padding-top ≈ padding-left so they look even)
_M_BORDER = 0.12 * inch
_M_TEXT   = 0.26 * inch


# ── Formatters ────────────────────────────────────────────────────────────────
def _fmt(v):
    try:   return f"${float(v):,.2f}"
    except: return "$0.00"

def _fmt0(v):
    try:   return f"${float(v):,.0f}"
    except: return "$0"

def _age(dob):
    if not dob: return ""
    try:
        from datetime import date
        y, m, d = (int(x) for x in dob.split("-"))
        t = date.today()
        return str(t.year - y - ((t.month, t.day) < (m, d)))
    except: return ""

def _format_date(report):
    months = ["January","February","March","April","May","June",
              "July","August","September","October","November","December"]
    ca = str(report.get("created_at", ""))
    if len(ca) >= 10:
        try:
            from datetime import datetime
            dt = datetime.strptime(ca[:10], "%Y-%m-%d")
            return f"{months[dt.month-1]} {dt.day}, {dt.year}"
        except: pass
    q = int(report.get("quarter", 1));  y = int(report.get("year", 2024))
    m, d = {1:(3,31),2:(6,30),3:(9,30),4:(12,31)}.get(q,(12,31))
    return f"{months[m-1]} {d}, {y}"


# ── Drawing primitives ─────────────────────────────────────────────────────────

def _box(c, cx, cy, w, h, fill=GRAY_BOX, border=GRAY_BORDER,
         lines=None, fs=9, tc=white, lw=0.6):
    x, y = cx - w/2, cy - h/2
    c.setFillColor(fill);  c.setStrokeColor(border);  c.setLineWidth(lw)
    c.rect(x, y, w, h, fill=1, stroke=1)
    if lines:
        lh = fs + 2.5;  bh = len(lines) * lh
        sy = cy + bh/2 - lh * 0.72
        for t in lines:
            c.setFillColor(tc);  c.setFont("Helvetica-Bold", fs)
            c.drawCentredString(cx, sy, t);  sy -= lh


def _ellipse(c, cx, cy, rx, ry, fill=white, stroke=ACCT_BORDER, lw=0.8):
    c.setFillColor(fill);  c.setStrokeColor(stroke);  c.setLineWidth(lw)
    c.ellipse(cx-rx, cy-ry, cx+rx, cy+ry, fill=1, stroke=1)


def _underlined(c, x, y, text, font, size, color=black):
    c.setFillColor(color);  c.setFont(font, size)
    c.drawString(x, y, text)
    w = c.stringWidth(text, font, size)
    c.setStrokeColor(color);  c.setLineWidth(0.5)
    c.line(x, y - 1.3, x + w, y - 1.3)


def _acct_oval(c, cx, cy, rx, ry, atype, anum, bal, asof, cash, stale=False):
    """Draw an account oval.  Cash value sits in a small inner circle glued to
    the bottom of the main oval (inner circle bottom = outer oval bottom)."""
    _ellipse(c, cx, cy, rx, ry)

    has_cash = bool(cash and float(cash or 0) > 0)
    fs_sm, fs_md = 7.0, 8.0
    lh = fs_sm + 2.2

    rows = []
    if anum:
        rows.append(("Helvetica-Bold", fs_sm, f"ACCT #{anum}"))
    rows.append(("Helvetica-Bold", fs_md, atype))
    rows.append(("Helvetica-Bold", fs_md, _fmt(bal)))
    if asof:
        rows.append(("Helvetica", fs_sm, f"a/o {asof}" + ("*" if stale else "")))

    if has_cash:
        c_ry = ry * 0.27
        c_rx = rx * 0.40
        # "glued bottom": sub-circle bottom = main oval bottom
        c_cy = cy - ry + c_ry
        # text block occupies space above the sub-circle
        text_top = cy + ry * 0.84
        text_bot = c_cy + c_ry + 0.04 * inch
    else:
        text_top = cy + ry * 0.84
        text_bot = cy - ry * 0.84

    th = len(rows) * lh
    area_h = text_top - text_bot
    sy = text_bot + area_h / 2 + th / 2 - lh * 0.65

    for fn, sz, tx in rows:
        c.setFillColor(black);  c.setFont(fn, sz)
        c.drawCentredString(cx, sy, tx);  sy -= lh

    if has_cash:
        _ellipse(c, cx, c_cy, c_rx, c_ry)
        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 6.5)
        c.drawCentredString(cx, c_cy + c_ry * 0.14, _fmt0(cash))
        c.setFont("Helvetica", 6.0)
        c.drawCentredString(cx, c_cy - c_ry * 0.58, "Cash")


def _client_oval(c, cx, cy, name, age, dob, ssn4):
    """Green oval with black border for client profile."""
    _ellipse(c, cx, cy, _OVL_RX, _OVL_RY, fill=CLIENT_GREEN, stroke=black, lw=1.4)
    c.setFillColor(white);  c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(cx, cy + 0.14 * inch, name)
    c.setFont("Helvetica", 7.5)
    ly = cy + 0.01 * inch
    for part in filter(None, [
            f"Age {age}" if age else None,
            f"DOB {dob}"  if dob  else None,
            f"SSN …{ssn4}" if ssn4 else None]):
        c.drawCentredString(cx, ly, part);  ly -= 0.115 * inch


# ── Dynamic position helpers ───────────────────────────────────────────────────

def _ret_xs(n, side):
    refs = _C1_RET_XS if side == "c1" else _C2_RET_XS
    if n == 0:  return []
    if n == 1:  return [refs[0]]          # always outermost slot first
    if n <= len(refs): return refs[:n]
    step = (refs[-1] - refs[0]) / (n - 1)
    return [refs[0] + i * step for i in range(n)]


def _col_ys(n, y_top, y_bot):
    if n == 0: return []
    if n == 1: return [(y_top + y_bot) / 2]
    step = (y_top - y_bot) / (n - 1)
    return [y_top - i * step for i in range(n)]


def _nr_c1_positions(items):
    """Alternate items between col A (outer-left) and col B (inner-left)."""
    col_a = [b for i, b in enumerate(items) if i % 2 == 0]
    col_b = [b for i, b in enumerate(items) if i % 2 != 0]
    ys_a  = _col_ys(len(col_a), _NR_C1_Y1, _NR_C1_Y2)
    ys_b  = _col_ys(len(col_b), _NR_C1_Y1, _NR_C1_Y2)
    result = []
    for i, b in enumerate(col_a): result.append((_NR_C1A, ys_a[i], b))
    for i, b in enumerate(col_b): result.append((_NR_C1B, ys_b[i], b))
    return result


def _nr_c2_ys(n):
    refs = [_NR_C2_Y1, _NR_C2_Y2, _NR_C2_Y3]
    if n <= 3: return refs[:n]
    step = (_NR_C2_Y1 - _NR_C2_Y3) / (n - 1)
    return [_NR_C2_Y1 - i * step for i in range(n)]


# ── Main draw ──────────────────────────────────────────────────────────────────

def draw_tcc_page(c, client, report, balances):
    c.setPageSize((W, H))
    c.setFillColor(white);  c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setStrokeColor(BORDER_GREEN);  c.setLineWidth(1.2)
    c.rect(_M_BORDER, _M_BORDER, W - 2*_M_BORDER, H - 2*_M_BORDER, fill=0, stroke=1)

    # ── Header  (padding-top ≈ padding-left = _M_TEXT) ────────────────────────
    # NAME and DATE are positioned so the visible cap-height is ~_M_TEXT below
    # the inner border edge, matching the left-margin padding visually.
    lbl_x = _M_TEXT;  val_x = lbl_x + 0.52 * inch
    name_y = H - _M_BORDER - _M_TEXT - 0.06 * inch   # baseline ≈ 0.26" from border
    date_y = name_y - 0.19 * inch

    c.setFillColor(black);  c.setFont("Helvetica-Bold", 9)
    c.drawString(lbl_x, name_y, "NAME:")
    _underlined(c, val_x, name_y, client["display_name"], "Helvetica", 9)

    c.setFillColor(black);  c.setFont("Helvetica-Bold", 9)
    c.drawString(lbl_x, date_y, "DATE:")
    _underlined(c, val_x, date_y, _format_date(report), "Helvetica", 9)

    # ── Categorise balances ────────────────────────────────────────────────────
    c1_ret = c2_ret = non_ret = trust_sum = liab_sum = 0.0
    ret_c1, ret_c2 = [], []
    nr_c1, nr_c2, nr_joint = [], [], []
    trust_list, liab_list = [], []

    for b in balances:
        bal = float(b["balance"] or 0)
        if   b["is_liability"]:  liab_sum  += bal;  liab_list.append(b)
        elif b["is_trust"]:      trust_sum += bal;  trust_list.append(b)
        elif b["is_retirement"]:
            if   b["owner"] == "client1": c1_ret += bal; ret_c1.append(b)
            elif b["owner"] == "client2": c2_ret += bal; ret_c2.append(b)
            else: c1_ret += bal/2; c2_ret += bal/2; ret_c1.append(b)
        else:
            if   b["owner"] == "client1": non_ret += bal; nr_c1.append(b)
            elif b["owner"] == "client2": non_ret += bal; nr_c2.append(b)
            else:                          non_ret += bal; nr_joint.append(b)

    grand = c1_ret + c2_ret + non_ret + trust_sum

    # ── Grand Total box ────────────────────────────────────────────────────────
    _box(c, _GT_CX, _GT_CY, _GT_W, _GT_H, fill=TOTAL_BOX, border=GRAY_BORDER,
         lines=["GRAND TOTAL", _fmt(grand)], fs=9.5)

    # ── Vertical spine – single continuous centre line, gaps only through boxes ─
    c.setStrokeColor(TREE_LINE);  c.setLineWidth(0.6);  c.setDash([])

    # Retirement section: GT bottom → LS top, then LS bottom → divider
    c.line(_VLX, _GT_BOT, _VLX, _LS_TOP)
    c.line(_VLX, _LS_BOT, _VLX, _HLY)

    # Non-retirement section (same X = _VLX = _NR_CTR):
    #   divider → Trust oval top border; Liab bottom → NRT top
    #   (no line from Trust bottom to Liab box – removes the short tail below the Trust oval)
    c.line(_VLX, _HLY,      _VLX, _TRUST_TOP)
    c.line(_VLX, _LIAB_BOT, _VLX, _NRT_TOP)

    # ── Liabilities summary box  (TAN – same colour as the itemised box below) ─
    liab_asof = next((b.get("as_of_date","") for b in liab_list
                      if b.get("as_of_date")), "")
    ls_lines = ["Liabilities:", _fmt(liab_sum)]
    if liab_asof:
        ls_lines.append(f"a/o {liab_asof}")
    _box(c, _LS_CX, _LS_CY, _LS_W, _LS_H,
         fill=TAN_BOX, border=HexColor("#9A905A"),
         lines=ls_lines, fs=7.5, tc=black)

    # ── Client ovals  (green, black border) ───────────────────────────────────
    _client_oval(c, _C1_CX, _OVL_CY,
                 f"{client.get('client1_first','')} {client.get('client1_last','')}",
                 _age(client.get("client1_dob","")),
                 client.get("client1_dob",""), client.get("client1_ssn4",""))
    if client.get("is_married"):
        _client_oval(c, _C2_CX, _OVL_CY,
                     f"{client.get('client2_first','')} {client.get('client2_last','')}",
                     _age(client.get("client2_dob","")),
                     client.get("client2_dob",""), client.get("client2_ssn4",""))

    # ── Retirement summary side-boxes  (SAME GRAY_BOX as liabilities summary) ─
    _box(c, _C1RB_CX, _OVL_CY, _RB_W, _RB_H, fill=GRAY_BOX, border=GRAY_BORDER,
         lines=["Client 1 Retirement Only", _fmt(c1_ret)], fs=8)
    _box(c, _C2RB_CX, _OVL_CY, _RB_W, _RB_H, fill=GRAY_BOX, border=GRAY_BORDER,
         lines=["Client 2 Retirement Only", _fmt(c2_ret)], fs=8)

    # ── Horizontal section divider ─────────────────────────────────────────────
    c.setStrokeColor(TREE_LINE);  c.setLineWidth(0.5)
    c.line(_M_TEXT, _HLY, W - _M_TEXT, _HLY)

    # Section labels
    lbl_cx_left  = _M_TEXT + 0.60 * inch
    lbl_cx_right = W - _M_TEXT - 0.60 * inch

    c.setFillColor(black);  c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(lbl_cx_left,  _HLY + 0.09 * inch, "RETIREMENT")
    c.drawCentredString(lbl_cx_right, _HLY + 0.09 * inch, "RETIREMENT")
    c.drawCentredString(lbl_cx_left,  _HLY - 0.15 * inch, "NON")
    c.drawCentredString(lbl_cx_left,  _HLY - 0.27 * inch, "RETIREMENT")
    c.drawCentredString(lbl_cx_right, _HLY - 0.15 * inch, "NON")
    c.drawCentredString(lbl_cx_right, _HLY - 0.27 * inch, "RETIREMENT")

    # ── Retirement account circles ─────────────────────────────────────────────
    c1_xs = _ret_xs(len(ret_c1), "c1")
    c2_xs = _ret_xs(len(ret_c2), "c2")

    for i, b in enumerate(ret_c1):
        cx = c1_xs[i] if i < len(c1_xs) else c1_xs[-1]
        _acct_oval(c, cx, _RET_CY, _RET_ARX, _RET_ARY,
                   b["account_type"], b.get("account_number_last4",""),
                   b["balance"], b.get("as_of_date",""),
                   b.get("cash_value",0), bool(b.get("is_stale")))

    for i, b in enumerate(ret_c2):
        cx = c2_xs[i] if i < len(c2_xs) else c2_xs[-1]
        _acct_oval(c, cx, _RET_CY, _RET_ARX, _RET_ARY,
                   b["account_type"], b.get("account_number_last4",""),
                   b["balance"], b.get("as_of_date",""),
                   b.get("cash_value",0), bool(b.get("is_stale")))

    # ── Trust oval (Family Trust – spine line passes through its centre) ───────
    tb_bal = sum(float(b["balance"] or 0) for b in trust_list)
    _ellipse(c, _NR_CTR, _TRUST_CY, _TRUST_RX, _TRUST_RY)
    c.setFillColor(black)
    n1 = client.get("client1_first","")
    n2 = client.get("client2_first","") if client.get("is_married") else ""
    trust_lbl = (f"{n1} and {n2} Family Trust" if n2 else f"{n1} Family Trust")
    c.setFont("Helvetica-Bold", 8.5)
    c.drawCentredString(_NR_CTR, _TRUST_CY + 0.18 * inch, trust_lbl)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(_NR_CTR, _TRUST_CY - 0.01 * inch, _fmt(tb_bal))
    if trust_list and trust_list[0].get("as_of_date"):
        c.setFont("Helvetica", 7.5)
        c.drawCentredString(_NR_CTR, _TRUST_CY - 0.22 * inch,
                            f"a/o {trust_list[0]['as_of_date']}")

    # ── Non-retirement account circles ─────────────────────────────────────────
    nr_all_c1 = nr_c1 + nr_joint
    for cx, cy, b in _nr_c1_positions(nr_all_c1):
        _acct_oval(c, cx, cy, _NR_ARX, _NR_ARY,
                   b["account_type"], b.get("account_number_last4",""),
                   b["balance"], b.get("as_of_date",""),
                   b.get("cash_value",0), bool(b.get("is_stale")))

    c2_ys = _nr_c2_ys(len(nr_c2))
    for i, b in enumerate(nr_c2):
        _acct_oval(c, _NR_C2, c2_ys[i], _NR_ARX, _NR_ARY,
                   b["account_type"], b.get("account_number_last4",""),
                   b["balance"], b.get("as_of_date",""),
                   b.get("cash_value",0), bool(b.get("is_stale")))

    # ── Liabilities itemised box  (padded, tan background) ────────────────────
    if liab_list:
        PAD   = 0.13 * inch
        n_row = len(liab_list)
        lb_h  = _LIAB_HDR_H + n_row * _LIAB_ROW_H + 0.14 * inch
        lb_h  = max(lb_h, 0.70 * inch)
        lb_x  = _LIAB_CX - _LIAB_W / 2

        c.setFillColor(TAN_BOX)
        c.setStrokeColor(HexColor("#9A905A"));  c.setLineWidth(0.6)
        c.rect(lb_x, _LIAB_BOT, _LIAB_W, lb_h, fill=1, stroke=1)

        c.setFillColor(black);  c.setFont("Helvetica-Bold", 8.5)
        c.drawCentredString(_LIAB_CX, _LIAB_BOT + lb_h - 0.18 * inch, "Liabilities:")

        c.setFont("Helvetica", 7.5)
        ry = _LIAB_BOT + lb_h - 0.36 * inch
        for b in liab_list:
            inst = (b.get("institution") or b.get("account_type",""))[:24]
            c.drawString(lb_x + PAD, ry, inst)
            c.drawRightString(lb_x + _LIAB_W - PAD, ry, _fmt(float(b["balance"] or 0)))
            ry -= _LIAB_ROW_H

    # ── NON RETIREMENT TOTAL ────────────────────────────────────────────────────
    _box(c, _NRT_CX, _NRT_BOT + _NRT_H/2, _NRT_W, _NRT_H,
         fill=TOTAL_BOX, border=GRAY_BORDER,
         lines=["NON RETIREMENT TOTAL", _fmt(non_ret)], fs=9)

    # ── Footnote with dark grey border ─────────────────────────────────────────
    fn_text = "* indicates we do not have up to date information"
    fn_fs   = 6.5
    c.setFont("Helvetica-Oblique", fn_fs)
    fn_w = c.stringWidth(fn_text, "Helvetica-Oblique", fn_fs)
    fn_x = W - _M_BORDER - 0.08*inch - fn_w
    fn_y = _M_BORDER + 0.05 * inch
    pad  = 0.045 * inch
    cap  = fn_fs / 72 * inch
    c.setFillColor(white)
    c.setStrokeColor(FOOTNOTE_BD);  c.setLineWidth(0.5)
    c.rect(fn_x - pad, fn_y - pad, fn_w + 2*pad, cap + 2*pad, fill=1, stroke=1)
    c.setFillColor(STALE_RED);  c.setFont("Helvetica-Oblique", fn_fs)
    c.drawString(fn_x, fn_y, fn_text)


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_tcc_pdf(client, report, balances):
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(W, H))
    draw_tcc_page(c, dict(client), dict(report), [dict(b) for b in balances])
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()
