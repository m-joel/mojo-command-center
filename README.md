# Mojo Command Center

A local-first personal dashboard for trading research, marketing and PR, AI drafting, tasks and notes. Built with Streamlit, SQLite and Python. No cloud account required.

## Features
- **Trading Lab:** manual P/L journal, win rate, profit factor, cumulative P/L, CSV exports, EMA 9/21 + RSI(14) signal explorer on uploaded OHLC CSV.
- **Marketing & PR:** campaign content planner, status updates and CSV exports.
- **Media Monitor:** fetch headlines from trusted public RSS feeds on demand.
- **AI Workspace:** ready-to-copy prompt templates and optional local Ollama generation.
- **Productivity:** tasks, due dates and priorities.
- **Notes & Backup:** notes and JSON data export.

## Windows quick start
1. Install Python 3.10+ from python.org.
2. Extract the ZIP. Open PowerShell in the extracted folder.
3. Run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

4. Open http://localhost:8501 .

No Docker needed. An internet connection is needed only for initial package installation, RSS fetching, and downloading Ollama/models.

## Android access
This app runs on Windows. To access it from Android on the same trusted Wi-Fi network, run:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 0.0.0.0
```

Find your laptop's LAN IP using `ipconfig` and open `http://LAPTOP_IP:8501` on Android. You may need to allow inbound TCP port 8501 on Windows Firewall **only on Private networks**. **There is no authentication built in**: any device able to reach that port can see and edit your data. Do not use public Wi-Fi, port forwarding, or expose this service to the internet. Prefer a private VPN with authentication for remote access. If you cannot secure the network, use Windows localhost only.

The Windows computer must be powered on while Android is accessing it. Android-only installation is not part of this first version.

## Optional local AI
Install Ollama from https://ollama.com/download and run:

```powershell
ollama pull llama3.2:1b
```

Then open the AI Workspace. The app contacts Ollama at `http://127.0.0.1:11434` from the Windows host. Ollama is optional; prompt templates work without it. Local AI quality and speed depend on hardware.

## CSV format for EMA/RSI explorer
Provide at least 40 rows, with a `Close` column (case insensitive); `Date,Open,High,Low,Close` is recommended. Data must be ordered oldest to newest. The explorer shows EMA crossover signals with RSI > 50 for buys and RSI < 50 for sells **on the crossover candle**. It is **not** a profitability backtest and does not implement stops, spreads, execution or live trading. Confirm any intended trading rules before relying on signals.

## Important limitations
- Trading performance is based on manually recorded realized P/L; there is no broker integration or trade verification.
- RSS sources are fetched on demand, not scheduled. Some feeds block automated readers.
- The AI feature does not send data to an external AI service, but you should review the local Ollama service's settings and security before enabling LAN access.
- Data is stored in `mojo_data.sqlite3` in the application folder. Back it up regularly. Do not commit the database, credentials, or sensitive exports to GitHub.
- This is an MVP, not a hardened multi-user or internet-facing product.

## GitHub upload
Create a **private** repository named `mojo-command-center`, then upload `app.py`, `requirements.txt`, `README.md`, and `.gitignore` from the ZIP. Never upload `mojo_data.sqlite3`.

## License
MIT — see LICENSE.
