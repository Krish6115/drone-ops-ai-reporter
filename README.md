# Skylark Drone Analytics BI Agent

A read-only Streamlit business-intelligence agent for the Monday.com **Deals** and **Work Orders** boards. It fetches live board data through Monday.com GraphQL API v2, cleans inconsistent operational inputs with pandas, and lets leadership ask natural-language questions through a LangChain pandas agent.

## Architecture

`app.py` owns the chat UI and session cache. `monday_client.py` performs authenticated GraphQL reads with 500-item cursor pagination, rolling rate limiting, retries, and cursor-expiration errors. `data_cleaner.py` preserves source columns, normalizes financial values, dates, sectors, statuses, and attaches missing-data metadata. `agent.py` supplies both cleaned DataFrames and the quality report to a GPT-4o LangChain pandas agent.

The app makes no write requests to Monday.com and contains no embedded CSV or business data.

## Local setup

1. Use Python 3.10+ and create an environment: `python -m venv .venv`.
2. Activate it, then run `pip install -r requirements.txt`.
3. Start the app: `streamlit run app.py`.
4. Enter a Monday API token, OpenAI API key, Deals board ID, and Work Orders board ID in the sidebar.
5. Select **Load / refresh boards**, then ask questions or select **Generate Leadership Update**.

Environment variables are also supported: `MONDAY_API_TOKEN`, `OPENAI_API_KEY`, `MONDAY_DEALS_BOARD_ID`, and `MONDAY_WORK_ORDERS_BOARD_ID`.

## Streamlit Community Cloud

For a concise click-by-click deployment and secrets checklist, see [DEPLOYMENT.md](DEPLOYMENT.md).

Push this directory to a private or public GitHub repository, create a new Streamlit Community Cloud app using `app.py` as the entry point, and set the Python version to 3.10 or newer. Add the dependencies from `requirements.txt`. Prefer Streamlit Secrets for credentials:

```toml
MONDAY_API_TOKEN = "your-monday-token"
OPENAI_API_KEY = "your-openai-key"
MONDAY_DEALS_BOARD_ID = "123456789"
MONDAY_WORK_ORDERS_BOARD_ID = "987654321"
```

The sidebar remains available for session-level overrides. Never commit tokens to source control. Review LangChain's code-execution security guidance before exposing the app to untrusted users; the pandas agent is deliberately enabled to execute generated analysis code over in-memory DataFrames.

## Data caveats

Column matching is intentionally heuristic because Monday column titles vary by office. Financial columns containing revenue, amount, value, budget, price, or cost are parsed as numbers. Date-like columns are parsed with pandas and invalid values become missing. Missing-cell counts are passed into every agent prompt, and answers are instructed to state caveats when relevant.

## Deployment notes

Monday cursors expire after a limited period (documented by Monday as 60 minutes); the client reports an actionable reload error if that happens. Data is fetched once per configured Streamlit session and cached in session state, so changing a board ID or credential triggers a fresh read.
