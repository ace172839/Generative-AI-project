import google.generativeai as genai
import sqlite3
import pandas as pd
import json
import re
import os
from datetime import datetime

with open('keys.json', 'r') as f:
    keys = json.load(f)
API_KEY = keys['gemini_api_key']
DB_PATH = "house.db"
genai.configure(api_key=API_KEY)

class HouseAgent:
    def __init__(self):
        self.db_path = DB_PATH
        self.model = genai.GenerativeModel(
            model_name='gemini-2.0-flash-exp', 
            system_instruction=self._construct_system_prompt()
        )
        self.chat_session = self.model.start_chat()

    def _construct_system_prompt(self):
        current_year = datetime.now().year
        return f"""
        你是一個專業的台灣房地產數據分析助手。現在時間是 {current_year} 年。
        
        【任務】
        將使用者問題轉換為 **SQLite SQL 查詢**。只產生 SQL，不要執行。

        【資料庫 Schema】
        1. `stats_monthly_trend` (月度趨勢): `year_month`, `city`, `district`, `type_category`, `avg_price_per_ping`, `tx_count`.
           - 用途: 趨勢、走勢。
        
        2. `houses` (原始交易資料 - **找房/查價用**): 
           - 欄位: `city`, `district`, `address`, `total_price`, `unit_price`, `area`, `age`, `floor`, `room`, `building_type`, `trade_date`, `latitude`, `longitude`。
           - **【地圖強制規範】(重要!)**:
             當查詢 `houses` 表以尋找特定路段、區域或物件時，**SQL 查詢務必包含 `latitude` 和 `longitude` 欄位**，以便前端繪製地圖。
             範例: `SELECT district, address, total_price, unit_price, latitude, longitude FROM houses WHERE address LIKE '%民權東路%' LIMIT 10`

        3. `stats_district_overview` (區域比較用): ...

        【輸出規定】
        1. SQL 包在 Markdown: ```sql SELECT ... ```
        2. JSON 設定:
           ```json
           {{
               "visual_type": "line_chart", // 或 "bar_chart", "table" (若不適合畫圖就用 table)
               "title": "查詢結果標題",
               "columns": ["X軸/第一欄", "Y軸/第二欄"], 
               "tooltips": ["其他欄位"]
           }}
           ```
        """

    def _execute_sql_locally(self, sql_query):
        print(f"\n[系統執行 SQL] {sql_query}")
        try:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql(sql_query, conn)
            conn.close()
            return df
        except Exception as e:
            print(f"[SQL Error] {e}")
            return pd.DataFrame()

    def chat(self, user_input):
        try:
            response = self.chat_session.send_message(user_input)
            raw_text = response.text
            result = {"text": raw_text, "chart_data": None}

            sql_match = re.search(r'```sql\s*(SELECT.*?)```', raw_text, re.DOTALL | re.IGNORECASE)
            if sql_match:
                sql_query = sql_match.group(1)
                df = self._execute_sql_locally(sql_query)
                
                if not df.empty:
                    json_config = {}
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', raw_text, re.DOTALL)
                    if json_match:
                        try: json_config = json.loads(json_match.group(1))
                        except: pass
                    
                    result["chart_data"] = {
                        "visual_type": json_config.get("visual_type", "table"), # 預設改為 table
                        "title": json_config.get("title", "查詢結果"),
                        "columns": json_config.get("columns", list(df.columns)),
                        "tooltips": json_config.get("tooltips", []),
                        "data": df.to_dict(orient='records')
                    }
                    result["text"] += f"\n\n(✨ 成功檢索到 {len(df)} 筆資料)"
                else:
                    result["text"] += "\n\n(查無資料)"
            
            return result
        except Exception as e:
            return {"text": str(e), "chart_data": None}