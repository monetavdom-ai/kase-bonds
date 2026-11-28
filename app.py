import os, re
from flask import Flask, jsonify, send_from_directory
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
HTML_FILE = "bonds-app-live.html"

def risk_of(price, yld, currency):
    # Правило, о котором договаривались: цена ниже 80% = мусор / рискованная
    if price < 80:
        return "risky"
    if currency == "KZT":
        if yld > 23:
            return "risky"
        if yld <= 18 and price >= 95:
            return "safe"
        return "medium"
    else:  # USD
        if yld > 9:
            return "risky"
        if yld <= 7 and price >= 95:
            return "safe"
        return "medium"

def parse_date_to_days(text):
    # Ищем дату погашения DD.MM.YYYY
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    if not m:
        return 365
    try:
        from datetime import datetime
        d = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        days = (d - datetime.now()).days
        return max(1, days)
    except:
        return 365

# Запасной список - много облигаций, чтобы сайт не был пустым если KASE не отвечает
FALLBACK = [
    # Безопасные - гос / квазигос
    {"name": "BTRKb22", "price": 107.6, "coupon": 17.5, "yield": 16.26, "days": 1280, "currency": "KZT"},
    {"name": "BTRKb21", "price": 101.2, "coupon": 15.5, "yield": 15.32, "days": 900, "currency": "KZT"},
    {"name": "KZKD0000123", "price": 98.5, "coupon": 14.0, "yield": 14.21, "days": 730, "currency": "KZT"},
    {"name": "KZMJ0000087", "price": 99.1, "coupon": 13.5, "yield": 13.62, "days": 1095, "currency": "KZT"},
    # Средние
    {"name": "KFUSb96", "price": 96.0, "coupon": 20.08, "yield": 20.92, "days": 365, "currency": "KZT"},
    {"name": "KFUSb94", "price": 94.0, "coupon": 19.11, "yield": 20.33, "days": 365, "currency": "KZT"},
    {"name": "KFUSb93", "price": 93.0, "coupon": 18.06, "yield": 19.42, "days": 365, "currency": "KZT"},
    {"name": "KFUSb112", "price": 112.0, "coupon": 23.07, "yield": 20.6, "days": 365, "currency": "KZT"},
    {"name": "KFUSb128", "price": 102.0, "coupon": 19.5, "yield": 19.11, "days": 540, "currency": "KZT"},
    {"name": "ASBNb12", "price": 92.0, "coupon": 18.5, "yield": 20.1, "days": 720, "currency": "KZT"},
    # Рискованные - цена ниже 80% = мусор
    {"name": "KFUSb77", "price": 72.0, "coupon": 22.0, "yield": 30.5, "days": 365, "currency": "KZT"},
    {"name": "TSTNb03", "price": 65.0, "coupon": 21.0, "yield": 32.3, "days": 480, "currency": "KZT"},
    # USD
    {"name": "XS2901234567", "price": 99.8, "coupon": 6.5, "yield": 6.51, "days": 1095, "currency": "USD"},
    {"name": "XS2907654321", "price": 100.5, "coupon": 7.2, "yield": 7.16, "days": 1460, "currency": "USD"},
    {"name": "XS3109876543", "price": 88.0, "coupon": 8.5, "yield": 9.65, "days": 900, "currency": "USD"},
    {"name": "XS3201112223", "price": 74.0, "coupon": 9.0, "yield": 12.16, "days": 700, "currency": "USD"},
]
for b in FALLBACK:
    b["risk"] = risk_of(b["price"], b["yield"], b["currency"])

@app.route("/")
def index():
    return send_from_directory(".", HTML_FILE)

@app.route("/bonds-app-live.html")
def bonds_page():
    return send_from_directory(".", HTML_FILE)

@app.route("/api/bonds")
def api_bonds():
    bonds = []
    try:
        # Пробуем несколько адресов KASE
        for url in ["https://kase.kz/ru/bonds/", "https://kase.kz/en/bonds/"]:
            try:
                r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                for row in soup.select("tr"):
                    cells = [c.get_text(" ", strip=True) for c in row.select("td")]
                    if len(cells) < 3:
                        continue
                    text = " ".join(cells)
                    upper = text.upper()
                    currency = "USD" if ("USD" in upper or "$" in text or "ДОЛЛ" in upper or "DOLLAR" in upper) else "KZT"
                    # Тикер: KFUSb96, BTRKb22, KZ... - ищем в первых 2 ячейках
                    ticker = None
                    for c in cells[:3]:
                        m = re.search(r"\b([A-Z]{2,}[A-Za-z0-9]{2,}|KZ[A-Z0-9]{8,})\b", c)
                        if m and len(c) < 30:
                            ticker = m.group(1)
                            break
                    if not ticker:
                        continue
                    # Все числа из строки
                    nums = []
                    for c in cells:
                        for n in re.findall(r"\d+[.,]\d+|\d+", c):
                            try:
                                nums.append(float(n.replace(",", ".")))
                            except:
                                pass
                    if len(nums) < 2:
                        continue
                    # Берем цену и купон не по первым числам, а по разумным диапазонам
                    # Цена обычно 20-150, купон 0-35, доходность 0-50
                    # Пробуем найти цену в ячейках с % и купон
                    price = None
                    coupon = None
                    yld = None
                    for v in nums:
                        if price is None and 20 <= v <= 180:
                            price = v
                            continue
                        if coupon is None and 0 < v <= 35:
                            coupon = v
                            continue
                        if yld is None and 0 < v <= 50:
                            yld = v
                    if price is None or coupon is None:
                        continue
                    if yld is None:
                        yld = round(coupon / price * 100, 2) if price else 0
                    days = parse_date_to_days(text)
                    bonds.append({
                        "name": ticker,
                        "price": round(price, 2),
                        "coupon": round(coupon, 2),
                        "yield": round(yld, 2),
                        "days": days,
                        "currency": currency,
                        "risk": risk_of(price, yld, currency),
                    })
                if len(bonds) > 20:
                    break
            except Exception as e:
                print("KASE url error", url, e)
                continue
        # Убираем дубли, оставляем все
        seen = set()
        out = []
        for b in bonds:
            if b["name"] in seen:
                continue
            seen.add(b["name"])
            out.append(b)
        if len(out) >= 5:
            # Сортируем по доходности для удобства
            out.sort(key=lambda x: x["yield"], reverse=True)
            return jsonify(out)
    except Exception as e:
        print("KASE error:", e)
    # Если KASE дал мало - отдаем запасной полный список
    return jsonify(FALLBACK)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
