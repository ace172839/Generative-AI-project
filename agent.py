import google.generativeai as genai
import sqlite3
import pandas as pd
import json
import os
import re
import sys
from datetime import datetime

# ================= 1. 跨平台路徑設定 =================
def get_base_path():
    """
    取得程式執行的根目錄：
    - 打包模式 (Frozen/Exe): 回傳 exe 所在目錄
    - 開發模式 (Dev/Python): 回傳 .py 所在目錄
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()
KEY_PATH = os.path.join(BASE_DIR, 'keys.json')
DB_PATH = os.path.join(BASE_DIR, 'house.db')

# 讀取 API Key
API_KEY = None
if os.path.exists(KEY_PATH):
    try:
        with open(KEY_PATH, 'r', encoding='utf-8') as f:
            keys = json.load(f)
            API_KEY = keys.get('gemini_api_key')
    except Exception as e:
        print(f"❌ 設定檔讀取錯誤: {e}")
else:
    print(f"❌ 找不到設定檔: {KEY_PATH}")

if API_KEY:
    genai.configure(api_key=API_KEY)

# ================= 2. Agent 類別 =================
class HouseAgent:
    def __init__(self):
        self.db_path = DB_PATH
        if not API_KEY:
            raise ValueError("API Key 未設定")
        
        # 取得真實 Table 白名單 (防呆用)
        self.valid_tables = self._get_valid_tables()
        self.schema_info = self._get_db_schema()
        
        self.model = genai.GenerativeModel(
            model_name='gemini-2.0-flash-exp', 
            system_instruction=self._construct_system_prompt()
        )
        self.chat_session = self.model.start_chat()

    def _get_valid_tables(self):
        tables = []
        if os.path.exists(self.db_path):
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                conn.close()
            except: pass
        return tables

    def _get_db_schema(self):
        if not self.valid_tables:
            return "錯誤：找不到資料庫檔案"
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            schema_str = "資料庫結構 (SQLite):\n"
            for table in self.valid_tables:
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
        
        【資料庫 Schema】
        {self.schema_info}
        
        【最高指導原則】
        1. **Table 防呆**：原始交易在 `houses`，統計在 `stats_...`。絕無 transactions 表。
        2. **維度最大化**：統計查詢保留 year, district, type_category。
        3. **統計完整性**：GROUP BY 時務必選取 `COUNT(*) AS tx_count`。
        4. **單位換算**：`total_price` (萬元), `unit_price` (萬元/坪)。
        5. **模糊搜尋**：找屋型/地址用 `LIKE`。
        6. **地圖支援**：`SELECT *` + `LIMIT 300` + `ORDER BY trade_date DESC`。
        
        7. **日期處理 (提取)**：
           - 嚴禁使用 `STRFTIME` 提取欄位。
           - 請改用 `SUBSTR(trade_date, 1, 4) AS year`。

        8. **[核心修正] 時間條件 (WHERE Clause)**：
           - **嚴禁在 SQL 中使用 `DATE('now')`、`STRFTIME('now')` 或 `datetime('now')`**。
           - 因為打包後的 SQLite 環境可能無法獲取系統時間。
           - **請直接使用具體的年份數字**。
           - 範例：若現在是 {current_year}，找過去三年，請直接寫 `year >= '{current_year - 3}'` (例如 `year >= '2022'`)。

        【輸出格式】
        1. SQL 包在 Markdown: ```sql SELECT ... ```
        2. JSON 設定: {{"title": "標題"}}
        """

    def _auto_correct_sql(self, sql_query):
        """ 防呆機制：強制替換不存在的表名 """
        pattern = r"FROM\s+([a-zA-Z0-9_]+)"
        match = re.search(pattern, sql_query, re.IGNORECASE)
        if match:
            wrong_table = match.group(1)
            if wrong_table not in self.valid_tables:
                print(f"⚠️ [防呆觸發] 修正幻覺表名 '{wrong_table}' -> 'houses'")
                sql_query = re.sub(pattern, "FROM houses", sql_query, count=1, flags=re.IGNORECASE)
        return sql_query

    def _execute_sql_locally(self, sql_query):
        sql_query = self._auto_correct_sql(sql_query)
        print(f"\n[系統正在執行 SQL] {sql_query}")
        try:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql(sql_query, conn)
            conn.close()
            if len(df) > 500:
                print(f"[系統保護] 資料量 ({len(df)}) 過大，自動截斷")
                df = df.head(500)
            return df, None
        except Exception as e:
            print(f"[SQL Error] {e}")
            return None, str(e)

    def chat(self, user_input):
        try:
            normalized_input = user_input.replace('臺', '台')
            response = self.chat_session.send_message(normalized_input)
            raw_text = response.text
            
            # 預設顯示文字 (稍後清理)
            display_text = raw_text
            result = {"text": "", "chart_data": None}
            
            # 解析 SQL
            sql_match = re.search(r'```sql\s*(SELECT.*?)```', raw_text, re.DOTALL | re.IGNORECASE)
            
            if sql_match:
                sql_query = sql_match.group(1)
                
                # [UI 清潔] 移除 SQL 與 JSON 區塊
                display_text = re.sub(r'```sql\s*(SELECT.*?)```', '', display_text, flags=re.DOTALL | re.IGNORECASE)
                display_text = re.sub(r'```json\s*(\{.*?\})\s*```', '', display_text, flags=re.DOTALL | re.IGNORECASE)
                display_text = display_text.strip()

                # 執行 SQL
                df, error_msg = self._execute_sql_locally(sql_query)
                
                if error_msg:
                    display_text += f"\n\n(❌ 系統訊息：資料讀取失敗。原因：{error_msg})"
                elif df is not None and not df.empty:
                    json_config = {}
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', raw_text, re.DOTALL)
                    if json_match:
                        try: json_config = json.loads(json_match.group(1))
                        except: pass
                    
                    result["chart_data"] = {
                        "visual_type": "dynamic",
                        "title": json_config.get("title", "查詢結果"),
                        "data": df.to_dict(orient='records')
                    }
                    display_text += f"\n\n(✨ 系統訊息：成功檢索到 {len(df)} 筆資料)"
                else:
                    display_text += "\n\n(系統訊息：查無符合條件的數據。)"
            
            result["text"] = display_text
            return result

        except Exception as e:
            return {"text": f"系統發生錯誤: {str(e)}", "chart_data": None}

if __name__ == "__main__":
    if API_KEY:
        agent = HouseAgent()
        print("✅ Agent 啟動成功 (Production Version)")