"""Mojo Command Center v2 — research and operations dashboard.
Educational research tool only; not a broker-connected trading system.
"""
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
import pandas as pd
import requests
import feedparser
import streamlit as st

ROOT = Path(__file__).parent
DB = ROOT / "mojo_data.sqlite3"

st.set_page_config(page_title="Mojo Command Center", page_icon="🧭", layout="wide")

def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    # Additive migrations: existing tables and user data are preserved.
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS tasks(
          id INTEGER PRIMARY KEY, title TEXT NOT NULL, area TEXT NOT NULL,
          priority TEXT NOT NULL, due TEXT, done INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS trades(
          id INTEGER PRIMARY KEY, day TEXT NOT NULL, symbol TEXT NOT NULL,
          side TEXT NOT NULL, pnl REAL NOT NULL, setup TEXT, notes TEXT);
        CREATE TABLE IF NOT EXISTS content(
          id INTEGER PRIMARY KEY, day TEXT NOT NULL, channel TEXT NOT NULL,
          topic TEXT NOT NULL, status TEXT NOT NULL, campaign TEXT);
        CREATE TABLE IF NOT EXISTS feeds(
          id INTEGER PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS notes(
          id INTEGER PRIMARY KEY, created TEXT NOT NULL, category TEXT NOT NULL,
          title TEXT NOT NULL, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS campaigns(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, objective TEXT,
          channel TEXT, budget REAL NOT NULL DEFAULT 0, spend REAL NOT NULL DEFAULT 0,
          impressions INTEGER NOT NULL DEFAULT 0, engagements INTEGER NOT NULL DEFAULT 0,
          conversions INTEGER NOT NULL DEFAULT 0, start_date TEXT, end_date TEXT,
          notes TEXT);
        CREATE TABLE IF NOT EXISTS coverage(
          id INTEGER PRIMARY KEY, fetched_at TEXT NOT NULL, feed_title TEXT,
          title TEXT NOT NULL, url TEXT NOT NULL UNIQUE, published TEXT,
          summary TEXT, tone TEXT DEFAULT 'Unreviewed', status TEXT DEFAULT 'New',
          tags TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS projects(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, area TEXT NOT NULL,
          owner TEXT DEFAULT '', priority TEXT NOT NULL, status TEXT NOT NULL,
          progress INTEGER NOT NULL DEFAULT 0, due TEXT, next_action TEXT,
          notes TEXT);
        """)

def rows(sql, params=()):
    with connect() as c:
        return pd.read_sql_query(sql, c, params=params)

def write(sql, params=()):
    with connect() as c:
        c.execute(sql, params)

def download_csv(df, label, filename):
    st.download_button(label, df.to_csv(index=False).encode("utf-8"), filename, "text/csv")

def money(value):
    return f"{float(value):,.2f}"

init_db()
st.title("🧭 Mojo Command Center")
st.caption("v2 • Trading research • Marketing analytics • Media intelligence • AI • Projects")
section = st.sidebar.radio("Workspace", [
    "Overview", "Trading Lab", "Marketing & PR", "Media Monitor",
    "AI Workspace", "Productivity", "Notes & Backup"
])
st.sidebar.info("Do not add credentials or sensitive personal information. This app is not hardened for public internet access.")

if section == "Overview":
    tasks = rows("SELECT * FROM tasks")
    trades = rows("SELECT * FROM trades")
    content = rows("SELECT * FROM content")
    campaigns = rows("SELECT * FROM campaigns")
    coverage = rows("SELECT * FROM coverage")
    projects = rows("SELECT * FROM projects")
    cols = st.columns(5)
    cols[0].metric("Open tasks", int((tasks.done == 0).sum()) if len(tasks) else 0)
    cols[1].metric("Projects", len(projects[projects.status != "Completed"]) if len(projects) else 0)
    cols[2].metric("Trades logged", len(trades))
    cols[3].metric("Net recorded P/L", money(trades.pnl.sum()) if len(trades) else "0.00")
    cols[4].metric("Archived stories", len(coverage))
    st.subheader("Priority actions")
    if len(tasks):
        open_tasks = tasks[tasks.done == 0].copy()
        order = {"High": 0, "Medium": 1, "Low": 2}
        if len(open_tasks):
            open_tasks["priority_order"] = open_tasks.priority.map(order).fillna(3)
            st.dataframe(open_tasks.sort_values(["priority_order", "due"])[["title", "area", "priority", "due"]].head(10),
                         use_container_width=True, hide_index=True)
        else:
            st.success("No open tasks. Review project next actions.")
    else:
        st.info("Start by adding a task in Productivity.")
    if len(campaigns):
        st.subheader("Campaign snapshot")
        campaigns["budget_used_pct"] = campaigns.apply(lambda r: round(100*r.spend/r.budget, 1) if r.budget else 0, axis=1)
        st.dataframe(campaigns[["name", "channel", "budget", "spend", "budget_used_pct", "conversions"]],
                     use_container_width=True, hide_index=True)

elif section == "Trading Lab":
    st.subheader("Trade journal")
    with st.form("trade_form"):
        a, b, c = st.columns(3)
        day = a.date_input("Trade date", date.today())
        symbol = b.text_input("Symbol", "XAUUSD")
        side = c.selectbox("Side", ["Buy", "Sell"])
        pnl = st.number_input("Realized P/L (account currency)", value=0.0, step=1.0)
        setup = st.text_input("Setup / strategy", "EMA 9/21 + RSI")
        notes = st.text_area("Execution notes")
        if st.form_submit_button("Save trade"):
            if symbol.strip():
                write("INSERT INTO trades(day,symbol,side,pnl,setup,notes) VALUES(?,?,?,?,?,?)",
                      (day.isoformat(), symbol.strip().upper(), side, pnl, setup, notes))
                st.success("Trade saved.")
                st.rerun()
    df = rows("SELECT * FROM trades ORDER BY day,id")
    if len(df):
        a, b, c = st.columns(3)
        gross_profit = df.loc[df.pnl > 0, "pnl"].sum()
        gross_loss = abs(df.loc[df.pnl < 0, "pnl"].sum())
        a.metric("Net P/L", money(df.pnl.sum()))
        b.metric("Win rate", f"{100*(df.pnl > 0).mean():.1f}%")
        c.metric("Journal profit factor", f"{gross_profit/gross_loss:.2f}" if gross_loss else "N/A")
        st.line_chart(df.assign(cumulative=df.pnl.cumsum()).set_index("day")["cumulative"])
        st.dataframe(df, use_container_width=True, hide_index=True)
        download_csv(df, "Export trades CSV", "trades.csv")

    st.divider()
    st.subheader("Historical EMA/RSI backtest")
    st.warning("Research only. Uses next-bar position changes and close-to-close returns. It does not model broker spreads, slippage, swaps, leverage, lot sizing, contract specifications, intrabar stops, or execution failures. Test assumptions before making decisions.")
    uploaded = st.file_uploader("Upload candles CSV (Date optional; Close required)", type=["csv"], key="backtest_csv")
    a, b, c = st.columns(3)
    fast_n = a.number_input("Fast EMA", min_value=2, max_value=100, value=9)
    slow_n = b.number_input("Slow EMA", min_value=3, max_value=300, value=21)
    rsi_n = c.number_input("RSI period", min_value=2, max_value=100, value=14)
    d, e, f = st.columns(3)
    initial = d.number_input("Initial equity", min_value=1.0, value=1000.0, step=100.0)
    cost_bps = e.number_input("Estimated cost per side (bps)", min_value=0.0, max_value=500.0, value=5.0, step=1.0)
    allow_short = f.checkbox("Allow short positions", value=True)
    if uploaded:
        try:
            candles = pd.read_csv(uploaded)
            lookup = {str(x).strip().lower(): x for x in candles.columns}
            if "close" not in lookup:
                raise ValueError("CSV needs a Close column.")
            close = pd.to_numeric(candles[lookup["close"]], errors="coerce")
            valid = close.notna()
            close = close[valid].reset_index(drop=True)
            dates = candles.loc[valid].reset_index(drop=True)
            if len(close) < max(40, int(slow_n) + int(rsi_n) + 3):
                raise ValueError("Not enough valid closing prices for these settings.")
            if (close <= 0).any():
                raise ValueError("Closing prices must be positive.")
            ema_fast = close.ewm(span=int(fast_n), adjust=False).mean()
            ema_slow = close.ewm(span=int(slow_n), adjust=False).mean()
            delta = close.diff()
            gains = delta.clip(lower=0).ewm(alpha=1/int(rsi_n), adjust=False).mean()
            losses = (-delta.clip(upper=0)).ewm(alpha=1/int(rsi_n), adjust=False).mean()
            rs = gains / losses.replace(0, float("nan"))
            rsi = (100 - 100/(1+rs)).fillna(50)
            # Strategy: only open/flip on confirmed EMA crossover with RSI filter.
            buy = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1)) & (rsi > 50)
            sell = (ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1)) & (rsi < 50)
            desired = pd.Series(0.0, index=close.index)
            position = 0.0
            for i in range(len(close)):
                if buy.iloc[i]:
                    position = 1.0
                elif sell.iloc[i]:
                    position = -1.0 if allow_short else 0.0
                desired.iloc[i] = position
            # Shift by one bar to avoid applying signal to the candle that generated it.
            held = desired.shift(1).fillna(0.0)
            asset_returns = close.pct_change().fillna(0.0)
            turnover = held.diff().abs().fillna(held.abs())
            net_returns = held * asset_returns - turnover * (float(cost_bps) / 10000.0)
            equity = float(initial) * (1 + net_returns).cumprod()
            peak = equity.cummax()
            drawdown = equity / peak - 1
            result = pd.DataFrame({
                "Date": dates[lookup["date"]] if "date" in lookup else range(len(close)),
                "Close": close, f"EMA{int(fast_n)}": ema_fast, f"EMA{int(slow_n)}": ema_slow,
                f"RSI{int(rsi_n)}": rsi, "Signal": ["BUY" if buy.iloc[i] else "SELL" if sell.iloc[i] else "" for i in range(len(close))],
                "Position": held, "AssetReturn": asset_returns, "StrategyReturn": net_returns,
                "Equity": equity, "DrawdownPct": drawdown * 100
            })
            total_return = equity.iloc[-1] / float(initial) - 1
            bars = net_returns[held != 0]
            gross_pos = net_returns[net_returns > 0].sum()
            gross_neg = abs(net_returns[net_returns < 0].sum())
            st.subheader("Backtest results")
            m = st.columns(4)
            m[0].metric("Total return", f"{total_return*100:.2f}%")
            m[1].metric("Ending equity", money(equity.iloc[-1]))
            m[2].metric("Max drawdown", f"{abs(drawdown.min())*100:.2f}%")
            m[3].metric("Bar-return profit factor", f"{gross_pos/gross_neg:.2f}" if gross_neg else "N/A")
            st.caption(f"Bars: {len(close):,} · Signal events: {int((buy|sell).sum())} · Exposure bars: {int((held != 0).sum())} · Profit factor here is calculated from bar returns, not individual closed trades.")
            st.line_chart(result.set_index("Date")["Equity"])
            st.line_chart(result.set_index("Date")["DrawdownPct"])
            st.dataframe(result[result.Signal != ""], use_container_width=True, hide_index=True)
            download_csv(result, "Download backtest results CSV", "mojo_backtest.csv")
        except Exception as exc:
            st.error(f"Could not run backtest: {exc}")

elif section == "Marketing & PR":
    st.subheader("Content calendar")
    with st.form("content_form"):
        a, b = st.columns(2)
        day = a.date_input("Publish date", date.today())
        channel = b.selectbox("Channel", ["Instagram", "Facebook", "LinkedIn", "TikTok", "Website", "Email", "Other"])
        topic = st.text_input("Post / story idea")
        campaign = st.text_input("Campaign name")
        status = st.selectbox("Status", ["Idea", "Drafting", "Review", "Scheduled", "Published"])
        if st.form_submit_button("Add content"):
            if topic.strip():
                write("INSERT INTO content(day,channel,topic,status,campaign) VALUES(?,?,?,?,?)",
                      (day.isoformat(), channel, topic.strip(), status, campaign.strip()))
                st.rerun()
    content = rows("SELECT * FROM content ORDER BY day,id")
    if len(content):
        st.dataframe(content, use_container_width=True, hide_index=True)
        download_csv(content, "Export content calendar", "content_calendar.csv")
        labels = {f"#{r.id} · {r.topic}": int(r.id) for r in content.itertuples()}
        selected = st.selectbox("Update content status", list(labels))
        new_status = st.selectbox("New status", ["Idea", "Drafting", "Review", "Scheduled", "Published"])
        if st.button("Save status"):
            write("UPDATE content SET status=? WHERE id=?", (new_status, labels[selected]))
            st.rerun()
    st.divider()
    st.subheader("Campaign performance tracker")
    with st.form("campaign_form"):
        name = st.text_input("Campaign name")
        objective = st.text_input("Objective / audience")
        a, b, c = st.columns(3)
        channel = a.selectbox("Primary channel", ["Instagram", "Facebook", "LinkedIn", "TikTok", "Website", "Email", "Multi-channel", "Other"])
        budget = b.number_input("Budget", min_value=0.0, value=0.0, step=100.0)
        spend = c.number_input("Actual spend", min_value=0.0, value=0.0, step=50.0)
        d, e, f = st.columns(3)
        impressions = d.number_input("Impressions / reach", min_value=0, value=0, step=100)
        engagements = e.number_input("Engagements", min_value=0, value=0, step=10)
        conversions = f.number_input("Conversions / actions", min_value=0, value=0, step=1)
        g, h = st.columns(2)
        start = g.date_input("Start date", date.today())
        end = h.date_input("End date", date.today())
        cnotes = st.text_area("Learning / notes")
        if st.form_submit_button("Save campaign"):
            if name.strip():
                write("""INSERT INTO campaigns(name,objective,channel,budget,spend,impressions,engagements,conversions,start_date,end_date,notes)
                          VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                      (name.strip(), objective, channel, budget, spend, impressions, engagements, conversions, start.isoformat(), end.isoformat(), cnotes))
                st.success("Campaign saved.")
                st.rerun()
    camps = rows("SELECT * FROM campaigns ORDER BY id DESC")
    if len(camps):
        camps["engagement_rate_pct"] = camps.apply(lambda r: 100*r.engagements/r.impressions if r.impressions else 0, axis=1).round(2)
        camps["cost_per_conversion"] = camps.apply(lambda r: r.spend/r.conversions if r.conversions else None, axis=1)
        camps["budget_used_pct"] = camps.apply(lambda r: 100*r.spend/r.budget if r.budget else None, axis=1).round(1)
        st.dataframe(camps, use_container_width=True, hide_index=True)
        download_csv(camps, "Export campaign analytics", "campaign_analytics.csv")
    st.caption("Enter metrics from your platform reports. Calculations are only as accurate as the supplied data; definitions of reach, engagement and conversion differ by platform.")

elif section == "Media Monitor":
    st.subheader("RSS feed manager")
    with st.form("feed_form"):
        title = st.text_input("Feed name", "Google News — marine conservation")
        url = st.text_input("RSS URL", "https://news.google.com/rss/search?q=marine+conservation&hl=en&gl=US&ceid=US:en")
        if st.form_submit_button("Add feed"):
            if url.startswith(("https://", "http://")):
                try:
                    write("INSERT INTO feeds(title,url) VALUES(?,?)", (title.strip() or "RSS feed", url.strip()))
                    st.success("Feed saved.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.warning("This URL is already saved.")
            else:
                st.error("Use an HTTP(S) URL.")
    feeds = rows("SELECT * FROM feeds ORDER BY title")
    if len(feeds):
        st.dataframe(feeds, use_container_width=True, hide_index=True)
        selected_ids = st.multiselect("Feeds to fetch (blank means all)", feeds.id.astype(int).tolist())
        if st.button("Fetch and archive latest stories"):
            chosen = feeds[feeds.id.isin(selected_ids)] if selected_ids else feeds
            count = 0
            for feed in chosen.itertuples():
                parsed = feedparser.parse(feed.url)
                for item in parsed.entries[:30]:
                    link = item.get("link", "").strip()
                    title_item = item.get("title", "Untitled").strip()
                    if not link:
                        continue
                    published = item.get("published", item.get("updated", ""))
                    summary = item.get("summary", "")
                    try:
                        write("""INSERT INTO coverage(fetched_at,feed_title,title,url,published,summary)
                                  VALUES(?,?,?,?,?,?)""",
                              (datetime.now().isoformat(timespec="seconds"), feed.title, title_item, link, published, summary))
                        count += 1
                    except sqlite3.IntegrityError:
                        pass
            st.success(f"Archived {count} new stories. Previously archived URLs were skipped.")
            st.rerun()
    st.divider()
    st.subheader("Coverage archive")
    query = st.text_input("Search headlines, summaries, source, or tags")
    status_filter = st.selectbox("Editorial status", ["All", "New", "Reviewing", "Relevant", "Used", "Dismissed"])
    archive = rows("SELECT * FROM coverage ORDER BY id DESC")
    if query.strip() and len(archive):
        q = query.strip().lower()
        mask = archive.apply(lambda r: q in " ".join(str(r.get(k, "")) for k in ["title","summary","feed_title","tags"]).lower(), axis=1)
        archive = archive[mask]
    if status_filter != "All" and len(archive):
        archive = archive[archive.status == status_filter]
    if len(archive):
        st.dataframe(archive[["id","fetched_at","feed_title","title","published","tone","status","tags","url"]],
                     use_container_width=True, hide_index=True, column_config={"url": st.column_config.LinkColumn("Story URL")})
        download_csv(archive, "Export coverage archive", "media_coverage.csv")
        options = {f"#{r.id} · {r.title}": int(r.id) for r in archive.itertuples()}
        chosen = st.selectbox("Review a story", list(options))
        story_id = options[chosen]
        existing = archive[archive.id == story_id].iloc[0]
        a, b = st.columns(2)
        tone = a.selectbox("Tone / framing", ["Unreviewed", "Positive", "Neutral", "Negative", "Mixed"], index=["Unreviewed","Positive","Neutral","Negative","Mixed"].index(existing.tone) if existing.tone in ["Unreviewed","Positive","Neutral","Negative","Mixed"] else 0)
        status = b.selectbox("Status", ["New", "Reviewing", "Relevant", "Used", "Dismissed"], index=["New","Reviewing","Relevant","Used","Dismissed"].index(existing.status) if existing.status in ["New","Reviewing","Relevant","Used","Dismissed"] else 0)
        tags = st.text_input("Tags (comma-separated)", str(existing.tags or ""))
        if st.button("Save story review"):
            write("UPDATE coverage SET tone=?,status=?,tags=? WHERE id=?", (tone, status, tags, story_id))
            st.rerun()
    else:
        st.info("No archived stories match yet. Add an RSS feed and fetch headlines.")
    st.caption("RSS coverage is fetched on demand, not continuously. Headlines and summaries are third-party content; verify facts and context before reporting or publishing.")

elif section == "AI Workspace":
    st.subheader("AI drafting workspace")
    template = st.selectbox("Prompt template", ["PR media brief", "Social content plan", "Trading journal review", "Weekly prioritization", "Campaign post-mortem"])
    context = st.text_area("Context / source material", height=180)
    prompts = {
        "PR media brief": "Draft a factual PR media brief: headline, verified facts, stakeholder implications, risks, and questions requiring verification. Never invent sources.",
        "Social content plan": "Create five content concepts with audience, format, hook, draft caption, CTA, accessibility considerations, and success metric.",
        "Trading journal review": "Review this journal for process patterns, risk management gaps, and missing data. Do not promise profitable outcomes or recommend a specific trade.",
        "Weekly prioritization": "Turn these notes into a realistic prioritized weekly plan with next actions, time estimates, and dependencies.",
        "Campaign post-mortem": "Create a campaign evaluation using objectives, spend, reach, engagement, conversions, limitations, lessons, and recommended experiments. Do not claim causation from correlation."
    }
    prompt = prompts[template] + "\n\nContext:\n" + context
    st.code(prompt, language="text")
    provider = st.selectbox("Generation provider", ["Prompt only", "Local Ollama"])
    if provider == "Local Ollama":
        st.caption("Ollama must be reachable from the machine running this Streamlit app. On Streamlit Community Cloud, 127.0.0.1 refers to the cloud container—not your laptop. Do not enter API keys into this app.")
        model = st.text_input("Installed Ollama model", "llama3.2:1b")
        endpoint = st.text_input("Ollama endpoint", "http://127.0.0.1:11434")
        if st.button("Generate with Ollama"):
            try:
                response = requests.post(endpoint.rstrip("/") + "/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False}, timeout=120)
                response.raise_for_status()
                st.markdown(response.json().get("response", "No response returned."))
            except Exception as exc:
                st.error(f"Could not reach Ollama: {exc}. Check the endpoint and model.")
    else:
        st.info("Copy the prompt into your preferred AI tool. Source material is not sent anywhere by this workspace.")

elif section == "Productivity":
    st.subheader("Tasks")
    with st.form("task_form"):
        title = st.text_input("Task")
        a, b, c = st.columns(3)
        area = a.selectbox("Area", ["Trading", "Marketing & PR", "AI", "Career", "Personal", "Project"])
        priority = b.selectbox("Priority", ["High", "Medium", "Low"])
        due = c.date_input("Due date", date.today())
        if st.form_submit_button("Add task") and title.strip():
            write("INSERT INTO tasks(title,area,priority,due) VALUES(?,?,?,?)",
                  (title.strip(), area, priority, due.isoformat()))
            st.rerun()
    tasks = rows("SELECT * FROM tasks ORDER BY done,due,id")
    if len(tasks):
        st.dataframe(tasks, use_container_width=True, hide_index=True)
        ids = {f"#{r.id} · {r.title}": int(r.id) for r in tasks.itertuples()}
        chosen = st.selectbox("Select task", list(ids))
        a, b = st.columns(2)
        if a.button("Mark complete"):
            write("UPDATE tasks SET done=1 WHERE id=?", (ids[chosen],))
            st.rerun()
        if b.button("Reopen"):
            write("UPDATE tasks SET done=0 WHERE id=?", (ids[chosen],))
            st.rerun()
        download_csv(tasks, "Export tasks", "tasks.csv")
    st.divider()
    st.subheader("Project tracker")
    with st.form("project_form"):
        name = st.text_input("Project name")
        a, b, c = st.columns(3)
        area = a.selectbox("Project area", ["Trading", "Marketing & PR", "AI", "Career", "Personal", "Other"])
        owner = b.text_input("Owner")
        priority = c.selectbox("Project priority", ["High", "Medium", "Low"])
        d, e, f = st.columns(3)
        status = d.selectbox("Project status", ["Not started", "In progress", "Blocked", "On hold", "Completed"])
        progress = e.slider("Progress (%)", 0, 100, 0)
        due = f.date_input("Project due date", date.today())
        next_action = st.text_input("Next action")
        notes = st.text_area("Project notes")
        if st.form_submit_button("Save project") and name.strip():
            write("""INSERT INTO projects(name,area,owner,priority,status,progress,due,next_action,notes)
                      VALUES(?,?,?,?,?,?,?,?,?)""",
                  (name.strip(), area, owner, priority, status, progress, due.isoformat(), next_action, notes))
            st.rerun()
    projects = rows("SELECT * FROM projects ORDER BY due,id")
    if len(projects):
        st.dataframe(projects, use_container_width=True, hide_index=True)
        download_csv(projects, "Export projects", "projects.csv")
        ids = {f"#{r.id} · {r.name}": int(r.id) for r in projects.itertuples()}
        chosen = st.selectbox("Update project", list(ids))
        new_status = st.selectbox("Set project status", ["Not started", "In progress", "Blocked", "On hold", "Completed"])
        new_progress = st.slider("Set project progress (%)", 0, 100, 0, key="project_update_progress")
        if st.button("Update project"):
            if new_status == "Completed":
                new_progress = 100
            write("UPDATE projects SET status=?,progress=? WHERE id=?", (new_status, new_progress, ids[chosen]))
            st.rerun()

elif section == "Notes & Backup":
    st.subheader("Research notes")
    with st.form("note_form"):
        title = st.text_input("Title")
        category = st.selectbox("Category", ["Research", "PR", "Trading", "Ideas", "Career", "Personal"])
        body = st.text_area("Note", height=180)
        if st.form_submit_button("Save note") and title.strip():
            write("INSERT INTO notes(created,category,title,body) VALUES(?,?,?,?)",
                  (datetime.now().isoformat(timespec="seconds"), category, title.strip(), body))
            st.rerun()
    notes = rows("SELECT * FROM notes ORDER BY id DESC")
    for n in notes.itertuples():
        with st.expander(f"{n.category} · {n.title}"):
            st.write(n.body)
    st.divider()
    st.subheader("Backup and exports")
    tables = ["tasks", "trades", "content", "feeds", "notes", "campaigns", "coverage", "projects"]
    bundle = {"exported_at": datetime.now().isoformat(timespec="seconds"),
              "schema_version": 2,
              "tables": {table: rows(f"SELECT * FROM {table}").to_dict(orient="records") for table in tables}}
    st.download_button("Download full JSON data export", json.dumps(bundle, indent=2, default=str),
                       file_name="mojo_command_center_backup_v2.json", mime="application/json")
    st.caption("This is an archival export, not a one-click restore. Also keep a separate copy of mojo_data.sqlite3. Never commit the database or private exports to GitHub.")
