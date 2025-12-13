import sqlite3
import pandas as pd
import os

# ================= 設定區 =================
DB_FILE = 'house.db'
# 我們要檢查這些欄位，看看裡面到底藏了什麼怪東西
TARGET_COLS = [
    'building_type',   # 建物型態 (最重要，決定公寓/大樓)
    'main_usage',      # 主要用途 (決定是住家、商業、停車場?)
    'district',        # 行政區 (檢查有沒有寫錯字的)
    'city',            # 縣市 (檢查是否統一)
    'floor'            # 樓別 (檢查格式)
]
# =========================================

def inspect_columns():
    if not os.path.exists(DB_FILE):
        print(f"❌ 找不到 {DB_FILE}，請先確認 Phase 1 是否執行成功。")
        return

    print(f"🔍 正在連接資料庫 {DB_FILE} 進行資料健檢...\n")
    conn = sqlite3.connect(DB_FILE)

    for col in TARGET_COLS:
        print(f"📊 正在分析欄位：【 {col} 】")
        print("-" * 40)
        
        try:
            # 使用 SQL Group By 計算每個值出現幾次，並由多到少排序
            query = f"""
            SELECT "{col}", COUNT(*) as count 
            FROM houses 
            GROUP BY "{col}" 
            ORDER BY count DESC
            """
            df = pd.read_sql(query, conn)
            
            # 印出結果
            if df.empty:
                print("   (空白 - 此欄位沒有資料)")
            else:
                # 為了版面整潔，如果不超過 50 種，全印；超過則印前 20 種
                print(df.to_string(index=False))
                
                if len(df) > 20:
                    print(f"\n   ... (還有 {len(df)-20} 種較少見的值未列出)")
        
        except Exception as e:
            print(f"   讀取失敗：{e}")
            
        print("\n" + "="*40 + "\n")

    conn.close()

if __name__ == "__main__":
    inspect_columns()