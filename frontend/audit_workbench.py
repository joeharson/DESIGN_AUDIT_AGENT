"""Streamlit UI for the Design Audit Agent."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx
import streamlit as st
import streamlit.components.v1 as components


DEFAULT_API_BASE = os.getenv("STREAMLIT_API_BASE", "http://localhost:8001")
CONFIG_PATH = Path("config/generated_scan_config.json")
SESSION_DIR = Path("output/ui_sessions")
NAV_ITEMS = [
    ("LEVEL 1", "Level 1 Audit"),
    ("LEVEL 2", "Level 2 Compare"),
    ("LEVEL 3", "Level 3 Website Scan"),
    ("Baseline", "Baselines"),
    ("History", "History"),
]


st.set_page_config(page_title="Design Audit Agent", page_icon="DA", layout="wide")
st.markdown(
    """
    <style>
      :root {
        --surface: #ffffff;
        --ink: #172026;
        --muted: #5d6872;
        --line: #e1e5e9;
        --soft: #f6f8fa;
        --teal: #0d7a75;
        --teal-hover: #0a625e;
        --amber: #8a6400;
      }
      header[data-testid="stHeader"] {
        background: transparent;
        height: 0;
      }
      div[data-testid="stToolbar"],
      div[data-testid="stDecoration"],
      div[data-testid="stStatusWidget"] {
        display: none !important;
      }
      .stApp {
        background: #fbfcfd;
        color: var(--ink);
      }
      .block-container {
        max-width: 1240px;
        padding-top: 1rem;
        padding-bottom: 3rem;
      }
      h1, h2, h3 { letter-spacing: 0; color: var(--ink); }
      h2 { font-size: 1.35rem; }
      h3 { font-size: 1.05rem; }
      label,
      [data-testid="stWidgetLabel"],
      [data-testid="stWidgetLabel"] p {
        color: #3d4852 !important;
        font-weight: 600;
      }
      div[data-testid="stButton"] > button,
      div[data-testid="stDownloadButton"] > button {
        border-radius: 6px;
        border: 1px solid #c9d1d9;
        box-shadow: none;
        font-weight: 650;
        min-height: 2.55rem;
        background: #ffffff !important;
        color: var(--ink) !important;
      }
      div[data-testid="stButton"] > button[kind="primary"],
      div[data-testid="stDownloadButton"] > button[kind="primary"] {
        background: var(--teal) !important;
        border-color: var(--teal) !important;
        color: #ffffff !important;
      }
      div[data-testid="stButton"] > button:hover,
      div[data-testid="stDownloadButton"] > button:hover {
        border-color: var(--teal) !important;
        color: var(--teal) !important;
      }
      div[data-testid="stButton"] > button[kind="primary"]:hover,
      div[data-testid="stDownloadButton"] > button[kind="primary"]:hover {
        background: var(--teal-hover) !important;
        color: #ffffff !important;
      }
      div[data-testid="stFileUploader"] section {
        background: var(--surface);
        border: 1px dashed #9aa5ad;
        border-radius: 8px;
      }
      div[data-testid="stFileUploader"] section * {
        color: var(--ink) !important;
      }
      div[data-testid="stFileUploader"] button {
        background: #ffffff !important;
        color: var(--ink) !important;
        border: 1px solid #c9d1d9 !important;
        border-radius: 6px !important;
      }
      div[data-testid="stTextInput"] input,
      div[data-testid="stNumberInput"] input,
      textarea {
        background: #ffffff !important;
        color: var(--ink) !important;
        border: 1px solid #c9d1d9 !important;
        border-radius: 6px;
      }
      div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        background: #ffffff !important;
        color: var(--ink) !important;
        border-color: #c9d1d9 !important;
        border-radius: 6px !important;
      }
      div[data-testid="stSelectbox"] div[data-baseweb="select"] span {
        color: var(--ink) !important;
      }
      div[data-testid="stSelectbox"] svg {
        color: var(--muted) !important;
        fill: var(--muted) !important;
      }
      div[data-testid="stCheckbox"] label,
      div[data-testid="stCheckbox"] p {
        color: var(--ink) !important;
      }
      div[data-testid="stDataFrame"],
      div[data-testid="stDataEditor"] {
        border-radius: 8px;
      }
      div[data-testid="stDataFrame"] *,
      div[data-testid="stDataEditor"] * {
        color: var(--ink) !important;
      }
      [data-testid="stMetric"] {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 12px 14px;
      }
      [data-testid="stMetricValue"] { color: var(--teal); }
      div[data-testid="stExpander"] {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 8px;
      }
      .app-shell {
        border-bottom: 1px solid var(--line);
        margin-bottom: 0.85rem;
        padding-bottom: 0.95rem;
      }
      .app-title {
        color: var(--ink);
        font-size: 1.85rem;
        font-weight: 760;
        line-height: 1.18;
        margin: 0 0 0.3rem 0;
      }
      .app-subtitle {
        color: var(--muted);
        max-width: 820px;
        margin: 0;
      }
      .top-meta {
        color: var(--muted);
        font-size: 0.84rem;
        margin-top: 0.35rem;
      }
      .nav-wrap {
        border-bottom: 1px solid var(--line);
        margin-bottom: 1.25rem;
        padding-bottom: 0.85rem;
      }
      .nav-wrap div[data-testid="column"] {
        display: flex;
        align-items: stretch;
      }
      .nav-wrap div[data-testid="stButton"] {
        width: 100%;
      }
      .nav-wrap div[data-testid="stButton"] > button {
        width: 100%;
        border: 0 !important;
        border-bottom: 3px solid transparent !important;
        border-radius: 0 !important;
        background: transparent !important;
        color: #35414c !important;
        min-height: 2.45rem;
        font-weight: 720;
      }
      .nav-wrap div[data-testid="stButton"] > button:hover {
        background: #f3f7f7 !important;
        color: var(--teal) !important;
        border-bottom-color: #bdd6d4 !important;
      }
      .nav-wrap div[data-testid="stButton"] > button[kind="primary"] {
        background: #eef8f7 !important;
        color: var(--teal) !important;
        border-bottom-color: var(--teal) !important;
      }
      .top-actions div[data-testid="stButton"] > button {
        width: 100%;
      }
      .workflow-head {
        background: var(--soft);
        border-radius: 8px;
        padding: 0.85rem 1rem;
        margin: 0 0 1rem 0;
        border: 1px solid var(--line);
      }
      .workflow-head h2 {
        font-size: 1.12rem;
        margin: 0;
      }
      .workflow-head p {
        color: var(--muted);
        margin: 0.35rem 0 0 0;
      }
      .section-label {
        color: var(--ink);
        font-size: 0.92rem;
        font-weight: 720;
        margin: 0.25rem 0 0.45rem 0;
      }
      .quiet-box {
        background: #ffffff;
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 0.85rem 0.95rem;
        margin-bottom: 0.85rem;
      }
      .status-note {
        border-left: 4px solid var(--amber);
        padding: 9px 12px;
        background: #fff8e6;
        border-radius: 6px;
        margin: 8px 0;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def api_url(api_base: str, endpoint: str) -> str:
    return f"{api_base.rstrip('/')}{endpoint}"


def get_ui_session_id() -> str:
    if "ui_session_id" in st.session_state:
        return st.session_state["ui_session_id"]
    session_id = st.query_params.get("session") or f"UI-{uuid.uuid4().hex[:10].upper()}"
    st.session_state["ui_session_id"] = session_id
    st.query_params["session"] = session_id
    return session_id


UI_SESSION_ID = get_ui_session_id()


def get_current_page() -> str:
    if "active_workflow" not in st.session_state:
        st.session_state["active_workflow"] = "Level 1 Audit"
    return st.session_state["active_workflow"]


def set_current_page(page: str) -> None:
    st.session_state["active_workflow"] = page


def render_top_navigation() -> tuple[str, str]:
    header_col, controls_col = st.columns([1.45, 1])
    with header_col:
        st.markdown(
            f"""
            <div class="app-shell">
              <div class="app-title">Design Audit Agent</div>
              <div class="app-subtitle">
                Screenshot audits, before/after comparisons, and autonomous regression scans in one review workspace.
              </div>
              <div class="top-meta">Session: {UI_SESSION_ID}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with controls_col:
        st.markdown('<div class="top-actions">', unsafe_allow_html=True)
        api_base = st.text_input("FastAPI URL", DEFAULT_API_BASE)
        action_col, session_col = st.columns(2)
        if action_col.button("Check API", use_container_width=True):
            try:
                health = get_json(api_base, "/api/v1/health")
                st.success(f"Online: {health.get('status')}")
                st.caption(health.get("llm_model", ""))
            except Exception as exc:
                st.error(f"API unavailable: {exc}")
        if session_col.button("New session", use_container_width=True):
            start_new_ui_session()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="nav-wrap">', unsafe_allow_html=True)
    nav_cols = st.columns(len(NAV_ITEMS))
    page = get_current_page()
    for nav_col, (label, value) in zip(nav_cols, NAV_ITEMS):
        if nav_col.button(label, key=f"nav-{value}", type="primary" if page == value else "secondary"):
            set_current_page(value)
            page = value
    st.markdown("</div>", unsafe_allow_html=True)
    return api_base, page


def render_workflow_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="workflow-head">
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def session_path(*parts: str) -> Path:
    return SESSION_DIR.joinpath(UI_SESSION_ID, *parts)


def safe_filename(value: str) -> str:
    allowed_symbols = {".", "-", "_"}
    cleaned = "".join(ch if ch.isalnum() or ch in allowed_symbols else "_" for ch in value)
    return cleaned.strip("._") or "upload.bin"


def load_session_json() -> dict:
    path = session_path("state.json")
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_session_json(data: dict) -> None:
    path = session_path("state.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_session_value(key: str):
    return load_session_json().get(key)


def set_session_value(key: str, value) -> None:
    data = load_session_json()
    data[key] = value
    save_session_json(data)


def persist_upload(slot: str, uploaded_file, clear_keys: list[str] | None = None) -> dict | None:
    if uploaded_file is None:
        return get_session_value(f"upload_{slot}")
    previous = get_session_value(f"upload_{slot}") or {}
    changed = previous.get("name") != uploaded_file.name or previous.get("size") != uploaded_file.size
    upload_dir = session_path("uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(uploaded_file.name)
    path = upload_dir / f"{slot}_{filename}"
    path.write_bytes(uploaded_file.getvalue())
    metadata = {
        "name": uploaded_file.name,
        "type": uploaded_file.type or "application/octet-stream",
        "path": str(path),
        "size": uploaded_file.size,
    }
    set_session_value(f"upload_{slot}", metadata)
    if changed:
        for key in clear_keys or []:
            set_session_value(key, None)
    return metadata


def upload_bytes(metadata: dict) -> bytes:
    return Path(metadata["path"]).read_bytes()


def show_thumbnail(metadata: dict, caption: str | None = None) -> None:
    st.image(upload_bytes(metadata), caption=caption or metadata["name"], width=220)


def start_new_ui_session() -> None:
    session_id = f"UI-{uuid.uuid4().hex[:10].upper()}"
    st.session_state.clear()
    st.session_state["ui_session_id"] = session_id
    st.query_params["session"] = session_id
    st.rerun()


def get_json(api_base: str, endpoint: str) -> dict | list:
    with httpx.Client(timeout=30) as client:
        response = client.get(api_url(api_base, endpoint))
        response.raise_for_status()
        return response.json()


def post_json(api_base: str, endpoint: str, payload: dict) -> dict:
    with httpx.Client(timeout=240) as client:
        response = client.post(api_url(api_base, endpoint), json=payload)
        response.raise_for_status()
        return response.json()


def post_files(api_base: str, endpoint: str, files: dict) -> dict:
    with httpx.Client(timeout=240) as client:
        response = client.post(api_url(api_base, endpoint), files=files)
        response.raise_for_status()
        return response.json()


def slug(value: str) -> str:
    parsed = urlparse(value)
    text = parsed.path.strip("/") or parsed.netloc or value or "page"
    cleaned = "".join((ch.lower() if ch.isalnum() else "_") for ch in text)
    return cleaned.strip("_") or "page"


def download_reports(report: dict, prefix: str) -> None:
    cols = st.columns(2)
    for col, label, key, mime in [
        (cols[0], "Download JSON", "json_report_path", "application/json"),
        (cols[1], "Download HTML", "html_report_path", "text/html"),
    ]:
        path = report.get(key)
        if path and Path(path).exists():
            col.download_button(
                label,
                Path(path).read_bytes(),
                file_name=Path(path).name,
                mime=mime,
                key=f"{prefix}-{key}-{path}",
            )
        elif path:
            col.caption(f"{label}: `{path}`")
    show_inline_report(report)


def show_inline_report(report: dict) -> None:
    html_path = report.get("html_report_path")
    json_path = report.get("json_report_path")
    if not html_path and not json_path:
        return
    tab_html, tab_json = st.tabs(["Report", "JSON"])
    with tab_html:
        if html_path and Path(html_path).exists():
            components.html(Path(html_path).read_text(encoding="utf-8"), height=760, scrolling=True)
        else:
            st.caption("HTML report file is not available yet.")
    with tab_json:
        if json_path and Path(json_path).exists():
            st.json(json.loads(Path(json_path).read_text(encoding="utf-8")))
        else:
            st.json(report)


def show_error_response(result: dict) -> bool:
    if result.get("report"):
        return False
    st.error(result.get("error") or "Request failed")
    if result.get("error_detail"):
        st.code(result["error_detail"])
    return True


def render_l1(api_base: str) -> None:
    render_workflow_header(
        "Level 1: Single Screenshot Audit",
        "Upload one UI screenshot and review validated design findings with downloadable reports.",
    )
    image = st.file_uploader("Screenshot", type=["png", "jpg", "jpeg", "webp"], key="l1_upload")
    image_meta = persist_upload("l1_screenshot", image, clear_keys=["l1_report"])
    if image_meta:
        show_thumbnail(image_meta)
    if st.button("Analyze screenshot", type="primary", disabled=image_meta is None):
        files = {"file": (image_meta["name"], upload_bytes(image_meta), image_meta["type"])}
        with st.spinner("Analyzing screenshot..."):
            result = post_files(api_base, "/api/v1/analyze", files)
        if show_error_response(result):
            return
        set_session_value("l1_report", result["report"])
    report = get_session_value("l1_report")
    if report:
        summary = report.get("summary", {})
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Findings", summary.get("total", 0))
        c2.metric("Critical", summary.get("critical", 0))
        c3.metric("High", summary.get("high", 0))
        c4.metric("Flagged", summary.get("flagged_for_review", 0))
        c5.metric("LLM Attempts", report.get("llm_attempts", 0))
        for finding in report.get("findings", []):
            with st.expander(f"{finding['finding_id']} | {finding['severity']} | {finding['principle']}"):
                st.write(f"Location: {finding['location']}")
                st.write(f"Observation: {finding['observation']}")
                st.write(f"Impact: {finding['user_impact']}")
                st.write(f"Recommendation: {finding['recommendation']}")
                st.write(f"Confidence: {finding['confidence']}%")
        download_reports(report, "l1")


def render_l2(api_base: str) -> None:
    render_workflow_header(
        "Level 2: Before / After Comparison",
        "Compare an approved baseline against the current candidate and classify visual change.",
    )
    st.caption("Baseline = before/original. Current = after/updated.")
    col_a, col_b = st.columns(2)
    baseline = col_a.file_uploader("Baseline screenshot", type=["png", "jpg", "jpeg", "webp"], key="baseline")
    current = col_b.file_uploader("Current screenshot", type=["png", "jpg", "jpeg", "webp"], key="current")
    swap = st.checkbox("Swap baseline and current before comparing")
    baseline_meta = persist_upload("l2_baseline", baseline, clear_keys=["l2_report"])
    current_meta = persist_upload("l2_current", current, clear_keys=["l2_report"])
    if baseline_meta:
        with col_a:
            show_thumbnail(baseline_meta)
    if current_meta:
        with col_b:
            show_thumbnail(current_meta)
    if st.button("Compare screenshots", type="primary", disabled=baseline_meta is None or current_meta is None):
        left = current_meta if swap else baseline_meta
        right = baseline_meta if swap else current_meta
        files = {
            "baseline": (left["name"], upload_bytes(left), left["type"]),
            "current": (right["name"], upload_bytes(right), right["type"]),
        }
        with st.spinner("Comparing screenshots..."):
            result = post_files(api_base, "/api/v1/compare", files)
        if show_error_response(result):
            return
        set_session_value("l2_report", result["report"])
    report = get_session_value("l2_report")
    if report:
        verdict = report["verdict"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Verdict", verdict["net_result"])
        c2.metric("Regressions", verdict["regression_count"])
        c3.metric("Improvements", verdict["improvement_count"])
        c4.metric("Accessibility", verdict["accessibility_regressions_count"])
        st.write(verdict["summary"])
        for finding in report.get("findings", []):
            with st.expander(f"{finding['finding_id']} | {finding['change_direction']} | {finding['severity']}"):
                st.write(f"Location: {finding['location']}")
                st.write(f"Change: {finding['change_summary']}")
                st.write(f"Reasoning: {finding['reasoning']}")
                st.write(f"Confidence: {finding['confidence']}%")
        download_reports(report, "l2")


def default_pages() -> list[dict]:
    return [
        {"url": "/secure", "name": "Authenticated Secure Area"},
        {"url": "/checkboxes", "name": "Checkboxes"},
        {"url": "/login", "name": "Login Form"},
    ]


def rows_to_pages(rows: list[dict], target_url: str) -> list[dict]:
    pages = []
    is_demo_site = "the-internet.herokuapp.com" in urlparse(target_url).netloc
    demo_defaults = {
        "/secure": {"wait_for_selector": ".flash.success", "dynamic_selectors": [".flash"]},
        "/checkboxes": {"wait_for_selector": "form#checkboxes", "dynamic_selectors": ["footer"]},
        "/login": {"wait_for_selector": "#login", "dynamic_selectors": [".flash", "footer"]},
    }
    for row in rows:
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        name = str(row.get("name") or slug(url)).strip()
        defaults = demo_defaults.get(url, {}) if is_demo_site else {}
        pages.append(
            {
                "page_id": name,
                "url": url,
                "name": name,
                "wait_for_selector": defaults.get("wait_for_selector") or "body",
                "dynamic_selectors": defaults.get("dynamic_selectors") or ["header", "footer"],
                "scroll_to_top": True,
            }
        )
    return pages


def comparison_status(page_result: dict) -> str:
    if page_result.get("error"):
        return "error"
    if page_result.get("comparison_report"):
        return page_result["comparison_report"]["verdict"]["net_result"]
    if not page_result.get("baseline_exists"):
        return "baseline_created_or_refreshed"
    diff = page_result.get("pixel_diff_percentage")
    if diff is not None:
        return f"not_run_pixel_diff_below_threshold_{diff}%"
    return "not_run"


def default_pages_for_url(target_url: str) -> list[dict]:
    host = urlparse(target_url).netloc
    generic_pages = [
        {"url": "/", "name": "Home"},
        {"url": "/about", "name": "About"},
        {"url": "/contact", "name": "Contact"},
    ]
    return default_pages() if "the-internet.herokuapp.com" in host else generic_pages


def render_l3(api_base: str) -> None:
    render_workflow_header(
        "Level 3: Autonomous Website Regression Scan",
        "Configure pages, authentication, and viewport settings for browser-based visual regression checks.",
    )
    saved_target_url = get_session_value("l3_target_url") or "https://the-internet.herokuapp.com"
    target_col, settings_col = st.columns([1.45, 1])
    with target_col:
        st.markdown('<div class="section-label">Target</div>', unsafe_allow_html=True)
        target_url = st.text_input("Website URL", saved_target_url)
    with settings_col:
        st.markdown('<div class="section-label">Scan Settings</div>', unsafe_allow_html=True)
        viewport_left, viewport_right = st.columns(2)
        viewport_width = viewport_left.number_input("Width", 320, 3840, 1440, step=10)
        viewport_height = viewport_right.number_input("Height", 320, 2160, 900, step=10)
        wait_ms = st.number_input("Wait after navigation ms", 0, 10000, 1500, step=100)
        refresh_baseline = st.checkbox("Refresh baselines instead of comparing")

    is_demo_site = "the-internet.herokuapp.com" in urlparse(target_url).netloc
    st.markdown('<div class="section-label">Pages</div>', unsafe_allow_html=True)
    page_rows = st.data_editor(
        default_pages_for_url(target_url),
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "url": st.column_config.TextColumn("URL/path", required=True, help="Relative path like /pricing or a full URL."),
            "name": st.column_config.TextColumn("Report name", help="Human-readable page name shown in reports."),
        },
        key=f"l3-pages-{slug(target_url)}",
    )
    pages = rows_to_pages(page_rows, target_url)

    auth_col, config_col = st.columns([1.1, 1])
    with auth_col:
        st.markdown('<div class="section-label">Authentication</div>', unsafe_allow_html=True)
        use_auth = st.checkbox("Website requires login", value=is_demo_site)
        login_url = username_selector = password_selector = submit_selector = success_indicator = ""
        username_env = "SCAN_USERNAME"
        password_env = "SCAN_PASSWORD"
        if use_auth:
            login_url = st.text_input("Login URL", "https://the-internet.herokuapp.com/login" if is_demo_site else "")
            auth_left, auth_right = st.columns(2)
            username_selector = auth_left.text_input("Username selector", "#username" if is_demo_site else "")
            password_selector = auth_right.text_input("Password selector", "#password" if is_demo_site else "")
            submit_selector = auth_left.text_input("Submit selector", "button[type=submit]" if is_demo_site else "")
            success_indicator = auth_right.text_input("Success indicator", ".flash.success" if is_demo_site else "body")
            username_env = auth_left.text_input("Username env var", "SCAN_USERNAME")
            password_env = auth_right.text_input("Password env var", "SCAN_PASSWORD")

    config = {
        "target_url": target_url,
        "pages": pages,
        "viewport_width": int(viewport_width),
        "viewport_height": int(viewport_height),
        "wait_after_navigation_ms": int(wait_ms),
        "baseline_dir": "output/baselines",
        "scan_output_dir": "output/scans",
    }
    if use_auth:
        config["auth"] = {
            "login_url": login_url,
            "username_selector": username_selector,
            "password_selector": password_selector,
            "submit_selector": submit_selector,
            "success_indicator": success_indicator,
            "username": username_env,
            "password": password_env,
        }

    with config_col:
        st.markdown('<div class="section-label">Run</div>', unsafe_allow_html=True)
        st.caption(f"{len(pages)} configured pages")
        if st.button("Start website scan", type="primary", use_container_width=True):
            if not target_url or len(pages) < 3:
                st.error("Level 3 requires a website URL and at least 3 configured pages.")
                return
            set_session_value("l3_target_url", target_url)
            set_session_value("l3_config", config)
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
            with st.spinner("Running Playwright scan..."):
                result = post_json(api_base, "/api/v1/scan/start", {"config_file": str(CONFIG_PATH), "refresh_baseline": refresh_baseline})
            if show_error_response(result):
                return
            set_session_value("l3_report", result["report"])
        with st.expander("Generated config"):
            st.json(config)

    report = get_session_value("l3_report")
    if report:
        st.markdown('<div class="section-label">Latest Result</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Status", report["overall_status"])
        c2.metric("Pages", report["pages_scanned"])
        c3.metric("Regressions", report["pages_with_regressions"])
        c4.metric("Duration", f"{report['total_duration_seconds']}s")
        for page in report.get("page_results", []):
            with st.expander(f"{page['page_id']} | {page.get('page_url')}"):
                status = comparison_status(page)
                st.markdown(f'<div class="status-note"><strong>Comparison status:</strong> {status}</div>', unsafe_allow_html=True)
                st.write(f"Screenshot: {page.get('screenshot_path')}")
                st.write(f"Baseline: {page.get('baseline_screenshot_path')}")
                st.write(f"Pixel diff: {page.get('pixel_diff_percentage')}")
                st.write(f"Dynamic regions filtered: {page.get('dynamic_regions_filtered')}")
                if page.get("error"):
                    st.error(page["error"])
                if page.get("comparison_report"):
                    st.write(page["comparison_report"]["verdict"]["summary"])
                else:
                    st.caption("No comparison report means the page created/refreshed a baseline or the visual diff was below the LLM threshold.")
        download_reports(report, "l3")


def render_baselines(api_base: str) -> None:
    render_workflow_header(
        "Level 3 Baselines",
        "Inspect the stored screenshot baselines used by autonomous scans.",
    )
    if st.button("Load baselines", type="primary"):
        set_session_value("baselines", get_json(api_base, "/api/v1/scan/baselines"))
    baselines = get_session_value("baselines")
    if baselines:
        st.json(baselines)


def render_history(api_base: str) -> None:
    render_workflow_header(
        "Scan History",
        "Review recent autonomous scan runs and their persisted report metadata.",
    )
    if st.button("Load history", type="primary"):
        set_session_value("history", get_json(api_base, "/api/v1/scan/history"))
    history = get_session_value("history")
    if history:
        st.json(history)


api_base, page = render_top_navigation()

if page == "Level 1 Audit":
    render_l1(api_base)
elif page == "Level 2 Compare":
    render_l2(api_base)
elif page == "Level 3 Website Scan":
    render_l3(api_base)
elif page == "Baselines":
    render_baselines(api_base)
else:
    render_history(api_base)
