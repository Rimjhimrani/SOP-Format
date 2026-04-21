import streamlit as st
import streamlit.components.v1 as components
import io
import json
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
    "Decision (Diamond)":  "diamond",
    "Oval / Terminator":   "oval",
    "Parallelogram (I/O)": "parallelogram",
    "Annotation Text":     "arrow_text",
}

COLUMN_OPTIONS       = ["left", "right"]
CONNECT_SIDE_OPTIONS = ["bottom (default)", "right side →", "left side ←"]

# ─── LIVE SVG FLOWCHART GENERATOR ─────────────────────────────────────────────

def generate_svg_preview(steps):
    """Generate an interactive SVG preview of the flowchart."""
    if not steps:
        return """
        <div style="display:flex;align-items:center;justify-content:center;height:200px;
                    color:#888;font-family:sans-serif;font-size:14px;
                    border:2px dashed #ddd;border-radius:12px;margin:8px 0;">
            <div style="text-align:center">
                <div style="font-size:32px;margin-bottom:8px">🔷</div>
                <div>Add steps to see your flowchart here</div>
            </div>
        </div>"""

    # Layout constants
    SVG_W      = 700
    BOX_W_L    = 180   # left-column box width
    BOX_W_R    = 180   # right-column box width
    COL_L_CX   = 200   # left column centre x
    COL_R_CX   = 500   # right column centre x

    SHAPE_H = {
        "rect":          60,
        "oval":          50,
        "parallelogram": 60,
        "diamond":       80,
        "arrow_text":    30,
    }
    V_GAP  = 28   # vertical gap between shapes
    TOP_Y  = 40   # first shape top y

    # ── PASS 1: pair steps into rows (same logic as PDF) ──────────────────
    paired_rows   = []
    step_to_pair  = {}

    for idx, step in enumerate(steps):
        col = step.get("column", "left")
        if col == "right":
            paired = False
            for pi in range(len(paired_rows) - 1, -1, -1):
                if paired_rows[pi]["right"] is None:
                    paired_rows[pi]["right"] = idx
                    step_to_pair[idx] = pi
                    paired = True
                    break
            if not paired:
                paired_rows.append({"left": None, "right": idx})
                step_to_pair[idx] = len(paired_rows) - 1
        else:
            paired_rows.append({"left": idx, "right": None})
            step_to_pair[idx] = len(paired_rows) - 1

    # ── PASS 2: compute row heights and vertical positions ─────────────────
    row_geom = []
    cur_y    = TOP_Y
    for pair in paired_rows:
        h_l = SHAPE_H.get(steps[pair["left"]]["shape"],  60) if pair["left"]  is not None else 0
        h_r = SHAPE_H.get(steps[pair["right"]]["shape"], 60) if pair["right"] is not None else 0
        row_h = max(h_l, h_r)
        row_geom.append({"y_top": cur_y, "row_h": row_h})
        cur_y += row_h + V_GAP

    SVG_H = cur_y + 40

    # ── PASS 3: build anchor lookup ─────────────────────────────────────────
    anchors = {}
    for idx, step in enumerate(steps):
        pi       = step_to_pair[idx]
        rg       = row_geom[pi]
        col      = step.get("column", "left")
        sh_h     = SHAPE_H.get(step["shape"], 60)
        cx       = COL_L_CX if col == "left" else COL_R_CX
        bw       = BOX_W_L  if col == "left" else BOX_W_R
        sh_top   = rg["y_top"]
        sh_bot   = sh_top + sh_h
        sh_mid_y = sh_top + sh_h / 2

        anchors[idx] = {
            "cx":    cx,
            "cy":    sh_mid_y,
            "top":   sh_top,
            "bot":   sh_bot,
            "left":  cx - bw / 2,
            "right": cx + bw / 2,
            "bw":    bw,
            "bh":    sh_h,
            "col":   col,
        }

    # ── Helpers ─────────────────────────────────────────────────────────────
    def esc(t):
        return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def wrap_label(text, max_chars=22):
        """Simple word-wrap returning list of lines."""
        words  = str(text).split()
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if len(trial) <= max_chars:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines or [""]

    def text_lines_svg(lines, cx, mid_y, font_size=11, bold=False, fill="#1a1a1a"):
        """Render multiple centred lines."""
        lh   = font_size + 3
        total = len(lines) * lh
        y0    = mid_y - total / 2 + lh * 0.75
        weight = "600" if bold else "400"
        out = ""
        for i, line in enumerate(lines):
            out += f'<text x="{cx}" y="{y0 + i*lh:.1f}" text-anchor="middle" ' \
                   f'font-size="{font_size}" font-weight="{weight}" fill="{fill}" ' \
                   f'font-family="\'Segoe UI\',sans-serif">{esc(line)}</text>'
        return out

    # ── PASS 4: draw arrows ──────────────────────────────────────────────────
    arrow_svg = ""
    ARROW_COLOR  = "#4a5568"
    YES_COLOR    = "#276749"
    NO_COLOR     = "#c53030"

    def arrowhead_d(tx, ty, direction="down"):
        sz = 5
        if direction == "down":
            return f"M{tx},{ty} L{tx-sz},{ty-sz*1.5} L{tx+sz},{ty-sz*1.5} Z"
        elif direction == "right":
            return f"M{tx},{ty} L{tx-sz*1.5},{ty-sz} L{tx-sz*1.5},{ty+sz} Z"
        elif direction == "left":
            return f"M{tx},{ty} L{tx+sz*1.5},{ty-sz} L{tx+sz*1.5},{ty+sz} Z"
        else:  # up
            return f"M{tx},{ty} L{tx-sz},{ty+sz*1.5} L{tx+sz},{ty+sz*1.5} Z"

    for idx, step in enumerate(steps):
        a   = anchors[idx]
        lbl = step.get("arrow_label", "").strip()
        lbl_upper = lbl.upper()
        col = "YES" if lbl_upper == "YES" else ("NO" if lbl_upper == "NO" else "")
        ac  = YES_COLOR if col == "YES" else (NO_COLOR if col == "NO" else ARROW_COLOR)

        connect_from = step.get("connect_from", "")
        connect_side = step.get("connect_side", "bottom (default)")

        if connect_from != "" and str(connect_from).isdigit():
            src = int(connect_from)
            if 0 <= src < len(anchors):
                s = anchors[src]
                if connect_side == "right side →":
                    sx, sy = s["right"], s["cy"]
                    ex, ey = a["cx"], a["top"]
                    # L-shaped: horizontal then vertical
                    mid_x = (sx + ex) / 2
                    arrow_svg += f'<path d="M{sx},{sy} L{ex},{sy} L{ex},{ey}" ' \
                                 f'fill="none" stroke="{ac}" stroke-width="1.5" stroke-linejoin="round"/>'
                    arrow_svg += f'<path d="{arrowhead_d(ex, ey, "down")}" fill="{ac}"/>'
                elif connect_side == "left side ←":
                    sx, sy = s["left"], s["cy"]
                    ex, ey = a["cx"], a["top"]
                    arrow_svg += f'<path d="M{sx},{sy} L{ex},{sy} L{ex},{ey}" ' \
                                 f'fill="none" stroke="{ac}" stroke-width="1.5" stroke-linejoin="round"/>'
                    arrow_svg += f'<path d="{arrowhead_d(ex, ey, "down")}" fill="{ac}"/>'
                else:
                    sx, sy = s["cx"], s["bot"]
                    ex, ey = a["cx"], a["top"]
                    if abs(sx - ex) < 2:
                        arrow_svg += f'<line x1="{sx}" y1="{sy}" x2="{ex}" y2="{ey}" ' \
                                     f'stroke="{ac}" stroke-width="1.5"/>'
                        arrow_svg += f'<path d="{arrowhead_d(ex, ey, "down")}" fill="{ac}"/>'
                    else:
                        mid_y_e = (sy + ey) / 2
                        arrow_svg += f'<path d="M{sx},{sy} L{sx},{mid_y_e} L{ex},{mid_y_e} L{ex},{ey}" ' \
                                     f'fill="none" stroke="{ac}" stroke-width="1.5" stroke-linejoin="round"/>'
                        arrow_svg += f'<path d="{arrowhead_d(ex, ey, "down")}" fill="{ac}"/>'
                if lbl:
                    mx = (sx + ex) / 2 if connect_side == "bottom (default)" else sx + 20
                    my = (sy + ey) / 2 - 4
                    arrow_svg += f'<rect x="{mx-18}" y="{my-9}" width="36" height="13" rx="3" ' \
                                 f'fill="white" stroke="{ac}" stroke-width="0.6" opacity="0.92"/>'
                    arrow_svg += f'<text x="{mx}" y="{my+1}" text-anchor="middle" font-size="9" ' \
                                 f'font-weight="700" fill="{ac}" font-family="\'Segoe UI\',sans-serif">{esc(lbl)}</text>'
        else:
            # auto: connect from nearest above in same column
            if idx > 0:
                prev = None
                for pi in range(idx - 1, -1, -1):
                    if anchors[pi]["col"] == a["col"]:
                        prev = pi
                        break
                if prev is not None:
                    ps = anchors[prev]
                    arrow_svg += f'<line x1="{a["cx"]}" y1="{ps["bot"]}" x2="{a["cx"]}" y2="{a["top"]}" ' \
                                 f'stroke="{ARROW_COLOR}" stroke-width="1.5"/>'
                    arrow_svg += f'<path d="{arrowhead_d(a["cx"], a["top"], "down")}" fill="{ARROW_COLOR}"/>'

        # loop-back arrow
        loop_to    = step.get("loop_to", "")
        loop_label = step.get("loop_label", "").strip()
        if loop_to != "" and str(loop_to).isdigit():
            lt = int(loop_to)
            if 0 <= lt < len(anchors):
                dest  = anchors[lt]
                lc    = YES_COLOR if loop_label.upper() == "YES" else (NO_COLOR if loop_label.upper() == "NO" else "#1a6dcc")
                lx    = a["left"] - 22
                arrow_svg += f'<path d="M{a["left"]},{a["cy"]} L{lx},{a["cy"]} L{lx},{dest["cy"]} L{dest["left"]},{dest["cy"]}" ' \
                             f'fill="none" stroke="{lc}" stroke-width="1.5" stroke-dasharray="4 2" stroke-linejoin="round"/>'
                arrow_svg += f'<path d="{arrowhead_d(dest["left"], dest["cy"], "right")}" fill="{lc}"/>'
                if loop_label:
                    my = (a["cy"] + dest["cy"]) / 2
                    arrow_svg += f'<text x="{lx-4}" y="{my}" text-anchor="end" font-size="9" ' \
                                 f'font-weight="700" fill="{lc}" font-family="\'Segoe UI\',sans-serif">{esc(loop_label)}</text>'

    # ── PASS 5: draw shapes ──────────────────────────────────────────────────
    shape_svg = ""

    COLORS = {
        "rect":          {"fill": "#EBF4FF", "stroke": "#2B6CB0", "text": "#1A365D"},
        "oval":          {"fill": "#2D3748", "stroke": "#1A202C", "text": "#FFFFFF"},
        "diamond":       {"fill": "#FFF9E6", "stroke": "#B7791F", "text": "#744210"},
        "parallelogram": {"fill": "#F0FFF4", "stroke": "#276749", "text": "#1C4532"},
        "arrow_text":    {"fill": "none",    "stroke": "none",    "text": "#4A5568"},
    }

    for idx, step in enumerate(steps):
        a     = anchors[idx]
        shape = step["shape"]
        cx, cy = a["cx"], a["cy"]
        bw, bh = a["bw"], a["bh"]
        x0    = cx - bw / 2
        y0    = a["top"]
        clr   = COLORS.get(shape, COLORS["rect"])
        lines = wrap_label(step["text"])
        tip   = f"Step {idx+1}: {step['text']}"

        shape_svg += f'<g class="sop-node" data-step="{idx}">'

        if shape == "rect":
            shape_svg += f'<rect x="{x0}" y="{y0}" width="{bw}" height="{bh}" rx="8" ' \
                         f'fill="{clr["fill"]}" stroke="{clr["stroke"]}" stroke-width="1.5"/>'
            shape_svg += text_lines_svg(lines, cx, cy, font_size=11, fill=clr["text"])

        elif shape == "oval":
            shape_svg += f'<ellipse cx="{cx}" cy="{cy}" rx="{bw/2}" ry="{bh/2}" ' \
                         f'fill="{clr["fill"]}" stroke="{clr["stroke"]}" stroke-width="1.5"/>'
            shape_svg += text_lines_svg(lines, cx, cy, font_size=11, fill=clr["text"])

        elif shape == "diamond":
            pts = f"{cx},{y0} {cx+bw/2},{cy} {cx},{y0+bh} {cx-bw/2},{cy}"
            shape_svg += f'<polygon points="{pts}" fill="{clr["fill"]}" stroke="{clr["stroke"]}" stroke-width="1.5"/>'
            shape_svg += text_lines_svg(lines, cx, cy, font_size=10, fill=clr["text"])
            # YES / NO labels
            yes_l = step.get("yes_label", "YES") or "YES"
            no_l  = step.get("no_label",  "NO")  or "NO"
            shape_svg += f'<text x="{cx + bw/2 + 6}" y="{cy+4}" font-size="9" font-weight="700" ' \
                         f'fill="{YES_COLOR}" font-family="\'Segoe UI\',sans-serif">{esc(yes_l)} →</text>'
            shape_svg += f'<text x="{cx - bw/2 - 6}" y="{cy+4}" font-size="9" font-weight="700" ' \
                         f'text-anchor="end" fill="{NO_COLOR}" font-family="\'Segoe UI\',sans-serif">← {esc(no_l)}</text>'

        elif shape == "parallelogram":
            skew = 10
            pts  = f"{x0+skew},{y0} {x0+bw},{y0} {x0+bw-skew},{y0+bh} {x0},{y0+bh}"
            shape_svg += f'<polygon points="{pts}" fill="{clr["fill"]}" stroke="{clr["stroke"]}" stroke-width="1.5"/>'
            shape_svg += text_lines_svg(lines, cx, cy, font_size=11, fill=clr["text"])

        elif shape == "arrow_text":
            shape_svg += f'<text x="{cx}" y="{cy+4}" text-anchor="middle" font-size="11" ' \
                         f'fill="{clr["text"]}" font-style="italic" font-family="\'Segoe UI\',sans-serif">{esc(step["text"])}</text>'

        # Step number badge
        shape_svg += f'<circle cx="{x0+12}" cy="{y0+12}" r="9" fill="{clr["stroke"]}" opacity="0.9"/>'
        shape_svg += f'<text x="{x0+12}" y="{y0+16}" text-anchor="middle" font-size="9" ' \
                     f'font-weight="700" fill="white" font-family="\'Segoe UI\',sans-serif">{idx+1}</text>'

        shape_svg += '</g>'

    # ── Column headers ───────────────────────────────────────────────────────
    has_right = any(s.get("column", "left") == "right" for s in steps)
    header_svg = ""
    header_svg += f'<rect x="30" y="6" width="{BOX_W_L+40}" height="22" rx="5" fill="#EBF4FF" stroke="#2B6CB0" stroke-width="0.8"/>'
    header_svg += f'<text x="{COL_L_CX}" y="21" text-anchor="middle" font-size="11" font-weight="600" ' \
                  f'fill="#1A365D" font-family="\'Segoe UI\',sans-serif">Main Flow (Left)</text>'
    if has_right:
        header_svg += f'<rect x="{COL_R_CX-BOX_W_R/2-20}" y="6" width="{BOX_W_R+40}" height="22" rx="5" fill="#F0FFF4" stroke="#276749" stroke-width="0.8"/>'
        header_svg += f'<text x="{COL_R_CX}" y="21" text-anchor="middle" font-size="11" font-weight="600" ' \
                      f'fill="#1C4532" font-family="\'Segoe UI\',sans-serif">Branch (Right)</text>'

    # ── Column divider ───────────────────────────────────────────────────────
    divider_svg = ""
    if has_right:
        mid_x = (COL_L_CX + BOX_W_L/2 + COL_R_CX - BOX_W_R/2) / 2
        divider_svg = f'<line x1="{mid_x}" y1="32" x2="{mid_x}" y2="{SVG_H-10}" ' \
                      f'stroke="#CBD5E0" stroke-width="1" stroke-dasharray="5 4"/>'

    # ── Legend ───────────────────────────────────────────────────────────────
    legend_x = SVG_W - 130
    legend_y = TOP_Y
    legend_items = [
        ("rect",          "#EBF4FF", "#2B6CB0", "Process"),
        ("oval",          "#2D3748", "#1A202C", "Terminator"),
        ("diamond",       "#FFF9E6", "#B7791F", "Decision"),
        ("parallelogram", "#F0FFF4", "#276749", "Input/Output"),
    ]
    legend_svg = f'<rect x="{legend_x-8}" y="{legend_y-8}" width="126" height="{len(legend_items)*22+16}" ' \
                 f'rx="8" fill="white" stroke="#CBD5E0" stroke-width="0.8" opacity="0.95"/>'
    legend_svg += f'<text x="{legend_x+4}" y="{legend_y+6}" font-size="10" font-weight="600" ' \
                  f'fill="#4A5568" font-family="\'Segoe UI\',sans-serif">Legend</text>'
    for i, (sh, fill, stroke, label) in enumerate(legend_items):
        ly = legend_y + 20 + i * 22
        lx = legend_x + 4
        if sh in ("rect", "parallelogram"):
            legend_svg += f'<rect x="{lx}" y="{ly-8}" width="20" height="14" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
        elif sh == "oval":
            legend_svg += f'<ellipse cx="{lx+10}" cy="{ly}" rx="10" ry="7" fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
        elif sh == "diamond":
            legend_svg += f'<polygon points="{lx+10},{ly-8} {lx+20},{ly} {lx+10},{ly+8} {lx},{ly}" fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
        legend_svg += f'<text x="{lx+26}" y="{ly+4}" font-size="10" fill="#4A5568" font-family="\'Segoe UI\',sans-serif">{label}</text>'

    full_svg = f"""
    <svg width="{SVG_W}" height="{SVG_H}" viewBox="0 0 {SVG_W} {SVG_H}"
         xmlns="http://www.w3.org/2000/svg" style="font-family:'Segoe UI',sans-serif;">
      <style>
        .sop-node {{ cursor:pointer; transition: opacity 0.15s; }}
        .sop-node:hover {{ opacity: 0.85; }}
        .sop-node:hover rect, .sop-node:hover ellipse, .sop-node:hover polygon {{
          filter: drop-shadow(0 2px 6px rgba(0,0,0,0.18));
        }}
      </style>
      <defs>
        <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
          <path d="M 30 0 L 0 0 0 30" fill="none" stroke="#F0F4F8" stroke-width="0.5"/>
        </pattern>
      </defs>
      <rect width="{SVG_W}" height="{SVG_H}" fill="#FAFBFC"/>
      <rect width="{SVG_W}" height="{SVG_H}" fill="url(#grid)"/>
      {header_svg}
      {divider_svg}
      {arrow_svg}
      {shape_svg}
      {legend_svg}
    </svg>"""
    return full_svg


def render_preview_html(steps):
    """Wrap SVG in a scrollable, zoomable HTML widget."""
    svg = generate_svg_preview(steps)
    step_count = len(steps)
    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #F7F9FC; font-family: 'Segoe UI', sans-serif; overflow: hidden; }}
  #toolbar {{
    display: flex; align-items: center; gap: 10px;
    padding: 8px 14px; background: white;
    border-bottom: 1px solid #E2E8F0;
    font-size: 12px; color: #4A5568;
  }}
  #toolbar strong {{ color: #1A365D; font-size: 13px; }}
  #zoom-controls {{ display:flex; gap:4px; align-items:center; margin-left:auto; }}
  .zbtn {{
    background: #EBF4FF; border: 1px solid #BEE3F8; color: #2B6CB0;
    border-radius: 5px; padding: 3px 9px; cursor: pointer; font-size: 13px;
    font-weight: 600; line-height: 1.4; transition: background 0.15s;
  }}
  .zbtn:hover {{ background: #BEE3F8; }}
  #zoom-label {{ font-size: 11px; color: #718096; min-width: 38px; text-align:center; }}
  #canvas-wrap {{
    width: 100%; height: calc(100vh - 44px);
    overflow: auto; position: relative;
    background: #F7F9FC;
  }}
  #svg-inner {{
    display: inline-block;
    transform-origin: top left;
    transition: transform 0.18s ease;
    padding: 10px;
  }}
  .badge {{
    background: #2B6CB0; color: white;
    border-radius: 12px; padding: 2px 10px;
    font-size: 11px; font-weight: 600;
    margin-left: 6px;
  }}
</style>
</head>
<body>
<div id="toolbar">
  <strong>📊 Live Flowchart Preview</strong>
  <span class="badge">{step_count} step{'s' if step_count != 1 else ''}</span>
  <span style="color:#718096">| Scroll to pan • Use buttons to zoom</span>
  <div id="zoom-controls">
    <button class="zbtn" onclick="zoom(-0.15)">−</button>
    <span id="zoom-label">100%</span>
    <button class="zbtn" onclick="zoom(+0.15)">+</button>
    <button class="zbtn" onclick="resetZoom()" style="font-size:11px;padding:3px 8px">Reset</button>
  </div>
</div>
<div id="canvas-wrap">
  <div id="svg-inner">
    {svg}
  </div>
</div>
<script>
  var scale = 1;
  function zoom(delta) {{
    scale = Math.max(0.3, Math.min(2.5, scale + delta));
    document.getElementById('svg-inner').style.transform = 'scale(' + scale + ')';
    document.getElementById('zoom-label').textContent = Math.round(scale*100) + '%';
  }}
  function resetZoom() {{
    scale = 1;
    document.getElementById('svg-inner').style.transform = 'scale(1)';
    document.getElementById('zoom-label').textContent = '100%';
  }}
</script>
</body>
</html>"""
    return html

# ─── PDF Text Helpers ─────────────────────────────────────────────────────────
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

# ─── Arrow Drawing ────────────────────────────────────────────────────────────
def arrowhead(c, tip_x, tip_y, direction="down"):
    size = 3.5
    c.setFillColor(colors.black)
    p = c.beginPath()
    if direction == "down":
        p.moveTo(tip_x, tip_y)
        p.lineTo(tip_x - size, tip_y + size * 1.5)
        p.lineTo(tip_x + size, tip_y + size * 1.5)
    elif direction == "up":
        p.moveTo(tip_x, tip_y)
        p.lineTo(tip_x - size, tip_y - size * 1.5)
        p.lineTo(tip_x + size, tip_y - size * 1.5)
    elif direction == "right":
        p.moveTo(tip_x, tip_y)
        p.lineTo(tip_x - size * 1.5, tip_y + size)
        p.lineTo(tip_x - size * 1.5, tip_y - size)
    elif direction == "left":
        p.moveTo(tip_x, tip_y)
        p.lineTo(tip_x + size * 1.5, tip_y + size)
        p.lineTo(tip_x + size * 1.5, tip_y - size)
    p.close()
    c.drawPath(p, fill=1, stroke=0)

def draw_arrow_down(c, x, y_from, y_to, color=colors.black):
    c.setStrokeColor(color); c.setLineWidth(0.8)
    size = 3.5
    c.line(x, y_from, x, y_to + size * 1.5)
    arrowhead(c, x, y_to, "down")
    c.setStrokeColor(colors.black)

def draw_arrow_right(c, x_from, x_to, y, color=colors.black, label="", label_color=colors.black):
    c.setStrokeColor(color); c.setLineWidth(0.8)
    size = 3.5
    c.line(x_from, y, x_to - size * 1.5, y)
    arrowhead(c, x_to, y, "right")
    if label:
        mid_x = (x_from + x_to) / 2
        c.setFont("Helvetica-Bold", 6); c.setFillColor(label_color)
        c.drawCentredString(mid_x, y + 2.5, label)
    c.setStrokeColor(colors.black); c.setFillColor(colors.black)

def draw_elbow_arrow(c, sx, sy, ex, ey, color=colors.black, label="", label_color=colors.black):
    c.setStrokeColor(color); c.setLineWidth(0.8)
    size = 3.5
    c.line(sx, sy, ex, sy)
    if ey < sy:
        c.line(ex, sy, ex, ey + size * 1.5)
        arrowhead(c, ex, ey, "down")
    else:
        c.line(ex, sy, ex, ey - size * 1.5)
        arrowhead(c, ex, ey, "up")
    if label:
        c.setFont("Helvetica-Bold", 6); c.setFillColor(label_color)
        lx = (sx + ex) / 2
        c.drawCentredString(lx, sy + 2.5, label)
    c.setStrokeColor(colors.black); c.setFillColor(colors.black)

# ─── Shape Drawing ────────────────────────────────────────────────────────────
def draw_rect_shape(c, x, y, w, h, text, font_size=7):
    c.setStrokeColor(colors.black); c.setFillColor(colors.white); c.setLineWidth(0.8)
    c.rect(x, y, w, h, fill=1, stroke=1)
    draw_centered_text(c, text, x + w/2, y + h/2, w - 4, font_size=font_size)

def draw_oval_shape(c, x, y, w, h, text, font_size=7):
    c.setStrokeColor(colors.black); c.setFillColor(colors.HexColor("#2c2c2c")); c.setLineWidth(0.8)
    c.ellipse(x, y, x + w, y + h, fill=1, stroke=1)
    draw_centered_text(c, text, x + w/2, y + h/2, w - 6, font_size=font_size, color=colors.white)

def draw_diamond_shape(c, x, y, w, h, text, font_size=6.5):
    cx, cy = x + w/2, y + h/2
    p = c.beginPath()
    p.moveTo(cx, y + h); p.lineTo(x + w, cy); p.lineTo(cx, y); p.lineTo(x, cy)
    p.close()
    c.setStrokeColor(colors.black); c.setFillColor(colors.white); c.setLineWidth(0.8)
    c.drawPath(p, fill=1, stroke=1)
    draw_centered_text(c, text, cx, cy, w * 0.55, font_size=font_size)

def draw_parallelogram_shape(c, x, y, w, h, text, font_size=7):
    skew = 7
    p = c.beginPath()
    p.moveTo(x + skew, y + h); p.lineTo(x + w, y + h)
    p.lineTo(x + w - skew, y); p.lineTo(x, y)
    p.close()
    c.setStrokeColor(colors.black); c.setFillColor(colors.white); c.setLineWidth(0.8)
    c.drawPath(p, fill=1, stroke=1)
    draw_centered_text(c, text, x + w/2, y + h/2, w - 10, font_size=font_size)

# ─── Table Structure ──────────────────────────────────────────────────────────
def draw_table_structure(c, XS, FLOW_COL_IDX, table_top, table_bottom, row_bottoms):
    ML_x    = XS[0]
    total_w = XS[-1] - XS[0]
    total_h = table_top - table_bottom
    c.setFillColor(colors.white)
    c.rect(ML_x, table_bottom, total_w, total_h, fill=1, stroke=0)
    c.setStrokeColor(colors.black); c.setLineWidth(0.8)
    c.rect(ML_x, table_bottom, total_w, total_h, fill=0, stroke=1)
    c.setLineWidth(0.5)
    for x in XS[1:-1]:
        c.line(x, table_bottom, x, table_top)
    c.setLineWidth(0.4)
    for row_bottom in row_bottoms[:-1]:
        y = row_bottom
        if FLOW_COL_IDX > 0:
            c.line(XS[0], y, XS[FLOW_COL_IDX], y)
        if FLOW_COL_IDX < len(XS) - 2:
            c.line(XS[FLOW_COL_IDX + 1], y, XS[-1], y)

# ─── Main PDF Generator ───────────────────────────────────────────────────────
def generate_pdf(steps, meta):
    buf = io.BytesIO()
    PW, PH = landscape(A4)
    c  = canvas.Canvas(buf, pagesize=(PW, PH))

    ML = 14 * mm; MR = 14 * mm; MT = 12 * mm
    TW = PW - ML - MR
    cur_y = PH - MT

    # Header
    HEADER_H = 22 * mm
    left_w   = 44 * mm; right_w = 83 * mm
    centre_w = TW - left_w - right_w

    c.setFont("Helvetica-Bold", 11); c.setFillColor(colors.black)
    c.drawString(ML, cur_y - 7, meta["company_name"])
    c.setFont("Helvetica-Bold", 10); c.setFillColor(colors.HexColor("#1a6dcc"))
    c.drawString(ML, cur_y - 18, "eka"); c.setFillColor(colors.black)

    cx_title = ML + left_w + centre_w / 2
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(cx_title, cur_y - 7, "STANDARD OPERATING PROCEDURE")
    c.setFont("Helvetica", 8.5)
    draw_centered_text(c, meta["title"], cx_title, cur_y - 18, centre_w - 4, font_size=8.5)

    RX = ML + left_w + centre_w
    c1w, c2w, c3w = 18*mm, 24*mm, 12*mm
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
            c.setStrokeColor(colors.black); c.setLineWidth(0.5)
            c.rect(rxs[ci], ry, cw, rh, fill=1, stroke=1)
            c.setFillColor(colors.black)
            fn = "Helvetica-Bold" if is_lbl else "Helvetica"
            fs = 5.8 if is_lbl else 6.2
            draw_left_text(c, txt, rxs[ci]+1.5, ry+rh/2, cw-3, fn, fs)

    c.setLineWidth(1)
    c.line(ML, cur_y - HEADER_H, ML + TW, cur_y - HEADER_H)
    cur_y -= HEADER_H

    # Purpose / Scope
    PS_H = 8 * mm
    PL_W, PV_W, SL_W = 18*mm, 82*mm, 14*mm
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

    # Column layout
    COL_IN   = 25 * mm; COL_OUT  = 22 * mm; COL_RESP = 28 * mm
    COL_DOC  = 24 * mm; COL_MEAS = 26 * mm
    COL_FLOW = TW - COL_IN - COL_OUT - COL_RESP - COL_DOC - COL_MEAS
    FLOW_COL_IDX = 1

    XS = [
        ML, ML + COL_IN, ML + COL_IN + COL_FLOW,
        ML + COL_IN + COL_FLOW + COL_OUT,
        ML + COL_IN + COL_FLOW + COL_OUT + COL_RESP,
        ML + COL_IN + COL_FLOW + COL_OUT + COL_RESP + COL_DOC,
        ML + TW,
    ]
    FLOW_L = XS[1]; FLOW_R = XS[2]
    SH_W_L   = COL_FLOW * 0.44 - 2*mm
    SH_W_R   = COL_FLOW * 0.44 - 2*mm
    LEFT_CX  = FLOW_L + COL_FLOW * 0.25
    RIGHT_CX = FLOW_L + COL_FLOW * 0.75

    HDR1_H = 7 * mm
    c.setFillColor(colors.HexColor("#DDEEFF"))
    c.rect(ML, cur_y - HDR1_H, TW, HDR1_H, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 9); c.setFillColor(colors.black)
    c.drawString(ML + 3, cur_y - HDR1_H + 2.5, "Process Steps:")
    c.drawString(XS[3] + 3, cur_y - HDR1_H + 2.5, f"OWNER :   {meta['owner']}")
    cur_y -= HDR1_H

    HDR2_H = 7 * mm
    col_labels = ["Input", "Process Flow", "Output", "Responsible",
                  "Doc. Format /\nSystem", "Effective\nMeasurement"]
    for i, label in enumerate(col_labels):
        cw = XS[i+1] - XS[i]
        c.setFillColor(colors.HexColor("#EEF3FF"))
        c.rect(XS[i], cur_y - HDR2_H, cw, HDR2_H, fill=1, stroke=1)
        c.setFillColor(colors.black)
        lines = label.split("\n")
        lh = 6.5; sy = cur_y - HDR2_H/2 + (len(lines)-1)*lh/2
        for li, ln in enumerate(lines):
            c.setFont("Helvetica-Bold", 6.5)
            c.drawCentredString(XS[i]+cw/2, sy - li*(lh+0.5), ln)
    cur_y -= HDR2_H

    SHAPE_H = {
        "rect": 9*mm, "oval": 9*mm, "parallelogram": 9*mm,
        "diamond": 15*mm, "arrow_text": 6*mm,
    }
    V_PAD = 5 * mm; table_top = cur_y

    # Pair rows
    paired_rows = []; step_to_pair = {}
    for idx, step in enumerate(steps):
        col = step.get("column", "left")
        if col == "right":
            paired = False
            for pi in range(len(paired_rows) - 1, -1, -1):
                if paired_rows[pi]["right"] is None:
                    paired_rows[pi]["right"] = idx
                    step_to_pair[idx] = pi; paired = True; break
            if not paired:
                paired_rows.append({"left": None, "right": idx})
                step_to_pair[idx] = len(paired_rows) - 1
        else:
            paired_rows.append({"left": idx, "right": None})
            step_to_pair[idx] = len(paired_rows) - 1

    row_geom = []; scan_y = cur_y
    for pair in paired_rows:
        h_left  = SHAPE_H.get(steps[pair["left"]]["shape"],  9*mm) if pair["left"]  is not None else 0
        h_right = SHAPE_H.get(steps[pair["right"]]["shape"], 9*mm) if pair["right"] is not None else 0
        ROW_H = max(h_left, h_right) + 2 * V_PAD
        ry = scan_y - ROW_H
        row_geom.append({"ry": ry, "ROW_H": ROW_H}); scan_y = ry
    table_bottom = scan_y

    row_bottoms = [rg["ry"] for rg in row_geom]
    draw_table_structure(c, XS, FLOW_COL_IDX, table_top, table_bottom, row_bottoms)

    for pi, pair in enumerate(paired_rows):
        rg = row_geom[pi]; ry, ROW_H = rg["ry"], rg["ROW_H"]
        ref_idx = pair["left"] if pair["left"] is not None else pair["right"]
        step = steps[ref_idx]
        for col_i, key in [(0,"input_label"),(2,"output_label"),(3,"responsible"),(4,"doc_format"),(5,"measurement")]:
            txt = step.get(key,"")
            if txt:
                cw = XS[col_i+1] - XS[col_i]
                draw_centered_text(c, txt, XS[col_i]+cw/2, ry+ROW_H/2, cw-4, font_size=6.5)

    anchors = {}
    for idx, step in enumerate(steps):
        pi = step_to_pair[idx]; rg = row_geom[pi]
        ry, ROW_H = rg["ry"], rg["ROW_H"]
        col = step.get("column", "left"); sh_h = SHAPE_H.get(step["shape"], 9*mm)
        if col == "right":
            cx = RIGHT_CX; sh_w = SH_W_R
        else:
            cx = LEFT_CX; sh_w = SH_W_L
        sh_x = cx - sh_w / 2; sh_bot = ry + V_PAD; sh_top = sh_bot + sh_h; sh_mid = sh_bot + sh_h / 2
        anchors[idx] = {"cx": cx, "cy": sh_mid, "top": sh_top, "bot": sh_bot,
                        "left": sh_x, "right": sh_x + sh_w,
                        "sh_x": sh_x, "sh_w": sh_w, "sh_h": sh_h, "sh_bot": sh_bot, "col": col}

    GREEN = colors.HexColor("#006600"); RED = colors.HexColor("#CC0000"); BLUE = colors.HexColor("#1a6dcc")

    for idx, step in enumerate(steps):
        a = anchors[idx]; col = a["col"]
        connect_from = step.get("connect_from", "")
        arrow_label  = step.get("arrow_label", "").strip()
        connect_side = step.get("connect_side", "bottom (default)")
        lbl_lower    = arrow_label.upper()
        arr_color = GREEN if lbl_lower == "YES" else (RED if lbl_lower == "NO" else colors.black)
        lbl_color = arr_color

        if connect_from != "" and str(connect_from).isdigit():
            src_idx = int(connect_from)
            if 0 <= src_idx < len(anchors):
                s = anchors[src_idx]
                if connect_side == "right side →":
                    sx, sy = s["right"], s["cy"]
                    draw_elbow_arrow(c, sx, sy, a["cx"], a["top"], color=arr_color, label=arrow_label, label_color=lbl_color)
                elif connect_side == "left side ←":
                    sx, sy = s["left"], s["cy"]
                    draw_elbow_arrow(c, sx, sy, a["cx"], a["top"], color=arr_color, label=arrow_label, label_color=lbl_color)
                else:
                    sx, sy = s["cx"], s["bot"]
                    if abs(sx - a["cx"]) < 2:
                        draw_arrow_down(c, a["cx"], sy, a["top"], color=arr_color)
                        if arrow_label:
                            c.setFont("Helvetica-Bold", 6); c.setFillColor(lbl_color)
                            c.drawCentredString(a["cx"] + 6, (sy + a["top"])/2, arrow_label)
                            c.setFillColor(colors.black)
                    else:
                        draw_elbow_arrow(c, sx, sy, a["cx"], a["top"], color=arr_color, label=arrow_label, label_color=lbl_color)
        else:
            if idx > 0:
                prev_same = None
                for pi in range(idx - 1, -1, -1):
                    if anchors[pi]["col"] == col: prev_same = pi; break
                if prev_same is not None:
                    ps = anchors[prev_same]
                    draw_arrow_down(c, a["cx"], ps["bot"], a["top"])

        loop_to = step.get("loop_to", ""); loop_label = step.get("loop_label", "").strip()
        if loop_to != "" and str(loop_to).isdigit():
            lt_idx = int(loop_to)
            if 0 <= lt_idx < len(anchors):
                dest = anchors[lt_idx]
                ll_color = GREEN if loop_label.upper() == "YES" else (RED if loop_label.upper() == "NO" else BLUE)
                margin = FLOW_L - 5 * mm
                c.setStrokeColor(ll_color); c.setLineWidth(0.8)
                start_x = a["sh_x"]; start_y = a["cy"]
                dest_x  = dest["left"]; dest_y  = dest["cy"]
                c.line(start_x, start_y, margin, start_y)
                c.line(margin, start_y, margin, dest_y)
                size = 3.5
                c.line(margin, dest_y, dest_x - size*1.5, dest_y)
                arrowhead(c, dest_x, dest_y, "right")
                if loop_label:
                    c.setFont("Helvetica-Bold", 6); c.setFillColor(ll_color)
                    c.drawString(margin + 2, (start_y + dest_y)/2 + 2, loop_label)
                    c.setFillColor(colors.black)
                c.setStrokeColor(colors.black)

    for idx, step in enumerate(steps):
        a = anchors[idx]; sh_x, sh_bot = a["sh_x"], a["sh_bot"]
        sh_w, sh_h = a["sh_w"], a["sh_h"]; shape = step["shape"]
        if shape == "rect":
            draw_rect_shape(c, sh_x, sh_bot, sh_w, sh_h, step["text"])
        elif shape == "oval":
            draw_oval_shape(c, sh_x, sh_bot, sh_w, sh_h, step["text"])
        elif shape == "diamond":
            draw_diamond_shape(c, sh_x, sh_bot, sh_w, sh_h, step["text"])
            yes_lbl = step.get("yes_label", "YES") or "YES"; no_lbl = step.get("no_label", "NO") or "NO"
            c.setFont("Helvetica-Bold", 6.5); c.setFillColor(GREEN)
            c.drawString(sh_x + sh_w + 3, a["cy"] - 3, f"{yes_lbl} →")
            no_w = c.stringWidth(f"← {no_lbl}", "Helvetica-Bold", 6.5)
            c.setFillColor(RED); c.drawString(sh_x - no_w - 3, a["cy"] - 3, f"← {no_lbl}")
            c.setFillColor(colors.black)
        elif shape == "parallelogram":
            draw_parallelogram_shape(c, sh_x, sh_bot, sh_w, sh_h, step["text"])
        elif shape == "arrow_text":
            c.setFont("Helvetica-Oblique", 7); c.setFillColor(colors.HexColor("#333333"))
            c.drawCentredString(a["cx"], a["cy"], step["text"]); c.setFillColor(colors.black)

    cur_y = table_bottom

    # Change record
    cur_y -= 4 * mm
    CR_TITLE_H = 6 * mm
    c.setFillColor(colors.HexColor("#DDEEFF"))
    c.rect(ML, cur_y - CR_TITLE_H, TW, CR_TITLE_H, fill=1, stroke=1)
    c.setFont("Helvetica-Bold", 8); c.setFillColor(colors.black)
    c.drawCentredString(ML + TW/2, cur_y - CR_TITLE_H + 2, "SOP Change Record")
    cur_y -= CR_TITLE_H

    CR_COLS   = ["S.No.", "Effective\nDate", "REV.\nNo.", "Change Description",
                 "Change Letter\n(Process:P / Doc:D / System:S)",
                 "Prepared By", "Reviewed By", "Approved By"]
    CR_WIDTHS = [10*mm, 20*mm, 14*mm, 52*mm, 46*mm, 22*mm, 22*mm, 0]
    CR_WIDTHS[-1] = TW - sum(CR_WIDTHS[:-1])
    CR_XS = [ML]
    for w in CR_WIDTHS: CR_XS.append(CR_XS[-1] + w)

    CR_HDR_H = 8 * mm
    for i, label in enumerate(CR_COLS):
        cw = CR_XS[i+1] - CR_XS[i]
        c.setFillColor(colors.HexColor("#EEF3FF"))
        c.rect(CR_XS[i], cur_y - CR_HDR_H, cw, CR_HDR_H, fill=1, stroke=1)
        c.setFillColor(colors.black)
        lines = label.split("\n"); lh = 6; sy = cur_y - CR_HDR_H/2 + (len(lines)-1)*lh/2
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

    c.setFont("Helvetica-Oblique", 6); c.setFillColor(colors.HexColor("#555555"))
    c.drawCentredString(ML + TW/2, cur_y - 5, f"Composed By: {meta['composed_by']}")
    c.save(); buf.seek(0)
    return buf


# ─── Streamlit UI ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .block-container { padding-top: 1rem; }
    h1 { font-size: 1.35rem; margin-bottom: 0.2rem; }
    h2 { font-size: 1.05rem; }
    .stButton > button { width: 100%; }
    .preview-label {
        font-size: 0.75rem; font-weight: 600; color: #4A5568;
        text-transform: uppercase; letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
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

    # ── Split layout: left = form, right = preview ──────────────────────────
    form_col, preview_col = st.columns([1, 1], gap="large")

    with form_col:
        with st.expander("📖 How to build branching flows — read this first", expanded=False):
            st.markdown("""
**Two columns are available:** `left` (main flow) and `right` (branch).

| Field | What it does |
|---|---|
| **Column** | Which column this shape lives in |
| **Connect from step #** | Arrow comes from that step (1-based). Blank = auto |
| **Arrow exits from** | Which side of source shape the arrow leaves |
| **Arrow label** | Text on arrow (e.g. `YES`, `NO`) |
| **Loop-back to step #** | Draws loop arrow back to an earlier step |

**Quick recipe:**
```
Step 1  left   oval      "Start"
Step 2  left   rect      "Step A"
Step 3  left   diamond   "Decision?"
Step 4  right  rect      "Branch" — from:3, exits: right side →, label: YES
Step 5  left   rect      "Continue" — from:3, label: NO
```
            """)

        st.subheader("Add a Process Step")
        n_steps = len(st.session_state.steps)

        with st.form("add_step_form", clear_on_submit=True):
            fa, fb = st.columns([2, 3])
            with fa:
                shape_label = st.selectbox("Shape Type", list(SHAPE_TYPES.keys()))
                col_choice  = st.selectbox("Column (left = main flow)", COLUMN_OPTIONS)
            with fb:
                step_text   = st.text_input("Text inside shape *")

            st.markdown("**Side-column data (optional)**")
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                input_label  = st.text_input("Input Label")
                output_label = st.text_input("Output Label")
            with sc2:
                responsible  = st.text_input("Responsible")
                doc_format   = st.text_input("Doc. Format / System")
            with sc3:
                measurement  = st.text_input("Effective Measurement")
                yes_label    = st.text_input("YES label (diamonds)", value="YES")
                no_label     = st.text_input("NO label (diamonds)",  value="NO")

            st.markdown("**Arrow / Connection settings**")
            ar1, ar2, ar3 = st.columns(3)
            with ar1:
                connect_from = st.text_input("Connect from step # (blank = auto)")
                connect_side = st.selectbox("Arrow exits source from", CONNECT_SIDE_OPTIONS)
            with ar2:
                arrow_label = st.text_input("Arrow label (e.g. YES / NO / blank)")
            with ar3:
                loop_to    = st.text_input("Loop-back to step # (blank = none)")
                loop_label = st.text_input("Loop arrow label")

            if st.form_submit_button("➕ Add Step", use_container_width=True):
                if step_text.strip():
                    cf = str(int(connect_from.strip()) - 1) if connect_from.strip().isdigit() else ""
                    lt = str(int(loop_to.strip()) - 1) if loop_to.strip().isdigit() else ""
                    st.session_state.steps.append({
                        "shape":        SHAPE_TYPES[shape_label],
                        "text":         step_text,
                        "column":       col_choice,
                        "input_label":  input_label,
                        "output_label": output_label,
                        "responsible":  responsible,
                        "doc_format":   doc_format,
                        "measurement":  measurement,
                        "yes_label":    yes_label,
                        "no_label":     no_label,
                        "connect_from": cf,
                        "connect_side": connect_side,
                        "arrow_label":  arrow_label,
                        "loop_to":      lt,
                        "loop_label":   loop_label,
                    })
                    st.success(f"✅ Step {n_steps+1} added: [{shape_label}] {step_text}")
                    st.rerun()
                else:
                    st.warning("Please enter shape text.")

        st.divider()
        st.subheader(f"Steps ({len(st.session_state.steps)})")
        if not st.session_state.steps:
            st.info("No steps yet. Use the form above to add process flow steps.")
        else:
            reverse_map = {v: k for k, v in SHAPE_TYPES.items()}
            for i, step in enumerate(st.session_state.steps):
                label   = reverse_map.get(step["shape"], step["shape"])
                col_tag = "🔵 left" if step.get("column","left") == "left" else "🟢 right"
                cf_raw  = step.get("connect_from","")
                cf_disp = str(int(cf_raw)+1) if cf_raw.isdigit() else "auto"
                lt_raw  = step.get("loop_to","")
                lt_disp = str(int(lt_raw)+1) if lt_raw.isdigit() else "—"
                with st.expander(f"**Step {i+1}** {col_tag} › [{label}]  {step['text']}", expanded=False):
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
                    st.write(f"**Connect from:** step {cf_disp}  |  "
                             f"**Side:** {step.get('connect_side','bottom')}  |  "
                             f"**Arrow label:** {step.get('arrow_label') or '—'}  |  "
                             f"**Loop to:** {lt_disp}")

    # ── RIGHT: Live Preview ──────────────────────────────────────────────────
    with preview_col:
        st.subheader("👁️ Live Flowchart Preview")
        st.caption("Updates automatically as you add/reorder/delete steps.")

        preview_html = render_preview_html(st.session_state.steps)

        # Calculate a good height for the iframe
        n = len(st.session_state.steps)
        # rough estimate: 88px per step + toolbar + headers + padding
        est_h = max(320, min(900, n * 88 + 150)) if n > 0 else 260

        components.html(preview_html, height=est_h, scrolling=False)

        if st.session_state.steps:
            st.markdown("---")
            st.markdown("**Shape colour guide:**")
            guide_cols = st.columns(4)
            guide_items = [
                ("🟦", "Rectangle", "Process step"),
                ("⬛", "Oval", "Start / End"),
                ("🟨", "Diamond", "Decision"),
                ("🟩", "Parallelogram", "Input / Output"),
            ]
            for gc, (icon, name, desc) in zip(guide_cols, guide_items):
                gc.markdown(f"{icon} **{name}**  \n{desc}")


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
            data=pdf_buf, file_name="SOP_Document.pdf",
            mime="application/pdf", use_container_width=True,
        )
        st.divider()
        st.subheader("Step Summary")
        reverse_map = {v: k for k, v in SHAPE_TYPES.items()}
        rows = [{
            "Step":         i + 1,
            "Col":          s.get("column","left"),
            "Shape":        reverse_map.get(s["shape"], s["shape"]),
            "Text":         s["text"],
            "Connect from": str(int(s.get("connect_from",""))+1) if s.get("connect_from","").isdigit() else "auto",
            "Arrow label":  s.get("arrow_label",""),
            "Loop to":      str(int(s.get("loop_to",""))+1) if s.get("loop_to","").isdigit() else "—",
        } for i, s in enumerate(st.session_state.steps)]
        st.dataframe(rows, use_container_width=True, hide_index=True)
