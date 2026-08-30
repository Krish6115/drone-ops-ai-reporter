"""Read-only Monday.com GraphQL API v2 client with cursor pagination."""

from __future__ import annotations

import time
from collections import deque
from typing import Any, Dict, List, Optional

import pandas as pd
import requests


MONDAY_API_URL = "https://api.monday.com/v2"
PAGE_SIZE = 500


class MondayAPIError(RuntimeError):
    """Raised when Monday.com returns an unusable response."""


class MondayClient:
    """Small, read-only GraphQL client for Monday board item extraction."""

    def __init__(
        self,
        api_token: str,
        timeout: int = 30,
        max_retries: int = 4,
        requests_per_minute: int = 60,
    ) -> None:
        if not api_token or not api_token.strip():
            raise ValueError("A Monday.com API token is required.")
        self.timeout = timeout
        self.max_retries = max_retries
        self.requests_per_minute = requests_per_minute
        self._request_times: deque[float] = deque()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": api_token.strip(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def _respect_rate_limit(self) -> None:
        """Allow at most 60 requests in any rolling 60-second window."""
        now = time.monotonic()
        while self._request_times and now - self._request_times[0] >= 60:
            self._request_times.popleft()
        if len(self._request_times) >= self.requests_per_minute:
            wait_for = 60 - (now - self._request_times[0]) + 0.05
            time.sleep(max(wait_for, 0))
        self._request_times.append(time.monotonic())

    def _post(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {"query": query, "variables": variables or {}}
        for attempt in range(self.max_retries + 1):
            self._respect_rate_limit()
            try:
                response = self.session.post(
                    MONDAY_API_URL, json=payload, timeout=self.timeout
                )
            except requests.RequestException as exc:
                if attempt >= self.max_retries:
                    raise MondayAPIError(f"Monday.com request failed: {exc}") from exc
                time.sleep(2**attempt)
                continue

            if response.status_code == 500 and attempt < self.max_retries:
                time.sleep(2**attempt)
                continue
            if response.status_code >= 400:
                raise MondayAPIError(
                    f"Monday.com HTTP {response.status_code}: {response.text[:500]}"
                )
            try:
                body = response.json()
            except ValueError as exc:
                raise MondayAPIError("Monday.com returned invalid JSON.") from exc
            if body.get("errors"):
                message = "; ".join(str(error.get("message", error)) for error in body["errors"])
                raise MondayAPIError(message)
            return body.get("data", {})
        raise MondayAPIError("Monday.com request exhausted its retry budget.")

    def fetch_board(self, board_id: str) -> pd.DataFrame:
        """Fetch every item from a board using items_page then next_items_page."""
        if not str(board_id).strip().isdigit():
            raise ValueError(f"Board ID must be numeric; received {board_id!r}.")

        initial_query = """
        query GetBoardItems($board_id: [ID!], $limit: Int!) {
          boards(ids: $board_id) {
            items_page(limit: $limit) {
              cursor
              items {
                id
                name
                column_values { id type text column { title } }
              }
            }
          }
        }
        """
        next_query = """
        query GetNextItems($cursor: String!, $limit: Int!) {
          next_items_page(cursor: $cursor, limit: $limit) {
            cursor
            items {
              id
              name
              column_values { id type text column { title } }
            }
          }
        }
        """
        data = self._post(initial_query, {"board_id": [str(board_id)], "limit": PAGE_SIZE})
        boards = data.get("boards", [])
        if not boards:
            raise MondayAPIError(f"No Monday.com board found for ID {board_id}.")
        page = boards[0].get("items_page", {})
        items: List[Dict[str, Any]] = list(page.get("items", []))
        cursor = page.get("cursor")

        while cursor:
            try:
                next_data = self._post(next_query, {"cursor": cursor, "limit": PAGE_SIZE})
            except MondayAPIError as exc:
                if "cursor" in str(exc).lower() or "expired" in str(exc).lower():
                    raise MondayAPIError(
                        "Monday.com pagination cursor expired; please reload the boards."
                    ) from exc
                raise
            page = next_data.get("next_items_page", {})
            items.extend(page.get("items", []))
            cursor = page.get("cursor")

        return self._items_to_dataframe(items)

    @staticmethod
    def _items_to_dataframe(items: List[Dict[str, Any]]) -> pd.DataFrame:
        rows: List[Dict[str, Any]] = []
        for item in items:
            row: Dict[str, Any] = {"Item ID": item.get("id"), "Item Name": item.get("name")}
            for column in item.get("column_values", []):
                col_info = column.get("column") or {}
                title = col_info.get("title") or column.get("title") or column.get("id") or "Unknown Column"
                row[title] = column.get("text")
            rows.append(row)
        return pd.DataFrame(rows)
