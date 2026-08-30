# Streamlit Community Cloud Deployment Guide

## 1. Push the project to GitHub

Commit the application files, `requirements.txt`, tests, and workflow to the target repository. Do **not** commit API keys, `.env` files, or copied production data.

If the repository is public, rotate any credential immediately if one is ever exposed in Git history.

## 2. Create the Streamlit app

1. Sign in at [share.streamlit.io](https://share.streamlit.io/) with the GitHub account that can access the repository.
2. Select **Create app** (or **New app**).
3. Choose the GitHub repository, branch (`main`), and main file path: `app.py`.
4. Select the desired Streamlit Cloud region/runtime if prompted.
5. Open **Advanced settings** before deploying.

## 3. Add secrets securely

In **Advanced settings → Secrets**, paste TOML in the editor. Replace every placeholder with the real value and keep the quotes:

```toml
MONDAY_API_TOKEN = "your_monday_api_token"
OPENAI_API_KEY = "your_openai_api_key"
MONDAY_DEALS_BOARD_ID = "123456789"
MONDAY_WORK_ORDERS_BOARD_ID = "987654321"
```

The board IDs are strings by design. Save the secrets, then deploy or reboot the app. The application reads Streamlit Secrets first and falls back to environment variables. The values are not required in the repository and must never be placed in `app.py`, `README.md`, an issue, or a commit.

## 4. Verify the deployment

1. Wait for the build to finish and open the app URL.
2. Confirm the sidebar is populated or enter the values in the session-only sidebar fields.
3. Select **Load / refresh boards**.
4. Ask a simple question such as “How many work orders are completed?”
5. Select **Generate Leadership Update** and confirm the response contains pipeline, operational, and bottleneck sections in three paragraphs.

If loading fails, verify the token has read access to both boards, the IDs are numeric, and the repository’s `requirements.txt` is present at its root. Monday data is fetched only after configuration and is cached in the active Streamlit session.

## 5. Ongoing operation

Every push to the configured branch triggers a new Streamlit deployment. Pull requests and pushes to `main` also run `.github/workflows/main.yml`, which installs Python 3.10 dependencies and executes the offline pytest suite. No Monday.com or OpenAI credentials are needed by CI.
