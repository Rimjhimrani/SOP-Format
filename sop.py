import streamlit as st
import io
import math
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm

st.set_page_config(page_title="SOP Builder", layout="wide")

# ─── Session State ────────────────────────────────────────────────────────────
defaults = {
    "steps": [],
    "sop_no": "SCM/STR/LS/02",
    "rev_no": "0.0",
    "date": "26-12-2024",
    "page_info": "1 OUT OF 1",
    "unit": "Chakan Plant",
    "area": "Stores",
    "sub_area": "Line Side",
    "zone": "DIRECT LOCATIONS",
    "title": "Direct Supply of Parts from Stores to Assy Line",
    "purpose": "Supply of Supplier Packs to Line Side",
    "scope": "All Parts under direct supply category (suggested by quality/operation)",
    "owner": "Stores Manager",
    "company_name": "PINNACLE MOBILITY",
    "composed_by": "Agilomatrix Pvt Ltd (connectus@agilomatrix.com)",
    "change_records": [
        {"sno": "1", "date": "17-12-2024", "rev": "0.0", "desc": "Original Version",
         "change_letter": "NA", "prepared": "Prince S", "reviewed": "Ajay G", "approved": "Vilas B"},
    ],
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

SHAPE_TYPES = {
    "Process (Rectangle)": "rect",
    "Decision (Diamond)": "diamond",
    "Oval / Terminator": "oval",
    "Parallelogram (Input/Output)": "parallelogram",
    "Connector / Annotation Text": "arrow_text",
}

# ─── PDF Helpers ──────────────────────────────────────────────────────────────
def wrapped_lines(c, text, max_w, font_name, font_size):
    words = str(text).split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if c.stringWidth(test, font_name, font_size) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines if lines else [""]

def draw_centered_text(c, text, cx, cy, max_w,
                       font_name="Helvetica", font_size=7, color=colors.black):
    lines = wrapped_lines(c, text, max_w, font_name, font_size)
    line_h = font_size + 1.5
    total_h = len(lines) * line_h
    start_y = cy + total_h / 2 - line_h * 0.7
    c.setFont(font_name, font_size)
    c.setFillColor(color)
    for i, line in enumerate(lines):
        c.drawCentredString(cx, start_y - i * line_h, line)

def draw_left_text(c, text, x, cy, max_w,
                   font_name="Helvetica", font_size=6.5, color=colors.black):
    lines = wrapped_lines(c, text, max_w, font_name, font_size)
    line_h = font_size + 1.5
    total_h = len(lines) * line_h
    start_y = cy + total_h / 2 - line_h * 0.7
    c.setFont(font_name, font_size)
    c.setFillColor(color)
    for i, line in enumerate(lines):
        c.drawString(x, start_y - i * line_h, line)

def draw_arrow_down(c, x, y_from, y_to):
    """Draw a downward arrow from y_from to y_to."""
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    size = 3.5
    c.line(x, y_from, x, y_to + size * 1.5)
    c.setFillColor(colors.black)
    p = c.beginPath()
    p.moveTo(x, y_to)
    p.lineTo(x - size, y_to + size * 1.5)
    p.lineTo(x + size, y_to + size * 1.5)
    p.close()
    c.drawPath(p, fill=1, stroke=0)

def draw_rect_shape(c, x, y, w, h, text, font_size=7):
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.white)
    c.setLineWidth(0.8)
    c.rect(x, y, w, h, fill=1, stroke=1)
    draw_centered_text(c, text, x + w / 2, y + h / 2, w - 4, font_size=font_size)

def draw_oval_shape(c, x, y, w, h, text, font_size=7):
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.HexColor("#2c2c2c"))
    c.setLineWidth(0.8)
    c.ellipse(x, y, x + w, y + h, fill=1, stroke=1)
    draw_centered_text(c, text, x + w / 2, y + h / 2, w - 6,
                       font_size=font_size, color=colors.white)

def draw_diamond_shape(c, x, y, w, h, text, font_size=6.5):
    cx, cy = x + w / 2, y + h / 2
    p = c.beginPath()
    p.moveTo(cx, y + h)
    p.lineTo(x + w, cy)
    p.lineTo(cx, y)
    p.lineTo(x, cy)
    p.close()
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.white)
    c.setLineWidth(0.8)
    c.drawPath(p, fill=1, stroke=1)
    draw_centered_text(c, text, cx, cy, w * 0.55, font_size=font_size)

def draw_parallelogram_shape(c, x, y, w, h, text, font_size=7):
    skew = 7
    p = c.beginPath()
    p.moveTo(x + skew, y + h)
    p.lineTo(x + w,     y + h)
    p.lineTo(x + w - skew, y)
    p.lineTo(x,         y)
    p.close()
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.white)
    c.setLineWidth(0.8)
    c.drawPath(p, fill=1, stroke=1)
    draw_centered_text(c, text, x + w / 2, y + h / 2, w - 10, font_size=font_size)

# ─── Table drawing helpers ────────────────────────────────────────────────────
def draw_table_structure(c, XS, FLOW_COL_IDX, table_top, table_bottom, row_bottoms):
    """
    Draw the entire process-steps table in ONE pass with clean borders:

    Strategy:
    - Fill full table area white
    - Draw outer border as one rect
    - Draw vertical column dividers top-to-bottom (no interruptions)
    - Draw horizontal row dividers ONLY for the side columns (not flow col)
    - Flow column stays uncut — seamless vertical channel
    """
    ML_x    = XS[0]
    total_w = XS[-1] - XS[0]
    total_h = table_top - table_bottom

    # 1. White fill entire table area
    c.setFillColor(colors.white)
    c.rect(ML_x, table_bottom, total_w, total_h, fill=1, stroke=0)

    # 2. Outer border
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    c.rect(ML_x, table_bottom, total_w, total_h, fill=0, stroke=1)

    # 3. Vertical column dividers (full height, top to bottom)
    c.setLineWidth(0.5)
    for x in XS[1:-1]:   # interior vertical lines only
        c.line(x, table_bottom, x, table_top)

    # 4. Horizontal row separators — ONLY between side columns, skip flow col
    flow_x1 = XS[FLOW_COL_IDX]
    flow_x2 = XS[FLOW_COL_IDX + 1]

    c.setLineWidth(0.4)
    for row_bottom in row_bottoms[:-1]:   # all except last (already covered by outer border)
        y = row_bottom
        # Left side columns (indices 0 .. FLOW_COL_IDX-1)
        if FLOW_COL_IDX > 0:
            c.line(XS[0], y, XS[FLOW_COL_IDX], y)
        # Right side columns (indices FLOW_COL_IDX+1 .. end)
        if FLOW_COL_IDX < 5:
            c.line(XS[FLOW_COL_IDX + 1], y, XS[-1], y)


# ─── PDF Generation ───────────────────────────────────────────────────────────
def generate_pdf(steps, meta):
    buf = io.BytesIO()
    PW, PH = landscape(A4)
    c  = canvas.Canvas(buf, pagesize=(PW, PH))

    ML = 14 * mm
    MR = 14 * mm
    MT = 12 * mm
    TW = PW - ML - MR

    cur_y = PH - MT

    # ══ 1. HEADER ════════════════════════════════════════════════════════════
    HEADER_H = 22 * mm
    left_w   = 44 * mm
    right_w  = 83 * mm
    centre_w = TW - left_w - right_w

    # Company name block (left)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.black)
    c.drawString(ML, cur_y - 7, meta["company_name"])

    # eka logo text with blue color
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.HexColor("#1a6dcc"))
    c.drawString(ML, cur_y - 18, "eka")
    c.setFillColor(colors.black)

    # Centre title block
    cx_title = ML + left_w + centre_w / 2
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(cx_title, cur_y - 7, "STANDARD OPERATING PROCEDURE")
    c.setFont("Helvetica", 8.5)
    draw_centered_text(c, meta["title"], cx_title, cur_y - 18, centre_w - 4, font_size=8.5)

    # Right meta grid
    RX  = ML + left_w + centre_w
    c1w = 18 * mm
    c2w = 24 * mm
    c3w = 12 * mm
    c4w = right_w - c1w - c2w - c3w
    rh  = HEADER_H / 4

    meta_rows = [
        ("SOP No.",  meta["sop_no"],   "Page",    meta["page_info"]),
        ("Rev No.",  meta["rev_no"],   "Date",    meta["date"]),
        ("Unit",     meta["unit"],     "Area",    meta["area"]),
        ("Sub Area", meta["sub_area"], "Zone",    meta["zone"]),
    ]
    for ri, (l1, v1, l2, v2) in enumerate(meta_rows):
        ry  = cur_y - (ri + 1) * rh
        rxs = [RX, RX+c1w, RX+c1w+c2w, RX+c1w+c2w+c3w, RX+right_w]
        for ci, (txt, is_lbl) in enumerate([(l1,True),(v1,False),(l2,True),(v2,False)]):
            cw = rxs[ci+1] - rxs[ci]
            c.setFillColor(colors.HexColor("#EEF3FF") if is_lbl else colors.white)
            c.setStrokeColor(colors.black)
            c.setLineWidth(0.5)
            c.rect(rxs[ci], ry, cw, rh, fill=1, stroke=1)
            c.setFillColor(colors.black)
            fn = "Helvetica-Bold" if is_lbl else "Helvetica"
            fs = 5.8 if is_lbl else 6.2
            draw_left_text(c, txt, rxs[ci]+1.5, ry+rh/2, cw-3, fn, fs)

    c.setLineWidth(1)
    c.line(ML, cur_y - HEADER_H, ML + TW, cur_y - HEADER_H)
    cur_y -= HEADER_H

    # ══ 2. PURPOSE / SCOPE ══════════════════════════════════════════════════
    PS_H = 8 * mm
    PL_W = 18 * mm
    PV_W = 82 * mm
    SL_W = 14 * mm
    SV_W = TW - PL_W - PV_W - SL_W

    c.setLineWidth(0.6)
    for x, w, txt, bold, centre in [
        (ML,           PL_W, "Purpose", True,  False),
        (ML+PL_W,      PV_W, meta["purpose"], False, False),
        (ML+PL_W+PV_W, SL_W, "Scope",   True,  False),
        (ML+PL_W+PV_W+SL_W, SV_W, meta["scope"], False, True),
    ]:
        c.setFillColor(colors.white)
        c.rect(x, cur_y - PS_H, w, PS_H, fill=1, stroke=1)
        c.setFillColor(colors.black)
        if bold:
            c.setFont("Helvetica-Bold", 8)
            c.drawString(x + 2, cur_y - PS_H + 2.5, txt)
        elif centre:
            draw_centered_text(c, txt, x + w/2, cur_y - PS_H/2, w - 4, font_size=6.5)
        else:
            draw_left_text(c, txt, x + 2, cur_y - PS_H/2, w - 4, font_size=7.5)

    cur_y -= PS_H

    # ══ 3. COLUMN LAYOUT ════════════════════════════════════════════════════
    COL_IN   = 28 * mm
    COL_OUT  = 26 * mm
    COL_RESP = 30 * mm
    COL_DOC  = 26 * mm
    COL_MEAS = 28 * mm
    COL_FLOW = TW - COL_IN - COL_OUT - COL_RESP - COL_DOC - COL_MEAS

    FLOW_COL_IDX = 1

    XS = [
        ML,
        ML + COL_IN,
        ML + COL_IN + COL_FLOW,
        ML + COL_IN + COL_FLOW + COL_OUT,
        ML + COL_IN + COL_FLOW + COL_OUT + COL_RESP,
        ML + COL_IN + COL_FLOW + COL_OUT + COL_RESP + COL_DOC,
        ML + TW,
    ]
    FLOW_CX = (XS[1] + XS[2]) / 2

    # ── Header row 1 ─────────────────────────────────────────────────────
    HDR1_H = 7 * mm
    c.setFillColor(colors.HexColor("#DDEEFF"))
    c.rect(ML, cur_y - HDR1_H, TW, HDR1_H, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.black)
    c.drawString(ML + 3, cur_y - HDR1_H + 2.5, "Process Steps:")
    c.drawString(XS[3] + 3, cur_y - HDR1_H + 2.5, f"OWNER :   {meta['owner']}")
    cur_y -= HDR1_H

    # ── Header row 2 ─────────────────────────────────────────────────────
    HDR2_H = 7 * mm
    col_labels = ["Input", "Process Flow", "Output", "Responsible",
                  "Doc. Format /\nSystem", "Effective\nMeasurement"]
    for i, label in enumerate(col_labels):
        cw = XS[i+1] - XS[i]
        c.setFillColor(colors.HexColor("#EEF3FF"))
        c.rect(XS[i], cur_y - HDR2_H, cw, HDR2_H, fill=1, stroke=1)
        c.setFillColor(colors.black)
        lines = label.split("\n")
        lh = 6.5
        sy = cur_y - HDR2_H/2 + (len(lines)-1)*lh/2
        for li, ln in enumerate(lines):
            c.setFont("Helvetica-Bold", 6.5)
            c.drawCentredString(XS[i]+cw/2, sy - li*(lh+0.5), ln)
    cur_y -= HDR2_H

    # ══ 4. STEP ROWS ════════════════════════════════════════════════════════
    SHAPE_H = {
        "rect":          9 * mm,
        "oval":          9 * mm,
        "parallelogram": 9 * mm,
        "diamond":      15 * mm,
        "arrow_text":    6 * mm,
    }
    V_PAD = 6 * mm

    table_top   = cur_y   # top of data rows (just below col header)
    total_steps = len(steps)

    # ── PASS 1: calculate all row geometries ─────────────────────────────────
    row_data = []   # list of (row_bottom_y, row_h, step)
    scan_y = cur_y
    for step in steps:
        sh_h  = SHAPE_H.get(step["shape"], 9 * mm)
        ROW_H = sh_h + 2 * V_PAD
        ry    = scan_y - ROW_H
        row_data.append((ry, ROW_H, step))
        scan_y = ry
    table_bottom = scan_y   # bottom of last row

    # ── PASS 2: draw table structure (clean, no interior flow-col lines) ─────
    row_bottoms = [rd[0] for rd in row_data]
    draw_table_structure(c, XS, FLOW_COL_IDX, table_top, table_bottom, row_bottoms)

    # ── PASS 3: side-column text ──────────────────────────────────────────────
    for (ry, ROW_H, step) in row_data:
        for col_i, key in [(0, "input_label"), (2, "output_label"),
                           (3, "responsible"), (4, "doc_format"), (5, "measurement")]:
            txt = step.get(key, "")
            if txt:
                cw = XS[col_i+1] - XS[col_i]
                draw_centered_text(c, txt, XS[col_i]+cw/2, ry+ROW_H/2, cw-4, font_size=6.5)

    # ── PASS 4: arrows and shapes on top ─────────────────────────────────────
    sh_w = COL_FLOW * 0.78
    position = step.get("position", "center")
    if position == "center":
        sh_x = FLOW_CX - sh_w / 2
    elif position == "right (YES)":
        sh_x = FLOW_CX + COL_FLOW * 0.55
    elif position == "left (NO)":
        sh_x = FLOW_CX - COL_FLOW * 0.55 - sh_w
    last_decision = None
    

    for idx, (ry, ROW_H, step) in enumerate(row_data):
        shape       = step["shape"]
        sh_h        = SHAPE_H.get(shape, 9 * mm)
        shape_bot   = ry + V_PAD
        shape_top_y = shape_bot + sh_h
        shape_mid   = shape_bot + sh_h / 2

        # Arrow: from midpoint of gap above this shape down to shape top
        if idx > 0:
            prev_ry, prev_rh, _ = row_data[idx - 1]
            prev_shape_bot = prev_ry + V_PAD
            prev_sh_h      = SHAPE_H.get(row_data[idx-1][2]["shape"], 9 * mm)
            arr_from = prev_shape_bot   # bottom of previous shape
            arr_to   = shape_top_y + 1 if shape != "diamond" else shape_mid + sh_h/2 + 1
            draw_arrow_down(c, FLOW_CX, arr_from, arr_to)

        if shape == "rect":
            draw_rect_shape(c, sh_x, shape_bot, sh_w, sh_h, step["text"])
        elif shape == "oval":
            draw_oval_shape(c, sh_x, shape_bot, sh_w, sh_h, step["text"])
        elif shape == "diamond":
            draw_diamond_shape(c, sh_x, shape_bot, sh_w, sh_h, step["text"])
            flow_type = step.get("decision_flow", "yes_main")
            # YES path (right side)
            c.setFont("Helvetica-Bold", 6.5)
            if flow_type == "yes_main":
                c.setFillColor(colors.HexColor("#006600"))
                c.drawString(sh_x + sh_w + 2, shape_mid - 3, "YES ↓")
            elif flow_type == "yes_end":
                c.setFillColor(colors.HexColor("#006600"))
                c.drawString(sh_x + sh_w + 2, shape_mid - 3, "YES → END")
            # NO path (bottom)
            if flow_type == "no_main":
                c.setFillColor(colors.HexColor("#CC0000"))
                c.drawString(FLOW_CX - 5, shape_bot - 8, "NO ↓")
            elif flow_type == "no_end":
                c.setFillColor(colors.HexColor("#CC0000"))
                c.drawString(FLOW_CX - 5, shape_bot - 8, "NO → END")
            c.setFillColor(colors.black)
        elif shape == "parallelogram":
            draw_parallelogram_shape(c, sh_x, shape_bot, sh_w, sh_h, step["text"])
        elif shape == "arrow_text":
            c.setFont("Helvetica-Oblique", 7)
            c.setFillColor(colors.HexColor("#333333"))
            c.drawCentredString(FLOW_CX, shape_mid, step["text"])
            c.setFillColor(colors.black)

    cur_y = table_bottom

    # ══ 5. SOP CHANGE RECORD ════════════════════════════════════════════════
    cur_y -= 4 * mm

    CR_TITLE_H = 6 * mm
    c.setFillColor(colors.HexColor("#DDEEFF"))
    c.rect(ML, cur_y - CR_TITLE_H, TW, CR_TITLE_H, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.black)
    c.drawCentredString(ML + TW/2, cur_y - CR_TITLE_H + 2, "SOP Change Record")
    cur_y -= CR_TITLE_H

    CR_COLS   = ["S.No.", "Effective\nDate", "REV.\nNo.", "Change Description",
                 "Change Letter\n(Process:P / Doc:D / System:S)",
                 "Prepared By", "Reviewed By", "Approved By"]
    CR_WIDTHS = [10*mm, 20*mm, 14*mm, 52*mm, 46*mm, 22*mm, 22*mm, 0]
    CR_WIDTHS[-1] = TW - sum(CR_WIDTHS[:-1])
    CR_XS = [ML]
    for w in CR_WIDTHS:
        CR_XS.append(CR_XS[-1] + w)

    CR_HDR_H = 8 * mm
    for i, label in enumerate(CR_COLS):
        cw = CR_XS[i+1] - CR_XS[i]
        c.setFillColor(colors.HexColor("#EEF3FF"))
        c.rect(CR_XS[i], cur_y - CR_HDR_H, cw, CR_HDR_H, fill=1, stroke=1)
        c.setFillColor(colors.black)
        lines = label.split("\n")
        lh = 6
        sy = cur_y - CR_HDR_H/2 + (len(lines)-1)*lh/2
        for li, ln in enumerate(lines):
            c.setFont("Helvetica-Bold", 5.5)
            c.drawCentredString(CR_XS[i]+cw/2, sy - li*(lh+0.5), ln)
    cur_y -= CR_HDR_H

    CR_ROW_H = 6 * mm
    for row in meta.get("change_records", []):
        vals = [row.get("sno",""), row.get("date",""), row.get("rev",""),
                row.get("desc",""), row.get("change_letter",""),
                row.get("prepared",""), row.get("reviewed",""), row.get("approved","")]
        for i, val in enumerate(vals):
            cw = CR_XS[i+1] - CR_XS[i]
            c.setFillColor(colors.white)
            c.rect(CR_XS[i], cur_y - CR_ROW_H, cw, CR_ROW_H, fill=1, stroke=1)
            draw_centered_text(c, val, CR_XS[i]+cw/2, cur_y-CR_ROW_H/2, cw-3, font_size=6)
        cur_y -= CR_ROW_H

    # Footer
    c.setFont("Helvetica-Oblique", 6)
    c.setFillColor(colors.HexColor("#555555"))
    c.drawCentredString(ML + TW/2, cur_y - 5, f"Composed By: {meta['composed_by']}")

    c.save()
    buf.seek(0)
    return buf


# ─── Streamlit UI ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 1rem; }
    h1 { font-size: 1.35rem; margin-bottom: 0.2rem; }
    h2 { font-size: 1.05rem; }
    .stButton > button { width: 100%; }
</style>
""", unsafe_allow_html=True)

st.title("📋 SOP Builder — Standard Operating Procedure")
st.caption("Fill in the details, build your process flow, then download as PDF.")

tab1, tab2, tab3, tab4 = st.tabs(
    ["🏷️ Header Info", "🔷 Process Flow", "📝 Change Record", "📄 Download PDF"])

# ── TAB 1 ─────────────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Document Header Fields")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.session_state.company_name = st.text_input("Company Name",  st.session_state.company_name)
        st.session_state.title        = st.text_input("SOP Sub-title", st.session_state.title)
        st.session_state.sop_no       = st.text_input("SOP No.",       st.session_state.sop_no)
        st.session_state.rev_no       = st.text_input("Rev. No.",      st.session_state.rev_no)
    with c2:
        st.session_state.date         = st.text_input("Date",          st.session_state.date)
        st.session_state.page_info    = st.text_input("Page Info",     st.session_state.page_info)
        st.session_state.unit         = st.text_input("Unit",          st.session_state.unit)
        st.session_state.area         = st.text_input("Area",          st.session_state.area)
    with c3:
        st.session_state.sub_area     = st.text_input("Sub Area",      st.session_state.sub_area)
        st.session_state.zone         = st.text_input("Zone",          st.session_state.zone)
        st.session_state.owner        = st.text_input("Owner",         st.session_state.owner)
        st.session_state.composed_by  = st.text_input("Composed By",   st.session_state.composed_by)
    st.divider()
    st.subheader("Purpose & Scope")
    st.session_state.purpose = st.text_input("Purpose", st.session_state.purpose)
    st.session_state.scope   = st.text_area("Scope",    st.session_state.scope, height=80)

# ── TAB 2 ─────────────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Add a Process Step")
    with st.form("add_step_form", clear_on_submit=True):
        shape_label = st.selectbox("Box / Shape Type", list(SHAPE_TYPES.keys()))
        step_text   = st.text_input("Text inside shape *")
        c1, c2, c3 = st.columns(3)
        with c1:
            input_label  = st.text_input("Input Label")
            output_label = st.text_input("Output Label")
        with c2:
            responsible  = st.text_input("Responsible")
            doc_format   = st.text_input("Doc. Format / System")
        with c3:
            measurement = st.text_input("Effective Measurement")
            yes_label   = st.text_input("YES label (diamonds)", value="YES")
            no_label    = st.text_input("NO label (diamonds)",  value="NO")

        if st.form_submit_button("➕ Add Step", use_container_width=True):
            if step_text.strip():
                st.session_state.steps.append({
                    "shape":        SHAPE_TYPES[shape_label],
                    "text":         step_text,
                    "input_label":  input_label,
                    "output_label": output_label,
                    "responsible":  responsible,
                    "doc_format":   doc_format,
                    "measurement":  measurement,
                    "yes_label":    yes_label,
                    "no_label":     no_label,

                    # ✅ ADD THESE
                    "position": position,
                    "branch_from_prev": branch_from_prev,
                })
                st.success(f"✅ Added: [{shape_label}] {step_text}")
            else:
                st.warning("Please enter shape text.")

    st.divider()
    st.subheader(f"Steps ({len(st.session_state.steps)})")
    if not st.session_state.steps:
        st.info("No steps yet. Use the form above to add process flow steps.")
    else:
        reverse_map = {v: k for k, v in SHAPE_TYPES.items()}
        for i, step in enumerate(st.session_state.steps):
            label = reverse_map.get(step["shape"], step["shape"])
            with st.expander(f"**Step {i+1}** › [{label}]  {step['text']}", expanded=False):
                bc1, bc2, bc3, _ = st.columns([1, 1, 1, 4])
                if bc1.button("⬆️ Up",     key=f"up_{i}"):
                    if i > 0:
                        st.session_state.steps[i], st.session_state.steps[i-1] = \
                            st.session_state.steps[i-1], st.session_state.steps[i]
                    st.rerun()
                if bc2.button("⬇️ Down",   key=f"dn_{i}"):
                    if i < len(st.session_state.steps)-1:
                        st.session_state.steps[i], st.session_state.steps[i+1] = \
                            st.session_state.steps[i+1], st.session_state.steps[i]
                    st.rerun()
                if bc3.button("🗑️ Delete", key=f"del_{i}"):
                    st.session_state.steps.pop(i); st.rerun()
                st.write(f"**Input:** {step['input_label'] or '—'}  |  **Output:** {step['output_label'] or '—'}")
                st.write(f"**Responsible:** {step['responsible'] or '—'}  |  "
                         f"**Doc:** {step['doc_format'] or '—'}  |  "
                         f"**Measurement:** {step['measurement'] or '—'}")

# ── TAB 3 ─────────────────────────────────────────────────────────────────────
with tab3:
    st.subheader("SOP Change Record")
    with st.form("cr_form", clear_on_submit=True):
        r1c1, r1c2, r1c3, r1c4 = st.columns(4)
        sno   = r1c1.text_input("S.No.")
        cdate = r1c2.text_input("Effective Date")
        rev   = r1c3.text_input("REV. No.")
        desc  = r1c4.text_input("Change Description")
        r2c1, r2c2, r2c3, r2c4 = st.columns(4)
        cl    = r2c1.text_input("Change Letter")
        prep  = r2c2.text_input("Prepared By")
        rev2  = r2c3.text_input("Reviewed By")
        appr  = r2c4.text_input("Approved By")
        if st.form_submit_button("➕ Add Row", use_container_width=True):
            st.session_state.change_records.append({
                "sno": sno, "date": cdate, "rev": rev, "desc": desc,
                "change_letter": cl, "prepared": prep,
                "reviewed": rev2, "approved": appr,
            })
            st.success("Row added.")
    st.divider()
    for i, cr in enumerate(st.session_state.change_records):
        cc1, cc2 = st.columns([9, 1])
        cc1.write(
            f"**{cr['sno']}** | {cr['date']} | Rev {cr['rev']} | {cr['desc']} | "
            f"Prepared: {cr['prepared']} | Reviewed: {cr['reviewed']} | Approved: {cr['approved']}"
        )
        if cc2.button("🗑️", key=f"crdel_{i}"):
            st.session_state.change_records.pop(i); st.rerun()

# ── TAB 4 ─────────────────────────────────────────────────────────────────────
with tab4:
    st.subheader("Generate & Download PDF")
    if not st.session_state.steps:
        st.warning("⚠️ Add at least one process step before generating the PDF.")
    else:
        st.success(f"Ready — **{len(st.session_state.steps)} step(s)** will be included.")
        meta = {k: st.session_state[k] for k in [
            "company_name", "title", "sop_no", "rev_no", "date", "page_info",
            "unit", "area", "sub_area", "zone", "owner", "purpose", "scope",
            "composed_by", "change_records",
        ]}
        pdf_buf = generate_pdf(st.session_state.steps, meta)
        st.download_button(
            label="📥 Download SOP PDF",
            data=pdf_buf,
            file_name="SOP_Document.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        st.divider()
        st.subheader("Step Summary")
        reverse_map = {v: k for k, v in SHAPE_TYPES.items()}
        rows = [{
            "Step":        i + 1,
            "Shape":       reverse_map.get(s["shape"], s["shape"]),
            "Text":        s["text"],
            "Input":       s["input_label"],
            "Output":      s["output_label"],
            "Responsible": s["responsible"],
        } for i, s in enumerate(st.session_state.steps)]
        st.dataframe(rows, use_container_width=True, hide_index=True)
