"""LangChain orchestration for conversational, two-board BI analysis."""

from __future__ import annotations

from typing import Optional

import pandas as pd
from langchain_experimental.agents import create_pandas_dataframe_agent
from langchain_openai import ChatOpenAI


BASE_PROMPT = """You are the Chief of Staff and Lead BI Analyst for a commercial drone analytics company serving the mining and solar sectors.
You have two pandas DataFrames: the Deals board and the Work Orders board, in that order. Always provide analytical context, state assumptions, and distinguish observed facts from inferences.
Use Python/pandas against the provided DataFrames for every quantitative answer; do not invent values. If a metric relies on columns with missing data based on the provided Data Quality Report, you MUST append a caveat.
When the user asks for a Leadership Update, autonomously cross-reference BOTH boards and return exactly three concise paragraphs: (1) macro pipeline health, (2) operational execution status and bandwidth, and (3) key bottlenecks, risks, and recommended leadership actions. If required fields are absent, say so explicitly.

{quality_report}
"""


class BIAnalyst:
    """Build and invoke a Pandas agent over the two cleaned board DataFrames."""

    def __init__(
        self,
        deals: pd.DataFrame,
        work_orders: pd.DataFrame,
        openai_api_key: str,
        quality_report: str,
    ) -> None:
        if not openai_api_key or not openai_api_key.strip():
            raise ValueError("An OpenAI API key is required.")
        self.deals = deals
        self.work_orders = work_orders
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.2,
            api_key=openai_api_key.strip(),
        )
        self.executor = create_pandas_dataframe_agent(
            llm,
            [deals, work_orders],
            agent_type="tool-calling",
            prefix=BASE_PROMPT.format(quality_report=quality_report),
            allow_dangerous_code=True,
            verbose=False,
            max_iterations=12,
            max_execution_time=90,
        )

    def ask(self, question: str) -> str:
        """Answer a question and normalize LangChain's output shape."""
        if not question or not question.strip():
            return "Please enter a business question."
        try:
            result = self.executor.invoke({"input": question.strip()})
            return str(result.get("output", result))
        except Exception as exc:  # surfaced cleanly in the UI, without leaking secrets
            return f"I could not complete that analysis. Technical detail: {exc}"
