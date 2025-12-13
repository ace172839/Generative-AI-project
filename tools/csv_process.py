import pandas as pd
import sqlite3
import re
import os

# ================= 設定區 =================
INPUT_FILE = 'house.csv'
DB_FILE = 'house.db'
TABLE_NAME = 'houses'

# 定義欄位映射： {原始中文欄位: 新的英文欄位}
# 這些英文名稱是為了讓 LLM (Gemini) 更容易理解並寫出正確 SQL
COLUMN_MAPPING = {
    '地址': 'address',
    '交易日期': 'trade_date',
    '總價(萬元)': 'total_price',
    '單價(萬元/坪)': 'unit_price',
    '建物移轉總面積(坪)': 'area',
    '建物型態': 'building_type',
    '屋齡': 'age',
    '樓別': 'floor',
    '車位筆數': 'parking_count',
    '房數': 'room',
    '廳數': 'hall',
    '衛數': 'bath',
    '管理組織': 'management_org',
    '電梯': 'elevator',
    '主要用途': 'main_usage',
    '經度': 'longitude',
    '緯度': 'latitude',
    '縣市': 'city',
    '行政區': 'district'  # 這是我們計算出來的欄位
}

# 需要強制轉為數字的欄位 (以便 SQL 做 > < = 運算)
NUMERIC_COLS = [
    'total_price', 'unit_price', 'area', 'age', 
    'parking_count', 'room', 'hall', 'bath', 
    'longitude', 'latitude'
]
# =========================================

def extract_district(addr):
    """ 從地址中擷取行政區 """
    if pd.isna(addr):
        return None
    addr = str(addr)
    match = re.search(r'^.{3}(.+?[區鄉鎮市])', addr)
    if match:
        return match.group(1)
    return None

def process_data():
    print(f"1. 讀取 {INPUT_FILE}...")
    try:
        df = pd.read_csv(INPUT_FILE, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(INPUT_FILE, encoding='big5')

    # 2. 產生「行政區」資料
    print("2. 計算行政區...")
    df['行政區'] = df['地址'].apply(extract_district)

    # 3. 過濾欄位 (只保留您指定的欄位)
    print("3. 篩選與重命名欄位...")
    
    # 檢查 CSV 裡是否真的有這些欄位，避免報錯
    existing_cols = [col for col in COLUMN_MAPPING.keys() if col in df.columns]
    
    # 只選取存在的欄位
    df = df[existing_cols]
    
    # 重命名為英文
    df.rename(columns=COLUMN_MAPPING, inplace=True)

    # 4. 型態轉換 (文字 -> 數字)
    print("4. 數值標準化...")
    for col in NUMERIC_COLS:
        if col in df.columns:
            # 轉數字，無法轉的變 NaN，然後補 0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 5. 寫入 SQLite
    print(f"5. 寫入資料庫 {DB_FILE}...")
    conn = sqlite3.connect(DB_FILE)
    df.to_sql(TABLE_NAME, conn, if_exists='replace', index=False)

    # 建立索引 (Index) 加速查詢
    cursor = conn.cursor()
    # 針對常用查詢欄位建立索引
    indices = ['district', 'total_price', 'room', 'age', 'building_type']
    for idx in indices:
        if idx in df.columns:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{idx} ON {TABLE_NAME} ({idx})")
    
    conn.close()

    print("="*30)
    print(f"✅ 資料庫重建完成！")
    print(f"   欄位檢查 (前5筆):")
    print(df[['address', 'district', 'total_price', 'room']].head())
    print("="*30)

if __name__ == "__main__":
    if os.path.exists(INPUT_FILE):
        process_data()
    else:
        print(f"❌ 找不到 {INPUT_FILE}")