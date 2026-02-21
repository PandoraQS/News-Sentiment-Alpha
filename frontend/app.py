import streamlit as st
import redis
import json
import requests
import pandas as pd
import altair as alt
from streamlit_autorefresh import st_autorefresh
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from datetime import datetime

st.set_page_config(page_title="Sentiment Alpha", layout="wide")

r = redis.Redis(host='redis-cache', port=6379, db=0, decode_responses=True)
OLLAMA_URL = "http://host.docker.internal:11434/api/generate"

if 'cross_history' not in st.session_state:
    st.session_state.cross_history = pd.DataFrame({
        'Time': pd.Series(dtype='datetime64[ns]'),
        'Sentiment': pd.Series(dtype='float'),
        'Spread': pd.Series(dtype='float')
    })

if 'ollama_results' not in st.session_state:
    st.session_state.ollama_results = {}

def ask_ollama(prompt, is_bulk=False):
    context = "Summarize market sentiment in 3 points:" if is_bulk else "Explain market impact:"
    try:
        st.toast("Neural Engine: Connecting to Llama 3...", icon="🧠")
        response = requests.post(OLLAMA_URL, json={
            "model": "llama3", "prompt": f"{context} {prompt}", "stream": False
        }, timeout=120)
        
        if response.status_code == 200:
            st.toast("Intelligence Synced: Analysis Ready", icon="✅")
            return response.json().get('response', "Error: Empty response.")
        else:
            st.error(f"Engine Error: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Core Connection Failed: {str(e)}")
        return None

def get_arbitrage_data():
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']
    data = []
    for s in symbols:
        rb = r.get(f"ticker:binance:{s}")
        rk = r.get(f"ticker:kraken:{s}")
        if rb and rk:
            b, k = json.loads(rb), json.loads(rk)
            spread = ((float(k['bid']) - float(b['ask'])) / float(b['ask'])) * 100
            data.append({"Symbol": s, "Spread": float(spread)})
    return pd.DataFrame(data)

@st.fragment(run_every=2)
def render_dynamic_charts():
    df_arb = get_arbitrage_data()
    keys = r.keys("news:*")
    news_list = [json.loads(r.get(k)) for k in keys]
    
    if news_list and not df_arb.empty:
        full_df = pd.DataFrame(news_list)
        full_df['score'] = full_df['sentiment'].map({'positive': 1, 'neutral': 0, 'negative': -1})
        avg_index = full_df['score'].mean()
        avg_spread_val = df_arb["Spread"].mean()

        new_entry = pd.DataFrame({
            'Time': [datetime.now()],
            'Sentiment': [float(avg_index)],
            'Spread': [float(avg_spread_val)]
        })
        st.session_state.cross_history = pd.concat([st.session_state.cross_history, new_entry]).tail(100)

        st.subheader("Cross-Intelligence: Trajectory")
        c1, c2 = st.columns([2, 1])
        with c1:
            base = alt.Chart(st.session_state.cross_history).encode(
                x=alt.X('Sentiment:Q', scale=alt.Scale(domain=[-1.1, 1.1])),
                y=alt.Y('Spread:Q', scale=alt.Scale(zero=False))
            )
            line = base.mark_line(point=True, color='#3498db', opacity=0.3).encode(order='Time:T')
            current = base.mark_circle(size=300, color='red').transform_filter(
                alt.datum.Time == st.session_state.cross_history['Time'].max()
            )
            st.altair_chart(line + current, width='stretch')
        with c2:
            st.write("**Current Regime**")
            if avg_spread_val > 0.05 and avg_index < 0:
                st.error("Panic Inefficiency")
            elif avg_spread_val < 0.02 and avg_index > 0:
                st.success("Efficient Bullishness")
            else:
                st.info("Stable Market")

st.title("Sentiment Alpha")

keys = r.keys("news:*")
news_list = [json.loads(r.get(k)) for k in keys]

with st.sidebar:
    st.header("Intelligence Control")
    conf_threshold = st.slider("Min. AI Confidence", 0.0, 1.0, 0.4)
    
    st.divider()
    if st.button("Run Global Market Pulse"):
        if news_list:
            all_titles = ". ".join([n['title'] for n in news_list[:15]])
            with st.spinner("Deep Learning Model: Synthesizing Global Narrative..."):
                res = ask_ollama(all_titles, is_bulk=True)
                if res:
                    st.session_state.bulk_analysis = res
                    st.rerun()
        else: st.toast("Data Sync Error", icon="⚠️")

if news_list:
    full_df = pd.DataFrame(news_list)
    full_df['dt'] = pd.to_datetime(full_df['timestamp'], unit='s')
    df = full_df[full_df['confidence'] >= conf_threshold].copy()

    if 'bulk_analysis' in st.session_state:
        st.info(f"### AI Global Summary\n{st.session_state.bulk_analysis}")
        if st.button("Clear Summary"):
            del st.session_state.bulk_analysis
            st.rerun()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Signals", len(df))
    df['score'] = df['sentiment'].map({'positive': 1, 'neutral': 0, 'negative': -1})
    m2.metric("Sentiment Index", f"{df['score'].mean():.2f}")
    m3.metric("Avg Confidence", f"{df['confidence'].mean():.2%}")
    m4.metric("Sources", "CoinTelegraph, CoinDesk")

    st.divider()

    render_dynamic_charts()

    st.divider()

    st.subheader("Intelligence Feed")
    color_emoji = {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}

    for _, item in df.sort_values('timestamp', ascending=False).iterrows():
        article_id = item['link']
        title_prefix = color_emoji.get(item['sentiment'].lower(), "⚪")
        
        with st.expander(f"{title_prefix} {item['sentiment'].upper()} - {item['title']}"):
            st.write(f"**Confidence:** {item['confidence']:.2%}")
            
            if st.button("Analyze Impact", key=f"llama_{article_id}"):
                with st.spinner("Llama 3 Pipeline: Computing Market Impact..."):
                    result = ask_ollama(item['title'])
                    if result:
                        st.session_state.ollama_results[article_id] = result

            if article_id in st.session_state.ollama_results:
                st.markdown("---")
                st.markdown(f"**AI Analysis:**\n\n{st.session_state.ollama_results[article_id]}")
                if st.button("Clear", key=f"clr_{article_id}"):
                    del st.session_state.ollama_results[article_id]
                    st.rerun()
        
        st.caption(f"Time: {item['dt'].strftime('%H:%M:%S')}")
else:
    st.info("Waiting for node synchronization...")