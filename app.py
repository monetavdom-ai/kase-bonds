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
    # ISIN еврооблигаций - всегда USD
    if t.startswith("XS") or t.startswith("US") or t.startswith("KZX"):
        return "USD"
    # Гос. бумаги Казахстана - всегда KZT
    if t.startswith("KZMJ") or t.startswith("KZKD") or t.startswith("KZ2D"):
        return "KZT"
    # Явный признак USD в строке таблицы KASE - только если нет признака KZT
    upper = text.upper()
    if "KZT" in upper or "ТЕНГЕ" in upper or "ТГ" in upper:
        # Если в строке есть и USD и KZT - приоритет за тикером, а не за текстом
        if t.startswith("XS") or t.startswith("US"):
            return "USD"
        return "KZT"
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

# НЕТ ВЫДУМАННОГО ЗАПАСНОГО СПИСКА - только реальные данные с KASE
# Если KASE не отвечает, API возвращает пустой список, а не выдуманные цены/купоны
FALLBACK = []

# ПРОВЕРЕНО ПО KASE - только эти бумаги берём из официальных пресс-релизов KASE, а не придумываем
# Источники:
# - KFUSb93-96: KASE новость "12 выпусков облигаций АО Казахстанский фонд устойчивости" - купон 12.50%
# - MFOKb38/39: KASE новость от 26 ноября - купон 23% / 24%, даты 20.11.26-20.05.27 / 20.11.26-20.11.27
VERIFIED_KASE = [
    # USD - проверено по KASE: еврооблигации КазМунайГаз
    {"name": "KMGZe1", "isin": "XS0373642585", "price": None, "coupon": 8.375, "yield": None, "days": None, "currency": "USD", "risk": "medium", "source": "KASE: 02.07.08-02.07.13, полугодовой купон 8.375%"},
    {"name": "KMGZe2", "isin": "XS0373641009", "price": None, "coupon": 9.125, "yield": None, "days": None, "currency": "USD", "risk": "medium", "source": "KASE: 02.07.08-02.07.18, полугодовой купон 9.125%"},
    {"name": "KMGZe3", "isin": "XS0441261921", "price": None, "coupon": 11.75, "yield": None, "days": None, "currency": "USD", "risk": "medium", "source": "KASE: 23.07.09-23.01.15, полугодовой купон 11.75%"},
    {"name": "KMGZe4", "isin": "XS0506527851", "price": None, "coupon": 7.0, "yield": None, "days": None, "currency": "USD", "risk": "medium", "source": "KASE: 05.05.10-05.05.20, полугодовой купон 7.00%"},

    {"name": "MFOKb39", "isin": "KZ2C00021046", "price": None, "coupon": 24.0, "yield": None, "days": 357, "currency": "KZT", "risk": "risky", "source": "KASE: 20.11.26-20.11.27, ежемесячный купон 24%"},
    {"name": "MFOKb38", "isin": "KZ2C00021020", "price": None, "coupon": 23.0, "yield": None, "days": 173, "currency": "KZT", "risk": "risky", "source": "KASE: 20.11.26-20.05.27, ежемесячный купон 23%"},
    {"name": "KFUSb93", "isin": "KZ2C00014835", "price": None, "coupon": 12.5, "yield": None, "days": 360, "currency": "KZT", "risk": "risky", "source": "KASE: 360 дней, годовой купон 12.50%"},
    {"name": "KFUSb94", "isin": "KZ2C00014843", "price": None, "coupon": 12.5, "yield": None, "days": 360, "currency": "KZT", "risk": "risky", "source": "KASE: 360 дней, годовой купон 12.50%"},
    {"name": "KFUSb95", "isin": "KZ2C00014850", "price": None, "coupon": 12.5, "yield": None, "days": 360, "currency": "KZT", "risk": "risky", "source": "KASE: 360 дней, годовой купон 12.50%"},
    {"name": "KFUSb96", "isin": "KZ2C00014868", "price": None, "coupon": 12.5, "yield": None, "days": 360, "currency": "KZT", "risk": "risky", "source": "KASE: 360 дней, годовой купон 12.50%"},
]



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
                        # Если купона нет в колонке - НЕ придумываем, ставим None, фронт покажет прочерк
                        # Цену тоже не придумываем. Строку НЕ пропускаем - показываем все облигации из KASE
                        if price is not None and not (70 <= price <= 130):
                            price = None  # цена вне диапазона - не выдумываем, ставим прочерк
                        # Купон 0.35% у KZMJ - реальный, поэтому не отбрасываем купоны <3%. Отбрасываем только явный мусор >35%
                        if coupon is not None and not (0.1 <= coupon <= 35):
                            coupon = None
                        # Доходность считаем сами, а не берем из таблицы
                        yld = round(coupon / price * 100, 2) if (price and coupon) else None
                        # Дни - ТОЛЬКО из колонки погашения
                        days = None
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
        # ВСЕ облигации из таблицы KASE - без ограничения в 6 штук
        # Логика: таблица KASE - главный источник. VERIFIED_KASE - только для дополнения купона,
        # если в таблице купон пустой (например, KASE показывает "-" для новых выпусков)
        # Никаких выдуманных цен/купонов - если цены нет, price=None
        verified_by_name = {v["name"]: v for v in VERIFIED_KASE}
        merged = []
        seen_names = set()
        for b in out:
            item = dict(b)
            # Если в таблице купон не нашли, но он есть в проверенных пресс-релизах KASE - берем оттуда
            if (not item.get("coupon") or item.get("coupon") == 0) and b["name"] in verified_by_name:
                item["coupon"] = verified_by_name[b["name"]]["coupon"]
                item["days"] = verified_by_name[b["name"]]["days"]
                item["source"] = verified_by_name[b["name"]]["source"]
            # Доходность пересчитываем только из реальных цены и купона, не берем из таблицы вслепую
            if item.get("price") and item.get("coupon"):
                item["yield"] = round(item["coupon"] / item["price"] * 100, 2)
            merged.append(item)
            seen_names.add(b["name"])
        # Добавляем проверенные, которых не было в таблице (например, новые выпуски MFOKb38/39 ещё не в таблице торгов)
        for v in VERIFIED_KASE:
            if v["name"] not in seen_names:
                item = dict(v)
                item["price"] = None
                item["yield"] = None
                merged.append(item)
        # Сортировка по купону, чтобы портфель было удобно смотреть
        merged.sort(key=lambda x: (x["coupon"] or 0), reverse=True)
        return jsonify(merged)
    except Exception as e:
        print("KASE error:", e)
    # Если KASE таблица вообще не ответила - отдаём только проверенные купоны из пресс-релизов KASE, без цены
    return jsonify(VERIFIED_KASE)

print("RISK CHECK: KFUSb96 (МФО) =", risk_by_issuer("KFUSb96"), "должно быть risky")
print("RISK CHECK: BTRKb22 (гос) =", risk_by_issuer("BTRKb22"), "должно быть safe")
print("RISK CHECK: ASBNb12 (банк) =", risk_by_issuer("ASBNb12"), "должно быть safe")
print("RISK CHECK: ASKQb1 (средние) =", risk_by_issuer("ASKQb1"), "должно быть medium")
print("FALLBACK", len(FALLBACK), "KZT", sum(1 for b in FALLBACK if b['currency']=='KZT'), "USD", sum(1 for b in FALLBACK if b['currency']=='USD'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
