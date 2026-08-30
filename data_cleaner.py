"""Cleaning and data-quality utilities for messy Monday.com exports."""

from __future__ import annotations

import re
from typing import Dict, Iterable, Tuple

import numpy as np
import pandas as pd


def _key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def _quality(df: pd.DataFrame, label: str) -> Dict[str, object]:
    missing = df.isna() | df.astype(object).applymap(
        lambda value: isinstance(value, str) and not value.strip()
    )
    by_column = missing.sum().astype(int).to_dict()
    return {
        "label": label,
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "missing_cells": int(missing.sum().sum()),
        "missing_by_column": {str(k): v for k, v in by_column.items() if v},
    }


def _find_columns(df: pd.DataFrame, words: Iterable[str]) -> list[str]:
    terms = tuple(words)
    return [column for column in df.columns if any(term in _key(column) for term in terms)]


def _normalise_dates(df: pd.DataFrame) -> None:
    candidates = _find_columns(df, ("date", "deadline", "close", "start", "end", "due"))
    for column in candidates:
        parsed = pd.to_datetime(
            df[column], errors="coerce", dayfirst=False, format="mixed", utc=True
        )
        if parsed.notna().any():
            df[column] = parsed.dt.tz_convert(None)


def _normalise_canonical_columns(df: pd.DataFrame) -> None:
    aliases = {
        "Sector": ("sector", "industry", "vertical", "market"),
        "Revenue": ("revenue", "deal value", "contract value", "amount", "value"),
        "Status": ("status", "stage", "state"),
    }
    for target, terms in aliases.items():
        if target not in df.columns:
            matches = _find_columns(df, terms)
            if matches:
                df[target] = df[matches[0]]


def _attach_quality(df: pd.DataFrame, label: str) -> pd.DataFrame:
    report = _quality(df, label)
    df.attrs["data_quality"] = report
    for column, count in report["missing_by_column"].items():
        df.attrs[f"missing_{_key(column).replace(' ', '_')}"] = count
    return df


def clean_deals_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean pipeline data while preserving source columns and quality metadata."""
    cleaned = df.copy()
    cleaned.columns = [str(column).strip() for column in cleaned.columns]
    cleaned = cleaned.replace({"": np.nan, "-": np.nan, "n/a": np.nan, "na": np.nan})
    _normalise_canonical_columns(cleaned)
    for column in _find_columns(cleaned, ("revenue", "amount", "value", "budget", "price", "cost")):
        cleaned[column] = pd.to_numeric(
            cleaned[column].astype(str).str.replace(r"[^0-9.\-]", "", regex=True),
            errors="coerce",
        ).fillna(0.0)
    _normalise_dates(cleaned)
    sector_columns = _find_columns(cleaned, ("sector", "industry", "vertical", "market"))
    for column in sector_columns:
        values = cleaned[column].astype("string").str.strip().str.lower()
        cleaned[column] = values.map(
            lambda value: "Energy Sector"
            if pd.notna(value)
            and ("solar" in value or "energy" in value or value == "sun")
            else "Mining"
            if pd.notna(value) and "min" in value
            else "Infrastructure"
            if pd.notna(value) and ("infra" in value or "construction" in value)
            else value.title() if pd.notna(value) else np.nan
        )
    for column in _find_columns(cleaned, ("status", "stage", "state")):
        cleaned[column] = cleaned[column].astype("string").str.strip().str.replace(
            r"\s+", " ", regex=True
        ).str.title()
    return _attach_quality(cleaned, "Deals")


def clean_work_orders_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean operational data and normalize common status variants."""
    cleaned = df.copy()
    cleaned.columns = [str(column).strip() for column in cleaned.columns]
    cleaned = cleaned.replace({"": np.nan, "-": np.nan, "n/a": np.nan, "na": np.nan})
    _normalise_canonical_columns(cleaned)
    _normalise_dates(cleaned)
    for column in _find_columns(cleaned, ("status", "stage", "state")):
        values = cleaned[column].astype("string").str.strip().str.lower()
        cleaned[column] = values.map(
            lambda value: "Completed"
            if pd.notna(value)
            and any(word in value for word in ("done", "finish", "complete", "closed"))
            else "In Progress"
            if pd.notna(value)
            and any(word in value for word in ("progress", "active", "started"))
            else "Cancelled"
            if pd.notna(value) and any(word in value for word in ("cancel", "void"))
            else value.title() if pd.notna(value) else np.nan
        )
    return _attach_quality(cleaned, "Work Orders")


def generate_data_quality_report(df1: pd.DataFrame, df2: pd.DataFrame) -> str:
    """Return concise, LLM-ready data-health context with explicit caveats."""
    reports = []
    for frame, fallback in ((df1, "Deals"), (df2, "Work Orders")):
        info = frame.attrs.get("data_quality") or _quality(frame, fallback)
        missing = info["missing_by_column"]
        details = ", ".join(f"{column}: {count}" for column, count in missing.items()) or "none"
        reports.append(
            f"{info['label']}: {info['rows']} rows, {info['columns']} columns, "
            f"{info['missing_cells']} missing cells. Missing by column: {details}."
        )
    return "Data Quality Report (treat missing metrics as caveats): " + " ".join(reports)
