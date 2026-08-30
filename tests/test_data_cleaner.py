"""Offline tests for the Monday.com data-cleaning layer.

These tests never create a network client or call Monday.com/OpenAI. They use
only local pandas fixtures and pytest assertions so they are suitable for CI.
"""

from datetime import datetime

import pandas as pd

from data_cleaner import (
    clean_deals_data,
    clean_work_orders_data,
    generate_data_quality_report,
)


def test_clean_deals_handles_currency_missing_values_dates_and_sectors():
    source = pd.DataFrame(
        {
            "Expected Revenue": ["$1,250.50", None, "£2,000"],
            "Close Date": ["12/05/2026", "May 12, 26", "not-a-date"],
            "Market Sector": ["solar", "Energy", "Sun"],
            "Deal Status": ["qualified", "proposal", None],
        }
    )

    cleaned = clean_deals_data(source)

    assert cleaned["Expected Revenue"].tolist() == [1250.50, 0.0, 2000.0]
    assert pd.api.types.is_datetime64_any_dtype(cleaned["Close Date"])
    assert cleaned.loc[1, "Close Date"] == datetime(2026, 5, 12)
    assert cleaned["Market Sector"].tolist() == [
        "Energy Sector",
        "Energy Sector",
        "Energy Sector",
    ]
    assert cleaned.loc[0, "Deal Status"] == "Qualified"
    assert cleaned.loc[1, "Deal Status"] == "Proposal"
    assert pd.isna(cleaned.loc[2, "Deal Status"])
    assert cleaned.attrs["data_quality"]["missing_by_column"]["Expected Revenue"] == 1
    assert cleaned.attrs["data_quality"]["missing_cells"] >= 2


def test_clean_work_orders_normalizes_status_and_dates():
    source = pd.DataFrame(
        {
            "Execution Status": ["Done", "finished", "in progress", "cancelled", None],
            "Execution Date": ["2026-05-12", "May 13, 2026", "13/05/2026", "bad", None],
        }
    )

    cleaned = clean_work_orders_data(source)

    assert cleaned.loc[:3, "Execution Status"].tolist() == [
        "Completed",
        "Completed",
        "In Progress",
        "Cancelled",
    ]
    assert pd.isna(cleaned.loc[4, "Execution Status"])
    assert pd.api.types.is_datetime64_any_dtype(cleaned["Execution Date"])
    assert cleaned.loc[0, "Execution Date"] == datetime(2026, 5, 12)
    assert cleaned.loc[1, "Execution Date"] == datetime(2026, 5, 13)


def test_cleaner_preserves_more_than_one_api_page_of_rows():
    row_count = 1001
    source = pd.DataFrame(
        {
            "Item ID": range(row_count),
            "Revenue": ["$1,000"] * row_count,
            "Sector": ["solar"] * row_count,
            "Status": ["Done"] * row_count,
        }
    )

    cleaned = clean_deals_data(source)

    # Monday pages are limited to 500; cleaning must not truncate a merged fetch.
    assert len(cleaned) == row_count
    assert cleaned["Revenue"].sum() == 1_000_000
    assert cleaned["Sector"].eq("Energy Sector").all()


def test_quality_report_mentions_both_boards_and_missing_columns():
    deals = clean_deals_data(pd.DataFrame({"Revenue": [None, "$10"]}))
    work_orders = clean_work_orders_data(pd.DataFrame({"Status": ["Done", None]}))

    report = generate_data_quality_report(deals, work_orders)

    assert "Deals" in report
    assert "Work Orders" in report
    assert "Revenue" in report
    assert "missing" in report.lower()


def test_empty_frames_are_supported():
    deals = clean_deals_data(pd.DataFrame())
    work_orders = clean_work_orders_data(pd.DataFrame())

    assert deals.empty
    assert work_orders.empty
    assert "Deals" in generate_data_quality_report(deals, work_orders)
