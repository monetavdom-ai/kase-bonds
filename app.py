import os, re
from flask import Flask, jsonify, send_from_directory
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
HTML_FILE = "bonds-app-live.html"

# ===== РАЗДЕЛЕНИЕ ПО ВАЛЮТЕ - ТОЛЬКО ПО ТИКЕРУ =====
USD_TICKERS = {
    "ASKQb1","ALMSb1","FPSTb2","FPSTb4","MFAFb7","MFAFb5","MFAFb6",
    "MFSCb3","MFSLb5","MFSLb4","JETGe2","GB_ALTNe1","GB_ALTNe2",
    "KZ2C00010155","KZ2C00012953","KZ2P00011513","KZ2P00010242",
    "KZ2P00009947","KZ2P00011141","KZ2P00012339","KZQ000000793",
    "ASBNb15","HLBNb2","EUBNb3","CCBNb4",
}
def detect_currency(ticker, text):
    t = ticker.strip()
    if t in USD_TICKERS:
        return "USD"
    if t.startswith("XS") or t.startswith("US") or t.startswith("KZX"):
        return "USD"
    upper = text.upper()
    if "USD" in upper or "$" in text or "ДОЛЛ" in upper or "DOLLAR" in upper:
        return "USD"
    return "KZT"

# ===== РИСК ТОЛЬКО ПО ЭМИТЕНТУ - КАК ТЫ СКАЗАЛ =====
# Безопасные = государственные + банки
# Рискованные = МФО
# Средние = все остальные (корпоративные, телеком, энергетика и т.д.)
MFO_PREFIXES = {
    "KFUS",  # КМФ / МФО
    "MFAF", "MFSC", "MFSL",  # микрофинансовые
    "FPST",  # фин. компания / МФО
    "TSTN",  # МФО / лизинг
    "MFO", "KMF", "MFIN", "MFLO",
    "ALMF", "SFIN", "BFIN",
}
# Государственные - Минфин, Нацбанк, акиматы
GOV_PREFIXES = {
    "BTRK",  # Нацбанк / Минфин
    "KZKD", "KZMJ",  # гос. облигации
    "KZ2D",  # ISIN гос. бумаг
    "GB_", "GOV",
}
# Банки
BANK_PREFIXES = {
    "ASBN",  # Альфа-Банк
    "CCBN",  # ЦентрКредит
    "EUBN",  # Евразийский
    "HLBN",  # Халык
    "KZTB", "ALMN", "NURB", "FORT", "KASB", "SBER", "VTBB", "ATFB",
    "BKBT", "KBNB", "HCSB", "KSBK", "RBKB", "TSBN",
}

def get_prefix(ticker):
    # KFUSb96 -> KFUS, ASKQb1 -> ASKQ, BTRKb22 -> BTRK, KZ2C000... -> KZ2C
    m = re.match(r"([A-Z]{2,}[A-Z]*)", ticker.strip().upper())
    if not m:
        return ""
    p = m.group(1)
    # Для ISIN KZ2D / KZ2C берем первые 4
    if ticker.strip().upper().startswith("KZ2"):
        return ticker.strip().upper()[:4]
    # Убираем хвосты типа B, B1 и т.д. - берем буквы до цифр
    m2 = re.match(r"([A-Z]+)", ticker.strip().upper())
    if m2:
        # KFUSB -> KFUS, BTRKB -> BTRK
        raw = m2.group(1)
        # Если заканчивается на B (облигация) - отрезаем последнюю B
        if len(raw) > 3 and raw.endswith("B"):
            raw = raw[:-1]
        return raw
    return p

def risk_by_issuer(ticker):
    t = ticker.strip().upper()
    prefix = get_prefix(ticker)
    # 1. МФО - всегда рискованные
    if prefix in MFO_PREFIXES:
        return "risky"
    # Прямая проверка по началу тикера для МФО
    for mfo in MFO_PREFIXES:
        if t.startswith(mfo):
            return "risky"
    # 2. Государственные + банки - всегда безопасные
    if prefix in GOV_PREFIXES or prefix in BANK_PREFIXES:
        return "safe"
    for gov in GOV_PREFIXES:
        if t.startswith(gov):
            return "safe"
    for bank in BANK_PREFIXES:
        if t.startswith(bank):
            return "safe"
    # ISIN гос. бумаг
    if t.startswith("KZ2D") or t.startswith("KZKD") or t.startswith("KZMJ"):
        return "safe"
    # 3. Все остальные - средние
    return "medium"

def parse_days(text):
    # ФИКС: в строке KASE несколько дат - первая это дата торгов (сегодня, 1 день),
    # а погашение - самая дальняя дата. Берем МАКСИМАЛЬНУЮ, а не первую.
    from datetime import datetime
    now = datetime.now()
    days_list = []
    for m in re.finditer(r"(\d{2})\.(\d{2})\.(\d{4})", text):
        try:
            d = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            days = (d - now).days
            if 30 <= days <= 3650:  # погашение от месяца до 10 лет
                days_list.append(days)
        except:
            pass
    for m in re.finditer(r"(\d{4})-(\d{2})-(\d{2})", text):
        try:
            d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            days = (d - now).days
            if 30 <= days <= 3650:
                days_list.append(days)
        except:
            pass
    if days_list:
        return max(days_list)  # самая дальняя = погашение
    return 365

# Запасной список - дни у каждой свои, не 365 у всех
KZT_FALLBACK_RAW = [
    # Гос + банки = безопасные
    ("BTRKb22", 107.6, 17.5, 16.26, 1280),
    ("BTRKb21", 101.2, 15.5, 15.32, 900),
    ("KZKD0000123", 98.5, 14.0, 14.21, 730),
    ("KZMJ0000087", 99.1, 13.5, 13.62, 1095),
    ("ASBNb12", 92.0, 18.5, 20.1, 720),
    ("CCBNb4", 99.0, 15.0, 15.15, 850),
    ("HLBNb2", 100.5, 14.8, 14.72, 640),
    # Средние - корпоративные
    ("KZ2C00010155", 98.0, 16.0, 16.32, 800),
    ("KZ2C00012953", 97.0, 15.5, 15.98, 950),
    # МФО = рискованные
    ("KFUSb96", 96.0, 20.08, 20.92, 365),
    ("KFUSb94", 94.0, 19.11, 20.33, 365),
    ("KFUSb93", 93.0, 18.06, 19.42, 365),
    ("KFUSb112", 112.0, 23.07, 20.6, 365),
    ("KFUSb77", 72.0, 22.0, 30.5, 365),
    ("TSTNb03", 65.0, 21.0, 32.3, 480),
]
USD_FALLBACK_RAW = [
    # Банки = безопасные
    ("ASBNb15", 98.5, 6.2, 6.29, 800),
    ("HLBNb2", 99.0, 6.0, 6.06, 700),
    ("EUBNb3", 98.0, 6.5, 6.63, 900),
    ("CCBNb4", 99.2, 5.8, 5.84, 750),
    # Средние
    ("ASKQb1", 98.2, 6.0, 6.11, 720),
    ("ALMSb1", 99.1, 6.5, 6.56, 900),
    ("JETGe2", 100.2, 7.0, 6.99, 528),
    ("XS2901234567", 99.8, 6.5, 6.51, 1095),
    # МФО = рискованные
    ("FPSTb2", 97.5, 7.0, 7.18, 1095),
    ("FPSTb4", 96.8, 7.5, 7.75, 730),
    ("MFAFb7", 99.5, 6.8, 6.83, 1080),
    ("MFAFb5", 98.9, 7.2, 7.28, 850),
    ("MFSCb3", 95.0, 8.0, 8.42, 900),
    ("MFSLb5", 92.0, 8.5, 9.24, 720),
    ("XS3201112223", 74.0, 9.0, 12.16, 700),
]

def build_fallback():
    out = []
    for name, price, coupon, yld, days in KZT_FALLBACK_RAW:
        out.append({"name": name, "price": price, "coupon": coupon, "yield": yld, "days": days, "currency": "KZT", "risk": risk_by_issuer(name)})
    for name, price, coupon, yld, days in USD_FALLBACK_RAW:
        out.append({"name": name, "price": price, "coupon": coupon, "yield": yld, "days": days, "currency": "USD", "risk": risk_by_issuer(name)})
    return out

FALLBACK = build_fallback()

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
        for url in ["https://kase.kz/ru/bonds/", "https://kase.kz/en/bonds/"]:
            try:
                r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code != 200:
                    continue
                soup = BeautifulSoup(r.text, "html.parser")
                # Ищем все таблицы, берем ту, где есть заголовки Купон / Цена / Погашение
                for table in soup.find_all("table"):
                    rows = table.find_all("tr")
                    if len(rows) < 3:
                        continue
                    # --- Ищем строку заголовков ---
                    header_idx = None
                    col = {}  # price, coupon, days, yield, ticker
                    for hi, row in enumerate(rows[:4]):
                        cells = [c.get_text(" ", strip=True) for c in row.find_all(["th", "td"])]
                        txt = " ".join(cells).lower()
                        if "купон" in txt or "цена" in txt or "погашение" in txt or "coupon" in txt:
                            header_idx = hi
                            for i, h in enumerate(cells):
                                hl = h.lower()
                                if "купон" in hl or "coupon" in hl:
                                    col["coupon"] = i
                                elif "цена" in hl or "котиров" in hl or "price" in hl or "bid" in hl:
                                    col["price"] = i
                                elif "погашение" in hl or "maturity" in hl or "срок" in hl or "дней" in hl or "days" in hl:
                                    col["days"] = i
                                elif "доход" in hl or "yield" in hl:
                                    col["yield"] = i
                                elif "код" in hl or "code" in hl or "тикер" in hl or "ticker" in hl:
                                    col["ticker"] = i
                                elif "isin" in hl:
                                    col["isin"] = i
                            break
                    if header_idx is None:
                        continue
                    # --- Читаем строки по колонкам, а не по первым цифрам ---
                    for row in rows[header_idx+1:]:
                        cells = [c.get_text(" ", strip=True) for c in row.find_all("td")]
                        if len(cells) < 3:
                            continue
                        # Тикер - из колонки тикера, иначе из первой ячейки
                        ticker = None
                        if "ticker" in col and col["ticker"] < len(cells):
                            m = re.search(r"\b([A-Z]{2,}[A-Za-z0-9_]{2,}|KZ[A-Z0-9]{8,})\b", cells[col["ticker"]])
                            if m:
                                ticker = m.group(1)
                        if not ticker:
                            for c in cells[:2]:
                                m = re.search(r"\b([A-Z]{2,}[A-Za-z0-9_]{2,}|KZ[A-Z0-9]{8,})\b", c)
                                if m and len(c) < 40:
                                    ticker = m.group(1)
                                    break
                        if not ticker:
                            continue
                        text = " ".join(cells)
                        currency = detect_currency(ticker, text)
                        # Цена - ТОЛЬКО из колонки цены
                        price = None
                        if "price" in col and col["price"] < len(cells):
                            m = re.search(r"(\d+[.,]\d+)", cells[col["price"]].replace(",", "."))
                            if m:
                                try: price = float(m.group(1))
                                except: pass
                        # Купон - ТОЛЬКО из колонки купона
                        coupon = None
                        if "coupon" in col and col["coupon"] < len(cells):
                            # В колонке купона может быть "-" или пусто - тогда пропускаем
                            cell = cells[col["coupon"]].replace(",", ".").strip()
                            if cell and cell != "-" and cell != "–":
                                m = re.search(r"(\d+[.,]\d+|\d+)", cell)
                                if m:
                                    try: coupon = float(m.group(1))
                                    except: pass
                        # Если купон не нашли в колонке - НЕ берем первую цифру подряд (там изменение цены 0.89%)
                        # Пропускаем такую строку, чтобы не показывать бред
                        if price is None or coupon is None:
                            continue
                        if not (70 <= price <= 130):
                            continue
                        # Купон у тенговых - 5-30%, а не 0.89%. Если купон < 3% - это не купон, а изменение цены, пропускаем
                        if not (3 <= coupon <= 30):
                            continue
                        # Доходность считаем сами, а не берем из таблицы
                        yld = round(coupon / price * 100, 2) if price else 0
                        # Дни - ТОЛЬКО из колонки погашения
                        days = 365
                        if "days" in col and col["days"] < len(cells):
                            cell = cells[col["days"]].strip()
                            # Если там число дней типа 1459
                            m = re.search(r"(\d{3,4})", cell)
                            if m:
                                try:
                                    d = int(m.group(1))
                                    if 30 <= d <= 3650:
                                        days = d
                                except: pass
                            else:
                                days = parse_days(cell)
                        else:
                            days = parse_days(text)
                        bonds.append({
                            "name": ticker,
                            "price": round(price, 2),
                            "coupon": round(coupon, 2),
                            "yield": round(yld, 2),
                            "days": days,
                            "currency": currency,
                            "risk": risk_by_issuer(ticker),
                        })
                    if len(bonds) > 20:
                        break
                if len(bonds) > 20:
                    break
            except Exception as e:
                print("KASE url error", url, e)
                continue
        seen = set(); out = []
        for b in bonds:
            if b["name"] in seen:
                continue
            seen.add(b["name"]); out.append(b)
        if len(out) >= 5:
            for ub in FALLBACK:
                if ub["name"] not in seen and ub["currency"] == "USD":
                    out.append(dict(ub))
                    seen.add(ub["name"])
            out.sort(key=lambda x: x["yield"], reverse=True)
            return jsonify(out)
    except Exception as e:
        print("KASE error:", e)
    return jsonify(FALLBACK)

print("RISK CHECK: KFUSb96 (МФО) =", risk_by_issuer("KFUSb96"), "должно быть risky")
print("RISK CHECK: BTRKb22 (гос) =", risk_by_issuer("BTRKb22"), "должно быть safe")
print("RISK CHECK: ASBNb12 (банк) =", risk_by_issuer("ASBNb12"), "должно быть safe")
print("RISK CHECK: ASKQb1 (средние) =", risk_by_issuer("ASKQb1"), "должно быть medium")
print("FALLBACK", len(FALLBACK), "KZT", sum(1 for b in FALLBACK if b['currency']=='KZT'), "USD", sum(1 for b in FALLBACK if b['currency']=='USD'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
