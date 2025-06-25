from flask import Flask, render_template, request
import re
import requests
import yfinance as yf
from datetime import datetime, timedelta

app = Flask(__name__)

# === Config ===
API_KEY = "AIzaSyATbwRYRrjv5JvCyJfw8pxvM2px6yhC0kg"
CSE_ID = "42708dbcedbe142d2"

# === Sentiment Keywords ===
very_positive_keywords = {"skyrocket", "blockbuster", "blowout", "explode", "unprecedented", "all time high", "record-breaking", "soars", "multiple", "expansion", "soar", "pop", "pops", }
positive_keywords = {"gain", "trending", "high", "gains", "rise", "rises", "raises", "beat", "beats", "expectations", "surge", "surges", "record", "profit", "strong", "up", "increase", "increases", "growth", "positive", "upgrade", "upgraded", "buy", "bullish", "rally", "boost", "opportunity", "leads", "upside", "boosts", "rallied", "outperforms", "accelerating", "great", "rebounds", "Bull", "best"}
negative_keywords = {"loss", "fall", "falls", "drop", "drops", "decline", "miss", "misses", "shortfall", "cut", "downgrade", "downgraded", "margin shortfall", "bearish", "warn", "weak", "down", "decrease", "layoff", "negative", "recall", "lawsuit", "hurt", "tariffs", "missed", "bad", "crossfire", "lower", "slams", "cut", "cuts", "downgrades", "slides", "pain", "warning", "lose"}
very_negative_keywords = {"collapse", "bankruptcy", "scandal", "meltdown", "fraud", "devastating", "catastrophic", "all-time low", "crash", "underperforming", "plunge", "plunges", "crisis", "death", "cross", "plummeting", "slashes", "collapsed", "crater"}

sentiment_colors = {
    "Very Positive": "#27ae60",
    "Positive": "#2ecc71",
    "Neutral": "#95a5a6",
    "Negative": "#e74c3c",
    "Very Negative": "#c0392b"
}

def get_sentiment_weighted(text):
    words = re.findall(r'\b\w+\b', text.lower())
    score = 0
    pos_count = neg_count = 0
    for word in words:
        if word in very_positive_keywords:
            score += 2
            pos_count += 1
        elif word in positive_keywords:
            score += 1
            pos_count += 1
        elif word in very_negative_keywords:
            score -= 2
            neg_count += 1
        elif word in negative_keywords:
            score -= 1
            neg_count += 1

    if score >= 4:
        sentiment = "Very Positive"
    elif score >= 1:
        sentiment = "Positive"
    elif score <= -4:
        sentiment = "Very Negative"
    elif score < 0:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"

    return sentiment, score, pos_count, neg_count

def search_stock_news_google(stock_symbol, max_results=25):
    query = f"{stock_symbol} stock"
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": API_KEY,
        "cx": CSE_ID,
        "q": query,
        "num": 10,
        "dateRestrict": "d14"
    }

    all_results = []
    start_index = 1
    while len(all_results) < max_results:
        params["start"] = start_index
        response = requests.get(url, params=params)
        data = response.json()
        if "items" not in data:
            break
        for item in data["items"]:
            title = item.get("title", "")
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            if "stock quote" in snippet.lower():
                continue
            all_results.append({"title": title, "link": link, "snippet": snippet})
            if len(all_results) >= max_results:
                break
        start_index += 10
    return all_results

@app.route("/home")
def home():
    return render_template("home.html")

@app.route("/", methods=["GET", "POST"])
def index():
    context = {}
    if request.method == "POST":
        ticker = request.form.get("ticker").upper()
        articles = search_stock_news_google(ticker)

        scored_articles = []
        sentiment_counts = {s: 0 for s in sentiment_colors}
        total_score = 0

        for article in articles:
            sentiment, score, pos, neg = get_sentiment_weighted(article["title"])
            sentiment_counts[sentiment] += 1
            total_score += score
            article.update({
                "sentiment": sentiment,
                "score": score,
                "pos": pos,
                "neg": neg,
                "color": sentiment_colors[sentiment]
            })
            scored_articles.append(article)

        avg_score = total_score / len(scored_articles) if scored_articles else 0
        overall = ("Very Positive" if avg_score >= 0.35 else
                   "Positive" if avg_score > 0.2 else
                   "Very Negative" if avg_score <= -0.35 else
                   "Negative" if avg_score < -0.2 else "Neutral")

        chart_data = []
        stats = {}
        try:
            end_date = datetime.today()
            start_date = end_date - timedelta(days=30)
            df = yf.download(ticker, start=start_date, end=end_date)
            chart_data = [
                {"Date": row["Date"].strftime("%Y-%m-%d"), "Close": round(row["Close"], 2)}
                for row in df.reset_index().to_dict("records")
                if "Date" in row and "Close" in row
            ]
        except:
            chart_data = []

        try:
            info = yf.Ticker(ticker).info
            stats = {
                "sector": info.get("sector", "N/A"),
                "market_cap": f"${round(info.get('marketCap', 0)/1e9, 2)}B",
                "pe_ratio": info.get("trailingPE", "N/A"),
                "div_yield": f"{round((info.get('dividendYield', 0) or 0) * 100, 2)}%",
                "week_52_range": f"${info.get('fiftyTwoWeekLow', 'N/A')} - ${info.get('fiftyTwoWeekHigh', 'N/A')}"
            }
        except:
            stats = {}

        context = {
            "ticker": ticker,
            "articles": scored_articles,
            "sentiment_counts": sentiment_counts,
            "overall": overall,
            "overall_color": sentiment_colors[overall],
            "chart_data": chart_data or [],
            "stats": stats,
            "sentiment_colors": sentiment_colors
        }

    return render_template("index.html", **context)

if __name__ == "__main__":
    app.run(debug=True)
