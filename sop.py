import streamlit as st
import streamlit.components.v1 as components
import io, json, base64
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from PIL import Image as PILImage

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="SOP Builder", layout="wide")

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔑 API Configuration")
    api_key = st.text_input(
        "Google Gemini API Key", type="password",
        placeholder="AIza...", value=st.session_state.get("gemini_api_key", ""))
    if api_key:
        st.session_state.gemini_api_key = api_key
        st.success("API key saved ✓")
    else:
        st.warning("Enter your Google Gemini API key to use AI generation.")
    st.markdown("[Get a free Gemini API key →](https://aistudio.google.com/app/apikey)")
    st.divider()
    st.header("🖼️ Company Logo")
    logo_file = st.file_uploader("Upload Logo (PNG/JPG)", type=["png","jpg","jpeg"], key="logo_upload")
    if logo_file:
        st.session_state.logo_bytes = logo_file.read()
        st.session_state.logo_name  = logo_file.name
        img_b64 = base64.b64encode(st.session_state.logo_bytes).decode()
        st.markdown(f'<img src="data:image/png;base64,{img_b64}" style="max-height:60px;max-width:160px"/>', unsafe_allow_html=True)
        st.success("Logo uploaded ✓")
    elif st.session_state.get("logo_bytes"):
        img_b64 = base64.b64encode(st.session_state.logo_bytes).decode()
        st.markdown(f'<img src="data:image/png;base64,{img_b64}" style="max-height:60px;max-width:160px"/>', unsafe_allow_html=True)
        st.caption("Current logo")

# ─── Session State Defaults ───────────────────────────────────────────────────
defaults = {
    "steps": [],
    "sop_no": "SCM/STR/LS/02", "rev_no": "0.0", "date": "26-12-2024",
    "page_info": "1 OUT OF 1", "unit": "Chakan Plant", "area": "Stores",
    "sub_area": "Line Side", "zone": "DIRECT LOCATIONS",
    "title": "Direct Supply of Parts from Stores to Assy Line",
    "purpose": "Supply of Supplier Packs to Line Side",
    "scope": "All Parts under direct supply category (suggested by quality/operation)",
    "owner": "Stores Manager", "company_name": "PINNACLE MOBILITY",
    "composed_by": "Agilomatrix Pvt Ltd (connectus@agilomatrix.com)",
    "ai_description": "", "ai_mode": "AI Generate", "gemini_api_key": "",
    "logo_bytes": None, "logo_name": "",
    "change_records": [
        {"sno":"1","date":"17-12-2024","rev":"0.0","desc":"Original Version",
         "change_letter":"NA","prepared":"Prince S","reviewed":"Ajay G","approved":"Vilas B"},
    ],
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── Constants ────────────────────────────────────────────────────────────────
SHAPE_TYPES = {
    "Process (Rectangle)": "rect",
    "Decision (Diamond)": "diamond",
    "Oval / Terminator": "oval",
    "Parallelogram (I/O)": "parallelogram",
    "Annotation Text": "arrow_text",
}
COLUMN_OPTIONS = ["left", "right"]
CONNECT_SIDE_OPTIONS = ["bottom (default)", "right side →", "left side ←"]

# ─── AI System Prompt ─────────────────────────────────────────────────────────
AI_SYSTEM_PROMPT = """You are an expert SOP flowchart designer. Convert the user's process into a JSON array of steps.

Rules:
- "oval" → Start/End only
- "rect" → process steps
- "diamond" → decisions (YES/NO)
- "parallelogram" → inputs/outputs
- "arrow_text" → annotations
- "left" → main flow column (center), "right" → branch column
- "connect_from": 0-based index of parent, null for auto
- "connect_side": "bottom (default)" | "right side →" | "left side ←"
- "loop_to": 0-based index to loop back to, null if none

Return ONLY valid JSON array. Every step must have ALL keys:
shape, text, column, connect_from, connect_side, arrow_label,
loop_to, loop_label, input_label, output_label, responsible,
doc_format, measurement, yes_label, no_label"""

EXAMPLES = [
    "Start → Receive purchase order → Check stock availability → If stock available (YES): Pick and pack items → Generate invoice → Ship to customer → End. If not available (NO): Raise procurement request → Wait for delivery → loop back to Check stock availability",
    "Employee raises leave request → Manager reviews → If approved (YES): Update HR system → Notify employee → End. If rejected (NO): Send rejection email → Employee can appeal → loop back to Manager reviews",
    "Raw material arrives → Inspect quality → If pass (YES): Move to production → Manufacture → Final QC → If QC pass (YES): Pack and dispatch → End. If fail (NO): Rework",
]

def sanitize_step(step):
    for f in ["arrow_label","loop_label","input_label","output_label","responsible",
              "doc_format","measurement","yes_label","no_label","connect_side","column","text"]:
        if step.get(f) is None: step[f] = ""
    step["connect_from"] = str(step["connect_from"]) if step.get("connect_from") is not None else ""
    step["loop_to"]      = str(step["loop_to"])      if step.get("loop_to")      is not None else ""
    if not step.get("yes_label"):    step["yes_label"] = "YES"
    if not step.get("no_label"):     step["no_label"]  = "NO"
    if not step.get("connect_side"): step["connect_side"] = "bottom (default)"
    if not step.get("column"):       step["column"] = "left"
    return step

def generate_steps_with_ai(description):
    import time
    api_key = st.session_state.get("gemini_api_key","").strip()
    if not api_key:
        st.error("⚠️ Enter your Google Gemini API key in the sidebar.")
        return None
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        st.error("Install google-genai: pip install google-generativeai")
        return None

    client = genai.Client(api_key=api_key)
    prompt = f"Convert this process into SOP flowchart steps:\n\n{description}"
    models = ["gemini-2.5-flash-lite","gemini-2.5-flash","gemini-2.0-flash"]
    response = None; last_error = None
    for model_name in models:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name, contents=prompt,
                    config=types.GenerateContentConfig(system_instruction=AI_SYSTEM_PROMPT))
                break
            except Exception as e:
                last_error = e
                if attempt < 2: time.sleep([5,10,20][attempt])
        if response: break
    if not response: raise last_error
    raw = response.text.strip().replace("```json","").replace("```","").strip()
    parsed = json.loads(raw)
    if not isinstance(parsed, list): raise ValueError("AI returned non-list JSON")
    for step in parsed:
        for k,v in [("input_label",""),("output_label",""),("responsible",""),
                    ("doc_format",""),("measurement",""),("yes_label","YES"),("no_label","NO"),
                    ("connect_from",None),("connect_side","bottom (default)"),
                    ("arrow_label",""),("loop_to",None),("loop_label",""),("column","left")]:
            step.setdefault(k,v)
        sanitize_step(step)
    return parsed

# ─── SVG Preview ──────────────────────────────────────────────────────────────
def generate_svg_preview(steps):
    if not steps:
        return """<div style="display:flex;align-items:center;justify-content:center;height:200px;
            color:#888;font-family:sans-serif;font-size:14px;border:2px dashed #ddd;border-radius:12px">
            <div style="text-align:center"><div style="font-size:32px;margin-bottom:8px">🔷</div>
            <div>Add steps to see your flowchart here</div></div></div>"""

    SVG_W    = 760
    # ── LAYOUT: main flow CENTERED, branch column to the right ──────────────
    # When no right-column steps exist, main flow sits at true center (380).
    # When right-column steps exist, main flow shifts slightly left (300)
    # and branch sits at 580 so shapes don't collide with the legend (starts ~615).
    has_right_steps = any(s.get("column","left") == "right" for s in steps)
    if has_right_steps:
        COL_L_CX = 290   # main flow — left of center to make room for branch
        COL_R_CX = 560   # branch column
    else:
        COL_L_CX = 380   # pure center when single-column
        COL_R_CX = 580   # unused but defined

    BOX_W    = 180
    SH_H = {"rect":56,"oval":44,"parallelogram":56,"diamond":76,"arrow_text":28}
    ROW_GAP  = 36
    TOP_Y    = 50

    rows = []
    step_to_row = {}

    for idx, step in enumerate(steps):
        col = step.get("column","left")
        if col == "right":
            placed = False
            for ri in range(len(rows)-1,-1,-1):
                if rows[ri]["right"] is None:
                    rows[ri]["right"] = idx; step_to_row[idx] = ri; placed = True; break
            if not placed:
                rows.append({"left":None,"right":idx}); step_to_row[idx] = len(rows)-1
        else:
            rows.append({"left":idx,"right":None}); step_to_row[idx] = len(rows)-1

    row_geom = []
    cy = TOP_Y
    for row in rows:
        hl = SH_H.get(steps[row["left"]]["shape"],  56) if row["left"]  is not None else 0
        hr = SH_H.get(steps[row["right"]]["shape"], 56) if row["right"] is not None else 0
        rh = max(hl, hr)
        row_geom.append({"y_top": cy, "row_h": rh})
        cy += rh + ROW_GAP
    SVG_H = cy + 20

    anchors = {}
    for idx, step in enumerate(steps):
        ri  = step_to_row[idx]; rg = row_geom[ri]
        col = step.get("column","left")
        cx  = COL_L_CX if col=="left" else COL_R_CX
        sh  = SH_H.get(step["shape"],56)
        y_top = rg["y_top"]
        y_bot = y_top + sh
        anchors[idx] = {
            "cx":cx, "cy":y_top+sh/2,
            "top":y_top, "bot":y_bot,
            "left":cx-BOX_W/2, "right":cx+BOX_W/2,
            "col":col, "sh":sh
        }

    def esc(t): return str(t).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    def wrap(text, maxc=26):
        words=str(text).split(); lines=[]; cur=""
        for w in words:
            t=(cur+" "+w).strip()
            if len(t)<=maxc: cur=t
            else:
                if cur: lines.append(cur)
                cur=w
        if cur: lines.append(cur)
        return lines or [""]
    def text_svg(lines, cx, midy, fs=12, bold=False, fill="#1a1a1a"):
        lh=fs+3; tot=len(lines)*lh; y0=midy-tot/2+lh*0.75; wt="600" if bold else "400"; out=""
        for i,ln in enumerate(lines):
            out+=f'<text x="{cx}" y="{y0+i*lh:.1f}" text-anchor="middle" font-size="{fs}" font-weight="{wt}" fill="{fill}" font-family="\'Segoe UI\',sans-serif">{esc(ln)}</text>'
        return out
    def ah(tx,ty,d="down"):
        sz=5
        if d=="down":  return f"M{tx},{ty} L{tx-sz},{ty-sz*1.5} L{tx+sz},{ty-sz*1.5} Z"
        if d=="right": return f"M{tx},{ty} L{tx-sz*1.5},{ty-sz} L{tx-sz*1.5},{ty+sz} Z"
        if d=="left":  return f"M{tx},{ty} L{tx+sz*1.5},{ty-sz} L{tx+sz*1.5},{ty+sz} Z"
        return f"M{tx},{ty} L{tx-sz},{ty+sz*1.5} L{tx+sz},{ty+sz*1.5} Z"

    ARROW = "#4a5568"; YES_C = "#276749"; NO_C = "#c53030"
    arrow_svg = ""

    for idx, step in enumerate(steps):
        a    = anchors[idx]
        lbl  = (step.get("arrow_label") or "").strip()
        cf   = str(step.get("connect_from") or "")
        side = step.get("connect_side","bottom (default)")
        lt   = str(step.get("loop_to") or "")
        ll   = (step.get("loop_label") or "").strip()

        ac = YES_C if lbl.upper()=="YES" else (NO_C if lbl.upper()=="NO" else ARROW)

        if cf.isdigit():
            src = int(cf)
            if 0 <= src < len(anchors):
                s = anchors[src]
                if side == "right side →":
                    sx,sy = s["right"],s["cy"]; ex,ey = a["cx"],a["top"]
                    arrow_svg += f'<path d="M{sx},{sy} L{ex},{sy} L{ex},{ey}" fill="none" stroke="{ac}" stroke-width="1.6" stroke-linejoin="round"/>'
                    arrow_svg += f'<path d="{ah(ex,ey)}" fill="{ac}"/>'
                elif side == "left side ←":
                    sx,sy = s["left"],s["cy"]; ex,ey = a["cx"],a["top"]
                    arrow_svg += f'<path d="M{sx},{sy} L{ex},{sy} L{ex},{ey}" fill="none" stroke="{ac}" stroke-width="1.6" stroke-linejoin="round"/>'
                    arrow_svg += f'<path d="{ah(ex,ey)}" fill="{ac}"/>'
                else:
                    sx,sy = s["cx"],s["bot"]; ex,ey = a["cx"],a["top"]
                    if abs(sx-ex)<3:
                        arrow_svg += f'<line x1="{sx}" y1="{sy}" x2="{ex}" y2="{ey}" stroke="{ac}" stroke-width="1.6"/>'
                    else:
                        my=(sy+ey)/2
                        arrow_svg += f'<path d="M{sx},{sy} L{sx},{my} L{ex},{my} L{ex},{ey}" fill="none" stroke="{ac}" stroke-width="1.6" stroke-linejoin="round"/>'
                    arrow_svg += f'<path d="{ah(ex,ey)}" fill="{ac}"/>'
                if lbl:
                    mx=(s["cx"]+a["cx"])/2; my=(s["bot"]+a["top"])/2-3
                    arrow_svg += f'<rect x="{mx-20}" y="{my-9}" width="40" height="14" rx="3" fill="white" stroke="{ac}" stroke-width="0.7" opacity="0.93"/>'
                    arrow_svg += f'<text x="{mx}" y="{my+2}" text-anchor="middle" font-size="10" font-weight="700" fill="{ac}" font-family="\'Segoe UI\',sans-serif">{esc(lbl)}</text>'
        else:
            if idx > 0:
                prev = next((pi for pi in range(idx-1,-1,-1) if anchors[pi]["col"]==a["col"]),None)
                if prev is not None:
                    ps = anchors[prev]
                    arrow_svg += f'<line x1="{a["cx"]}" y1="{ps["bot"]}" x2="{a["cx"]}" y2="{a["top"]}" stroke="{ARROW}" stroke-width="1.6"/>'
                    arrow_svg += f'<path d="{ah(a["cx"],a["top"])}" fill="{ARROW}"/>'

        if lt.isdigit():
            dest = anchors[int(lt)]
            lc = YES_C if ll.upper()=="YES" else (NO_C if ll.upper()=="NO" else "#1a6dcc")
            # Loop arrows go to the LEFT of the main flow to avoid overlapping shapes
            lx = min(anchors[i]["left"] for i in range(len(anchors))) - 28
            arrow_svg += f'<path d="M{a["left"]},{a["cy"]} L{lx},{a["cy"]} L{lx},{dest["cy"]} L{dest["left"]},{dest["cy"]}" fill="none" stroke="{lc}" stroke-width="1.6" stroke-dasharray="5 3" stroke-linejoin="round"/>'
            arrow_svg += f'<path d="{ah(dest["left"],dest["cy"],"right")}" fill="{lc}"/>'
            if ll:
                my=(a["cy"]+dest["cy"])/2
                arrow_svg += f'<text x="{lx-5}" y="{my}" text-anchor="end" font-size="10" font-weight="700" fill="{lc}" font-family="\'Segoe UI\',sans-serif">{esc(ll)}</text>'

    CLRS = {
        "rect":          {"fill":"#EBF4FF","stroke":"#2B6CB0","text":"#1A365D"},
        "oval":          {"fill":"#2D3748","stroke":"#1A202C","text":"#FFFFFF"},
        "diamond":       {"fill":"#FFF9E6","stroke":"#B7791F","text":"#744210"},
        "parallelogram": {"fill":"#F0FFF4","stroke":"#276749","text":"#1C4532"},
        "arrow_text":    {"fill":"none",   "stroke":"none",   "text":"#4A5568"},
    }
    shape_svg = ""
    for idx, step in enumerate(steps):
        a  = anchors[idx]; shape = step["shape"]
        cx,cy = a["cx"],a["cy"]
        bw = BOX_W; bh = a["sh"]
        x0 = cx-bw/2; y0 = a["top"]
        cl = CLRS.get(shape,CLRS["rect"])
        lines = wrap(step.get("text",""))
        yl = step.get("yes_label","YES"); nl = step.get("no_label","NO")
        shape_svg += '<g>'
        if shape=="rect":
            shape_svg += f'<rect x="{x0}" y="{y0}" width="{bw}" height="{bh}" rx="7" fill="{cl["fill"]}" stroke="{cl["stroke"]}" stroke-width="1.5"/>'
            shape_svg += text_svg(lines,cx,cy,12,fill=cl["text"])
        elif shape=="oval":
            shape_svg += f'<ellipse cx="{cx}" cy="{cy}" rx="{bw/2}" ry="{bh/2}" fill="{cl["fill"]}" stroke="{cl["stroke"]}" stroke-width="1.5"/>'
            shape_svg += text_svg(lines,cx,cy,12,fill=cl["text"])
        elif shape=="diamond":
            pts=f"{cx},{y0} {cx+bw/2},{cy} {cx},{y0+bh} {cx-bw/2},{cy}"
            shape_svg += f'<polygon points="{pts}" fill="{cl["fill"]}" stroke="{cl["stroke"]}" stroke-width="1.5"/>'
            shape_svg += text_svg(lines,cx,cy,11,fill=cl["text"])
            shape_svg += f'<text x="{cx+bw/2+8}" y="{cy+4}" font-size="10" font-weight="700" fill="{YES_C}" font-family="\'Segoe UI\',sans-serif">{esc(yl)} →</text>'
            shape_svg += f'<text x="{cx-bw/2-8}" y="{cy+4}" font-size="10" font-weight="700" text-anchor="end" fill="{NO_C}" font-family="\'Segoe UI\',sans-serif">← {esc(nl)}</text>'
        elif shape=="parallelogram":
            sk=10; pts=f"{x0+sk},{y0} {x0+bw},{y0} {x0+bw-sk},{y0+bh} {x0},{y0+bh}"
            shape_svg += f'<polygon points="{pts}" fill="{cl["fill"]}" stroke="{cl["stroke"]}" stroke-width="1.5"/>'
            shape_svg += text_svg(lines,cx,cy,12,fill=cl["text"])
        elif shape=="arrow_text":
            shape_svg += f'<text x="{cx}" y="{cy+4}" text-anchor="middle" font-size="12" fill="{cl["text"]}" font-style="italic" font-family="\'Segoe UI\',sans-serif">{esc(step.get("text",""))}</text>'
        shape_svg += f'<circle cx="{x0+11}" cy="{y0+11}" r="9" fill="{cl["stroke"]}" opacity="0.9"/>'
        shape_svg += f'<text x="{x0+11}" y="{y0+15}" text-anchor="middle" font-size="8" font-weight="700" fill="white" font-family="\'Segoe UI\',sans-serif">{idx+1}</text>'
        shape_svg += '</g>'

    # ── Column headers & divider ──────────────────────────────────────────────
    hdr_svg = ""
    if has_right_steps:
        # Main flow header centered over COL_L_CX
        hdr_svg += f'<rect x="{COL_L_CX-100}" y="6" width="200" height="20" rx="4" fill="#EBF4FF" stroke="#2B6CB0" stroke-width="0.8"/>'
        hdr_svg += f'<text x="{COL_L_CX}" y="20" text-anchor="middle" font-size="12" font-weight="600" fill="#1A365D" font-family="\'Segoe UI\',sans-serif">Main Flow</text>'
        # Branch header
        hdr_svg += f'<rect x="{COL_R_CX-100}" y="6" width="200" height="20" rx="4" fill="#F0FFF4" stroke="#276749" stroke-width="0.8"/>'
        hdr_svg += f'<text x="{COL_R_CX}" y="20" text-anchor="middle" font-size="12" font-weight="600" fill="#1C4532" font-family="\'Segoe UI\',sans-serif">Branch</text>'
        # Divider line between columns
        mid = (COL_L_CX + BOX_W/2 + COL_R_CX - BOX_W/2) / 2
        hdr_svg += f'<line x1="{mid}" y1="30" x2="{mid}" y2="{SVG_H-10}" stroke="#CBD5E0" stroke-width="1" stroke-dasharray="4 4"/>'
    else:
        # Single column — just a centered header
        hdr_svg += f'<rect x="{COL_L_CX-100}" y="6" width="200" height="20" rx="4" fill="#EBF4FF" stroke="#2B6CB0" stroke-width="0.8"/>'
        hdr_svg += f'<text x="{COL_L_CX}" y="20" text-anchor="middle" font-size="12" font-weight="600" fill="#1A365D" font-family="\'Segoe UI\',sans-serif">Main Flow</text>'

    # ── Legend — only shown when no right-column steps (avoids overlap) ───────
    leg_svg = ""
    if not has_right_steps:
        LX=SVG_W-145; LY=TOP_Y
        leg_items=[("rect","#EBF4FF","#2B6CB0","Process"),("oval","#2D3748","#1A202C","Terminator"),
                   ("diamond","#FFF9E6","#B7791F","Decision"),("parallelogram","#F0FFF4","#276749","Input/Output")]
        leg_svg =f'<rect x="{LX-8}" y="{LY-8}" width="140" height="{len(leg_items)*22+20}" rx="8" fill="white" stroke="#CBD5E0" stroke-width="0.8" opacity="0.95"/>'
        leg_svg+=f'<text x="{LX+4}" y="{LY+6}" font-size="11" font-weight="600" fill="#4A5568" font-family="\'Segoe UI\',sans-serif">Legend</text>'
        for i,(sh,f,s,lab) in enumerate(leg_items):
            ly=LY+20+i*22; lx=LX+4
            if sh=="oval": leg_svg+=f'<ellipse cx="{lx+10}" cy="{ly}" rx="10" ry="7" fill="{f}" stroke="{s}" stroke-width="1"/>'
            elif sh=="diamond": leg_svg+=f'<polygon points="{lx+10},{ly-8} {lx+20},{ly} {lx+10},{ly+8} {lx},{ly}" fill="{f}" stroke="{s}" stroke-width="1"/>'
            else: leg_svg+=f'<rect x="{lx}" y="{ly-8}" width="20" height="14" rx="3" fill="{f}" stroke="{s}" stroke-width="1"/>'
            leg_svg+=f'<text x="{lx+26}" y="{ly+4}" font-size="11" fill="#4A5568" font-family="\'Segoe UI\',sans-serif">{lab}</text>'

    return f'''<svg width="{SVG_W}" height="{SVG_H}" viewBox="0 0 {SVG_W} {SVG_H}" xmlns="http://www.w3.org/2000/svg">
      <defs><pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
        <path d="M 30 0 L 0 0 0 30" fill="none" stroke="#F0F4F8" stroke-width="0.5"/></pattern></defs>
      <rect width="{SVG_W}" height="{SVG_H}" fill="#FAFBFC"/>
      <rect width="{SVG_W}" height="{SVG_H}" fill="url(#grid)"/>
      {hdr_svg}{arrow_svg}{shape_svg}{leg_svg}
    </svg>'''

def render_preview_html(steps):
    svg = generate_svg_preview(steps)
    n = len(steps)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#F7F9FC;font-family:'Segoe UI',sans-serif;overflow:hidden}}
#tb{{display:flex;align-items:center;gap:10px;padding:7px 14px;background:white;border-bottom:1px solid #E2E8F0;font-size:13px;color:#4A5568}}
#tb strong{{color:#1A365D;font-size:14px}}
.zbtn{{background:#EBF4FF;border:1px solid #BEE3F8;color:#2B6CB0;border-radius:5px;padding:3px 9px;cursor:pointer;font-size:13px;font-weight:600}}
.zbtn:hover{{background:#BEE3F8}}
#zl{{font-size:12px;color:#718096;min-width:38px;text-align:center}}
#cw{{width:100%;height:calc(100vh - 42px);overflow:auto;background:#F7F9FC}}
#si{{display:inline-block;transform-origin:top left;transition:transform 0.18s;padding:10px}}
.badge{{background:#2B6CB0;color:white;border-radius:12px;padding:2px 10px;font-size:12px;font-weight:600;margin-left:6px}}
</style></head><body>
<div id="tb"><strong>📊 Live Flowchart Preview</strong>
<span class="badge">{n} step{'s' if n!=1 else ''}</span>
<span style="color:#718096">| Scroll to pan</span>
<div style="margin-left:auto;display:flex;gap:4px;align-items:center">
<button class="zbtn" onclick="zoom(-0.15)">−</button>
<span id="zl">100%</span>
<button class="zbtn" onclick="zoom(+0.15)">+</button>
<button class="zbtn" onclick="resetZoom()" style="font-size:12px">Reset</button>
</div></div>
<div id="cw"><div id="si">{svg}</div></div>
<script>
var s=1;
function zoom(d){{s=Math.max(0.3,Math.min(3,s+d));document.getElementById('si').style.transform='scale('+s+')';document.getElementById('zl').textContent=Math.round(s*100)+'%';}}
function resetZoom(){{s=1;document.getElementById('si').style.transform='scale(1)';document.getElementById('zl').textContent='100%';}}
</script></body></html>"""

# ─── PDF Generation ────────────────────────────────────────────────────────────
def wrapped_lines_pdf(c, text, max_w, fn, fs):
    words=str(text).split(); lines=[]; cur=""
    for w in words:
        t=(cur+" "+w).strip()
        if c.stringWidth(t,fn,fs)<=max_w: cur=t
        else:
            if cur: lines.append(cur)
            cur=w
    if cur: lines.append(cur)
    return lines or [""]

def draw_ctext(c, text, cx, cy, max_w, fn="Helvetica", fs=10, col=colors.black):
    lines = wrapped_lines_pdf(c, text, max_w, fn, fs)
    lh = fs * 1.2
    block_h = len(lines) * lh
    y0 = cy + block_h / 2 - lh + lh * 0.25
    c.setFont(fn, fs); c.setFillColor(col)
    for i, ln in enumerate(lines):
        c.drawCentredString(cx, y0 - i * lh, ln)

def draw_ltext(c, text, x, cy, max_w, fn="Helvetica", fs=10, col=colors.black):
    lines = wrapped_lines_pdf(c, text, max_w, fn, fs)
    lh = fs * 1.2
    block_h = len(lines) * lh
    y0 = cy + block_h / 2 - lh + lh * 0.25
    c.setFont(fn, fs); c.setFillColor(col)
    for i, ln in enumerate(lines):
        c.drawString(x, y0 - i * lh, ln)

def arrow_head(c, tx, ty, d="down"):
    sz=2.5; c.setFillColor(colors.black); p=c.beginPath()
    if d=="down":  p.moveTo(tx,ty); p.lineTo(tx-sz,ty+sz*1.5); p.lineTo(tx+sz,ty+sz*1.5)
    elif d=="up":  p.moveTo(tx,ty); p.lineTo(tx-sz,ty-sz*1.5); p.lineTo(tx+sz,ty-sz*1.5)
    elif d=="right": p.moveTo(tx,ty); p.lineTo(tx-sz*1.5,ty+sz); p.lineTo(tx-sz*1.5,ty-sz)
    elif d=="left":  p.moveTo(tx,ty); p.lineTo(tx+sz*1.5,ty+sz); p.lineTo(tx+sz*1.5,ty-sz)
    p.close(); c.drawPath(p,fill=1,stroke=0)

def pdf_arrow_down(c, x, y1, y2, col=colors.black):
    c.setStrokeColor(col); c.setLineWidth(0.7)
    c.line(x,y1,x,y2+2.5*1.5); arrow_head(c,x,y2,"down"); c.setStrokeColor(colors.black)

def pdf_elbow(c, sx,sy, ex,ey, col=colors.black, lbl="", lbl_col=colors.black):
    c.setStrokeColor(col); c.setLineWidth(0.7)
    c.line(sx,sy,ex,sy)
    if ey<sy: c.line(ex,sy,ex,ey+2.5*1.5); arrow_head(c,ex,ey,"down")
    else:     c.line(ex,sy,ex,ey-2.5*1.5); arrow_head(c,ex,ey,"up")
    if lbl:
        c.setFont("Helvetica-Bold",9); c.setFillColor(lbl_col)
        c.drawCentredString((sx+ex)/2,sy+2,lbl)
    c.setStrokeColor(colors.black); c.setFillColor(colors.black)

def draw_rect(c, x,y,w,h,text, fs=10):
    c.setStrokeColor(colors.black); c.setFillColor(colors.white); c.setLineWidth(0.6)
    c.rect(x,y,w,h,fill=1,stroke=1); draw_ctext(c,text,x+w/2,y+h/2,w-4,fs=fs)

def draw_oval(c, x,y,w,h,text, fs=10):
    c.setStrokeColor(colors.black); c.setFillColor(colors.HexColor("#2c2c2c")); c.setLineWidth(0.6)
    c.ellipse(x,y,x+w,y+h,fill=1,stroke=1)
    draw_ctext(c,text,x+w/2,y+h/2,w-4,fs=fs,col=colors.white)

def draw_diamond(c, x,y,w,h,text, fs=9):
    cx,cy=x+w/2,y+h/2; p=c.beginPath()
    p.moveTo(cx,y+h); p.lineTo(x+w,cy); p.lineTo(cx,y); p.lineTo(x,cy); p.close()
    c.setStrokeColor(colors.black); c.setFillColor(colors.white); c.setLineWidth(0.6)
    c.drawPath(p,fill=1,stroke=1); draw_ctext(c,text,cx,cy,w*0.48,fs=fs)

def draw_para(c, x,y,w,h,text, fs=10):
    sk=5; p=c.beginPath()
    p.moveTo(x+sk,y+h); p.lineTo(x+w,y+h); p.lineTo(x+w-sk,y); p.lineTo(x,y); p.close()
    c.setStrokeColor(colors.black); c.setFillColor(colors.white); c.setLineWidth(0.6)
    c.drawPath(p,fill=1,stroke=1); draw_ctext(c,text,x+w/2,y+h/2,w-8,fs=fs)

def generate_pdf(steps, meta):
    buf = io.BytesIO()
    PW, PH = landscape(A4)
    c = canvas.Canvas(buf, pagesize=(PW,PH))

    ML=10*mm; MR=10*mm; MT=10*mm
    TW=PW-ML-MR
    cur_y=PH-MT

    HDR_H = 30*mm
    LOGO_W = 52*mm
    TITLE_W = 95*mm
    META_W  = TW - LOGO_W - TITLE_W

    c.setStrokeColor(colors.black); c.setLineWidth(0.8)
    c.rect(ML, cur_y-HDR_H, TW, HDR_H, fill=0, stroke=1)
    c.line(ML+LOGO_W, cur_y-HDR_H, ML+LOGO_W, cur_y)
    c.line(ML+LOGO_W+TITLE_W, cur_y-HDR_H, ML+LOGO_W+TITLE_W, cur_y)

    c.setFont("Helvetica-Bold", 11); c.setFillColor(colors.black)
    c.drawString(ML+4, cur_y-10, meta["company_name"])

    if meta.get("logo_bytes"):
        try:
            logo_img = ImageReader(io.BytesIO(meta["logo_bytes"]))
            lw=44*mm; lh=18*mm
            logo_x = ML+4
            logo_y = cur_y - HDR_H + (HDR_H - lh) / 2
            c.drawImage(logo_img, logo_x, logo_y,
                        width=lw, height=lh, preserveAspectRatio=True, mask="auto")
        except Exception:
            pass
    else:
        c.setFont("Helvetica-Bold", 22); c.setFillColor(colors.HexColor("#1a6dcc"))
        eka_y = cur_y - HDR_H/2 - 5
        c.drawString(ML+4, eka_y, "eka")
        c.setFillColor(colors.black)

    title_cx  = ML + LOGO_W + TITLE_W / 2
    cell_top  = cur_y
    cell_bot  = cur_y - HDR_H

    SOP_FS   = 14
    SUB_FS   = 11
    SUB_LH   = SUB_FS + 2
    GAP      = 5
    SOP_LH   = SOP_FS + 2

    sub_lines = wrapped_lines_pdf(c, meta["title"], TITLE_W - 8, "Helvetica", SUB_FS)
    block_h   = SOP_LH + GAP + len(sub_lines) * SUB_LH
    block_top = (cell_top + cell_bot) / 2.0 + block_h / 2.0

    c.setFont("Helvetica-Bold", SOP_FS)
    c.setFillColor(colors.black)
    c.drawCentredString(title_cx, block_top - SOP_LH * 0.80, "STANDARD OPERATING PROCEDURE")

    c.setFont("Helvetica", SUB_FS)
    sub_y0 = block_top - SOP_LH - GAP
    for i, ln in enumerate(sub_lines):
        c.drawCentredString(title_cx, sub_y0 - SUB_LH * 0.80 - i * SUB_LH, ln)

    RX = ML+LOGO_W+TITLE_W
    rh = HDR_H/4
    meta_rows=[
        ("SOP No.", meta["sop_no"],  "Page", meta["page_info"]),
        ("Rev No.", meta["rev_no"],  "Date", meta["date"]),
        ("Unit",    meta["unit"],    "Area", meta["area"]),
        ("Sub Area",meta["sub_area"],"Zone", meta["zone"]),
    ]
    c1w=20*mm; c2w=34*mm; c3w=16*mm; c4w=META_W-c1w-c2w-c3w
    for ri,(l1,v1,l2,v2) in enumerate(meta_rows):
        ry=cur_y-(ri+1)*rh
        xs=[RX, RX+c1w, RX+c1w+c2w, RX+c1w+c2w+c3w, RX+META_W]
        for ci,(txt,is_lbl) in enumerate([(l1,True),(v1,False),(l2,True),(v2,False)]):
            cw=xs[ci+1]-xs[ci]
            c.setFillColor(colors.HexColor("#D6E8F7") if is_lbl else colors.white)
            c.setStrokeColor(colors.black); c.setLineWidth(0.4)
            c.rect(xs[ci],ry,cw,rh,fill=1,stroke=1); c.setFillColor(colors.black)
            fn="Helvetica-Bold" if is_lbl else "Helvetica"; fs=11
            draw_ltext(c,txt,xs[ci]+2,ry+rh/2,cw-3,fn,fs)
    cur_y -= HDR_H
    cur_y -= 3*mm

    PS_H=12*mm
    PL_W=20*mm; PV_W=80*mm; SL_W=16*mm; SV_W=TW-PL_W-PV_W-SL_W
    c.setLineWidth(0.6)
    for x,w,txt,is_lbl in [
        (ML,          PL_W,"Purpose", True),
        (ML+PL_W,     PV_W,meta["purpose"],False),
        (ML+PL_W+PV_W,SL_W,"Scope",  True),
        (ML+PL_W+PV_W+SL_W,SV_W,meta["scope"],False),
    ]:
        c.setFillColor(colors.HexColor("#D6E8F7") if is_lbl else colors.white)
        c.rect(x,cur_y-PS_H,w,PS_H,fill=1,stroke=1); c.setFillColor(colors.black)
        if is_lbl:
            c.setFont("Helvetica-Bold",11)
            c.drawString(x+3, cur_y - PS_H/2 - 11*0.3, txt)
        else:
            draw_ltext(c,txt,x+3,cur_y-PS_H/2,w-5,fs=10)
    cur_y -= PS_H
    cur_y -= 3*mm

    COL_IN   = 24*mm
    COL_OUT  = 22*mm
    COL_RESP = 26*mm
    COL_DOC  = 24*mm
    COL_MEAS = 26*mm
    COL_FLOW = TW - COL_IN - COL_OUT - COL_RESP - COL_DOC - COL_MEAS

    XS = [ML,
          ML+COL_IN,
          ML+COL_IN+COL_FLOW,
          ML+COL_IN+COL_FLOW+COL_OUT,
          ML+COL_IN+COL_FLOW+COL_OUT+COL_RESP,
          ML+COL_IN+COL_FLOW+COL_OUT+COL_RESP+COL_DOC,
          ML+TW]

    FLOW_L = XS[1]; FLOW_W = COL_FLOW
    FLOW_R = XS[2]

    # ── PDF LAYOUT: main flow CENTERED in flow column ─────────────────────────
    has_right_pdf = any(s.get("column","left") == "right" for s in steps)
    if has_right_pdf:
        # Split flow column: left 55% for main, right 45% for branch
        LEFT_CX  = FLOW_L + FLOW_W * 0.30   # main flow center (left portion)
        RIGHT_CX = FLOW_L + FLOW_W * 0.78   # branch center (right portion)
        SH_W_L   = FLOW_W * 0.44            # main flow box width
        SH_W_R   = FLOW_W * 0.30            # branch box width
    else:
        # Single column — true center of flow column
        LEFT_CX  = FLOW_L + FLOW_W * 0.50   # dead center
        RIGHT_CX = FLOW_L + FLOW_W * 0.78   # unused but defined
        SH_W_L   = FLOW_W * 0.70            # wide centered boxes
        SH_W_R   = FLOW_W * 0.30

    HDR1_H=8*mm
    c.setFillColor(colors.HexColor("#BDD7EE"))
    c.rect(ML,cur_y-HDR1_H,TW,HDR1_H,fill=1,stroke=1)
    c.setFont("Helvetica-Bold",11); c.setFillColor(colors.black)
    _banner_y = cur_y - HDR1_H/2 - 11*0.3
    c.drawString(ML+3, _banner_y, "Process Steps:")
    c.drawString(XS[2]+3, _banner_y, f"OWNER :   {meta['owner']}")
    cur_y -= HDR1_H

    HDR2_H=11*mm
    hdr_labels=["Input","Process Flow","Output","Responsible","Doc. Format /\nSystem","Effective\nMeasurement"]
    for i,label in enumerate(hdr_labels):
        cw=XS[i+1]-XS[i]
        c.setFillColor(colors.HexColor("#D6E8F7"))
        c.rect(XS[i],cur_y-HDR2_H,cw,HDR2_H,fill=1,stroke=1); c.setFillColor(colors.black)
        lines=label.split("\n")
        fs_h = 9; lh = fs_h * 1.2
        total_h = len(lines) * lh
        y_mid = cur_y - HDR2_H / 2
        y0 = y_mid + total_h / 2 - lh + lh * 0.25
        for li, ln in enumerate(lines):
            c.setFont("Helvetica-Bold", fs_h)
            c.drawCentredString(XS[i]+cw/2, y0 - li*lh, ln)
    cur_y -= HDR2_H

    SH_H_PDF={"rect":12*mm,"oval":10*mm,"parallelogram":12*mm,"diamond":18*mm,"arrow_text":7*mm}
    V_PAD=3*mm
    TABLE_TOP=cur_y

    rows=[]; step_to_row={}
    for idx,step in enumerate(steps):
        col=step.get("column","left")
        if col=="right":
            placed=False
            for ri in range(len(rows)-1,-1,-1):
                if rows[ri]["right"] is None:
                    rows[ri]["right"]=idx; step_to_row[idx]=ri; placed=True; break
            if not placed:
                rows.append({"left":None,"right":idx}); step_to_row[idx]=len(rows)-1
        else:
            rows.append({"left":idx,"right":None}); step_to_row[idx]=len(rows)-1

    row_geom=[]; sy2=cur_y
    for row in rows:
        hl=SH_H_PDF.get(steps[row["left"]]["shape"],12*mm)  if row["left"]  is not None else 0
        hr=SH_H_PDF.get(steps[row["right"]]["shape"],12*mm) if row["right"] is not None else 0
        ROW_H=max(hl,hr)+2*V_PAD
        ry=sy2-ROW_H; row_geom.append({"ry":ry,"ROW_H":ROW_H}); sy2=ry
    TABLE_BOTTOM=sy2

    TBL_H=TABLE_TOP-TABLE_BOTTOM
    c.setFillColor(colors.white); c.rect(ML,TABLE_BOTTOM,TW,TBL_H,fill=1,stroke=0)
    c.setStrokeColor(colors.black); c.setLineWidth(0.8)
    c.rect(ML,TABLE_BOTTOM,TW,TBL_H,fill=0,stroke=1)
    c.setLineWidth(0.5)
    for x in XS[1:-1]: c.line(x,TABLE_BOTTOM,x,TABLE_TOP)
    c.setLineWidth(0.35)
    for ri,rg in enumerate(row_geom[:-1]):
        y=rg["ry"]
        c.line(XS[0],y,XS[1],y)
        c.line(XS[2],y,XS[-1],y)

    # ── Sub-divider between main flow and branch (PDF) ────────────────────────
    if has_right_pdf:
        mid_flow_x = FLOW_L + FLOW_W * 0.54
        c.setStrokeColor(colors.HexColor("#CBD5E0")); c.setLineWidth(0.4)
        c.setDash([3,3]); c.line(mid_flow_x,TABLE_BOTTOM,mid_flow_x,TABLE_TOP)
        c.setDash(); c.setStrokeColor(colors.black)

    anchors={}
    for idx,step in enumerate(steps):
        ri=step_to_row[idx]; rg=row_geom[ri]; ry,ROW_H=rg["ry"],rg["ROW_H"]
        col=step.get("column","left")
        sh_h=SH_H_PDF.get(step["shape"],12*mm)
        cx=LEFT_CX if col=="left" else RIGHT_CX
        sh_w=SH_W_L if col=="left" else SH_W_R
        sh_x=cx-sh_w/2
        sh_bot=ry+V_PAD; sh_top=sh_bot+sh_h; sh_mid=sh_bot+sh_h/2
        anchors[idx]={"cx":cx,"cy":sh_mid,"top":sh_top,"bot":sh_bot,
                      "left":sh_x,"right":sh_x+sh_w,"sh_x":sh_x,
                      "sh_w":sh_w,"sh_h":sh_h,"sh_bot":sh_bot,"col":col}

    GREEN=colors.HexColor("#006600"); RED=colors.HexColor("#CC0000"); BLUE=colors.HexColor("#1a6dcc")

    for pi,row in enumerate(rows):
        rg=row_geom[pi]; ry,ROW_H=rg["ry"],rg["ROW_H"]
        ref=row["left"] if row["left"] is not None else row["right"]
        step=steps[ref]
        for ci,key in [(0,"input_label"),(2,"output_label"),(3,"responsible"),(4,"doc_format"),(5,"measurement")]:
            txt=(step.get(key) or "")
            if txt:
                cw=XS[ci+1]-XS[ci]
                draw_ctext(c,txt,XS[ci]+cw/2,ry+ROW_H/2,cw-3,fs=10)

    for idx,step in enumerate(steps):
        a=anchors[idx]
        cf=str(step.get("connect_from") or "")
        lbl=(step.get("arrow_label") or "").strip()
        side=step.get("connect_side","bottom (default)")
        lt=str(step.get("loop_to") or "")
        ll=(step.get("loop_label") or "").strip()

        ac=GREEN if lbl.upper()=="YES" else (RED if lbl.upper()=="NO" else colors.black)

        if cf.isdigit():
            src=int(cf)
            if 0<=src<len(anchors):
                s=anchors[src]
                if side=="right side →":
                    pdf_elbow(c,s["right"],s["cy"],a["cx"],a["top"],col=ac,lbl=lbl,lbl_col=ac)
                elif side=="left side ←":
                    pdf_elbow(c,s["left"],s["cy"],a["cx"],a["top"],col=ac,lbl=lbl,lbl_col=ac)
                else:
                    if abs(s["cx"]-a["cx"])<2:
                        pdf_arrow_down(c,a["cx"],s["bot"],a["top"],col=ac)
                        if lbl:
                            c.setFont("Helvetica-Bold",9); c.setFillColor(ac)
                            c.drawCentredString(a["cx"]+5,(s["bot"]+a["top"])/2,lbl)
                            c.setFillColor(colors.black)
                    else:
                        pdf_elbow(c,s["cx"],s["bot"],a["cx"],a["top"],col=ac,lbl=lbl,lbl_col=ac)
        else:
            if idx>0:
                prev=next((pi for pi in range(idx-1,-1,-1) if anchors[pi]["col"]==a["col"]),None)
                if prev is not None:
                    ps=anchors[prev]; pdf_arrow_down(c,a["cx"],ps["bot"],a["top"])

        if lt.isdigit():
            dest=anchors[int(lt)]
            lc=GREEN if ll.upper()=="YES" else (RED if ll.upper()=="NO" else BLUE)
            # Loop arrows use a margin to the LEFT of the flow column
            margin=FLOW_L-4*mm; sz=2.5
            c.setStrokeColor(lc); c.setLineWidth(0.7)
            c.line(a["sh_x"],a["cy"],margin,a["cy"])
            c.line(margin,a["cy"],margin,dest["cy"])
            c.line(margin,dest["cy"],dest["left"]-sz*1.5,dest["cy"])
            arrow_head(c,dest["left"],dest["cy"],"right")
            if ll:
                c.setFont("Helvetica-Bold",8); c.setFillColor(lc)
                c.drawString(margin+1,(a["cy"]+dest["cy"])/2+1,ll)
                c.setFillColor(colors.black)
            c.setStrokeColor(colors.black)

    for idx,step in enumerate(steps):
        a=anchors[idx]
        sh_x,sh_bot=a["sh_x"],a["sh_bot"]; sh_w,sh_h=a["sh_w"],a["sh_h"]
        shape=step["shape"]; txt=(step.get("text") or "")
        yl=(step.get("yes_label") or "YES"); nl=(step.get("no_label") or "NO")

        if   shape=="rect":          draw_rect(c,sh_x,sh_bot,sh_w,sh_h,txt)
        elif shape=="oval":          draw_oval(c,sh_x,sh_bot,sh_w,sh_h,txt)
        elif shape=="parallelogram": draw_para(c,sh_x,sh_bot,sh_w,sh_h,txt)
        elif shape=="diamond":
            draw_diamond(c,sh_x,sh_bot,sh_w,sh_h,txt)
            c.setFont("Helvetica-Bold",9); c.setFillColor(GREEN)
            c.drawString(sh_x+sh_w+2,a["cy"]-2,yl)
            nw=c.stringWidth(nl,"Helvetica-Bold",9); c.setFillColor(RED)
            c.drawString(sh_x-nw-4,a["cy"]-2,nl); c.setFillColor(colors.black)
        elif shape=="arrow_text":
            c.setFont("Helvetica-Oblique",9); c.setFillColor(colors.HexColor("#333333"))
            c.drawCentredString(a["cx"],a["cy"],txt); c.setFillColor(colors.black)

    cur_y=TABLE_BOTTOM

    cur_y -= 3*mm
    CR_TH=8*mm
    c.setFillColor(colors.HexColor("#BDD7EE"))
    c.rect(ML,cur_y-CR_TH,TW,CR_TH,fill=1,stroke=1)
    c.setFont("Helvetica-Bold",11); c.setFillColor(colors.black)
    c.drawCentredString(ML+TW/2, cur_y - CR_TH/2 - 11*0.3, "SOP Change Record")
    cur_y-=CR_TH

    CR_COLS=["S.No.","Effective\nDate","REV.\nNo.","Change Description",
             "Change Letter\n(Process:P / Doc:D / System:S)","Prepared By","Reviewed By","Approved By"]
    CR_W=[10*mm,20*mm,13*mm,54*mm,48*mm,22*mm,22*mm,0]
    CR_W[-1]=TW-sum(CR_W[:-1])
    CR_XS=[ML]
    for w in CR_W: CR_XS.append(CR_XS[-1]+w)

    CR_HH=9*mm
    for i,lbl in enumerate(CR_COLS):
        cw=CR_XS[i+1]-CR_XS[i]
        c.setFillColor(colors.HexColor("#D6E8F7"))
        c.rect(CR_XS[i],cur_y-CR_HH,cw,CR_HH,fill=1,stroke=1); c.setFillColor(colors.black)
        lines=lbl.split("\n")
        fs_cr = 8; lh_cr = fs_cr * 1.2
        total_h = len(lines) * lh_cr
        y_mid = cur_y - CR_HH / 2
        y0 = y_mid + total_h / 2 - lh_cr + lh_cr * 0.25
        for li,ln in enumerate(lines):
            c.setFont("Helvetica-Bold", fs_cr)
            c.drawCentredString(CR_XS[i]+cw/2, y0 - li*lh_cr, ln)
    cur_y-=CR_HH

    CR_RH=8*mm
    for row in meta.get("change_records",[]):
        vals=[row.get("sno",""),row.get("date",""),row.get("rev",""),row.get("desc",""),
              row.get("change_letter",""),row.get("prepared",""),row.get("reviewed",""),row.get("approved","")]
        for i,val in enumerate(vals):
            cw=CR_XS[i+1]-CR_XS[i]
            c.setFillColor(colors.white); c.rect(CR_XS[i],cur_y-CR_RH,cw,CR_RH,fill=1,stroke=1)
            draw_ctext(c,val,CR_XS[i]+cw/2,cur_y-CR_RH/2,cw-3,fs=9)
        cur_y-=CR_RH
    for _ in range(2):
        for i in range(len(CR_COLS)):
            cw=CR_XS[i+1]-CR_XS[i]
            c.setFillColor(colors.white); c.rect(CR_XS[i],cur_y-CR_RH,cw,CR_RH,fill=1,stroke=1)
        cur_y-=CR_RH

    cur_y -= 5*mm
    c.setFont("Helvetica-Oblique",9); c.setFillColor(colors.HexColor("#555555"))
    c.drawCentredString(ML+TW/2, cur_y, f"Composed By: {meta['composed_by']}")

    c.save(); buf.seek(0); return buf

# ─── Streamlit UI ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
.block-container{padding-top:1rem}
h1{font-size:1.3rem;margin-bottom:0.2rem}
h2{font-size:1.05rem}
.stButton>button{width:100%}
.ai-banner{background:linear-gradient(135deg,#E6F4EA,#E8F0FE);border:1.5px solid #34A853;border-radius:10px;padding:12px 16px;margin-bottom:12px;font-size:13px;color:#1a3d2b}
.step-ref-banner{background:#FFFBEB;border:1px solid #F6E05E;border-radius:6px;padding:6px 12px;font-size:11.5px;color:#744210;margin-bottom:8px}
.yes-section{background:#F0FFF4;border:1.5px solid #9AE6B4;border-radius:8px;padding:10px 12px;margin-bottom:6px}
.no-section{background:#FFF5F5;border:1.5px solid #FEB2B2;border-radius:8px;padding:10px 12px;margin-bottom:6px}
.branch-sub{background:rgba(255,255,255,0.7);border:1px dashed #CBD5E0;border-radius:6px;padding:8px 10px;margin-top:6px}
</style>""", unsafe_allow_html=True)

st.title("📋 SOP Builder — Standard Operating Procedure")
st.caption("Fill details, build process flow, then download as PDF.")

tab1,tab2,tab3,tab4 = st.tabs(["🏷️ Header Info","🤖 Process Flow","📝 Change Record","📄 Download PDF"])

# ═══════════════════════════════════════════════════════════
# TAB 1 — HEADER INFO
# ═══════════════════════════════════════════════════════════
with tab1:
    st.subheader("Document Header Fields")
    c1,c2,c3=st.columns(3)
    with c1:
        st.session_state.company_name=st.text_input("Company Name",  st.session_state.company_name)
        st.session_state.title       =st.text_input("SOP Sub-title", st.session_state.title)
        st.session_state.sop_no      =st.text_input("SOP No.",       st.session_state.sop_no)
        st.session_state.rev_no      =st.text_input("Rev. No.",      st.session_state.rev_no)
    with c2:
        st.session_state.date        =st.text_input("Date",          st.session_state.date)
        st.session_state.page_info   =st.text_input("Page Info",     st.session_state.page_info)
        st.session_state.unit        =st.text_input("Unit",          st.session_state.unit)
        st.session_state.area        =st.text_input("Area",          st.session_state.area)
    with c3:
        st.session_state.sub_area    =st.text_input("Sub Area",      st.session_state.sub_area)
        st.session_state.zone        =st.text_input("Zone",          st.session_state.zone)
        st.session_state.owner       =st.text_input("Owner",         st.session_state.owner)
        st.session_state.composed_by =st.text_input("Composed By",   st.session_state.composed_by)
    st.divider()
    st.subheader("Purpose & Scope")
    st.session_state.purpose=st.text_input("Purpose",st.session_state.purpose)
    st.session_state.scope  =st.text_area("Scope",   st.session_state.scope,height=80)

# ═══════════════════════════════════════════════════════════
# TAB 2 — PROCESS FLOW
# ═══════════════════════════════════════════════════════════
with tab2:
    st.markdown('<div class="ai-banner">✨ <b>Gemini-Powered Flow Builder</b> — Describe your process in plain English, or switch to Manual mode to add steps one by one.</div>', unsafe_allow_html=True)

    mode_col,_=st.columns([2,5])
    with mode_col:
        mode=st.radio("Input mode",["🤖 AI Generate","✏️ Manual"],horizontal=True,label_visibility="collapsed")
    st.session_state.ai_mode=mode

    input_col,preview_col=st.columns([1,1],gap="large")

    with input_col:
        if "AI" in mode:
            st.subheader("✍️ Describe Your Process")
            st.caption("Write naturally — mention decisions, branches, loops, and who does what.")
            st.markdown("**Quick examples:**")
            ec=st.columns(3)
            for i,(el,label) in enumerate(zip(ec,["📦 Procurement","🏖️ Leave Approval","🏭 Manufacturing QC"])):
                if el.button(label,key=f"ex_{i}"):
                    st.session_state.ai_description=EXAMPLES[i]; st.rerun()
            description=st.text_area("Process description",value=st.session_state.ai_description,height=200,
                placeholder="e.g. Start → Receive goods → Inspect quality → If OK: update stock → End.",
                label_visibility="collapsed",key="ai_desc_input")
            st.session_state.ai_description=description
            gc,clr=st.columns([3,1])
            with gc: gen_btn=st.button("✨ Generate Flowchart with Gemini",type="primary",use_container_width=True)
            with clr:
                if st.button("🗑️ Clear",use_container_width=True):
                    st.session_state.steps=[]; st.session_state.ai_description=""; st.rerun()
            if gen_btn:
                if not description.strip(): st.warning("Please describe your process first.")
                elif not st.session_state.get("gemini_api_key","").strip():
                    st.error("⚠️ Please enter your Google Gemini API key in the sidebar first.")
                else:
                    with st.spinner("✨ Gemini is building the flowchart…"):
                        try:
                            result=generate_steps_with_ai(description)
                            if result:
                                st.session_state.steps=result
                                st.success(f"✅ Generated {len(result)} steps!")
                                st.rerun()
                        except json.JSONDecodeError: st.error("⚠️ AI returned unexpected output. Try rephrasing.")
                        except Exception as e: st.error(f"⚠️ Error: {e}")

        # ══════════════════════════════════════════════════════════
        # ✏️ MANUAL MODE
        # ══════════════════════════════════════════════════════════
        else:
            SHAPE_NO_DIAM = [k for k in SHAPE_TYPES if k != "Decision (Diamond)"]

            if st.session_state.steps:
                refs = "  |  ".join([
                    f"**{i}** = {(s.get('text') or SHAPE_TYPES.get(s.get('shape',''),''))[:20]}"
                    for i, s in enumerate(st.session_state.steps)
                ])
                st.markdown(f'<div class="step-ref-banner">📌 <b>Step index (0-based):</b> {refs}</div>',
                            unsafe_allow_html=True)

            def step_opts():
                return [f"Step {i} : {st.session_state.steps[i].get('text','')[:40]}"
                        for i in range(len(st.session_state.steps))]

            def idx_from_opt(opt_str):
                try: return int(opt_str.split("Step ")[1].split(" :")[0])
                except: return None

            shape_label = st.selectbox("🔷 Shape Type", list(SHAPE_TYPES.keys()), key="shape_sel")
            is_diamond  = (shape_label == "Decision (Diamond)")

            BRANCH_ACTIONS = [
                "➕ Add new shape",
                "↩️ Loop back to existing step",
                "🔗 Join / connect to existing step",
                "— None —",
            ]

            with st.form("add_step_form", clear_on_submit=True):
                fc, ft = st.columns([2, 3])
                with fc: col_choice = st.selectbox("Column", COLUMN_OPTIONS)
                with ft: step_text  = st.text_input("Text inside shape *", placeholder="e.g. Start, Check Quality…")

                # ── NON-DIAMOND ──────────────────────────────────────────────
                if not is_diamond:
                    st.markdown("**Side-column data (optional)**")
                    sc1,sc2,sc3=st.columns(3)
                    with sc1:
                        input_label  = st.text_input("Input Label",  key="f_il")
                        output_label = st.text_input("Output Label", key="f_ol")
                    with sc2:
                        responsible = st.text_input("Responsible", key="f_re")
                        doc_format  = st.text_input("Doc. Format",  key="f_df")
                    with sc3:
                        measurement = st.text_input("Measurement", key="f_me")
                    st.markdown("**Arrow / Connection**")
                    a1,a2,a3=st.columns(3)
                    with a1:
                        connect_from = st.text_input("Connect from step # (0-based, blank=auto)", key="f_cf")
                        connect_side = st.selectbox("Arrow exits from", CONNECT_SIDE_OPTIONS, key="f_cs")
                    with a2:
                        arrow_label = st.text_input("Arrow label (YES/NO/blank)", key="f_al")
                    with a3:
                        loop_to    = st.text_input("Loop-back to step # (0-based)", key="f_lt")
                        loop_label = st.text_input("Loop label", key="f_ll")

                # ── DIAMOND ────────────────────────────────────────────────
                else:
                    st.markdown("### 🔀 Decision Branch Configuration")

                    st.markdown("**Arrow into this diamond**")
                    dc1, dc2 = st.columns(2)
                    with dc1:
                        d_cf   = st.text_input("Connect from step # (0-based, blank=auto)", key="f_dcf")
                    with dc2:
                        d_side = st.selectbox("Arrow exits source from", CONNECT_SIDE_OPTIONS, key="f_ds")

                    yl_c, nl_c = st.columns(2)
                    with yl_c: yes_lbl = st.text_input("YES label text", value="YES", key="f_yes_lbl")
                    with nl_c: no_lbl  = st.text_input("NO label text",  value="NO",  key="f_no_lbl")

                    opts     = step_opts()
                    no_steps = len(opts) == 0

                    st.markdown("---")
                    # ── YES BRANCH ──────────────────────────────────────────
                    st.markdown('<div class="yes-section">', unsafe_allow_html=True)
                    st.markdown("#### ✅ YES Branch")
                    yes_flow = st.selectbox("YES branch action", BRANCH_ACTIONS, key="f_yf")

                    yes_new_shape=yes_new_text=yes_new_col=""
                    yes_new_side="right side →"
                    yes_loop_to=yes_loop_lbl=""
                    yes_join_step=""
                    yes_sub_action=""
                    yes_sub_shape=yes_sub_text=yes_sub_col=""
                    yes_sub_loop_to=yes_sub_loop_lbl=""

                    if yes_flow == BRANCH_ACTIONS[0]:
                        y1, y2, y3 = st.columns(3)
                        with y1:
                            ysl          = st.selectbox("Shape type", SHAPE_NO_DIAM, key="f_ysl")
                            yes_new_shape= SHAPE_TYPES[ysl]
                        with y2:
                            yes_new_col  = st.selectbox("Column", COLUMN_OPTIONS, key="f_ycol")
                        with y3:
                            yes_new_side = st.selectbox("Arrow exits diamond from", CONNECT_SIDE_OPTIONS, key="f_ysd")
                        yes_new_text = st.text_input("Text in YES shape", key="f_yt")

                        st.markdown('<div class="branch-sub">', unsafe_allow_html=True)
                        st.markdown("**After this YES shape → next action:**")
                        yes_sub_action = st.selectbox("YES sub-action", BRANCH_ACTIONS, key="f_ysa")
                        if yes_sub_action == BRANCH_ACTIONS[0]:
                            ys1, ys2 = st.columns(2)
                            with ys1:
                                yssl           = st.selectbox("Sub-shape type", SHAPE_NO_DIAM, key="f_yssl")
                                yes_sub_shape  = SHAPE_TYPES[yssl]
                            with ys2:
                                yes_sub_col    = st.selectbox("Sub-shape column", COLUMN_OPTIONS, key="f_yscol")
                            yes_sub_text = st.text_input("Sub-shape text", key="f_yst")
                        elif yes_sub_action == BRANCH_ACTIONS[1]:
                            if no_steps: st.info("No steps yet to loop back to.")
                            else:
                                sel             = st.selectbox("Loop back to", opts, key="f_ysls")
                                yes_sub_loop_to = str(idx_from_opt(sel)) if idx_from_opt(sel) is not None else ""
                            yes_sub_loop_lbl = st.text_input("Loop label", value="YES", key="f_ysll")
                        elif yes_sub_action == BRANCH_ACTIONS[2]:
                            if no_steps: st.info("No steps yet.")
                            else:
                                selj            = st.selectbox("Join step", opts, key="f_ysjs")
                                yes_sub_loop_to = str(idx_from_opt(selj)) if idx_from_opt(selj) is not None else ""
                            yes_sub_loop_lbl = st.selectbox("Arrow side", CONNECT_SIDE_OPTIONS, key="f_ysjsd")
                        st.markdown('</div>', unsafe_allow_html=True)

                    elif yes_flow == BRANCH_ACTIONS[1]:
                        if no_steps: st.info("No steps yet to loop back to.")
                        else:
                            sel        = st.selectbox("Loop back to step", opts, key="f_yls")
                            yes_loop_to= str(idx_from_opt(sel)) if idx_from_opt(sel) is not None else ""
                        yes_loop_lbl = st.text_input("Loop label", value="YES", key="f_yll")

                    elif yes_flow == BRANCH_ACTIONS[2]:
                        if no_steps: st.info("No steps yet.")
                        else:
                            selj           = st.selectbox("Connect YES to step", opts, key="f_yjs")
                            yes_join_step  = str(idx_from_opt(selj)) if idx_from_opt(selj) is not None else ""

                    st.markdown('</div>', unsafe_allow_html=True)
                    st.markdown("---")

                    # ── NO BRANCH ──────────────────────────────────────────
                    st.markdown('<div class="no-section">', unsafe_allow_html=True)
                    st.markdown("#### ❌ NO Branch")
                    no_flow = st.selectbox("NO branch action", BRANCH_ACTIONS, key="f_nf")

                    no_new_shape=no_new_text=no_new_col=""
                    no_new_side="left side ←"
                    no_loop_to=no_loop_lbl=""
                    no_join_step=""
                    no_sub_action=""
                    no_sub_shape=no_sub_text=no_sub_col=""
                    no_sub_loop_to=no_sub_loop_lbl=""

                    if no_flow == BRANCH_ACTIONS[0]:
                        n1, n2, n3 = st.columns(3)
                        with n1:
                            nsl          = st.selectbox("Shape type", SHAPE_NO_DIAM, key="f_nsl")
                            no_new_shape = SHAPE_TYPES[nsl]
                        with n2:
                            no_new_col   = st.selectbox("Column", COLUMN_OPTIONS, key="f_ncol")
                        with n3:
                            no_new_side  = st.selectbox("Arrow exits diamond from", CONNECT_SIDE_OPTIONS, key="f_nsd")
                        no_new_text = st.text_input("Text in NO shape", key="f_nt")

                        st.markdown('<div class="branch-sub">', unsafe_allow_html=True)
                        st.markdown("**After this NO shape → next action:**")
                        no_sub_action = st.selectbox("NO sub-action", BRANCH_ACTIONS, key="f_nsa")
                        if no_sub_action == BRANCH_ACTIONS[0]:
                            ns1, ns2 = st.columns(2)
                            with ns1:
                                nssl          = st.selectbox("Sub-shape type", SHAPE_NO_DIAM, key="f_nssl")
                                no_sub_shape  = SHAPE_TYPES[nssl]
                            with ns2:
                                no_sub_col    = st.selectbox("Sub-shape column", COLUMN_OPTIONS, key="f_nscol")
                            no_sub_text = st.text_input("Sub-shape text", key="f_nst")
                        elif no_sub_action == BRANCH_ACTIONS[1]:
                            if no_steps: st.info("No steps yet to loop back to.")
                            else:
                                sel            = st.selectbox("Loop back to", opts, key="f_nsls")
                                no_sub_loop_to = str(idx_from_opt(sel)) if idx_from_opt(sel) is not None else ""
                            no_sub_loop_lbl = st.text_input("Loop label", value="NO", key="f_nsll")
                        elif no_sub_action == BRANCH_ACTIONS[2]:
                            if no_steps: st.info("No steps yet.")
                            else:
                                selj           = st.selectbox("Join step", opts, key="f_nsjs")
                                no_sub_loop_to = str(idx_from_opt(selj)) if idx_from_opt(selj) is not None else ""
                            no_sub_loop_lbl = st.selectbox("Arrow side", CONNECT_SIDE_OPTIONS, key="f_nsjsd")
                        st.markdown('</div>', unsafe_allow_html=True)

                    elif no_flow == BRANCH_ACTIONS[1]:
                        if no_steps: st.info("No steps yet to loop back to.")
                        else:
                            sel       = st.selectbox("Loop back to step", opts, key="f_nls")
                            no_loop_to= str(idx_from_opt(sel)) if idx_from_opt(sel) is not None else ""
                        no_loop_lbl = st.text_input("Loop label", value="NO", key="f_nll")

                    elif no_flow == BRANCH_ACTIONS[2]:
                        if no_steps: st.info("No steps yet.")
                        else:
                            selj          = st.selectbox("Connect NO to step", opts, key="f_njs")
                            no_join_step  = str(idx_from_opt(selj)) if idx_from_opt(selj) is not None else ""

                    st.markdown('</div>', unsafe_allow_html=True)
                    st.markdown("---")

                    st.markdown("**Side-column data (optional)**")
                    d1,d2,d3=st.columns(3)
                    d_inp  = d1.text_input("Input Label",  key="f_di")
                    d_out  = d1.text_input("Output Label", key="f_do")
                    d_resp = d2.text_input("Responsible",  key="f_dr")
                    d_doc  = d2.text_input("Doc Format",   key="f_dd")
                    d_meas = d3.text_input("Measurement",  key="f_dm")

                submitted = st.form_submit_button("➕ Add Step(s)", use_container_width=True, type="primary")

            # ── PROCESS SUBMISSION ────────────────────────────────────────────
            if submitted:
                if not step_text.strip():
                    st.warning("⚠️ Please enter text for the shape.")

                elif not is_diamond:
                    cf_v = connect_from.strip() if connect_from.strip().isdigit() else ""
                    lt_v = loop_to.strip()       if loop_to.strip().isdigit()      else ""
                    st.session_state.steps.append(sanitize_step({
                        "shape": SHAPE_TYPES[shape_label], "text": step_text.strip(),
                        "column": col_choice,
                        "input_label": input_label, "output_label": output_label,
                        "responsible": responsible, "doc_format": doc_format,
                        "measurement": measurement, "yes_label": "YES", "no_label": "NO",
                        "connect_from": cf_v, "connect_side": connect_side,
                        "arrow_label": arrow_label, "loop_to": lt_v, "loop_label": loop_label,
                    }))
                    st.success(f"✅ Step {len(st.session_state.steps)} added"); st.rerun()

                else:
                    added = 0
                    d_cf_v = d_cf.strip() if d_cf.strip().isdigit() else ""

                    diamond_loop_to  = ""
                    diamond_loop_lbl = ""
                    if yes_flow == BRANCH_ACTIONS[1] and yes_loop_to:
                        diamond_loop_to  = yes_loop_to
                        diamond_loop_lbl = yes_loop_lbl

                    # 1. Append diamond
                    diamond = sanitize_step({
                        "shape": "diamond", "text": step_text.strip(),
                        "column": col_choice,
                        "input_label": d_inp, "output_label": d_out,
                        "responsible": d_resp, "doc_format": d_doc, "measurement": d_meas,
                        "yes_label": yes_lbl or "YES", "no_label": no_lbl or "NO",
                        "connect_from": d_cf_v, "connect_side": d_side,
                        "arrow_label": "", "loop_to": diamond_loop_to, "loop_label": diamond_loop_lbl,
                    })
                    st.session_state.steps.append(diamond)
                    d_idx = len(st.session_state.steps) - 1
                    added += 1

                    # ── YES BRANCH ────────────────────────────────────────────
                    if yes_flow == BRANCH_ACTIONS[0] and yes_new_text.strip():
                        yes_step_idx = len(st.session_state.steps)
                        yes_step = sanitize_step({
                            "shape": yes_new_shape or "rect",
                            "text":  yes_new_text.strip(),
                            "column": yes_new_col or "right",
                            "connect_from": str(d_idx),
                            "connect_side": yes_new_side or "right side →",
                            "arrow_label":  yes_lbl or "YES",
                            "loop_to": "", "loop_label": "",
                            "yes_label": "YES", "no_label": "NO",
                            "input_label": "", "output_label": "",
                            "responsible": "", "doc_format": "", "measurement": "",
                        })
                        st.session_state.steps.append(yes_step)
                        added += 1

                        if yes_sub_action == BRANCH_ACTIONS[1] and yes_sub_loop_to:
                            st.session_state.steps[yes_step_idx]["loop_to"]    = yes_sub_loop_to
                            st.session_state.steps[yes_step_idx]["loop_label"] = yes_sub_loop_lbl
                        elif yes_sub_action == BRANCH_ACTIONS[2] and yes_sub_loop_to:
                            st.session_state.steps[yes_step_idx]["loop_to"]    = yes_sub_loop_to
                            st.session_state.steps[yes_step_idx]["loop_label"] = yes_sub_loop_lbl or "YES"
                        elif yes_sub_action == BRANCH_ACTIONS[0] and yes_sub_text.strip():
                            st.session_state.steps.append(sanitize_step({
                                "shape": yes_sub_shape or "rect",
                                "text":  yes_sub_text.strip(),
                                "column": yes_sub_col or "right",
                                "connect_from": str(yes_step_idx),
                                "connect_side": "bottom (default)",
                                "arrow_label": "",
                                "loop_to": "", "loop_label": "",
                                "yes_label": "YES", "no_label": "NO",
                                "input_label": "", "output_label": "",
                                "responsible": "", "doc_format": "", "measurement": "",
                            }))
                            added += 1

                    elif yes_flow == BRANCH_ACTIONS[2] and yes_join_step:
                        if not st.session_state.steps[d_idx]["loop_to"]:
                            st.session_state.steps[d_idx]["loop_to"]    = yes_join_step
                            st.session_state.steps[d_idx]["loop_label"] = yes_lbl or "YES"

                    # ── NO BRANCH ─────────────────────────────────────────────
                    if no_flow == BRANCH_ACTIONS[1] and no_loop_to:
                        if not st.session_state.steps[d_idx]["loop_to"]:
                            st.session_state.steps[d_idx]["loop_to"]    = no_loop_to
                            st.session_state.steps[d_idx]["loop_label"] = no_loop_lbl
                        else:
                            st.session_state.steps.append(sanitize_step({
                                "shape": "arrow_text",
                                "text":  f"← {no_lbl or 'NO'}",
                                "column": "left",
                                "connect_from": str(d_idx),
                                "connect_side": "left side ←",
                                "arrow_label":  no_lbl or "NO",
                                "loop_to":    no_loop_to,
                                "loop_label": no_loop_lbl,
                                "yes_label": "YES", "no_label": "NO",
                                "input_label": "", "output_label": "",
                                "responsible": "", "doc_format": "", "measurement": "",
                            }))
                            added += 1

                    elif no_flow == BRANCH_ACTIONS[0] and no_new_text.strip():
                        no_step_idx = len(st.session_state.steps)
                        no_step = sanitize_step({
                            "shape": no_new_shape or "rect",
                            "text":  no_new_text.strip(),
                            "column": no_new_col or "left",
                            "connect_from": str(d_idx),
                            "connect_side": no_new_side or "left side ←",
                            "arrow_label":  no_lbl or "NO",
                            "loop_to": "", "loop_label": "",
                            "yes_label": "YES", "no_label": "NO",
                            "input_label": "", "output_label": "",
                            "responsible": "", "doc_format": "", "measurement": "",
                        })
                        st.session_state.steps.append(no_step)
                        added += 1

                        if no_sub_action == BRANCH_ACTIONS[1] and no_sub_loop_to:
                            st.session_state.steps[no_step_idx]["loop_to"]    = no_sub_loop_to
                            st.session_state.steps[no_step_idx]["loop_label"] = no_sub_loop_lbl
                        elif no_sub_action == BRANCH_ACTIONS[2] and no_sub_loop_to:
                            st.session_state.steps[no_step_idx]["loop_to"]    = no_sub_loop_to
                            st.session_state.steps[no_step_idx]["loop_label"] = no_sub_loop_lbl or "NO"
                        elif no_sub_action == BRANCH_ACTIONS[0] and no_sub_text.strip():
                            st.session_state.steps.append(sanitize_step({
                                "shape": no_sub_shape or "rect",
                                "text":  no_sub_text.strip(),
                                "column": no_sub_col or "left",
                                "connect_from": str(no_step_idx),
                                "connect_side": "bottom (default)",
                                "arrow_label": "",
                                "loop_to": "", "loop_label": "",
                                "yes_label": "YES", "no_label": "NO",
                                "input_label": "", "output_label": "",
                                "responsible": "", "doc_format": "", "measurement": "",
                            }))
                            added += 1

                    elif no_flow == BRANCH_ACTIONS[2] and no_join_step:
                        if not st.session_state.steps[d_idx]["loop_to"]:
                            st.session_state.steps[d_idx]["loop_to"]    = no_join_step
                            st.session_state.steps[d_idx]["loop_label"] = no_lbl or "NO"
                        else:
                            st.session_state.steps.append(sanitize_step({
                                "shape": "arrow_text",
                                "text":  f"← {no_lbl or 'NO'}",
                                "column": "left",
                                "connect_from": str(d_idx),
                                "connect_side": "left side ←",
                                "arrow_label":  no_lbl or "NO",
                                "loop_to":    no_join_step,
                                "loop_label": no_lbl or "NO",
                                "yes_label": "YES", "no_label": "NO",
                                "input_label": "", "output_label": "",
                                "responsible": "", "doc_format": "", "measurement": "",
                            }))
                            added += 1

                    st.success(f"✅ Added {added} step(s) — total: {len(st.session_state.steps)}")
                    st.rerun()

        # ── Steps list ─────────────────────────────────────────────────────────
        st.divider()
        n=len(st.session_state.steps)
        if n:
            st.subheader(f"Steps ({n})  — click to edit or reorder")
            rev_map={v:k for k,v in SHAPE_TYPES.items()}
            for i,step in enumerate(st.session_state.steps):
                lbl=rev_map.get(step["shape"],step["shape"])
                ct="🔵 left" if step.get("column","left")=="left" else "🟢 right"
                cf=(step.get("connect_from") or "")
                cf_d=f"step {cf}" if str(cf).isdigit() else "auto"
                lt=(step.get("loop_to") or "")
                lt_d=f"step {lt}" if str(lt).isdigit() else "—"
                with st.expander(f"**Step {i} (idx {i})** {ct} › [{lbl}]  {step.get('text','')}",expanded=False):
                    nt=st.text_input("Edit text",value=(step.get("text") or ""),key=f"e_{i}")
                    if nt!=step.get("text",""): st.session_state.steps[i]["text"]=nt; st.rerun()
                    e1,e2,e3=st.columns(3)
                    nr=e1.text_input("Responsible",value=(step.get("responsible") or ""),key=f"r_{i}")
                    nd=e2.text_input("Doc Format", value=(step.get("doc_format")  or ""),key=f"d_{i}")
                    nm=e3.text_input("Measurement",value=(step.get("measurement") or ""),key=f"m_{i}")
                    if nr!=step.get("responsible",""): st.session_state.steps[i]["responsible"]=nr; st.rerun()
                    if nd!=step.get("doc_format",""):  st.session_state.steps[i]["doc_format"]=nd;  st.rerun()
                    if nm!=step.get("measurement",""): st.session_state.steps[i]["measurement"]=nm; st.rerun()

                    ea1,ea2,ea3=st.columns(3)
                    n_cf   = ea1.text_input("Connect from step #", value=(step.get("connect_from") or ""), key=f"cf_{i}")
                    n_side = ea2.selectbox("Arrow side", CONNECT_SIDE_OPTIONS,
                                           index=CONNECT_SIDE_OPTIONS.index(step.get("connect_side","bottom (default)"))
                                           if step.get("connect_side") in CONNECT_SIDE_OPTIONS else 0, key=f"cs_{i}")
                    n_al   = ea3.text_input("Arrow label", value=(step.get("arrow_label") or ""), key=f"al_{i}")
                    eb1,eb2=st.columns(2)
                    n_lt   = eb1.text_input("Loop-to step #", value=(step.get("loop_to") or ""), key=f"lt_{i}")
                    n_ll   = eb2.text_input("Loop label",     value=(step.get("loop_label") or ""), key=f"ll_{i}")
                    for fk,fv in [("connect_from",n_cf),("connect_side",n_side),
                                   ("arrow_label",n_al),("loop_to",n_lt),("loop_label",n_ll)]:
                        if step.get(fk,"") != fv:
                            st.session_state.steps[i][fk]=fv; st.rerun()

                    b1,b2,b3,_=st.columns([1,1,1,4])
                    if b1.button("⬆️",key=f"u_{i}"):
                        if i>0: st.session_state.steps[i],st.session_state.steps[i-1]=st.session_state.steps[i-1],st.session_state.steps[i]
                        st.rerun()
                    if b2.button("⬇️",key=f"dn_{i}"):
                        if i<len(st.session_state.steps)-1: st.session_state.steps[i],st.session_state.steps[i+1]=st.session_state.steps[i+1],st.session_state.steps[i]
                        st.rerun()
                    if b3.button("🗑️",key=f"del_{i}"):
                        st.session_state.steps.pop(i); st.rerun()
                    st.caption(f"Connect from: {cf_d}  |  Side: {step.get('connect_side','bottom')}  |  Arrow: {step.get('arrow_label','—')}  |  Loop to: {lt_d}")
        else:
            st.info("No steps yet. Use the form above to add process flow steps." if "Manual" in mode
                    else "Describe your process above and click ✨ Generate Flowchart with Gemini.")

    with preview_col:
        st.subheader("👁️ Live Flowchart Preview")
        st.caption("Main flow is centered. Updates automatically as steps change.")
        html=render_preview_html(st.session_state.steps)
        n=len(st.session_state.steps)
        est_h=max(320,min(950,n*92+160)) if n>0 else 260
        components.html(html,height=est_h,scrolling=False)

# ═══════════════════════════════════════════════════════════
# TAB 3 — CHANGE RECORD
# ═══════════════════════════════════════════════════════════
with tab3:
    st.subheader("SOP Change Record")
    with st.form("cr_form",clear_on_submit=True):
        r1=st.columns(4); sno=r1[0].text_input("S.No."); cdate=r1[1].text_input("Effective Date")
        rev=r1[2].text_input("REV. No."); desc=r1[3].text_input("Change Description")
        r2=st.columns(4); cl=r2[0].text_input("Change Letter"); prep=r2[1].text_input("Prepared By")
        rev2=r2[2].text_input("Reviewed By"); appr=r2[3].text_input("Approved By")
        if st.form_submit_button("➕ Add Row",use_container_width=True):
            st.session_state.change_records.append({"sno":sno,"date":cdate,"rev":rev,"desc":desc,
                "change_letter":cl,"prepared":prep,"reviewed":rev2,"approved":appr})
            st.success("Row added.")
    st.divider()
    for i,cr in enumerate(st.session_state.change_records):
        cc1,cc2=st.columns([9,1])
        cc1.write(f"**{cr['sno']}** | {cr['date']} | Rev {cr['rev']} | {cr['desc']} | "
                  f"Prepared: {cr['prepared']} | Reviewed: {cr['reviewed']} | Approved: {cr['approved']}")
        if cc2.button("🗑️",key=f"cr_{i}"):
            st.session_state.change_records.pop(i); st.rerun()

# ═══════════════════════════════════════════════════════════
# TAB 4 — DOWNLOAD PDF
# ═══════════════════════════════════════════════════════════
with tab4:
    st.subheader("Generate & Download PDF")
    if not st.session_state.steps:
        st.warning("⚠️ Add at least one process step before generating the PDF.")
    else:
        st.success(f"Ready — **{len(st.session_state.steps)} step(s)** will be included.")
        logo_b=st.session_state.get("logo_bytes")
        meta={k:st.session_state[k] for k in ["company_name","title","sop_no","rev_no","date","page_info",
            "unit","area","sub_area","zone","owner","purpose","scope","composed_by","change_records"]}
        meta["logo_bytes"]=logo_b
        pdf_buf=generate_pdf(st.session_state.steps,meta)
        st.download_button(label="📥 Download SOP PDF",data=pdf_buf,
            file_name="SOP_Document.pdf",mime="application/pdf",use_container_width=True)
        st.divider()
        st.subheader("Step Summary")
        rev_map={v:k for k,v in SHAPE_TYPES.items()}
        rows=[{"Step (idx)":f"{i} (idx {i})","Col":s.get("column","left"),"Shape":rev_map.get(s["shape"],s["shape"]),
               "Text":(s.get("text") or ""),
               "Connect from":s.get("connect_from","") if str(s.get("connect_from","")).isdigit() else "auto",
               "Arrow label":(s.get("arrow_label") or ""),
               "Loop to":s.get("loop_to","") if str(s.get("loop_to","")).isdigit() else "—"}
              for i,s in enumerate(st.session_state.steps)]
        st.dataframe(rows,use_container_width=True,hide_index=True)
