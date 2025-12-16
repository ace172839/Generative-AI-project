import sqlite3
import pandas as pd
import os

# ================= 設定區 =================
DB_FILE = 'house.db'
# =========================================

def classify_building_type(raw_type):
    if pd.isna(raw_type): return '其他'
    t = str(raw_type)
    if '套房' in t: return '套房'
    elif '公寓' in t: return '公寓'
    elif '透天' in t or '別墅' in t: return '透天'
    elif '大樓' in t or '華廈' in t or '電梯' in t: return '電梯大樓'
    else: return '其他'

def is_valid_residential(usage, building_type):
    if pd.isna(usage): return False
    u = str(usage)
    bt = str(building_type)
    exclude_keywords = ['車', '工', '廠', '倉', '農', '其他'] 
    for kw in exclude_keywords:
        if kw in u: return False
    if '工廠' in bt or '廠辦' in bt or '倉庫' in bt: return False
    if '住' in u or '商' in u: return True
    return False

def generate_stats():
    print(f"1. 連接資料庫 {DB_FILE}...")
    conn = sqlite3.connect(DB_FILE)
    
    # [修正 1] SELECT 加入 'city'
    query = """
    SELECT city, district, total_price, unit_price, area, 
           building_type, main_usage, trade_date, room, age
    FROM houses
    WHERE district IS NOT NULL
    """
    df = pd.read_sql(query, conn)
    print(f"   共讀取 {len(df)} 筆原始資料")

    print("2. 正在進行資料清洗與分類...")
    df['type_category'] = df['building_type'].apply(classify_building_type)
    mask = df.apply(lambda x: is_valid_residential(x['main_usage'], x['building_type']), axis=1)
    df_clean = df[mask].copy()
    
    df_clean['trade_date'] = pd.to_datetime(df_clean['trade_date'], errors='coerce')
    df_clean['year'] = df_clean['trade_date'].dt.year
    df_clean['month'] = df_clean['trade_date'].dt.month
    df_clean = df_clean[(df_clean['year'] >= 2012) & (df_clean['year'] <= 2025)]

    # [修正 2] 所有的 groupby 都必須加入 'city'
    
    # 表 1: 區域總覽
    print("3. 計算：區域總覽 (stats_district_overview)...")
    overview_stats = df_clean.groupby(['city', 'district', 'type_category']).agg(
        avg_price_per_ping=('unit_price', 'mean'),
        median_price_per_ping=('unit_price', 'median'),
        avg_total_price=('total_price', 'mean'),
        median_total_price=('total_price', 'median'),
        avg_area=('area', 'mean'),
        avg_age=('age', 'mean'),
        min_total_price=('total_price', 'min'),
        max_total_price=('total_price', 'max'),
        tx_count=('total_price', 'count')
    ).reset_index().round(1)

    # 表 2: 月度趨勢
    print("4. 計算：月度趨勢 (stats_monthly_trend)...")
    monthly_stats = df_clean.groupby(['year', 'month', 'city', 'district', 'type_category']).agg(
        avg_price_per_ping=('unit_price', 'mean'),
        avg_total_price=('total_price', 'mean'),
        tx_count=('total_price', 'count')
    ).reset_index()

    monthly_stats['year_month'] = monthly_stats['year'].astype(str) + '-' + \
                                  monthly_stats['month'].astype(str).str.zfill(2)
    monthly_stats = monthly_stats.round(1)

    # 表 3: 年度趨勢
    print("5. 計算：年度趨勢 (stats_yearly_trend)...")
    yearly_stats = df_clean.groupby(['year', 'city', 'district', 'type_category']).agg(
        avg_price_per_ping=('unit_price', 'mean'),
        avg_total_price=('total_price', 'mean'),
        tx_count=('total_price', 'count')
    ).reset_index().round(1)

    print("6. 寫入資料庫...")
    overview_stats.to_sql('stats_district_overview', conn, if_exists='replace', index=False)
    monthly_stats.to_sql('stats_monthly_trend', conn, if_exists='replace', index=False)
    yearly_stats.to_sql('stats_yearly_trend', conn, if_exists='replace', index=False)

    cursor = conn.cursor()
    # [修正 3] 索引也加入 city
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ov_dist ON stats_district_overview (city, district, type_category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mo_date ON stats_monthly_trend (city, year, district)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_yr_date ON stats_yearly_trend (city, year, district)")
    
    conn.close()
    print("✅ 統計工程完成！(已包含 city 欄位)")

if __name__ == "__main__":
    if os.path.exists(DB_FILE):
        generate_stats()
    else:
        print(f"❌ 找不到 {DB_FILE}")