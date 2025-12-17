import pandas as pd
import sqlite3
import os

# ================= 設定區 =================
# 請依據您的實際檔名修改
INPUT_FILE = 'house.csv' 
DB_FILE = 'house.db'
# =========================================

def process_data():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ 找不到輸入檔案: {INPUT_FILE}")
        return

    print(f"1. 讀取 CSV 檔案: {INPUT_FILE} ...")
    try:
        df = pd.read_csv(INPUT_FILE)
    except Exception as e:
        print(f"❌ 讀取失敗: {e}")
        return

    print(f"   原始資料筆數: {len(df)}")

    # ================= [新增] 資料正規化與清洗 =================
    
    # 1. 欄位更名 (對應資料庫欄位)
    # 建議先確保欄位名稱是對應的英文，方便後續處理
    rename_map = {
        '縣市': 'city',
        '行政區': 'district',
        '地址': 'address',
        '總價(萬元)': 'total_price',
        '單價(萬元/坪)': 'unit_price',
        '建物移轉總面積(坪)': 'area',
        '屋齡': 'age',
        '樓別': 'floor',
        '房數': 'room',
        '廳數': 'hall',
        '衛數': 'bath',
        '建物型態': 'building_type',
        '主要用途': 'main_usage',
        '交易日期': 'trade_date',
        '緯度': 'latitude',
        '經度': 'longitude'
    }
    # 只更名有存在的欄位
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

    # 2. 字元正規化：把 '臺' 轉為 '台'
    print("2. 執行正規化 (臺 -> 台)...")
    str_cols = df.select_dtypes(include=['object']).columns
    for col in str_cols:
        df[col] = df[col].astype(str).str.replace('臺', '台')

    # 3. [關鍵] 去除髒資料 (Outlier Cleaning)
    print("3. 執行髒資料過濾 (去除價格異常值)...")
    
    # 轉換數值型態 (避免有些數字是字串導致比較失敗)
    df['unit_price'] = pd.to_numeric(df['unit_price'], errors='coerce')
    df['total_price'] = pd.to_numeric(df['total_price'], errors='coerce')
    
    # 設定過濾條件
    # 條件 A: 單價介於 1 萬 ~ 500 萬之間 (排除 0 與 13萬萬)
    # 條件 B: 總價大於 10 萬 (排除總價 2 萬元的異常交易)
    valid_price_mask = (
        (df['unit_price'] >= 1.0) & 
        (df['unit_price'] <= 500.0) &
        (df['total_price'] >= 10.0)
    )
    
    dirty_data_count = len(df) - valid_price_mask.sum()
    df_clean = df[valid_price_mask].copy()
    
    print(f"   🧹 已移除 {dirty_data_count} 筆異常資料 (單價<1萬 或 >500萬 或 總價<10萬)")

    # =========================================================

    print("4. 寫入 SQLite 資料庫...")
    conn = sqlite3.connect(DB_FILE)
    
    # 將處理乾淨的資料寫入 'houses' 表
    # if_exists='replace' 會刪除舊表重建，確保髒資料徹底消失
    df_clean.to_sql('houses', conn, if_exists='replace', index=False)
    
    # 建立索引以加速查詢
    cursor = conn.cursor()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_city_dist ON houses (city, district)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_price ON houses (total_price)")
    conn.close()
    
    print(f"✅ 資料處理完成！有效資料共 {len(df_clean)} 筆。")

if __name__ == "__main__":
    process_data()