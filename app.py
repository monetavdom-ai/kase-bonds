# app.py - Render, ВСЕ облигации 149, фильтры валюта + риск
from flask import Flask, jsonify, send_from_directory
import json, re, time, threading, datetime, os
import requests
from bs4 import BeautifulSoup
HEADERS = {'User-Agent': 'Mozilla/5.0'}
CODES_TENGE = ['BRKZb36', 'KZIKb46', 'KEGCb3', 'KFUSb1', 'JSBNb10', 'SMTLb2', 'IDFRb8', 'MFRFb30', 'HCBNb17', 'BTRKb8', 'CLSGb14', 'CLSGb13', 'JSBNb8', 'BTRKb22', 'CLSGb16', 'MFRFb27', 'TTLSb3', 'CLSGb11', 'JSBNb6', 'MFKMb12', 'CLSGb15', 'MFRFb26', 'CLSGb10', 'MFOKb28', 'INBNb18', 'HCBNb29', 'ATBNb3', 'CLSGb9', 'MFTSb8', 'MFMOb38', 'MFSFb1', 'MFDFb4', 'MFRFb24', 'KAFIb12', 'MFLGb24', 'SMTLb1', 'QBTMb1', 'MFOKb31', 'MFOKb30', 'ERBBb2', 'MFKMb8', 'MFBLb7', 'JSBNb3', 'CLSGb8', 'MFMOb37', 'MFKTb4', 'MFCRb1', 'SCLBb2', 'MFTSb9', 'MFRFb15', 'MFRFb19', 'MFBHb2', 'GLLKb2', 'MFSCb10', 'KZIKb42', 'UZPAb1', 'MFSLb15', 'MFUCb8', 'SWPSb1', 'MFLNb2', 'MFOKb26', 'MFMCb3', 'ORBSb8', 'TSSPb1', 'BIGDb11', 'BIGDb7', 'BIGDb8', 'MFACb4', 'MFRFb16', 'KZTCb3', 'MFOKb24', 'TTLSb2', 'SCLBb3', 'MFOKb25', 'MFBLb10', 'MFMOb30', 'SCLBb1', 'MNLTb1', 'MFOKb21', 'HCBNb13', 'MFAFb19', 'MFUCb9', 'MFHCb1', 'MFMOb46', 'MFMOb29', 'ORBSb6', 'TSSPb8', 'MFSLb12', 'MFMOb40', 'MFCIb2', 'QGLDb1', 'BIGDb6', 'FPSTb14', 'MFAFb14', 'MFMOb25', 'MFRFb21', 'MFRFb18', 'MFOKb20', 'MFMOb34', 'MFRFb13', 'MFACb3', 'MFOKb35', 'CLSGb4', 'MFDFb3', 'ACARb1', 'KZIKb27', 'MFSFb19', 'MFSCb8', 'MFAFb18', 'MFMOb23', 'MFMOb33', 'HCBNb14', 'BIGDb5', 'MFOKb27', 'NCOMb16', 'MFOKb37', 'MFMOb32', 'MFSLb5', 'MRDNb1', 'FIVEb7', 'SKKZb11', 'MFMOb28', 'ORBSb7', 'MFSTb1', 'MFMOb26', 'MFCFb2', 'MFLGb8', 'LZGRb21', 'MFSLb11', 'MFSCb5', 'MFOKb36', 'FPSTb9', 'MFLGb22', 'MFOKb19', 'KFUSb47', 'KFUSb46', 'NCOMb10', 'MFDFb5', 'MFSFb7', 'GLLKb1', 'MFRFb9', 'LZGRb18', 'MFCFb1', 'ASKQb1']
CODES_USD = ['AMRLs1', 'ALMSb1', 'KMGZe11', 'JETGe1', 'HSBKb22']
CODES = CODES_TENGE + CODES_USD
FALLBACK_TENGE = [('BRKZb36', 99.98, 2510, 15.6), ('KZIKb46', 109.86, 2373, 16.99), ('KEGCb3', 94.7, 3066, 11.0), ('KFUSb1', 93.15, 2129, 12.0), ('JSBNb10', 110.96, 1550, 17.5), ('SMTLb2', 101.0, 1040, 23.0), ('IDFRb8', 112.93, 1397, 19.0), ('MFRFb30', 101.0, 1071, 22.0), ('HCBNb17', 108.25, 1312, 19.1), ('BTRKb8', 87.7, 1829, 11.0), ('CLSGb14', 101.0, 1057, 21.5), ('CLSGb13', 100.1, 992, 22.5), ('JSBNb8', 111.1, 1341, 18.0), ('BTRKb22', 107.6, 1280, 17.5), ('CLSGb16', 101.5, 891, 23.0), ('MFRFb27', 101.94, 871, 23.0), ('TTLSb3', 100.0, 981, 20.0), ('CLSGb11', 101.79, 864, 23.0), ('JSBNb6', 108.1, 1258, 16.5), ('MFKMb12', 102.6, 904, 21.0), ('CLSGb15', 99.5, 794, 23.0), ('MFRFb26', 102.0, 799, 23.0), ('CLSGb10', 100.69, 788, 23.0), ('MFOKb28', 99.48, 752, 23.0), ('INBNb18', 102.68, 1021, 17.25), ('HCBNb29', 102.06, 993, 17.5), ('ATBNb3', 100.59, 1022, 16.5), ('CLSGb9', 101.55, 738, 23.0), ('MFTSb8', 101.17, 761, 22.0), ('MFMOb38', 99.99, 701, 23.0), ('MFSFb1', 100.0, 729, 22.0), ('MFDFb4', 100.0, 715, 22.0), ('MFRFb24', 101.93, 692, 23.0), ('KAFIb12', 105.0, 966, 16.85), ('MFLGb24', 100.0, 670, 23.0), ('SMTLb1', 99.0, 692, 22.0), ('QBTMb1', 101.39, 703, 22.0), ('MFOKb31', 100.0, 719, 21.0), ('MFOKb30', 100.0, 719, 21.0), ('ERBBb2', 100.1, 602, 25.0), ('MFKMb8', 104.0, 740, 21.0), ('MFBLb7', 98.51, 662, 21.0), ('JSBNb3', 97.29, 962, 14.25), ('CLSGb8', 99.5, 664, 21.0), ('MFMOb37', 101.0, 605, 23.0), ('MFKTb4', 98.5, 658, 20.0), ('MFCRb1', 100.0, 558, 23.0), ('SCLBb2', 101.0, 616, 21.0), ('MFTSb9', 101.5, 581, 22.0), ('MFRFb15', 101.47, 547, 23.0), ('MFRFb19', 98.0, 574, 21.0), ('MFBHb2', 99.98, 532, 23.0), ('GLLKb2', 99.99, 532, 23.0), ('MFSCb10', 99.99, 578, 21.0), ('KZIKb42', 104.05, 662, 18.85), ('UZPAb1', 102.4, 552, 21.5), ('MFSLb15', 100.2, 553, 21.0), ('MFUCb8', 99.0, 566, 20.0), ('SWPSb1', 101.0, 546, 21.0), ('MFLNb2', 100.0, 489, 23.0), ('MFOKb26', 96.02, 568, 19.0), ('MFMCb3', 101.91, 538, 21.0), ('ORBSb8', 101.83, 509, 22.0), ('TSSPb1', 98.59, 588, 18.0), ('BIGDb11', 102.2, 539, 20.0), ('BIGDb7', 102.53, 539, 20.0), ('BIGDb8', 102.53, 539, 20.0), ('MFACb4', 99.5, 497, 21.0), ('MFRFb16', 97.99, 486, 21.0), ('KZTCb3', 104.49, 475, 22.0), ('MFOKb24', 100.5, 470, 21.0), ('TTLSb2', 100.0, 981, 10.0), ('SCLBb3', 110.0, 959, 11.0), ('MFOKb25', 97.0, 489, 19.0), ('MFBLb10', 101.0, 419, 23.0), ('MFMOb30', 90.0, 379, 22.0), ('SCLBb1', 99.98, 428, 20.25), ('MNLTb1', 101.0, 394, 22.0), ('MFOKb21', 97.86, 426, 19.0), ('HCBNb13', 101.0, 455, 18.15), ('MFAFb19', 100.0, 337, 23.0), ('MFUCb9', 98.19, 676, 11.0), ('MFHCb1', 98.0, 325, 22.0), ('MFMOb46', 99.99, 328, 22.0), ('MFMOb29', 97.0, 314, 22.0), ('ORBSb6', 100.0, 724, 9.5), ('TSSPb8', 99.98, 340, 20.0), ('MFSLb12', 100.78, 325, 21.0), ('MFMOb40', 100.1, 572, 11.0), ('MFCIb2', 60.1, 171, 22.0), ('QGLDb1', 100.0, 613, 10.0), ('BIGDb6', 101.0, 296, 20.5), ('FPSTb14', 99.97, 300, 20.0), ('MFAFb14', 101.0, 254, 23.0), ('MFMOb25', 99.8, 259, 22.0), ('MFRFb21', 99.9, 256, 22.0), ('MFRFb18', 101.17, 240, 22.0), ('MFOKb20', 97.98, 263, 19.0), ('MFMOb34', 100.0, 454, 11.0), ('MFRFb13', 99.1, 223, 22.0), ('MFACb3', 100.64, 248, 20.0), ('MFOKb35', 100.7, 198, 24.0), ('CLSGb4', 100.0, 228, 20.5), ('MFDFb3', 99.5, 214, 21.0), ('ACARb1', 98.9, 229, 19.5), ('KZIKb27', 95.72, 383, 10.5), ('MFSFb19', 100.0, 350, 12.0), ('MFSCb8', 97.3, 184, 21.5), ('MFAFb18', 99.18, 310, 13.0), ('MFMOb23', 97.0, 174, 22.0), ('MFMOb33', 99.95, 357, 11.0), ('HCBNb14', 99.28, 213, 17.25), ('BIGDb5', 101.65, 187, 19.5), ('MFOKb27', 99.6, 356, 10.0), ('NCOMb16', 99.98, 321, 11.0), ('MFOKb37', 100.0, 141, 23.0), ('MFMOb32', 97.0, 268, 11.0), ('MFSLb5', 99.59, 143, 21.0), ('MRDNb1', 100.0, 289, 10.0), ('FIVEb7', 100.0, 110, 25.0), ('SKKZb11', 97.82, 251, 10.5), ('MFMOb28', 99.9, 208, 12.0), ('ORBSb7', 100.32, 104, 22.0), ('MFSTb1', 100.65, 86, 24.5), ('MFMOb26', 100.0, 174, 12.0), ('MFCFb2', 101.4, 88, 22.5), ('MFLGb8', 99.29, 94, 20.0), ('LZGRb21', 104.0, 86, 22.0), ('MFSLb11', 100.21, 82, 21.0), ('MFSCb5', 100.0, 153, 10.5), ('MFOKb36', 99.61, 141, 11.0), ('FPSTb9', 99.98, 138, 10.5), ('MFLGb22', 99.0, 61, 22.0), ('MFOKb19', 99.2, 116, 10.0), ('KFUSb47', 102.92, 424, 2.55), ('KFUSb46', 103.04, 368, 2.4), ('NCOMb10', 100.0, 70, 11.0), ('MFDFb5', 101.2, 33, 23.0), ('MFSFb7', 99.25, 27, 23.0), ('GLLKb1', 101.0, 26, 24.0), ('MFRFb9', 100.0, 22, 25.0), ('LZGRb18', 100.6, 52, 10.5), ('MFCFb1', 100.0, 5, 21.0), ('ASKQb1', 94.8, 9, 9.0)]
FALLBACK_USD = [('AMRLs1', 10.25, 726, 11.0), ('ALMSb1', 101.3, 394, 8.0), ('KMGZe11', 99.98, 147, 4.75), ('JETGe1', 99.7, 29, 20.75), ('HSBKb22', 101.77, 376, 1.25)]
KURS_USD = 525
app = Flask(__name__)
def clean_num(s):
    if not s: return 0
    s = str(s).replace('\xa0','').replace(' ','').replace(',','.')
    m = re.search(r'(\d+\.?\d*)', s)
    return float(m.group(1)) if m else 0
def risk_for(code, price, coupon):
    yld = coupon/price*100 if price else 0
    if price < 50: return "МУСОР"
    if price < 80: return "ПРОВЕРЬ"
    if re.match(r'^MF', code): return "РИСК"
    if yld > 25: return "РИСК"
    if yld > 18: return "сред"
    return "ОК"
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
        currency = 'USD' if code in CODES_USD else 'KZT'
        yld = coupon/price*100
        return {'code': code, 'price': price, 'days': days, 'coupon': coupon, 'yld': round(yld,2), 'risk': risk_for(code, price, coupon), 'currency': currency}
    except Exception as e:
        print(f"| {code} ошибка: {e}")
        return None
def make_fallback():
    out=[]
    for code, price, days, coupon in FALLBACK_TENGE:
        yld = coupon/price*100
        out.append({'code': code, 'price': price, 'days': days, 'coupon': coupon, 'yld': round(yld,2), 'risk': risk_for(code, price, coupon), 'currency': 'KZT'})
    for code, price, days, coupon in FALLBACK_USD:
        yld = coupon/price*100
        out.append({'code': code, 'price': price, 'days': days, 'coupon': coupon, 'yld': round(yld,2), 'risk': risk_for(code, price, coupon), 'currency': 'USD'})
    return out
def update_loop():
    while True:
        try:
            print("| Качаю ВСЕ 149 с KASE (тенге + доллары, безопасные + рисковые)...")
            fresh=[]
            for i, code in enumerate(CODES):
                b = get_info(code)
                if b: fresh.append(b)
                if i % 20 == 0: print(f"| {i}/{len(CODES)}...")
                time.sleep(0.2)
            if len(fresh) > 10:
                now = datetime.datetime.now().strftime("%d.%m %H:%M:%S")
                with open("bonds_live.json","w",encoding="utf-8") as f:
                    json.dump({"updated": now+" (настоящие с KASE)", "status": "live", "bonds": fresh, "kurs_usd": KURS_USD}, f, ensure_ascii=False)
                print(f"| ГОТОВО! {len(fresh)} облигаций в {now}")
        except Exception as e:
            print(f"| Ошибка: {e}")
        print("| Жду 15 минут...")
        time.sleep(15*60)
@app.route("/")
def index(): return send_from_directory(".", "bonds_app_live.html")
@app.route("/bonds_app_live.html")
def app_html(): return send_from_directory(".", "bonds_app_live.html")
@app.route("/api/bonds")
def api():
    try:
        with open("bonds_live.json", encoding="utf-8") as f: return jsonify(json.load(f))
    except:
        return jsonify({"updated": "еще нет", "status": "fallback", "bonds": make_fallback(), "kurs_usd": KURS_USD})
threading.Thread(target=update_loop, daemon=True).start()
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
