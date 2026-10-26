"""Mojo Command Center — local-first personal operations dashboard."""
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
import pandas as pd
import requests
import feedparser
import streamlit as st

ROOT = Path(__file__).parent
DB = ROOT / 'mojo_data.sqlite3'
st.set_page_config(page_title='Mojo Command Center', page_icon='🧭', layout='wide')


def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY, title TEXT NOT NULL, area TEXT NOT NULL, priority TEXT NOT NULL, due TEXT, done INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS trades(id INTEGER PRIMARY KEY, day TEXT NOT NULL, symbol TEXT NOT NULL, side TEXT NOT NULL, pnl REAL NOT NULL, setup TEXT, notes TEXT);
        CREATE TABLE IF NOT EXISTS content(id INTEGER PRIMARY KEY, day TEXT NOT NULL, channel TEXT NOT NULL, topic TEXT NOT NULL, status TEXT NOT NULL, campaign TEXT);
        CREATE TABLE IF NOT EXISTS feeds(id INTEGER PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL UNIQUE);
        CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, created TEXT NOT NULL, category TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL);
        ''')


def rows(sql, params=()):
    with connect() as c:
        return pd.read_sql_query(sql, c, params=params)


def write(sql, params=()):
    with connect() as c:
        c.execute(sql, params)


def csv_download(df, label, name):
    st.download_button(label, df.to_csv(index=False).encode('utf-8'), file_name=name, mime='text/csv')

init_db()
st.title('🧭 Mojo Command Center')
st.caption('Local-first • Trading • Marketing & PR • AI • Productivity')
section = st.sidebar.radio('Workspace', ['Overview', 'Trading Lab', 'Marketing & PR', 'Media Monitor', 'AI Workspace', 'Productivity', 'Notes & Backup'])
st.sidebar.info('Your data stays in a local SQLite file. Do not expose this app directly to the public internet.')

if section == 'Overview':
    t = rows('SELECT * FROM tasks')
    trades = rows('SELECT * FROM trades')
    content = rows('SELECT * FROM content')
    a,b,c,d = st.columns(4)
    a.metric('Open tasks', int((t.done == 0).sum()) if len(t) else 0)
    b.metric('Trades logged', len(trades))
    c.metric('Net trading P/L', f"{trades.pnl.sum():,.2f}" if len(trades) else '0.00')
    d.metric('Content items', len(content))
    st.subheader('Next actions')
    if len(t):
        st.dataframe(t[t.done == 0][['title','area','priority','due']].sort_values('due'), use_container_width=True, hide_index=True)
    else: st.info('Add your first task under Productivity.')

elif section == 'Trading Lab':
    st.subheader('Trading journal')
    with st.form('trade'):
        a,b,c = st.columns(3)
        day = a.date_input('Trade date', date.today())
        symbol = b.text_input('Symbol', 'XAUUSD')
        side = c.selectbox('Side', ['Buy','Sell'])
        pnl = st.number_input('Realized P/L (account currency)', value=0.0, step=1.0)
        setup = st.text_input('Setup / strategy', 'EMA 9/21 + RSI')
        notes = st.text_area('Notes')
        if st.form_submit_button('Save trade'):
            if symbol.strip():
                write('INSERT INTO trades(day,symbol,side,pnl,setup,notes) VALUES(?,?,?,?,?,?)',(day.isoformat(),symbol.strip().upper(),side,pnl,setup,notes))
                st.success('Trade saved'); st.rerun()
    df = rows('SELECT * FROM trades ORDER BY day,id')
    if len(df):
        a,b,c = st.columns(3)
        a.metric('Net P/L', f'{df.pnl.sum():.2f}')
        b.metric('Win rate', f'{100*(df.pnl>0).mean():.1f}%')
        c.metric('Profit factor', f"{df.loc[df.pnl>0,'pnl'].sum()/abs(df.loc[df.pnl<0,'pnl'].sum()):.2f}" if (df.pnl<0).any() else 'N/A')
        st.line_chart(df.assign(cumulative=df.pnl.cumsum()).set_index('day')['cumulative'])
        st.dataframe(df, use_container_width=True, hide_index=True)
        csv_download(df,'Export trades CSV','trades.csv')
    st.divider()
    st.subheader('EMA + RSI historical signal explorer')
    st.caption('Research only: close-to-close illustrative returns; no spread, slippage, financing, position sizing or stop-loss simulation. Not a broker-grade backtest.')
    uploaded = st.file_uploader('Upload OHLC candles CSV (Date optional, Close required)', type='csv')
    if uploaded:
        try:
            candles = pd.read_csv(uploaded)
            cols = {x.lower():x for x in candles.columns}
            if 'close' not in cols: raise ValueError('CSV must contain a Close column.')
            close = pd.to_numeric(candles[cols['close']],errors='coerce').dropna().reset_index(drop=True)
            if len(close)<40: raise ValueError('Please provide at least 40 valid closing prices.')
            fast=close.ewm(span=9,adjust=False).mean()
            slow=close.ewm(span=21,adjust=False).mean()
            delta=close.diff(); gain=delta.clip(lower=0).ewm(alpha=1/14,adjust=False).mean(); loss=(-delta.clip(upper=0)).ewm(alpha=1/14,adjust=False).mean()
            rs=gain/loss.replace(0,float('nan'))
            rsi=(100-100/(1+rs)).fillna(50)
            bullish=(fast>slow)&(fast.shift(1)<=slow.shift(1))&(rsi>50)
            bearish=(fast<slow)&(fast.shift(1)>=slow.shift(1))&(rsi<50)
            signals=pd.DataFrame({'Close':close,'EMA9':fast,'EMA21':slow,'RSI14':rsi,'Signal':['BUY' if x else 'SELL' if y else '' for x,y in zip(bullish,bearish)]})
            st.line_chart(signals[['Close','EMA9','EMA21']]); st.dataframe(signals[signals.Signal!=''],hide_index=False,use_container_width=True)
            csv_download(signals,'Download indicator and signal CSV','signals.csv')
        except Exception as exc: st.error(f'Cannot analyze this file: {exc}')

elif section == 'Marketing & PR':
    st.subheader('Content and campaign planner')
    with st.form('content'):
        a,b = st.columns(2)
        day=a.date_input('Publish date',date.today()); channel=b.selectbox('Channel',['Instagram','Facebook','LinkedIn','TikTok','Website','Other'])
        topic=st.text_input('Post / story idea'); campaign=st.text_input('Campaign / client')
        status=st.selectbox('Status',['Idea','Drafting','Review','Scheduled','Published'])
        if st.form_submit_button('Add content'):
            if topic.strip():
                write('INSERT INTO content(day,channel,topic,status,campaign) VALUES(?,?,?,?,?)',(day.isoformat(),channel,topic.strip(),status,campaign))
                st.success('Content added'); st.rerun()
    df=rows('SELECT * FROM content ORDER BY day')
    if len(df):
        st.dataframe(df,use_container_width=True,hide_index=True)
        csv_download(df,'Export content calendar','content_calendar.csv')
        ids=dict(zip(df.apply(lambda x:f"#{x['id']} · {x['topic']}",axis=1),df.id))
        chosen=st.selectbox('Update content item',list(ids))
        new=st.selectbox('New status',['Idea','Drafting','Review','Scheduled','Published'])
        if st.button('Update status'):
            write('UPDATE content SET status=? WHERE id=?',(new,int(ids[chosen])));st.rerun()
    st.info('Publishing to social platforms is not automated; platform APIs and permissions are required.')

elif section == 'Media Monitor':
    st.subheader('Public RSS media monitor')
    with st.form('feed'):
        title=st.text_input('Feed name', 'Google News topic')
        url=st.text_input('RSS URL', 'https://news.google.com/rss/search?q=marine+conservation&hl=en&gl=US&ceid=US:en')
        if st.form_submit_button('Add feed'):
            if url.startswith(('https://','http://')):
                try: write('INSERT INTO feeds(title,url) VALUES(?,?)',(title,url));st.success('Feed saved');st.rerun()
                except sqlite3.IntegrityError: st.warning('Feed already saved.')
            else: st.error('Use an HTTP(S) URL.')
    feeds=rows('SELECT * FROM feeds')
    if len(feeds):
        st.dataframe(feeds,use_container_width=True,hide_index=True)
        if st.button('Fetch latest headlines'):
            for _,f in feeds.iterrows():
                st.markdown(f"**{f['title']}**")
                try:
                    # feedparser handles feeds; only add trusted RSS URLs.
                    parsed=feedparser.parse(f['url'])
                    for item in parsed.entries[:10]:
                        st.markdown(f"- [{item.get('title','Untitled')}]({item.get('link','#')})")
                    if not parsed.entries: st.caption('No items returned.')
                except Exception as exc: st.warning(str(exc))
    st.caption('Requires internet. Verify stories before publishing or sharing. Use only trusted feed URLs.')

elif section == 'AI Workspace':
    st.subheader('AI drafting assistant (optional local Ollama)')
    template=st.selectbox('Prompt template',['PR media brief','Instagram content calendar','Trading journal review','Weekly prioritization'])
    context=st.text_area('Your context / source material',height=160)
    prompts={
      'PR media brief':'Draft a factual PR media brief with headline, verified facts, potential reputational implications, and questions requiring verification. Do not invent sources.',
      'Instagram content calendar':'Create 5 Instagram content concepts with target audience, format, hook, caption, CTA and success metric.',
      'Trading journal review':'Analyze this trading journal for patterns, risk issues, and missing data. Do not promise profitable outcomes.',
      'Weekly prioritization':'Turn these notes into a realistic prioritized weekly plan with next actions and dependencies.'}
    prompt=prompts[template]+'\n\nContext:\n'+context
    st.code(prompt,language='text')
    st.caption('Start Ollama separately on Windows, then use a locally installed model.')
    model=st.text_input('Installed Ollama model', 'llama3.2:1b')
    if st.button('Generate with local Ollama'):
        try:
            response=requests.post('http://127.0.0.1:11434/api/generate',json={'model':model,'prompt':prompt,'stream':False},timeout=120)
            response.raise_for_status();st.markdown(response.json().get('response','No response'))
        except Exception as exc: st.error(f'Ollama unavailable: {exc}. Install Ollama and pull the selected model first.')

elif section == 'Productivity':
    st.subheader('Tasks and priorities')
    with st.form('task'):
        title=st.text_input('Task')
        a,b,c=st.columns(3)
        area=a.selectbox('Area',['Trading','Marketing & PR','AI','Personal','Career'])
        priority=b.selectbox('Priority',['High','Medium','Low'])
        due=c.date_input('Due date',date.today())
        if st.form_submit_button('Add task'):
            if title.strip():write('INSERT INTO tasks(title,area,priority,due) VALUES(?,?,?,?)',(title.strip(),area,priority,due.isoformat()));st.rerun()
    df=rows('SELECT * FROM tasks ORDER BY done,due,id')
    if len(df):
        st.dataframe(df,use_container_width=True,hide_index=True)
        ids=dict(zip(df.apply(lambda x:f"#{x['id']} · {x['title']}",axis=1),df.id))
        chosen=st.selectbox('Task',list(ids))
        a,b=st.columns(2)
        if a.button('Mark complete'):write('UPDATE tasks SET done=1 WHERE id=?',(int(ids[chosen]),));st.rerun()
        if b.button('Reopen'):write('UPDATE tasks SET done=0 WHERE id=?',(int(ids[chosen]),));st.rerun()
        csv_download(df,'Export tasks','tasks.csv')

elif section == 'Notes & Backup':
    st.subheader('Research notes')
    with st.form('note'):
        title=st.text_input('Title'); category=st.selectbox('Category',['Research','PR','Trading','Ideas','Personal'])
        body=st.text_area('Note',height=180)
        if st.form_submit_button('Save note') and title.strip():
            write('INSERT INTO notes(created,category,title,body) VALUES(?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),category,title.strip(),body));st.rerun()
    df=rows('SELECT * FROM notes ORDER BY id DESC')
    for _,n in df.iterrows():
        with st.expander(f"{n['category']} · {n['title']}"):st.write(n['body'])
    st.divider();st.subheader('Export all data')
    bundle={table:rows(f'SELECT * FROM {table}').to_dict(orient='records') for table in ['tasks','trades','content','feeds','notes']}
    st.download_button('Download JSON backup',json.dumps(bundle,indent=2),file_name='mojo_backup.json',mime='application/json')
    st.caption('Back up the SQLite file separately for full restoration. This JSON export is for archival and migration, not one-click restore.')
