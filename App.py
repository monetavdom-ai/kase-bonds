from flask import Flask, jsonify, send_from_directory
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
HTML_FILE = "bonds-app-live.html"

FALLBACK = [
    {"name": "BTRKb22", "price": 107.6, "coupon": 17.5, "yield": 16.26, "days": 1280, "currency": "KZT", "maturity": "2029"},
    {"name": "BTRKb21", "price": 101.2, "coupon": 15.5, "yield": 15.32, "days": 900, "currency": "KZT", "maturity": "2028"},
    {"name": "XS2901234567", "price": 99.8, "coupon": 6.5, "yield": 6.51, "days": 1095, "currency": "USD", "maturity": "2028"},
    {"name": "XS2907654321", "price": 100.5, "coupon": 7.2, "yield": 7.16, "days": 1460, "currency": "USD", "maturity": "2029"},
]

@app.route("/")
def index():
    return send_from_directory(".", HTML_FILE)

@app.route("/bonds-app-live.html")
def bonds_page():
    return send_from_directory(".", HTML_FILE)

@app.route("/api/bonds")
def api_bonds():
    try:
        r = requests.get("https://kase.kz/ru/bonds/", timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(r.text, "html.parser")
        bonds = []
        for row in soup.select("tr"):
            cells = [c.get_text(" ", strip=True) for c in row.select("td")]
            if len(cells) < 5:
                continue
            text = " ".join(cells)
            # Валюта - определяем строго по строке: USD / $ / доллар = USD, остальное = KZT
            upper = text.upper()
            if "USD" in upper or "$" in text or "ДОЛЛ" in upper or "DOLLAR" in upper:
                currency = "USD"
            else:
                currency = "KZT"
            m_ticker = re.search(r"\b([A-Z]{3,}[A-Za-z0-9]{2,})\b", text)
            nums = re.findall(r"\d+[.,]\d+|\d+", text)
            if not m_ticker or len(nums) < 2:
                continue
            try:
                price = float(nums[0].replace(",", "."))
                coupon = float(nums[1].replace(",", "."))
            except:
                continue
            if not (50 < price < 200 and 0 < coupon < 40):
                continue
            bonds.append({
                "name": m_ticker.group(1),
                "price": price,
                "coupon": coupon,
                "yield": round(coupon / price * 100, 2) if price else 0,
                "days": 365,
                "currency": currency,
                "maturity": "",
            })
        seen = set()
        out = []
        for b in bonds:
            if b["name"] in seen:
                continue
            seen.add(b["name"])
            out.append(b)
        if out:
            return jsonify(out)
    except Exception as e:
        print("KASE error:", e)
    return jsonify(FALLBACK)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
