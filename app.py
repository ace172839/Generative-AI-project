import json
import os
import re
import sys
import threading
import webview
from flask import Flask, request, jsonify, render_template
from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError
from math import radians, sin, cos, sqrt, atan2

# --- 輔助函式：處理打包後的路徑 ---
def resource_path(relative_path):
    """ 取得資源的絕對路徑，對開發和 PyInstaller 打包都有效 """
    try:
        # PyInstaller 會建立一個暫存資料夾，並將路徑儲存在 _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- 配置 ---
template_folder = resource_path('templates')
app = Flask(__name__, template_folder=template_folder)
API_TOKEN = ""  # 請確保這是您有效的 Hugging Face Token
AI_MODEL = "google/gemma-2-9b-it"
DATA_FILE = resource_path('data.json')

# --- 載入房屋資料 ---
try:
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        house_data = json.load(f)
    print(f"✅ 成功載入 {len(house_data)} 筆房屋資料。")
except FileNotFoundError:
    print(f"🔴 錯誤: 找不到資料檔案 {DATA_FILE}")
    house_data = []
except json.JSONDecodeError:
    print(f"🔴 錯誤: {DATA_FILE} 格式不正確。")
    house_data = []


# --- 輔助函式 ---

def get_ai_criteria(user_requirement: str) -> dict:
    """呼叫 AI 模型將使用者需求轉換為 JSON 格式的 SQL 查詢"""
    prompt_for_ai = f"""Please help me convert the user's requirement: "{user_requirement}" into a structured JSON format.
The JSON should contain these keys: [location, distance, age, size, price, labels_to_exclude, labels_to_include].

- 'location': A tuple (latitude, longitude) for the central point of search (e.g., a specific MRT station).
- 'distance': A number in kilometers for the search radius. Assume 10 minutes of commute time equals 1 km.
- 'age': A SQL-like condition for the house's age (e.g., "age <= 10").
- 'size': A SQL-like condition for the house's size in square meters (e.g., "size >= 30").
- 'price': A SQL-like condition for the house's price in NT dollars (e.g., "price <= 24000000").
- 'labels_to_exclude': A list of strings for labels to exclude (e.g., ["temple", "funeral_home"]).
- 'labels_to_include': A list of strings for labels that must be included (e.g., ["hospital", "MRT station"]).

Please answer with only the JSON object, without any additional text or markdown.
If a field is not specified, set its value to null.
"""
    client = InferenceClient(model=AI_MODEL, token=API_TOKEN)
    try:
        response = client.chat_completion(
            messages=[{"role": "user", "content": prompt_for_ai}],
            max_tokens=500,
            temperature=0.1, # 降低隨機性以獲得更穩定的 JSON 輸出
        )
        response_text = response.choices[0].message.content or ""
        
        # 清理 AI 回應，只留下 JSON 部分
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if not json_match:
            print("🔴 AI 未回傳有效的 JSON 格式。")
            return {}
            
        return json.loads(json_match.group(0))

    except HfHubHTTPError as e:
        print(f"🔴 Hugging Face API 錯誤: {e.response.text}")
        return {}
    except Exception as e:
        print(f"🔴 未預期的錯誤: {e}")
        return {}

def haversine(lat1, lon1, lat2, lon2):
    """計算兩個經緯度座標之間的距離（公里）"""
    R = 6371.0  # 地球半徑（公里）
    lat1_rad, lon1_rad = radians(lat1), radians(lon1)
    lat2_rad, lon2_rad = radians(lat2), radians(lon2)
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = sin(dlat / 2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c

def evaluate_sql_condition(value, condition_str):
    """評估一個簡單的 SQL-like 條件"""
    if not condition_str or not isinstance(condition_str, str):
        return True
    try:
        # 為了安全，只允許簡單的比較
        match = re.match(r'^\w+\s*([<>=!]+)\s*([\d\.]+)$', condition_str.replace("price", "value").replace("age", "value").replace("size", "value"))
        if not match: return True
        
        operator = match.group(1)
        condition_value = float(match.group(2))
        
        if operator == '<=': return value <= condition_value
        if operator == '>=': return value >= condition_value
        if operator == '<': return value < condition_value
        if operator == '>': return value > condition_value
        if operator == '=': return value == condition_value
        if operator == '!=': return value != condition_value
        return True
    except:
        return True # 如果條件解析失敗，則忽略此條件

def filter_houses(criteria: dict) -> list:
    """根據 AI 解析出的條件篩選房屋"""
    if not house_data:
        return []

    filtered = house_data

    # 1. 地點和距離篩選
    if criteria.get('location') and criteria.get('distance'):
        center_lat, center_lon = criteria['location']
        max_dist = criteria['distance']
        filtered = [h for h in filtered if haversine(center_lat, center_lon, h['latitude'], h['longitude']) <= max_dist]

    # 2. 價格、年齡、大小篩選
    if criteria.get('price'):
        filtered = [h for h in filtered if evaluate_sql_condition(h['price'], criteria['price'])]
    if criteria.get('age'):
        filtered = [h for h in filtered if evaluate_sql_condition(h['age'], criteria['age'])]
    if criteria.get('size'):
        filtered = [h for h in filtered if evaluate_sql_condition(h['size'], criteria['size'])]

    # 3. 標籤篩選
    if criteria.get('labels_to_exclude'):
        exclude_labels = set(criteria['labels_to_exclude'])
        filtered = [h for h in filtered if not exclude_labels.intersection(set(h.get('label', [])))]
    if criteria.get('labels_to_include'):
        include_labels = set(criteria['labels_to_include'])
        filtered = [h for h in filtered if include_labels.issubset(set(h.get('label', [])))]

    return filtered[:10] # 回傳前 10 筆

# --- Flask 路由 ---

@app.route('/')
def index():
    """渲染主頁面"""
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    """處理聊天訊息"""
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({"error": "沒有收到訊息"}), 400

    print(f"💬 使用者需求: {user_message}")

    # 步驟 1: 呼叫 AI 取得篩選條件
    criteria = get_ai_criteria(user_message)
    print(f"🤖 AI 解析結果: {criteria}")

    if not criteria:
        return jsonify({"reply": "抱歉，我無法理解您的需求，請換個方式說說看？"})

    # 步驟 2: 根據條件篩選房屋
    results = filter_houses(criteria)
    print(f"🔍 找到 {len(results)} 筆符合條件的房屋。")

    # 步驟 3: 組合回覆訊息
    if not results:
        reply_message = "很抱歉，目前找不到完全符合您條件的房屋。您可以試著放寬一些條件，例如預算或通勤距離。"
    else:
        reply_message = f"為您找到 {len(results)} 筆可能符合需求的房屋：\n\n"
        for house in results:
            reply_message += (
                f"🏠 **{house['name']}**\n"
                f"- 地址: {house['address']}\n"
                f"- 價格: {house['price']/10000:,.0f} 萬\n"
                f"- 坪數: {house['size']} 坪\n"
                f"- 格局: {house['bedroom']}房 / {house['living_room']}廳 / {house['bathroom']}衛\n"
                f"- 連結: [點此查看]({house['link']})\n---\n"
            )

    return jsonify({"reply": reply_message})

def run_server():
    """在背景執行緒中執行 Flask 伺服器"""
    # 使用 waitress 作為生產環境的 WSGI 伺服器，比 Flask 內建的更穩定
    from waitress import serve
    print("伺服器已啟動於 http://127.0.0.1:8080")
    serve(app, host='0.0.0.0', port=8080)

if __name__ == '__main__':
    # 步驟 1: 在背景執行緒中啟動 Flask 伺服器
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True  # 確保主程式關閉時，背景執行緒也會關閉
    server_thread.start()

    # 步驟 2: 建立並啟動 pywebview 視窗
    webview.create_window(
        'AI 智能找房助理',      # 視窗標題
        'http://127.0.0.1:8080', # 載入的網址
        width=900, height=700, resizable=True
    )
    webview.start()