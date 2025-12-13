import google.generativeai as genai
import sqlite3
import pandas as pd
import os
from datetime import datetime

# ================= 設定區 =================

import json
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
        
        # 綁定工具
        self.tools = [self.query_database]
        
        # 初始化模型
        self.model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            tools=self.tools,
            system_instruction=self._construct_system_prompt()
        )
        
        # 啟動對話
        self.chat_session = self.model.start_chat(enable_automatic_function_calling=True)

    def _get_db_schema(self):
        if not os.path.exists(self.db_path):
            return "錯誤：找不到資料庫檔案 house.db"
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        schema_str = "資料庫結構 (SQLite):\n"
        tables = ['houses', 'stats_district_overview', 'stats_monthly_trend', 'stats_yearly_trend']
        
        for table in tables:
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                if columns:
                    col_names = [f"{col[1]} ({col[2]})" for col in columns]
                    schema_str += f"- 表名: {table}\n  欄位: {', '.join(col_names)}\n"
            except Exception:
                continue
        conn.close()
        return schema_str

    def _construct_system_prompt(self):
        # 獲取當前年份，讓 AI 知道「去年」是哪一年
        current_year = datetime.now().year
        
        return f"""
        你是一個專業的台灣房地產看房助手。現在時間是 {current_year} 年。
        
        【你的任務】
        將使用者的自然語言問題轉換為 SQL，查詢 SQLite 資料庫，並根據結果回答問題。
        
        【資料庫 Schema】
        {self.schema_info}
        
        【重要欄位與值域說明】
        1. type_category: '電梯大樓', '公寓', '透天', '套房', '其他'。
        2. district: 例如 '松山區', '大安區'。
        3. year_month: 格式 'YYYY-MM' (stats_monthly_trend 表)。
        4. year: 數字格式 (例如 2023)。
        
        【查詢策略 Router (重要！)】
        1. **問「趨勢」、「走勢」、「每個月」：**
           - 查詢 `stats_monthly_trend`。
           - **務必加上時間篩選**：例如「過去一年」代表 `WHERE year >= {current_year - 1}`。
           - **務必排序**：`ORDER BY year_month ASC`。
           - 範例 SQL: SELECT year_month, avg_price_per_ping FROM stats_monthly_trend WHERE district='大安區' AND year >= {current_year - 1} ORDER BY year_month ASC;
        
        2. **問「行情」、「平均」、「比較」：**
           - 查詢 `stats_district_overview` 表。
        
        3. **問「找房子」、「具體物件」：**
           - 查詢 `houses` 表，**務必加上 `LIMIT 10`**。

        【回答規範】
        - 若 SQL 查無資料，請回答「資料庫中找不到符合條件的數據」。
        - 請根據數據做簡單分析（例如：呈現上漲或下跌趨勢）。
        """

    def query_database(self, sql_query: str):
        """ 執行 SQLite 查詢並回傳結果 (JSON 格式) """
        print(f"\n[系統] 正在執行 SQL: \033[96m{sql_query}\033[0m") 
        
        try:
            conn = sqlite3.connect(self.db_path)
            df = pd.read_sql(sql_query, conn)
            conn.close()
            
            if df.empty:
                return "查詢成功，但結果為空 (No Data Found)。"
            
            # 限制回傳行數，避免 Token 爆炸導致 AI 當機
            if len(df) > 30:
                print(f"[系統提醒] 資料量過大 ({len(df)} 筆)，已自動截斷為前 30 筆給 AI 分析。")
                df = df.head(30)
            
            # 轉為 JSON 字串
            return df.to_json(orient='records', force_ascii=False)
            
        except Exception as e:
            error_msg = f"SQL Error: {str(e)}"
            print(f"[系統錯誤] {error_msg}")
            return error_msg

    def chat(self, user_input):
        try:
            response = self.chat_session.send_message(user_input)
            
            # 安全地獲取文字內容
            if response.parts:
                return response.text
            else:
                # 如果沒有文字部分，可能是模型認為工具執行完就結束了，嘗試檢查是否有其他內容
                # 或者回傳一個預設訊息
                return "（系統：AI 已執行查詢，但沒有產生文字回應。請試著換個方式問，例如『請根據上述數據告訴我結論』）"
                
        except ValueError:
            # 這是捕捉您剛剛遇到的那個 "Quick accessor" 錯誤
            return "發生格式錯誤 (ValueError)。這通常是因為查詢結果太長，或是 AI 忘記說話。請嘗試縮小查詢範圍（例如：指定具體年份）。"
        except Exception as e:
            return f"發生未知錯誤: {str(e)}"

if __name__ == "__main__":
    agent = HouseAgent()
    
    print("🏠 看房小助手已啟動 (輸入 'exit' 離開)")
    print("--------------------------------------------------")
    
    while True:
        user_text = input("\n請輸入您的問題: ")
        if user_text.lower() in ['exit', 'quit']:
            break
            
        response = agent.chat(user_text)
        print(f"\n🤖 小助手: {response}")
        print("-" * 50)