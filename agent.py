import google.generativeai as genai
import sqlite3
import pandas as pd
import json
import os
import re
from datetime import datetime

# ================= 設定區 =================
with open('keys.json', 'r') as f:
    keys = json.load(f)

API_KEY = keys['gemini_api_key']
DB_PATH = "house.db"

genai.configure(api_key=API_KEY)
# =========================================

class HouseAgent:
    def __init__(self):
        self.db_path = DB_PATH
        self.schema_info = self._get_db_schema()
        
        self.model = genai.GenerativeModel(
            model_name='gemini-2.0-flash-exp', 
            system_instruction=self._construct_system_prompt()
        )
        self.chat_session = self.model.start_chat()

    def _get_db_schema(self):
        """ 動態讀取資料庫 Schema """
        if not os.path.exists(self.db_path):
            return "錯誤：找不到資料庫檔案 house.db"
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            schema_str = "資料庫結構 (SQLite):\n"
            tables = ['houses', 'stats_district_overview', 'stats_monthly_trend', 'stats_yearly_trend']
            
            for table in tables:
                cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
                if cursor.fetchone():
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = cursor.fetchall()
                    if columns:
                        col_names = [f"{col[1]} ({col[2]})" for col in columns]
                        schema_str += f"- 表名: {table}\n  欄位: {', '.join(col_names)}\n"
            
            conn.close()
            return schema_str
        except Exception as e:
            return f"讀取 Schema 失敗: {str(e)}"

    def _construct_system_prompt(self):
        current_year = datetime.now().year
        
        return f"""
        你是一個專業的台灣房地產看房助手。現在時間是 {current_year} 年。
        
        【任務】
        將使用者問題轉換為 **SQLite SQL 查詢**。
        **注意：你不需要執行查詢，只要產生 SQL 語法即可。**

        【資料庫 Schema】
        {self.schema_info}
        
        【最高指導原則 (Prime Directives)】
        1. **正規化**：請統一使用「台」字 (如：台北市)。
        
        2. **維度最大化**：統計查詢請保留所有維度 (year, district, type_category)，讓前端處理。
        
        3. **統計完整性 (Statistical Completeness)**：
           - **當使用 `GROUP BY` 進行統計時，請務必選取 `COUNT(*) AS tx_count`。**
           - 這樣使用者才能看到該分類下的「成交總量」，判斷市場熱度。
           - 範例：`SELECT district, AVG(unit_price), COUNT(*) AS tx_count FROM ... GROUP BY district`
           
        4. **單位換算**：
           - `total_price` 單位是「萬元」。預算 2000 萬 -> `total_price <= 2000`。
           - `unit_price` 單位是「萬元/坪」。

        5. **模糊搜尋**：找屋型或地址請用 `LIKE`。

        6. **地圖支援**：找房請 `SELECT *` + `LIMIT 300`。

        【輸出格式】
        1. SQL 包在 Markdown: ```sql SELECT ... ```
        2. JSON 設定:
           ```json
           {{
               "title": "查詢結果標題"
           }}
           ```
        """

    def _execute_sql_locally(self, sql_query):
        """ 本地執行 SQL """
        print(f"\n[系統正在執行 SQL] {sql_query}")
        try:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql(sql_query, conn)
            conn.close()
            
            if len(df) > 500:
                print(f"[系統保護] 資料量 ({len(df)}) 過大，自動截斷至 500 筆")
                df = df.head(500)
                
            return df
        except Exception as e:
            print(f"[SQL Error] {e}")
            return pd.DataFrame()

    def chat(self, user_input):
        try:
            # 1. 輸入正規化
            normalized_input = user_input.replace('臺', '台')
            
            # 2. 取得 LLM 回覆
            response = self.chat_session.send_message(normalized_input)
            raw_text = response.text
            
            result = {
                "text": raw_text,
                "chart_data": None
            }

            # 3. 解析並執行 SQL
            sql_match = re.search(r'```sql\s*(SELECT.*?)```', raw_text, re.DOTALL | re.IGNORECASE)
            
            if sql_match:
                sql_query = sql_match.group(1)
                
                # 強制執行 SQL
                df = self._execute_sql_locally(sql_query)
                
                if not df.empty:
                    # 4. 抓取圖表設定
                    json_config = {}
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', raw_text, re.DOTALL)
                    if json_match:
                        try:
                            json_config = json.loads(json_match.group(1))
                        except: pass
                    
                    # 5. 組裝資料
                    result["chart_data"] = {
                        "visual_type": json_config.get("visual_type", "table"),
                        "title": json_config.get("title", "查詢結果"),
                        "columns": json_config.get("columns", list(df.columns)),
                        "tooltips": json_config.get("tooltips", []),
                        "data": df.to_dict(orient='records')
                    }
                    
                    result["text"] += f"\n\n(✨ 系統訊息：成功檢索到 {len(df)} 筆資料)"
                else:
                    result["text"] += "\n\n(系統訊息：SQL 語法正確，但在資料庫中查無符合條件的數據。可能原因：金額單位不符或無此條件物件。)"
            
            return result

        except Exception as e:
            return {"text": f"系統發生錯誤: {str(e)}", "chart_data": None}

if __name__ == "__main__":
    agent = HouseAgent()
    print("🏠 Agent 初始化成功！(已加入單位換算與模糊搜尋)")