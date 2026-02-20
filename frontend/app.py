import streamlit as st
import redis
import json
import requests
import pandas as pd
import altair as alt
from streamlit_autorefresh import st_autorefresh
from wordcloud import WordCloud
import matplotlib.pyplot as plt

st.set_page_config(page_title="Sentiment Alpha", layout="wide")
st_autorefresh(interval=30000, key="datarefresh")

r = redis.Redis(host='redis-cache', port=6379, db=0, decode_responses=True)
OLLAMA_URL = "http://host.docker.internal:11434/api/generate"

def ask_ollama(prompt, is_bulk=False):
    context = "Summarize the overall crypto market sentiment in 3 bullet points based on these headlines:" if is_bulk else "Explain the impact of this news:"
    try:
        response = requests.post(OLLAMA_URL, json={
            "model": "llama3", "prompt": f"{context} {prompt}", "stream": False
        }, timeout=60)
        return response.json().get('response', "Error.")
    except: return "Ollama Offline."

keys = r.keys("news:*")
news_list = [json.loads(r.get(k)) for k in keys]

with st.sidebar:
    st.header("Intelligence Control")
    conf_threshold = st.slider("Min. AI Confidence", 0.0, 1.0, 0.4)
    
    st.divider()
    if st.button("Run Global Market Pulse"):
        if news_list:
            all_titles = ". ".join([n['title'] for n in news_list[:15]])
            with st.spinner("Llama 3 is analyzing global trends..."):
                st.session_state.bulk_analysis = ask_ollama(all_titles, is_bulk=True)
        else: st.error("No data.")

st.title("Sentiment Alpha")

if news_list:
    full_df = pd.DataFrame(news_list)
    full_df['dt'] = pd.to_datetime(full_df['timestamp'], unit='s')
    df = full_df[full_df['confidence'] >= conf_threshold].copy()
    
    if 'bulk_analysis' in st.session_state:
        st.info(f"### 🤖 AI Market Summary\n{st.session_state.bulk_analysis}")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Signals", len(df))
    
    df['score'] = df['sentiment'].map({'positive': 1, 'neutral': 0, 'negative': -1})
    avg_index = df['score'].mean()
    m2.metric("Sentiment Index", f"{avg_index:.2f}", delta="Bullish" if avg_index > 0 else "Bearish")
    m3.metric("High Strength", len(df[df['confidence'] > 0.9]))
    m4.metric("Sources", "CoinTelegraph, CoinDesk")

    st.divider()

    c_left, c_right = st.columns([1, 2])

    with c_left:
        st.subheader("Topic Clusters")
        text_corpus = " ".join(df['title'].tolist())
        if text_corpus:
            wc = WordCloud(
                width=600, height=340, 
                background_color="black", mode="RGBA",
                colormap="cool", 
                max_words=25
            ).generate(text_corpus)
            fig, ax = plt.subplots(figsize=(6, 3.4))
            ax.imshow(wc, interpolation="bilinear")
            ax.axis("off")
            fig.patch.set_facecolor('black')
            st.pyplot(fig)
        else:
            st.write("Awaiting news...")

    with c_right:
        st.subheader("Sentiment Flow (Sequential)")
        if len(df) > 1:
            df_flow = df.sort_values('timestamp').reset_index(drop=True)
            df_flow['news_index'] = df_flow.index + 1
            
            df_flow['moving_avg'] = df_flow['score'].rolling(window=3, min_periods=1).mean()

            flow_chart = alt.Chart(df_flow).mark_area(
                line={'color':'#3498db', 'strokeWidth': 3},
                color=alt.Gradient(
                    gradient='linear',
                    stops=[alt.GradientStop(color='#3498db', offset=1),
                           alt.GradientStop(color='rgba(52, 152, 219, 0.05)', offset=0)],
                    x1=1, x2=1, y1=1, y2=0
                )
            ).encode(
                x=alt.X('news_index:O', title='Sequential News Feed (Oldest → Newest)', axis=alt.Axis(labelAngle=0)),
                y=alt.Y('moving_avg:Q', title='Sentiment Score', scale=alt.Scale(domain=[-1.1, 1.1])),
                tooltip=['title', 'sentiment', 'confidence']
            ).properties(height=280)
            
            st.altair_chart(flow_chart, width='stretch')
            st.caption("Each point represents one news item. The curve shows the rolling narrative trend.")
        else:
            st.info("Insufficient data points for flow analysis.")
            
    st.divider()
    
    st.subheader("Intelligence Feed")
    color_map = {"positive": "green", "negative": "red", "neutral": "gray"}

    for _, item in df.sort_values('timestamp', ascending=False).iterrows():
        cols = st.columns([4, 1])
        with cols[0]:
            display_color = color_map.get(item['sentiment'].lower(), "gray")
            with st.expander(f":{display_color}[{item['sentiment'].upper()}] - {item['title']}"):
                st.write(f"**Confidence:** {item['confidence']:.2%}")
                st.progress(item['confidence'])
                st.write(f"[Source Article]({item['link']})")
                if st.button("Ask Llama 3 Impact", key=item['link']):
                    st.write(ask_ollama(item['title']))
        with cols[1]:
            st.caption(f"{item['dt'].strftime('%H:%M:%S')}")
else:
    st.info("Syncing with Blockchain News Nodes...")