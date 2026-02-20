import feedparser
import redis
import json
import time
from transformers import pipeline

r = redis.Redis(host='redis-cache', port=6379, db=0)
RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeed/rss/"
]

print("Loading FinBERT model...")
sentiment_pipeline = pipeline("sentiment-analysis", model="ProsusAI/finbert")

def fetch_and_analyze():
    for url in RSS_FEEDS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:10]:
            title = entry.title
            
            result = sentiment_pipeline(title)[0]
            label = result['label']
            score = result['score']
            
            data = {
                "title": title,
                "link": entry.link,
                "sentiment": label,
                "confidence": score,
                "timestamp": time.time()
            }
            
            r.set(f"news:{entry.link}", json.dumps(data), ex=86400)
    print("News successfully updated.")

if __name__ == "__main__":
    while True:
        fetch_and_analyze()
        time.sleep(300)