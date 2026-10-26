# Mojo Command Center v2

A Streamlit + SQLite personal operations dashboard for trading research, marketing and PR analytics, media monitoring, AI-assisted drafting, tasks, projects, notes, and exports.

## v2 additions
- Historical EMA/RSI backtest with configurable EMA/RSI periods, next-bar signal application, estimated transaction cost, equity curve, drawdown, return metrics, and CSV export.
- Marketing campaign tracker with budget, spend, impressions, engagements, conversions, engagement rate, cost per conversion, and budget usage.
- Persistent RSS coverage archive with duplicate URL prevention, search, editorial tone/status, tags, and CSV export.
- Project tracker with owner, priority, status, progress, due date, and next action.
- Expanded JSON backup containing all eight data tables.
- Additive SQLite schema migration: existing tables are preserved.

## Deploy on Streamlit Community Cloud
1. Download and extract `mojo-command-center-v2-upload.zip`.
2. In GitHub, open `m-joel/mojo-command-center`.
3. Use **Add file → Upload files** to upload `app.py`, `requirements.txt`, and `README.md` from the extracted `mojo-command-center-v2` folder.
4. Review the changed files and commit to a new branch if the GitHub interface offers that choice. Prefer a branch named `feature/mojo-command-center-2`, then open a pull request to `main`. If branch selection is not available, create the branch first using GitHub's branch selector, then upload the files there.
5. After review/merge, Streamlit Community Cloud should redeploy from the repository. Check app logs if dependencies or deployment fail.

**Important:** the app uses a local SQLite file. Streamlit Community Cloud filesystems may be ephemeral; persistence across restarts/redeploys is not guaranteed. Keep regular exports, and consider a managed database before relying on this for important records.

## Local Windows run
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```
Open `http://localhost:8501`.

## Backtest assumptions and limits
The backtest uses the uploaded closing-price series. EMA crossover plus RSI > 50 triggers a long position; the opposite crossover with RSI < 50 triggers a short or flat position depending on the setting. Positions are shifted one bar so signals are not applied to the same candle that created them. Costs are approximated as basis points per side on position turnover.

It is not a broker-grade simulator. It does not model spread, variable slippage, swaps/funding, margin, leverage, contract size, lot sizing, intrabar stops, gaps, order rejection, or instrument-specific execution. Profit factor is based on bar returns, not individual closed trades. Past results do not predict future returns. Validate data ordering and strategy rules before making decisions.

## AI limitations
Prompt-only mode works anywhere. Ollama generation only works if the Ollama endpoint is reachable from the machine/container running Streamlit. On Streamlit Community Cloud, `127.0.0.1` refers to the cloud container, not your personal computer. Do not expose Ollama publicly or paste API keys into the app.

## Security
This is a single-user prototype without authentication. Do not expose it directly to the public internet. Never upload `mojo_data.sqlite3`, credentials, tokens, or sensitive exports to GitHub.
