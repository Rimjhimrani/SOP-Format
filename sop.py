import streamlit as st
import io
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader
import math

st.set_page_config(page_title="SOP Builder", layout="wide")

# ─── Session State Init ───────────────────────────────────────────────────────
if "steps" not in st.session_state:
    st.session_state.steps = []
if "sop_no" not in st.session_state:
    st.session_state.sop_no = "SCM/STR/LS/02"
if "rev_no" not in st.session_state:
    st.session_state.rev_no = "0.0"
if "date" not in st.session_state:
    st.session_state.date = "26-12-2024"
if "page_info" not in st.session_state:
    st.session_state.page_info = "1 OUT OF 1"
if "unit" not in st.session_state:
    st.session_state.unit = "Chakan Plant"
if "area" not in st.session_state:
    st.session_state.area = "Stores"
if "sub_area" not in st.session_state:
    st.session_state.sub_area = "Line Side"
if "zone" not in st.session_state:
    st.session_state.zone = "DIRECT LOCATIONS"
if "title" not in st.session_state:
    st.session_state.title = "Direct Supply of Parts from Stores to Assy Line"
if "purpose" not in st.session_state:
    st.session_state.purpose = "Supply of Supplier Packs to Line Side"
if "scope" not in st.session_state:
    st.session_state.scope = "All Parts under direct supply category (suggested by quality/operation)"
if "owner" not in st.session_state:
    st.session_state.owner = "Stores Manager"
if "company_name" not in st.session_state:
    st.session_state.company_name = "PINNACLE MOBILITY"
if "composed_by" not in st.session_state:
    st.session_state.composed_by = "Agilomatrix Pvt Ltd (connectus@agilomatrix.com)"
if "change_records" not in st.session_state:
    st.session_state.change_records = [
        {"sno": "1", "date": "17-12-2024", "rev": "0.0", "desc": "Original Version",
         "change_letter": "NA", "prepared": "Prince S", "reviewed": "Ajay G", "approved": "Vilas B"},
    ]

# ─── Helpers ─────────────────────────────────────────────────────────────────
SHAPE_TYPES = {
    "Process (Rectangle)": "rect",
    "Decision (Diamond)": "diamond",
    "Oval / Terminator": "oval",
    "Parallelogram (Input/Output)": "parallelogram",
    "Arrow / Connector Text": "arrow_text",
}

def add_step(shape, text, input_label="", output_label="", responsible="", doc_format="", measurement="", yes_label="YES", no_label="NO"):
    st.session_state.steps.append({
        "shape": shape,
        "text": text,
        "input_label": input_label,
        "output_label": output_label,
        "responsible": responsible,
        "doc_format": doc_format,
        "measurement": measurement,
        "yes_label": yes_label,
        "no_label": no_label,
    })

def move_up(i):
    if i > 0:
        st.session_state.steps[i], st.session_state.steps[i-1] = st.session_state.steps[i-1], st.session_state.steps[i]

def move_down(i):
    if i < len(st.session_state.steps) - 1:
        st.session_state.steps[i], st.session_state.steps[i+1] = st.session_state.steps[i+1], st.session_state.steps[i]

def delete_step(i):
    st.session_state.steps.pop(i)

# ─── PDF Generation ───────────────────────────────────────────────────────────
def draw_rect(c, x, y, w, h, text, font_size=7):
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.white)
    c.rect(x, y, w, h, fill=1)
    c.setFillColor(colors.black)
    _draw_wrapped_text(c, text, x + w/2, y + h/2, w - 4, font_size)

def draw_oval(c, x, y, w, h, text, font_size=7):
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.HexColor("#2c2c2c"))
    c.ellipse(x, y, x+w, y+h, fill=1)
    c.setFillColor(colors.white)
    _draw_wrapped_text(c, text, x + w/2, y + h/2, w - 4, font_size)

def draw_diamond(c, x, y, w, h, text, font_size=6.5):
    cx, cy = x + w/2, y + h/2
    path = c.beginPath()
    path.moveTo(cx, y + h)
    path.lineTo(x + w, cy)
    path.lineTo(cx, y)
    path.lineTo(x, cy)
    path.close()
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.white)
    c.drawPath(path, fill=1)
    c.setFillColor(colors.black)
    _draw_wrapped_text(c, text, cx, cy, w * 0.6, font_size)

def draw_parallelogram(c, x, y, w, h, text, font_size=7):
    skew = 8
    path = c.beginPath()
    path.moveTo(x + skew, y + h)
    path.lineTo(x + w, y + h)
    path.lineTo(x + w - skew, y)
    path.lineTo(x, y)
    path.close()
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.white)
    c.drawPath(path, fill=1)
    c.setFillColor(colors.black)
    _draw_wrapped_text(c, text, x + w/2, y + h/2, w - 8, font_size)

def _draw_wrapped_text(c, text, cx, cy, max_w, font_size=7):
    c.setFont("Helvetica", font_size)
    words = text.split()
    lines = []
    cur = ""
    for w in words:
        test = (cur + " " + w).strip()
        if c.stringWidth(test, "Helvetica", font_size) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    line_h = font_size + 1.5
    total_h = len(lines) * line_h
    start_y = cy + total_h/2 - line_h/2
    for i, line in enumerate(lines):
        c.drawCentredString(cx, start_y - i * line_h, line)

def draw_arrow(c, x1, y1, x2, y2):
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.8)
    c.line(x1, y1, x2, y2)
    # arrowhead
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 4
    c.setFillColor(colors.black)
    path = c.beginPath()
    path.moveTo(x2, y2)
    path.lineTo(x2 - size * math.cos(angle - 0.4), y2 - size * math.sin(angle - 0.4))
    path.lineTo(x2 - size * math.cos(angle + 0.4), y2 - size * math.sin(angle + 0.4))
    path.close()
    c.drawPath(path, fill=1)

def generate_pdf(steps, meta):
    buf = io.BytesIO()
    W, H = landscape(A4)
    c = canvas.Canvas(buf, pagesize=(W, H))

    margin = 15 * mm
    top = H - margin
    
    # ── Header ────────────────────────────────────────────────────────────────
    # Company block
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(colors.black)
    c.drawString(margin, top - 10, meta["company_name"])
    c.setFont("Helvetica", 7)
    c.drawString(margin, top - 20, "eka")

    # Title block
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(W/2, top - 8, "STANDARD OPERATING PROCEDURE")
    c.setFont("Helvetica", 9)
    c.drawCentredString(W/2, top - 20, meta["title"])

    # Right meta grid
    rx = W - margin - 80*mm
    ry = top - 8
    meta_data = [
        ["SOP No.", meta["sop_no"], "Page", meta["page_info"]],
        ["Rev No.", meta["rev_no"], "Date", meta["date"]],
        ["Unit", meta["unit"], "Area", meta["area"]],
        ["Sub Area", meta["sub_area"], "Zone", meta["zone"]],
    ]
    col_w = [18*mm, 25*mm, 14*mm, 24*mm]
    row_h = 5*mm
    for ri, row in enumerate(meta_data):
        cx_pos = rx
        for ci, cell in enumerate(row):
            cw = col_w[ci]
            c.setStrokeColor(colors.black)
            c.setFillColor(colors.white)
            c.rect(cx_pos, ry - (ri+1)*row_h, cw, row_h, fill=1)
            c.setFillColor(colors.black)
            fs = 6 if ci % 2 == 0 else 6.5
            fw = "Helvetica-Bold" if ci % 2 == 0 else "Helvetica"
            c.setFont(fw, fs)
            c.drawString(cx_pos + 1.5, ry - (ri+1)*row_h + 1.5, str(cell))
            cx_pos += cw

    header_bottom = top - 32
    c.line(margin, header_bottom, W - margin, header_bottom)

    # ── Purpose / Scope ───────────────────────────────────────────────────────
    ps_y = header_bottom - 7*mm
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.black)
    c.rect(margin, ps_y - 6*mm, 20*mm, 6*mm, fill=0)
    c.drawString(margin + 1, ps_y - 4*mm, "Purpose")
    c.rect(margin + 20*mm, ps_y - 6*mm, 90*mm, 6*mm, fill=0)
    c.setFont("Helvetica", 7.5)
    c.drawString(margin + 21*mm, ps_y - 4*mm, meta["purpose"])

    scope_x = margin + 115*mm
    c.setFont("Helvetica-Bold", 8)
    c.rect(scope_x, ps_y - 6*mm, 18*mm, 6*mm, fill=0)
    c.drawString(scope_x + 1, ps_y - 4*mm, "Scope")
    c.rect(scope_x + 18*mm, ps_y - 6*mm, W - margin - scope_x - 18*mm, 6*mm, fill=0)
    c.setFont("Helvetica", 6.5)
    _draw_wrapped_text(c, meta["scope"], scope_x + 18*mm + (W - margin - scope_x - 18*mm)/2,
                       ps_y - 3*mm, W - margin - scope_x - 20*mm, 6.5)

    table_top = ps_y - 7*mm
    c.line(margin, table_top, W - margin, table_top)

    # ── Process Steps Table Header ────────────────────────────────────────────
    th_h = 6*mm
    # col widths
    col_input = 28*mm
    col_flow  = W - 2*margin - col_input - 28*mm - 32*mm - 28*mm - 28*mm
    col_output= 28*mm
    col_resp  = 32*mm
    col_doc   = 28*mm
    col_meas  = 28*mm

    xs = [margin,
          margin + col_input,
          margin + col_input + col_flow,
          margin + col_input + col_flow + col_output,
          margin + col_input + col_flow + col_output + col_resp,
          margin + col_input + col_flow + col_output + col_resp + col_doc,
          margin + col_input + col_flow + col_output + col_resp + col_doc + col_meas]

    # "Process Steps" spanning row
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#DDEEFF"))
    c.rect(margin, table_top - th_h, W - 2*margin, th_h, fill=1)
    c.setFillColor(colors.black)
    c.drawString(margin + 3, table_top - th_h + 2, "Process Steps:")

    # Owner
    c.setFont("Helvetica-Bold", 8)
    c.drawString(xs[3] + 2, table_top - th_h + 2, f"OWNER :  {meta['owner']}")

    # Sub-header row
    sub_y = table_top - 2*th_h
    sub_labels = ["Input", "Process Flow", "Output", "Responsible", "Doc. Format / System", "Effective Measurement"]
    for i, label in enumerate(sub_labels):
        c.setFillColor(colors.HexColor("#EEF3FF"))
        c.rect(xs[i], sub_y, xs[i+1]-xs[i], th_h, fill=1)
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString((xs[i]+xs[i+1])/2, sub_y + 2, label)

    # Draw column borders for header
    for x in xs:
        c.line(x, table_top, x, table_top - 2*th_h)
    c.line(xs[-1], table_top, xs[-1], table_top - 2*th_h)
    c.line(margin, table_top - 2*th_h, W - margin, table_top - 2*th_h)

    # ── Process Steps Rows ────────────────────────────────────────────────────
    row_h_step = 22*mm
    flow_cx = (xs[1] + xs[2]) / 2
    shape_w = col_flow * 0.72
    shape_h_rect = 8*mm
    shape_h_diam = 14*mm
    shape_h_oval = 8*mm

    current_y = table_top - 2*th_h

    for idx, step in enumerate(steps):
        sy = current_y - row_h_step
        shape = step["shape"]

        # Draw row bg
        c.setFillColor(colors.white)
        for i in range(len(xs)-1):
            c.rect(xs[i], sy, xs[i+1]-xs[i], row_h_step, fill=1)

        # Input label
        c.setFillColor(colors.black)
        c.setFont("Helvetica", 6.5)
        if step["input_label"]:
            c.drawCentredString((xs[0]+xs[1])/2, sy + row_h_step/2, step["input_label"])

        # Output label
        if step["output_label"]:
            c.drawCentredString((xs[2]+xs[3])/2, sy + row_h_step/2, step["output_label"])

        # Responsible
        c.drawCentredString((xs[3]+xs[4])/2, sy + row_h_step/2, step["responsible"])

        # Doc Format
        c.drawCentredString((xs[4]+xs[5])/2, sy + row_h_step/2, step["doc_format"])

        # Measurement
        c.drawCentredString((xs[5]+xs[6])/2, sy + row_h_step/2, step["measurement"])

        # Draw shape in flow column
        shape_x = flow_cx - shape_w/2
        center_y = sy + row_h_step/2

        # Arrow from previous
        if idx > 0:
            c.setLineWidth(0.8)
            c.setStrokeColor(colors.black)
            c.line(flow_cx, current_y, flow_cx, center_y + (shape_h_diam/2 if shape == "diamond" else shape_h_rect/2))
            draw_arrow(c, flow_cx, center_y + (shape_h_diam/2 if shape == "diamond" else shape_h_rect/2)+3,
                       flow_cx, center_y + (shape_h_diam/2 if shape == "diamond" else shape_h_rect/2))

        if shape == "rect":
            draw_rect(c, shape_x, center_y - shape_h_rect/2, shape_w, shape_h_rect, step["text"])
        elif shape == "diamond":
            draw_diamond(c, shape_x, center_y - shape_h_diam/2, shape_w, shape_h_diam, step["text"])
            # YES / NO labels
            c.setFont("Helvetica-Bold", 6)
            c.setFillColor(colors.HexColor("#007700"))
            c.drawString(flow_cx + shape_w/2 + 1, center_y + 1, step.get("yes_label", "YES"))
            c.setFillColor(colors.HexColor("#CC0000"))
            c.drawString(flow_cx - 6, center_y - shape_h_diam/2 - 5, step.get("no_label", "NO"))
            c.setFillColor(colors.black)
        elif shape == "oval":
            draw_oval(c, shape_x, center_y - shape_h_oval/2, shape_w, shape_h_oval, step["text"])
        elif shape == "parallelogram":
            draw_parallelogram(c, shape_x, center_y - shape_h_rect/2, shape_w, shape_h_rect, step["text"])
        elif shape == "arrow_text":
            c.setFont("Helvetica-Oblique", 7)
            c.setFillColor(colors.HexColor("#444444"))
            c.drawCentredString(flow_cx, center_y, step["text"])
            c.setFillColor(colors.black)

        # Row grid lines
        for i in range(len(xs)):
            c.setStrokeColor(colors.black)
            c.setLineWidth(0.5)
            c.line(xs[i], sy, xs[i], sy + row_h_step)
        c.line(margin, sy, W - margin, sy)

        current_y = sy

    # Close bottom of table
    c.setLineWidth(0.8)
    c.line(margin, current_y, W - margin, current_y)

    # ── SOP Change Record ─────────────────────────────────────────────────────
    cr_y = current_y - 6*mm
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(colors.HexColor("#DDEEFF"))
    c.rect(margin, cr_y - 6*mm, W - 2*margin, 6*mm, fill=1)
    c.setFillColor(colors.black)
    c.drawCentredString(W/2, cr_y - 4*mm, "SOP Change Record")

    cr_cols = ["S.No.", "Effective Date", "REV. No.", "Change Description",
               "Change Letter\n(Process:P / Doc:D / System:S)", "Prepared By", "Reviewed By", "Approved By"]
    cr_widths = [10*mm, 22*mm, 16*mm, 55*mm, 42*mm, 22*mm, 22*mm, 22*mm]
    cr_xs = [margin]
    for w in cr_widths:
        cr_xs.append(cr_xs[-1] + w)

    cr_sub_y = cr_y - 12*mm
    c.setFillColor(colors.HexColor("#EEF3FF"))
    c.rect(margin, cr_sub_y, W - 2*margin, 6*mm, fill=1)
    c.setFillColor(colors.black)
    for i, label in enumerate(cr_cols):
        c.setFont("Helvetica-Bold", 5.5)
        lines = label.split("\n")
        for li, ln in enumerate(lines):
            c.drawCentredString((cr_xs[i]+cr_xs[i+1])/2, cr_sub_y + 4 - li*5, ln)

    for ri, row in enumerate(meta.get("change_records", [])):
        row_y = cr_sub_y - (ri+1)*6*mm
        vals = [row.get("sno",""), row.get("date",""), row.get("rev",""),
                row.get("desc",""), row.get("change_letter",""),
                row.get("prepared",""), row.get("reviewed",""), row.get("approved","")]
        c.setFillColor(colors.white)
        c.rect(margin, row_y, W-2*margin, 6*mm, fill=1)
        c.setFillColor(colors.black)
        for ci, val in enumerate(vals):
            c.setFont("Helvetica", 6)
            c.drawCentredString((cr_xs[ci]+cr_xs[ci+1])/2, row_y + 2, str(val))
        c.line(margin, row_y, W-margin, row_y)

    # Grid for change record
    final_y = cr_sub_y - len(meta.get("change_records",[])) * 6*mm
    for x in cr_xs:
        c.line(x, cr_y - 6*mm, x, final_y)
    c.line(margin, final_y, W-margin, final_y)
    c.line(margin, cr_y-6*mm, W-margin, cr_y-6*mm)

    # Footer
    c.setFont("Helvetica-Oblique", 6.5)
    c.setFillColor(colors.HexColor("#555555"))
    c.drawCentredString(W/2, final_y - 6, f"Composed By: {meta['composed_by']}")

    c.save()
    buf.seek(0)
    return buf


# ─── UI ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 1rem; }
    .stButton > button { width: 100%; }
    h1 { font-size: 1.4rem; }
    h2 { font-size: 1.1rem; }
</style>
""", unsafe_allow_html=True)

st.title("📋 SOP Builder — Standard Operating Procedure")
st.caption("Design your SOP, add process flow steps, then download as PDF.")

tab1, tab2, tab3, tab4 = st.tabs(["🏷️ Header Info", "🔷 Process Flow", "📝 Change Record", "📄 Preview & Download"])

# ── TAB 1: Header Info ────────────────────────────────────────────────────────
with tab1:
    st.subheader("Company & Document Info")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.company_name = st.text_input("Company Name", st.session_state.company_name)
        st.session_state.title = st.text_input("SOP Title (subtitle)", st.session_state.title)
        st.session_state.sop_no = st.text_input("SOP No.", st.session_state.sop_no)
        st.session_state.rev_no = st.text_input("Rev. No.", st.session_state.rev_no)
    with col2:
        st.session_state.date = st.text_input("Date", st.session_state.date)
        st.session_state.page_info = st.text_input("Page Info", st.session_state.page_info)
        st.session_state.unit = st.text_input("Unit", st.session_state.unit)
        st.session_state.area = st.text_input("Area", st.session_state.area)
    with col3:
        st.session_state.sub_area = st.text_input("Sub Area", st.session_state.sub_area)
        st.session_state.zone = st.text_input("Zone", st.session_state.zone)
        st.session_state.owner = st.text_input("Owner", st.session_state.owner)
        st.session_state.composed_by = st.text_input("Composed By", st.session_state.composed_by)

    st.divider()
    st.subheader("Purpose & Scope")
    st.session_state.purpose = st.text_input("Purpose", st.session_state.purpose)
    st.session_state.scope = st.text_area("Scope", st.session_state.scope, height=80)

# ── TAB 2: Process Flow ───────────────────────────────────────────────────────
with tab2:
    st.subheader("Add a Process Step")

    with st.form("add_step_form", clear_on_submit=True):
        shape_label = st.selectbox("Shape / Box Type", list(SHAPE_TYPES.keys()))
        step_text = st.text_input("Step Text (label inside the shape)")
        col1, col2 = st.columns(2)
        with col1:
            input_label = st.text_input("Input Label (left column)")
            output_label = st.text_input("Output Label (right column)")
            responsible = st.text_input("Responsible")
        with col2:
            doc_format = st.text_input("Doc. Format / System")
            measurement = st.text_input("Effective Measurement")
            yes_label = st.text_input("YES label (diamonds only)", value="YES")
            no_label = st.text_input("NO label (diamonds only)", value="NO")

        submitted = st.form_submit_button("➕ Add Step", use_container_width=True)
        if submitted and step_text.strip():
            add_step(SHAPE_TYPES[shape_label], step_text, input_label, output_label,
                     responsible, doc_format, measurement, yes_label, no_label)
            st.success(f"Added: {step_text}")

    st.divider()
    st.subheader("Current Steps")

    if not st.session_state.steps:
        st.info("No steps yet. Add steps above.")
    else:
        for i, step in enumerate(st.session_state.steps):
            shape_name = {v: k for k, v in SHAPE_TYPES.items()}.get(step["shape"], step["shape"])
            with st.expander(f"Step {i+1}: [{shape_name}] {step['text']}", expanded=False):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    if st.button("⬆️ Up", key=f"up_{i}"):
                        move_up(i); st.rerun()
                with col2:
                    if st.button("⬇️ Down", key=f"dn_{i}"):
                        move_down(i); st.rerun()
                with col3:
                    if st.button("🗑️ Delete", key=f"del_{i}"):
                        delete_step(i); st.rerun()
                st.write(f"**Input:** {step['input_label']} | **Output:** {step['output_label']}")
                st.write(f"**Responsible:** {step['responsible']} | **Doc:** {step['doc_format']} | **Measurement:** {step['measurement']}")

# ── TAB 3: Change Record ──────────────────────────────────────────────────────
with tab3:
    st.subheader("SOP Change Record")

    with st.form("add_cr_form", clear_on_submit=True):
        cols = st.columns(4)
        sno  = cols[0].text_input("S.No.")
        date = cols[1].text_input("Effective Date")
        rev  = cols[2].text_input("REV. No.")
        desc = cols[3].text_input("Change Description")
        cols2 = st.columns(4)
        cl   = cols2[0].text_input("Change Letter")
        prep = cols2[1].text_input("Prepared By")
        rev2 = cols2[2].text_input("Reviewed By")
        appr = cols2[3].text_input("Approved By")
        if st.form_submit_button("➕ Add Change Record"):
            st.session_state.change_records.append({
                "sno": sno, "date": date, "rev": rev, "desc": desc,
                "change_letter": cl, "prepared": prep, "reviewed": rev2, "approved": appr
            })
            st.success("Added!")

    st.divider()
    for i, cr in enumerate(st.session_state.change_records):
        cols = st.columns([6,1])
        cols[0].write(f"**{cr['sno']}** | {cr['date']} | Rev {cr['rev']} | {cr['desc']} | Prepared: {cr['prepared']}")
        if cols[1].button("🗑️", key=f"crdel_{i}"):
            st.session_state.change_records.pop(i); st.rerun()

# ── TAB 4: Preview & Download ─────────────────────────────────────────────────
with tab4:
    st.subheader("Download SOP as PDF")

    if not st.session_state.steps:
        st.warning("Add at least one process step before generating PDF.")
    else:
        st.info(f"Ready to generate PDF with **{len(st.session_state.steps)} step(s)**.")

        meta = {
            "company_name": st.session_state.company_name,
            "title": st.session_state.title,
            "sop_no": st.session_state.sop_no,
            "rev_no": st.session_state.rev_no,
            "date": st.session_state.date,
            "page_info": st.session_state.page_info,
            "unit": st.session_state.unit,
            "area": st.session_state.area,
            "sub_area": st.session_state.sub_area,
            "zone": st.session_state.zone,
            "owner": st.session_state.owner,
            "purpose": st.session_state.purpose,
            "scope": st.session_state.scope,
            "composed_by": st.session_state.composed_by,
            "change_records": st.session_state.change_records,
        }

        pdf_buf = generate_pdf(st.session_state.steps, meta)

        st.download_button(
            label="📥 Download SOP PDF",
            data=pdf_buf,
            file_name="SOP_Document.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

        st.success("Click the button above to download your SOP as PDF.")

        # Summary table
        st.markdown("### Process Flow Summary")
        summary = []
        for i, s in enumerate(st.session_state.steps):
            shape_name = {v: k for k, v in SHAPE_TYPES.items()}.get(s["shape"], s["shape"])
            summary.append({
                "Step": i+1,
                "Shape": shape_name,
                "Text": s["text"],
                "Input": s["input_label"],
                "Output": s["output_label"],
                "Responsible": s["responsible"],
            })
        st.dataframe(summary, use_container_width=True)
