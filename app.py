"""Streamlit entry point for the Monday.com BI Agent."""

from __future__ import annotations

import os

import streamlit as st

from agent import BIAnalyst
from data_cleaner import (
    clean_deals_data,
    clean_work_orders_data,
    generate_data_quality_report,
)
from monday_client import MondayAPIError, MondayClient


st.set_page_config(page_title="Skylark BI Agent", page_icon="🚁", layout="wide")
st.title("Skylark Drone Analytics BI Agent")
st.caption("Read-only Monday.com intelligence for pipeline, delivery, and leadership decisions.")


def _setting(name: str) -> str:
    """Read Streamlit Secrets first, then fall back to environment variables."""
    try:
        value = st.secrets.get(name, "")
    except (FileNotFoundError, KeyError):
        value = ""
    return str(value or os.getenv(name, ""))

for key, default in (("messages", []), ("deals", None), ("work_orders", None), ("analyst", None), ("config_signature", None), ("quality_report", "")):
    st.session_state.setdefault(key, default)

with st.sidebar:
    st.header("Configuration")
    monday_token = st.text_input(
        "Monday.com API token", value=_setting("MONDAY_API_TOKEN"), type="password"
    )
    openai_key = st.text_input(
        "OpenAI API key", value=_setting("OPENAI_API_KEY"), type="password"
    )
    deals_board_id = st.text_input("Deals board ID", value=_setting("MONDAY_DEALS_BOARD_ID"))
    work_orders_board_id = st.text_input(
        "Work Orders board ID", value=_setting("MONDAY_WORK_ORDERS_BOARD_ID")
    )
    configure = st.button("Load / refresh boards", type="primary", use_container_width=True)
    leadership = st.button("Generate Leadership Update", use_container_width=True)


def load_data() -> None:
    if not all((monday_token, openai_key, deals_board_id, work_orders_board_id)):
        st.error("Enter both credentials and both numeric board IDs before loading data.")
        return
    signature = (monday_token, openai_key, deals_board_id, work_orders_board_id)
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
        st.session_state.analyst = BIAnalyst(deals, work_orders, openai_key, quality)
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
