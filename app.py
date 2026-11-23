# app.py - версия для Render, работает 24/7, сама обновляет цены каждые 15 минут
# Запуск на Render: python app.py
from flask import Flask, jsonify, send_from_directory
import json, re, time, threading, datetime, os
import requests
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0'}
CODES = ["BRKZb36","KZIKb46","KEGCb3","KFUSb1","JSBNb10","SMTLb2","IDFRb8","HCBNb17","BTRKb8","CLSGb14","CLSGb13","JSBNb8","BTRKb22","CLSGb16","TTLSb3","CLSGb11","JSBNb6","CLSGb15","CLSGb10","INBNb18","HCBNb29","ATBNb3","CLSGb9","KAFIb12","SMTLb1","QBTMb1","ERBBb2","JSBNb3","CLSGb8","SCLBb2","GLLKb2","UZPAb1","SWPSb1","ORBSb8","TSSPb1","BIGDb11","BIGDb7","BIGDb8","KZTCb3","TTLSb2","SCLBb3","SCLBb1","MNLTb1","HCBNb13","ORBSb6","TSSPb8","QGLDb1","BIGDb6","CLSGb4","ACARb1","KZIKb27","HCBNb14","BIGDb5","NCOMb16","MRDNb1","FIVEb7","SKKZb11","ORBSb7","LZGRb21","FPSTb9","KFUSb47","KFUSb46","NCOMb10","GLLKb1","LZGRb18","ASKQb1"]

app = Flask(__name__)

def clean_num(s):
    if not s: return 0
    s = str(s).replace('\xa0','').replace(' ','').replace(',','.')
    m = re.search(r'(\d+\.?\d*)', s)
    return float(m.group(1)) if m else 0

def get_info(code):
    url = f'https://kase.kz/ru/investors/bonds/{code}'
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        text = soup.get_text(' ', strip=True)
        m = re.search(r'Последняя купонная ставка.*?(\d+[.,]\d+)', text)
        coupon = clean_num(m.group(1)) if m else 0
        m2 = re.search(r'Количество дней до погашения:\s*(\d+)', text)
        days = int(m2.group(1)) if m2 else 0
        price = 0
        m3 = re.search(r'Цена.*?(\d+[.,]\d+)\s*%', text)
        if m3: price = clean_num(m3.group(1))
        if price > 1000: price = price/100
        if price == 0: price = 100
        if coupon == 0 or days == 0: return None
        yld = coupon/price*100
        risk = "ОК" if yld<=18 else ("сред" if yld<=25 else "РИСК")
        return {'code': code, 'price': price, 'days': days, 'coupon': coupon, 'yld': round(yld,2), 'risk': risk}
    except Exception as e:
        print(f"| {code} ошибка: {e}")
        return None

def update_loop():
    # Сразу пишем заглушку, чтобы сайт не был пустым
    while True:
        try:
            print("| Качаю настоящие цены с KASE...")
            fresh=[]
            for i, code in enumerate(CODES):
                b = get_info(code)
                if b: fresh.append(b)
                if i % 10 == 0: print(f"| {i}/{len(CODES)}...")
                time.sleep(0.2)
            if len(fresh) > 10:
                now = datetime.datetime.now().strftime("%d.%m %H:%M:%S")
                with open("bonds_live.json","w",encoding="utf-8") as f:
                    json.dump({"updated": now+" (настоящие с KASE)", "status": "live", "bonds": fresh}, f, ensure_ascii=False)
                print(f"| ГОТОВО! {len(fresh)} облигаций в {now}")
            else:
                print(f"| KASE не ответил, осталось {len(fresh)}")
        except Exception as e:
            print(f"| Ошибка: {e}")
        print("| Жду 15 минут...")
        time.sleep(15*60)

@app.route("/")
def index():
    return send_from_directory(".", "bonds_app_live.html")
@app.route("/bonds_app_live.html")
def app_html():
    return send_from_directory(".", "bonds_app_live.html")
@app.route("/api/bonds")
def api():
    try:
        with open("bonds_live.json", encoding="utf-8") as f:
            return jsonify(json.load(f))
    except:
        return jsonify({"updated": "еще нет", "status": "fallback", "bonds": []})

# Запускаем обновление в фоне при старте
threading.Thread(target=update_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
