import streamlit as st

st.set_page_config(
    page_title="Line Supply SOP - Direct Supply",
    page_icon="🏭",
    layout="wide"
)

# ── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap');

  html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }

  /* Header banner */
  .sop-header {
    background: linear-gradient(135deg, #004080 0%, #0066cc 100%);
    color: white;
    padding: 14px 24px;
    border-radius: 8px;
    margin-bottom: 18px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .sop-header .title { font-size: 20px; font-weight: 700; }
  .sop-header .subtitle { font-size: 12px; opacity: 0.85; margin-top: 3px; }
  .sop-header .meta { text-align: right; font-size: 11px; opacity: 0.85; }

  /* Step cards */
  .step-card {
    background: white;
    border: 1px solid #d0dce8;
    border-left: 5px solid #0066cc;
    border-radius: 6px;
    padding: 12px 16px;
    margin: 6px 0;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
    font-size: 13px;
    color: #1a1a2e;
  }
  .step-card.completed {
    border-left-color: #28a745;
    background: #f0fff4;
  }
  .step-card.active {
    border-left-color: #fd7e14;
    background: #fff8f0;
    box-shadow: 0 2px 8px rgba(253,126,20,0.2);
  }
  .step-card.decision {
    border-left-color: #6f42c1;
    background: #f8f5ff;
  }

  /* Decision badge */
  .badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    margin-left: 8px;
  }
  .badge-yes { background: #d4edda; color: #155724; }
  .badge-no  { background: #f8d7da; color: #721c24; }

  /* Arrow */
  .arrow { text-align: center; color: #aaa; font-size: 18px; line-height: 1.2; }

  /* Summary table */
  .info-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .info-table th {
    background: #004080; color: white;
    padding: 6px 10px; text-align: left;
  }
  .info-table td { padding: 6px 10px; border-bottom: 1px solid #e0e0e0; }
  .info-table tr:nth-child(even) td { background: #f5f8fc; }

  /* Coverage metric */
  .metric-box {
    background: #004080; color: white;
    border-radius: 8px; padding: 14px 18px;
    text-align: center;
  }
  .metric-box .val { font-size: 28px; font-weight: 700; }
  .metric-box .lbl { font-size: 11px; opacity: 0.8; margin-top: 3px; }

  /* Status pill */
  .status-pill {
    display: inline-block;
    padding: 3px 12px; border-radius: 20px;
    font-size: 11px; font-weight: 600;
  }
  .pill-green  { background: #d4edda; color: #155724; }
  .pill-orange { background: #fff3cd; color: #856404; }
  .pill-red    { background: #f8d7da; color: #721c24; }

  div[data-testid="stRadio"] label { font-size: 13px; }
  .stButton > button {
    border-radius: 6px; font-size: 13px;
    background: #0066cc; color: white; border: none;
    padding: 6px 18px;
  }
  .stButton > button:hover { background: #004fa3; }
</style>
""", unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="sop-header">
  <div>
    <div class="title">🏭 PINNACLE MOBILITY &nbsp;|&nbsp; eka</div>
    <div class="subtitle">Standard Operating Procedure — Direct Supply of Parts from Stores to Assy Line</div>
  </div>
  <div class="meta">
    SOP No: SCM/STR/LS/02 &nbsp;|&nbsp; Rev: 0.0<br>
    Unit: Chakan Plant &nbsp;|&nbsp; Area: Stores<br>
    Sub Area: Line Side &nbsp;|&nbsp; Zone: DIRECT LOCATIONS
  </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar: Run Mode ─────────────────────────────────────────────────────────
st.sidebar.title("⚙️ SOP Controls")
mode = st.sidebar.radio("Select Mode", ["📋 View Full SOP", "▶️ Step-by-Step Walkthrough", "📊 Coverage Dashboard"])
st.sidebar.markdown("---")
st.sidebar.markdown("**Purpose:** Supply of Supplier Packs to Line Side")
st.sidebar.markdown("**Scope:** All Parts under direct supply category (suggested by quality/operation)")
st.sidebar.markdown("**Owner:** Stores Manager")

# ═══════════════════════════════════════════════════════════════════════════
# MODE 1: Full SOP View
# ═══════════════════════════════════════════════════════════════════════════
if mode == "📋 View Full SOP":
    st.subheader("Process Flow — Line Supply SOP")

    steps = [
        ("🔵", "START", "Production lay sequence for N+1 day", "trigger", None),
        ("📋", "Step 1", "Verify line side stock & Update Direct Coverage Sheet", "process", "Line Supervisor"),
        ("📋", "Step 2", "Check material coverage w.r.t. N (today) day plan", "process", "Line Supervisor"),
        ("🔷", "Decision 1", "Is Part available for N day?", "decision", "Line Supervisor"),
        ("✅", "YES Path", "Check material coverage w.r.t. N+1 (tomorrow) day plan", "process", "Line Supervisor"),
        ("🔷", "Decision 2", "Is Part available for N+1 day?", "decision", "Line Supervisor"),
        ("📋", "Step 3", "Check the part availability in Loaded Trolley Area", "process", "Line Supervisor"),
        ("🔷", "Decision 3", "Is available in Loaded Trolley Area?", "decision", "Line Supervisor"),
        ("🅰️", "YES Path (A)", "Move Loaded Trolley to Direct Part Location & Update Bincard of Loaded Trolley Area & Direct coverage sheet", "process", "Line Supervisor"),
        ("🅱️", "NO Path (B)", "Inform Responsible person & seek for readiness confirmation", "process", "Line Supervisor"),
        ("🔷", "Decision 4", "Any more shortfall as per?", "decision", "Line Supervisor"),
        ("🔴", "END", "Process Complete — No more shortfall", "end", None),
    ]

    col1, col2 = st.columns([2, 1])

    with col1:
        for icon, label, desc, stype, resp in steps:
            card_class = "decision" if stype == "decision" else ("step-card" if stype == "process" else "step-card")
            resp_html = f'<span style="float:right;font-size:11px;color:#666;">👤 {resp}</span>' if resp else ""
            st.markdown(f"""
            <div class="step-card {'decision' if stype=='decision' else ''}">
              {resp_html}
              <strong>{icon} {label}</strong><br>
              <span style="color:#333;">{desc}</span>
            </div>
            """, unsafe_allow_html=True)
            if stype != "end":
                st.markdown('<div class="arrow">↓</div>', unsafe_allow_html=True)

    with col2:
        st.markdown("#### 📌 Key Info")
        st.markdown("""
        <table class="info-table">
          <tr><th>Field</th><th>Value</th></tr>
          <tr><td>SOP No.</td><td>SCM/STR/LS/02</td></tr>
          <tr><td>Rev No.</td><td>0.0</td></tr>
          <tr><td>Date</td><td>26-12-2024</td></tr>
          <tr><td>Unit</td><td>Chakan Plant</td></tr>
          <tr><td>Area</td><td>Stores</td></tr>
          <tr><td>Sub Area</td><td>Line Side</td></tr>
          <tr><td>Zone</td><td>Direct Locations</td></tr>
          <tr><td>Owner</td><td>Stores Manager</td></tr>
        </table>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div class="metric-box">
          <div class="val">100%</div>
          <div class="lbl">MTRL Coverage (N+1) Target</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>**📝 Change Record**", unsafe_allow_html=True)
        st.markdown("""
        <table class="info-table">
          <tr><th>Rev</th><th>Date</th><th>Description</th></tr>
          <tr><td>0.0</td><td>17-12-2024</td><td>Original Version</td></tr>
        </table>
        """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# MODE 2: Step-by-Step Walkthrough
# ═══════════════════════════════════════════════════════════════════════════
elif mode == "▶️ Step-by-Step Walkthrough":
    st.subheader("▶️ Interactive Process Walkthrough")
    st.info("Answer each question to walk through the SOP process flow and get guided next steps.")

    if "step" not in st.session_state:
        st.session_state.step = 0
        st.session_state.log = []

    def go(next_step, log_msg):
        st.session_state.log.append(log_msg)
        st.session_state.step = next_step

    def reset():
        st.session_state.step = 0
        st.session_state.log = []

    step = st.session_state.step

    # Show log
    if st.session_state.log:
        with st.expander("📜 Steps completed so far", expanded=True):
            for i, entry in enumerate(st.session_state.log, 1):
                st.markdown(f"**{i}.** {entry}")
        st.markdown("---")

    # ── Flow Steps ──
    if step == 0:
        st.markdown('<div class="step-card active"><strong>🔵 START</strong><br>Production lay sequence for N+1 day is ready.</div>', unsafe_allow_html=True)
        if st.button("▶️ Begin Process"):
            go(1, "✅ Started — Production lay sequence for N+1 day noted.")

    elif step == 1:
        st.markdown('<div class="step-card active"><strong>📋 Step 1 — Line Supervisor</strong><br>Verify line side stock & Update Direct Coverage Sheet</div>', unsafe_allow_html=True)
        if st.button("✅ Done — Coverage Sheet Updated"):
            go(2, "✅ Line side stock verified & Direct Coverage Sheet updated.")

    elif step == 2:
        st.markdown('<div class="step-card active"><strong>📋 Step 2 — Line Supervisor</strong><br>Check material coverage w.r.t. N (today) day plan</div>', unsafe_allow_html=True)
        if st.button("✅ Done — Material Coverage Checked for Today"):
            go(3, "✅ Material coverage checked against today's (N) day plan.")

    elif step == 3:
        st.markdown('<div class="step-card decision"><strong>🔷 Decision 1 — Is Part available for N day?</strong></div>', unsafe_allow_html=True)
        ans = st.radio("Is the part available for N (today) day?", ["YES", "NO"], key="d1")
        if st.button("Confirm"):
            if ans == "YES":
                go(4, "✅ Part IS available for N day → Checking N+1 coverage.")
            else:
                go(6, "❌ Part NOT available for N day → Checking Loaded Trolley Area.")

    elif step == 4:
        st.markdown('<div class="step-card active"><strong>📋 YES Path — Line Supervisor</strong><br>Check material coverage w.r.t. N+1 (tomorrow) day plan</div>', unsafe_allow_html=True)
        if st.button("✅ Done — N+1 Coverage Checked"):
            go(5, "✅ Material coverage checked against N+1 (tomorrow) day plan.")

    elif step == 5:
        st.markdown('<div class="step-card decision"><strong>🔷 Decision 2 — Is Part available for N+1 day?</strong></div>', unsafe_allow_html=True)
        ans = st.radio("Is the part available for N+1 (tomorrow) day?", ["YES", "NO"], key="d2")
        if st.button("Confirm"):
            if ans == "YES":
                go(10, "✅ Part IS available for N+1 → No shortfall. Checking final.")
            else:
                go(6, "❌ Part NOT available for N+1 → Checking Loaded Trolley Area.")

    elif step == 6:
        st.markdown('<div class="step-card active"><strong>📋 Step 3 — Line Supervisor</strong><br>Check the part availability in Loaded Trolley Area</div>', unsafe_allow_html=True)
        if st.button("✅ Done — Loaded Trolley Area Checked"):
            go(7, "✅ Part availability in Loaded Trolley Area checked.")

    elif step == 7:
        st.markdown('<div class="step-card decision"><strong>🔷 Decision 3 — Is part available in Loaded Trolley Area?</strong></div>', unsafe_allow_html=True)
        ans = st.radio("Is the part available in Loaded Trolley Area?", ["YES", "NO"], key="d3")
        if st.button("Confirm"):
            if ans == "YES":
                go(8, "✅ Part IS in Loaded Trolley → Moving trolley & updating records (Path A).")
            else:
                go(9, "❌ Part NOT in Loaded Trolley → Informing responsible person (Path B).")

    elif step == 8:
        st.markdown('<div class="step-card active"><strong>🅰️ Path A — Line Supervisor</strong><br>Move Loaded Trolley to Direct Part Location & Update Bincard of Loaded Trolley Area & Direct coverage sheet</div>', unsafe_allow_html=True)
        if st.button("✅ Done — Trolley Moved & Bincard Updated"):
            go(10, "✅ Path A: Trolley moved, Bincard and Direct Coverage Sheet updated.")

    elif step == 9:
        st.markdown('<div class="step-card active"><strong>🅱️ Path B — Line Supervisor</strong><br>Inform Responsible person & seek for readiness confirmation</div>', unsafe_allow_html=True)
        if st.button("✅ Done — Person Informed & Confirmation Sought"):
            go(10, "✅ Path B: Responsible person informed, awaiting readiness confirmation.")

    elif step == 10:
        st.markdown('<div class="step-card decision"><strong>🔷 Decision 4 — Any more shortfall?</strong></div>', unsafe_allow_html=True)
        ans = st.radio("Is there any more shortfall as per coverage sheet?", ["YES — Loop back", "NO — Complete"], key="d4")
        if st.button("Confirm"):
            if ans == "YES — Loop back":
                go(6, "🔁 Shortfall exists → Looping back to check Loaded Trolley Area again.")
            else:
                go(11, "✅ No more shortfall. Process complete.")

    elif step == 11:
        st.success("🎉 **Process Complete!** No more shortfall detected. Line supply SOP executed successfully.")
        st.markdown('<div class="step-card completed"><strong>🔴 END — Process Complete</strong><br>All parts have been supplied to the line side. Coverage sheet is up to date.</div>', unsafe_allow_html=True)

    st.markdown("---")
    if st.button("🔄 Restart Walkthrough"):
        reset()
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# MODE 3: Coverage Dashboard
# ═══════════════════════════════════════════════════════════════════════════
elif mode == "📊 Coverage Dashboard":
    st.subheader("📊 Coverage Dashboard — MTRL Tracking")

    import datetime
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        coverage = st.number_input("MTRL Coverage N+1 (%)", min_value=0, max_value=100, value=85)
    with col2:
        total_parts = st.number_input("Total Parts (Direct Supply)", min_value=1, value=120)
    with col3:
        shortfall = st.number_input("Shortfall Count", min_value=0, value=18)
    with col4:
        date = st.date_input("Date", value=datetime.date.today())

    st.markdown("---")

    # Coverage meter
    c1, c2, c3 = st.columns(3)
    with c1:
        if coverage >= 100:
            pill = '<span class="status-pill pill-green">✅ TARGET MET</span>'
        elif coverage >= 80:
            pill = '<span class="status-pill pill-orange">⚠️ NEAR TARGET</span>'
        else:
            pill = '<span class="status-pill pill-red">❌ BELOW TARGET</span>'
        st.markdown(f"""
        <div class="metric-box">
          <div class="val">{coverage}%</div>
          <div class="lbl">MTRL Coverage (N+1)</div>
          <div style="margin-top:6px;">{pill}</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        available = total_parts - shortfall
        st.markdown(f"""
        <div class="metric-box" style="background:linear-gradient(135deg,#155724,#28a745)">
          <div class="val">{available}</div>
          <div class="lbl">Parts Available</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-box" style="background:linear-gradient(135deg,#721c24,#dc3545)">
          <div class="val">{shortfall}</div>
          <div class="lbl">Shortfall Parts</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### Part-wise Coverage Entry")

    part_names = st.text_area("Enter Part Names (one per line)", value="Engine Mount\nGear Shaft\nBrake Pad\nAxle Housing\nFilter Assembly")
    parts = [p.strip() for p in part_names.strip().split("\n") if p.strip()]

    if parts:
        import random
        st.markdown('<table class="info-table"><tr><th>#</th><th>Part Name</th><th>Available (N)</th><th>Available (N+1)</th><th>Status</th></tr>', unsafe_allow_html=True)
        rows = ""
        for i, part in enumerate(parts, 1):
            n_ok = random.choice(["Yes", "Yes", "No"])
            n1_ok = random.choice(["Yes", "Yes", "No"]) if n_ok == "Yes" else "No"
            if n_ok == "Yes" and n1_ok == "Yes":
                status = '<span class="status-pill pill-green">✅ OK</span>'
            elif n_ok == "Yes":
                status = '<span class="status-pill pill-orange">⚠️ N+1 Shortfall</span>'
            else:
                status = '<span class="status-pill pill-red">❌ Shortfall</span>'
            rows += f"<tr><td>{i}</td><td>{part}</td><td>{n_ok}</td><td>{n1_ok}</td><td>{status}</td></tr>"
        st.markdown(rows + "</table>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f"<small style='color:#888;'>Composed By: Agilomatrix Pvt Ltd &nbsp;|&nbsp; SOP: SCM/STR/LS/02 &nbsp;|&nbsp; Date: {date}</small>", unsafe_allow_html=True)
