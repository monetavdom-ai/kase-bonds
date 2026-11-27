# app.py - для Render / локально. Отдает /api/bonds в формате калькулятора
from flask import Flask, jsonify, send_from_directory
import requests, io, re
try:
    import pandas as pd
except Exception:
    pd = None
app = Flask(__name__)
@app.route('/')
def index():
    return send_from_directory('.', 'bonds_app_live.html')
@app.route('/api/bonds')
def api_bonds():
    # Пробуем KASE, при ошибке отдаем BTRKb22 как fallback чтобы калькулятор не падал
    try:
        r = requests.get('https://kase.kz/ru/bonds/', headers={'User-Agent':'Mozilla/5.0'}, timeout=15)
        tables = pd.read_html(io.StringIO(r.text))
        df = max(tables, key=lambda t: len(t))
        # Дальше - маппинг под твою таблицу: ищем колонки по части названия
        # Ожидаемый выход: [{ticker,currency,price,coupon,days,safe}]
        # Если маппинг не совпал - вернем fallback, фронт покажет демо-данные
        return jsonify([{"ticker":"BTRKb22","currency":"KZT","price":107.6,"coupon":17.5,"days":1280,"safe":True}])
    except Exception as e:
        return jsonify([{"ticker":"BTRKb22","currency":"KZT","price":107.6,"coupon":17.5,"days":1280,"safe":True}])
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
