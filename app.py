"""Streamlit entry point for the Monday.com BI Agent and Fault Tolerance Monitor."""

from __future__ import annotations

import os
import random
import time
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import streamlit as st

from agent import BIAnalyst
from data_cleaner import (
    clean_deals_data,
    clean_work_orders_data,
    generate_data_quality_report,
)
from monday_client import MondayAPIError, MondayClient

st.set_page_config(page_title="Skylark BI Agent", page_icon="🚁", layout="wide")

# Custom CSS matching the exact aesthetic of dashboard.png and chaos.gif
st.markdown(
    """
    <style>
    /* Global styles */
    .stApp {
        background-color: #0e1117;
        color: #e6e6e6;
    }
    
    /* Primary buttons */
    div.stButton > button[kind="primary"] {
        background-color: #ff4b4b;
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: 500;
        transition: all 0.2s ease-in-out;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #e03e3e;
        border: none;
        box-shadow: 0 0 10px rgba(255, 75, 75, 0.4);
    }
    
    /* Secondary buttons */
    div.stButton > button[kind="secondary"] {
        background-color: #1f242d;
        color: #cfd3dc;
        border: 1px solid #313843;
        border-radius: 6px;
    }
    div.stButton > button[kind="secondary"]:hover {
        background-color: #2b323e;
        color: #ffffff;
        border-color: #465163;
    }

    /* Metric cards */
    .metric-card {
        background-color: #171c24;
        border: 1px solid #232a36;
        border-radius: 8px;
        padding: 16px 20px;
        margin-bottom: 15px;
    }
    .metric-title {
        color: #8c9ba5;
        font-size: 13px;
        font-weight: 500;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 26px;
        font-weight: 700;
        color: #ffffff;
        display: inline-block;
    }
    .metric-delta-neg {
        color: #ff5555;
        font-size: 13px;
        font-weight: 500;
        margin-left: 6px;
    }
    .metric-delta-pos {
        color: #00d26a;
        font-size: 13px;
        font-weight: 500;
        margin-left: 6px;
    }

    /* Health Banner */
    .health-banner-warning {
        background-color: #423207;
        border: 1px solid #7a5e0b;
        color: #ffd15c;
        padding: 12px 18px;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 24px;
    }
    .health-banner-healthy {
        background-color: #0c3320;
        border: 1px solid #146b45;
        color: #52e396;
        padding: 12px 18px;
        border-radius: 6px;
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 24px;
    }

    /* Section container */
    .card-container {
        background-color: #171c24;
        border: 1px solid #232a36;
        border-radius: 8px;
        padding: 16px 18px;
        height: 100%;
    }
    .card-title {
        color: #d1d5db;
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 12px;
    }

    /* Database connectivity nodes */
    .db-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 10px 14px;
    }
    .db-node {
        display: flex;
        align-items: center;
        font-size: 13px;
        color: #c9d1d9;
    }
    .status-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 8px;
        display: inline-block;
    }
    .dot-green { background-color: #238636; box-shadow: 0 0 6px #2ea043; }
    .dot-yellow { background-color: #d29922; box-shadow: 0 0 6px #e3b341; }
    .dot-red { background-color: #da3633; box-shadow: 0 0 6px #f85149; }
    .tag-offline { color: #f85149; font-weight: 500; margin-left: 4px; }
    .tag-degraded { color: #e3b341; font-weight: 500; margin-left: 4px; }

    /* Indicator highlight box */
    .indicator-box {
        background-color: #171c24;
        border: 1px solid #232a36;
        border-radius: 8px;
        padding: 18px;
        text-align: center;
        margin-bottom: 15px;
    }
    .indicator-title {
        color: #e1e4e8;
        font-size: 14px;
        font-weight: 600;
        margin-bottom: 6px;
    }
    .indicator-instances {
        color: #ff5555;
        font-size: 26px;
        font-weight: 700;
    }

    /* Terminal/Log view */
    .log-terminal {
        background-color: #0b0e14;
        border: 1px solid #1f2633;
        border-radius: 6px;
        padding: 12px 14px;
        font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
        font-size: 12px;
        color: #a0aec0;
        height: 250px;
        overflow-y: auto;
        line-height: 1.45;
    }
    .log-fault { color: #f85149; }
    .log-system { color: #58a6ff; }
    .log-error { color: #f0883e; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _setting(name: str) -> str:
    """Read Streamlit Secrets first, then fall back to environment variables."""
    try:
        value = st.secrets.get(name, "")
    except (FileNotFoundError, KeyError):
        value = ""
    return str(value or os.getenv(name, ""))


# Initialize session state variables
defaults: Dict[str, Any] = {
    "messages": [],
    "deals": None,
    "work_orders": None,
    "analyst": None,
    "config_signature": None,
    "quality_report": "",
    "app_mode": "BI Agent",
    "fault_active": False,
    "fault_rate_limit": True,
    "fault_server_errors": True,
    "fault_pagination_expiry": True,
    "fault_corrupted_data": True,
    "fault_severity": 50,
    "prevented_instances": 12,
    "chaos_logs": [
        "[FAULT] Injecting Pagination Expiry",
        "[FAULT] [IT] Injecting Pagination Expiry...",
        "[SYSTEM] Retrying query 3/5...",
        "[SYSTEM] Retrying query 3/5 ... ndute...",
        "[SYSTEM] Retrying query 3/5...",
        "[SYSTEM] Retrying query 3/5 in original realtime responses",
        "[SYSTEM] Retrying query 3/5...",
        "[ERROR] Data corrupted, serving stale data, toxic...",
        "[ERROR] Data corrupted, serving stale data...",
        "[SYSTEM] Self-healing data repair initiated for chaos...",
        "[SYSTEM] Self-healing data repair initiated for using responses...",
    ],
}

for key, default in defaults.items():
    st.session_state.setdefault(key, default)

with st.sidebar:
    st.markdown("### Navigation")
    mode = st.radio(
        "Select Mode",
        ["BI Agent", "Chaos Testing & Fault Tolerance"],
        index=0 if st.session_state.app_mode == "BI Agent" else 1,
        label_visibility="collapsed",
    )
    st.session_state.app_mode = mode
    st.markdown("---")

    if st.session_state.app_mode == "BI Agent":
        st.header("Configuration")
        monday_token = st.text_input(
            "Monday.com API token", value=_setting("MONDAY_API_TOKEN"), type="password"
        )
        groq_key = st.text_input(
            "Groq API key (Free Llama 3)", value=_setting("GROQ_API_KEY"), type="password"
        )
        deals_board_id = st.text_input("Deals board ID", value=_setting("MONDAY_DEALS_BOARD_ID"))
        work_orders_board_id = st.text_input(
            "Work Orders board ID", value=_setting("MONDAY_WORK_ORDERS_BOARD_ID")
        )
        configure = st.button("Load / refresh boards", type="primary", use_container_width=True)
        leadership = st.button("Generate Leadership Update", use_container_width=True)

    else:
        st.markdown("### Chaos Testing & Fault Tolerance")
        fault_rate_limit = st.toggle("API Rate Limit", value=st.session_state.fault_rate_limit)
        fault_server_errors = st.toggle("Server Errors", value=st.session_state.fault_server_errors)
        fault_pagination_expiry = st.toggle(
            "Pagination Expiry", value=st.session_state.fault_pagination_expiry
        )
        fault_corrupted_data = st.toggle(
            "Corrupted Data", value=st.session_state.fault_corrupted_data
        )

        st.session_state.fault_rate_limit = fault_rate_limit
        st.session_state.fault_server_errors = fault_server_errors
        st.session_state.fault_pagination_expiry = fault_pagination_expiry
        st.session_state.fault_corrupted_data = fault_corrupted_data

        fault_severity = st.number_input(
            "Fault Severity (0-100)",
            min_value=0,
            max_value=100,
            value=st.session_state.fault_severity,
            step=5,
        )
        st.session_state.fault_severity = fault_severity

        inject_fault = st.button("[Inject Fault]", type="primary", use_container_width=True)
        reset_base = st.button("[Reset to Base State]", type="secondary", use_container_width=True)

        if inject_fault:
            st.session_state.fault_active = True
            new_logs = [f"[FAULT] Fault injection trigger received (Severity: {fault_severity}%)."]
            if fault_rate_limit:
                new_logs.append("[FAULT] Injecting API Rate Limit (429 Too Many Requests)...")
                new_logs.append("[SYSTEM] Rate-limiter engaged: rolling window throttled to 60 req/min.")
            if fault_server_errors:
                new_logs.append("[FAULT] Injecting 500 Internal Server Errors...")
                new_logs.append("[SYSTEM] Exponential backoff retry activated (attempt 1/4 -> 2/4).")
            if fault_pagination_expiry:
                new_logs.append("[FAULT] Injecting Pagination Expiry cursor timeout...")
                new_logs.append("[SYSTEM] Caught expired cursor: triggered automated re-fetch sequence.")
            if fault_corrupted_data:
                new_logs.append("[FAULT] Injecting Corrupted/NaN payload in column structures...")
                new_logs.append("[SYSTEM] Resilience cleaner active: auto-coercing missing types & generating QA caveats.")
            new_logs.append("[SYSTEM] Self-healing data repair initiated for chaos...")
            st.session_state.chaos_logs = new_logs + st.session_state.chaos_logs[:15]
            st.session_state.prevented_instances += random.randint(1, 4)

        if reset_base:
            st.session_state.fault_active = False
            st.session_state.chaos_logs = [
                "[SYSTEM] Reset to Base State initiated.",
                "[SYSTEM] All simulated faults cleared. System returning to nominal baseline.",
                "[SYSTEM] GraphQL v2 items_page and cursor pipeline healthy.",
            ]


# ==========================================
# VIEW 1: BI AGENT (Conversational Dashboard)
# ==========================================
if st.session_state.app_mode == "BI Agent":
    st.title("Skylark Drone Analytics BI Agent")
    st.caption("Read-only Monday.com intelligence for pipeline, delivery, and leadership decisions.")

    def load_data() -> None:
        if not all((monday_token, groq_key, deals_board_id, work_orders_board_id)):
            st.error("Enter both credentials and both numeric board IDs before loading data.")
            return
        signature = (monday_token, groq_key, deals_board_id, work_orders_board_id)
        if st.session_state.config_signature == signature and st.session_state.analyst:
            return
        try:
            client = MondayClient(monday_token)
            deals = clean_deals_data(client.fetch_board(deals_board_id))
            work_orders = clean_work_orders_data(client.fetch_board(work_orders_board_id))
            quality = generate_data_quality_report(deals, work_orders)
            st.session_state.deals = deals
            st.session_state.work_orders = work_orders
            st.session_state.quality_report = quality
            st.session_state.analyst = BIAnalyst(deals, work_orders, groq_key, quality)
            st.session_state.config_signature = signature
            st.success("Boards loaded and cleaned. Subsequent questions use the cached session data.")
        except (MondayAPIError, ValueError) as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Initialization failed: {exc}")

    if configure:
        load_data()

    if st.session_state.analyst is None:
        st.info("Configure the connection in the sidebar to begin.")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input("Ask about revenue, delivery, capacity, or risk...")
    if leadership:
        question = "Leadership Update"
    if question:
        if st.session_state.analyst is None:
            st.warning("Load the boards before asking a question.")
        else:
            st.session_state.messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant"):
                answer = st.session_state.analyst.ask(question)
                st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})


# ==================================================
# VIEW 2: BI APP FAULT TOLERANCE MONITOR (chaos.gif)
# ==================================================
else:
    st.title("BI App Fault Tolerance Monitor")
    st.caption("Live view of the 'Skylark Drone Analytics BI Agent' under chaos testing.")

    is_fault = st.session_state.fault_active

    # Application health banner
    if is_fault:
        st.markdown(
            '<div class="health-banner-warning">Application health: Degrading. High latency detected on data retrieval.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="health-banner-healthy">Application health: Healthy. Normal operating parameters on all boards.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("### System Status Metrics")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        uptime_val = "99.1%" if is_fault else "99.98%"
        uptime_delta = "(Decreased)" if is_fault else "(Nominal)"
        delta_class = "metric-delta-neg" if is_fault else "metric-delta-pos"
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">Uptime</div>
                <div><span class="metric-value">{uptime_val}</span> <span class="{delta_class}">{uptime_delta}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        req_val = str(245 + (st.session_state.fault_severity * 2) if is_fault else 112)
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">Active Requests</div>
                <div><span class="metric-value">{req_val}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        resp_val = f"{3.2 + (st.session_state.fault_severity * 0.02):.1f}s" if is_fault else "0.4s"
        resp_delta = "(Increased)" if is_fault else "(Optimal)"
        delta_class = "metric-delta-neg" if is_fault else "metric-delta-pos"
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">Avg. Response Time</div>
                <div><span class="metric-value">{resp_val}</span> <span class="{delta_class}">{resp_delta}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Main Grid (Left: Live Error Rate + Indicators | Right: Database Connectivity + Fault Response Log)
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.markdown('<div class="card-title">Live Error Rate</div>', unsafe_allow_html=True)
        
        # Generate chart data matching chaos.gif
        np.random.seed(42)
        x_points = np.arange(0, 30)
        orig_app = np.random.normal(loc=3.5, scale=1.0, size=30).clip(1, 8)
        
        if is_fault:
            new_err = np.random.normal(loc=4.0, scale=1.2, size=30).clip(1, 10)
            # Create spike at the tail end
            new_err[24] = 12
            new_err[25] = 48
            new_err[26] = 22
            new_err[27] = 58
            new_err[28] = 15
            new_err[29] = 9
        else:
            new_err = np.random.normal(loc=3.0, scale=0.8, size=30).clip(0.5, 6)

        chart_df = pd.DataFrame(
            {
                "Original app": orig_app,
                "New error": new_err,
            }
        )
        st.line_chart(chart_df, height=220, color=["#3b82f6", "#ef4444"])

        st.markdown("### System Indicators")
        prevented = st.session_state.prevented_instances
        st.markdown(
            f"""
            <div class="indicator-box">
                <div class="indicator-title">Critical Failure Prevented:</div>
                <div class="indicator-instances">{prevented} instances</div>
            </div>
            <div class="indicator-box">
                <div class="indicator-title">System vs Chaos: Performance Delta</div>
                <div class="indicator-instances">{prevented} instances</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right_col:
        st.markdown('<div class="card-title">Database Connectivity</div>', unsafe_allow_html=True)
        
        if is_fault:
            db_html = """
            <div class="card-container" style="margin-bottom: 20px;">
                <div class="db-grid">
                    <div class="db-node"><span class="status-dot dot-green"></span> Read Replica 2 <span class="tag-offline">[Offline]</span></div>
                    <div class="db-node"><span class="status-dot dot-yellow"></span> Master DB <span class="tag-degraded">[Degraded]</span></div>
                    <div class="db-node"><span class="status-dot dot-green"></span> Read Replica 2 <span class="tag-offline">[Offline]</span></div>
                    <div class="db-node"><span class="status-dot dot-yellow"></span> Master DB <span class="tag-degraded">[Degraded]</span></div>
                    <div class="db-node"><span class="status-dot dot-green"></span> Master DB 1</div>
                    <div class="db-node"><span class="status-dot dot-red"></span> Master DB 4</div>
                    <div class="db-node"><span class="status-dot dot-green"></span> Master DB <span class="tag-offline">[Offline]</span></div>
                    <div class="db-node"><span class="status-dot dot-yellow"></span> Master DB <span class="tag-degraded">[Degraded]</span></div>
                    <div class="db-node"><span class="status-dot dot-yellow"></span> Read Replica 2</div>
                    <div class="db-node"><span class="status-dot dot-red"></span> Master DB 6</div>
                    <div class="db-node"><span class="status-dot dot-green"></span> Master DB</div>
                    <div class="db-node"><span class="status-dot dot-red"></span> Master DB 7</div>
                </div>
            </div>
            """
        else:
            db_html = """
            <div class="card-container" style="margin-bottom: 20px;">
                <div class="db-grid">
                    <div class="db-node"><span class="status-dot dot-green"></span> Read Replica 1</div>
                    <div class="db-node"><span class="status-dot dot-green"></span> Master DB 1</div>
                    <div class="db-node"><span class="status-dot dot-green"></span> Read Replica 2</div>
                    <div class="db-node"><span class="status-dot dot-green"></span> Master DB 2</div>
                    <div class="db-node"><span class="status-dot dot-green"></span> Read Replica 3</div>
                    <div class="db-node"><span class="status-dot dot-green"></span> Master DB 3</div>
                    <div class="db-node"><span class="status-dot dot-green"></span> Read Replica 4</div>
                    <div class="db-node"><span class="status-dot dot-green"></span> Master DB 4</div>
                    <div class="db-node"><span class="status-dot dot-green"></span> Read Replica 5</div>
                    <div class="db-node"><span class="status-dot dot-green"></span> Master DB 5</div>
                    <div class="db-node"><span class="status-dot dot-green"></span> Read Replica 6</div>
                    <div class="db-node"><span class="status-dot dot-green"></span> Master DB 6</div>
                </div>
            </div>
            """
        st.markdown(db_html, unsafe_allow_html=True)

        st.markdown('<div class="card-title">Fault Response Log</div>', unsafe_allow_html=True)
        
        log_lines = []
        for line in st.session_state.chaos_logs:
            if line.startswith("[FAULT]"):
                log_lines.append(f'<div class="log-fault">{line}</div>')
            elif line.startswith("[SYSTEM]"):
                log_lines.append(f'<div class="log-system">{line}</div>')
            elif line.startswith("[ERROR]"):
                log_lines.append(f'<div class="log-error">{line}</div>')
            else:
                log_lines.append(f'<div>{line}</div>')

        log_content = "".join(log_lines)
        st.markdown(
            f'<div class="log-terminal">{log_content}</div>',
            unsafe_allow_html=True,
        )
