import sqlite3
import os

DB_PATH = 'house.db'

def normalize_database():
    if not os.path.exists(DB_PATH):
        print(f"❌ 找不到資料庫: {DB_PATH}")
        return

    print(f"正在連線至 {DB_PATH} 進行標準化 (臺 -> 台)...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. 處理主表 houses
        # 針對可能出現「臺」的欄位進行取代
        tables = {
            'houses': ['city', 'district', 'address'],
            'stats_monthly_trend': ['city', 'district'],
            'stats_district_overview': ['city', 'district'],
            'stats_yearly_trend': ['city', 'district'] # 如果有這張表的話
        }

        for table, columns in tables.items():
            # 先檢查表是否存在
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            if cursor.fetchone():
                print(f"正在處理資料表: {table}...")
                for col in columns:
                    # 使用 SQLite 內建的 REPLACE 函數
                    sql = f"UPDATE {table} SET {col} = REPLACE({col}, '臺', '台') WHERE {col} LIKE '%臺%'"
                    cursor.execute(sql)
                    if cursor.rowcount > 0:
                        print(f"   - 欄位 {col}: 更新了 {cursor.rowcount} 筆資料")
            else:
                print(f"跳過 (找不到表): {table}")

        conn.commit()
        print("✅ 資料庫標準化完成！所有「臺」已轉為「台」。")

    except Exception as e:
        conn.rollback()
        print(f"❌ 發生錯誤: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    normalize_database()