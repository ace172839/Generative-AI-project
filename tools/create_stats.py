import sqlite3
import pandas as pd
import os

# ================= 設定區 =================
DB_FILE = 'house.db'
# =========================================

def classify_building_type(raw_type):
    """ 
    根據健檢結果優化的分類邏輯 
    將數十種雜亂的型態歸納為 5 大類
    """
    if pd.isna(raw_type):
        return '其他'
    
    t = str(raw_type)
    
    # 優先順序很重要
    if '套房' in t:
        return '套房'
    elif '公寓' in t:
        return '公寓'
    elif '透天' in t or '別墅' in t:
        return '透天'
    elif '大樓' in t or '華廈' in t or '電梯' in t:
        return '電梯大樓'
    else:
        return '其他' # 店面、辦公、工廠等

def is_valid_residential(usage, building_type):
    """
    判斷是否為「居住類」房產。
    排除工廠、停車場、倉庫，避免拉低平均房價。
    """
    if pd.isna(usage):
        return False
    
    u = str(usage)
    bt = str(building_type)
    
    # 1. 負面表列：如果有這些字，直接剔除
    exclude_keywords = ['車', '工', '廠', '倉', '農', '其他'] 
    for kw in exclude_keywords:
        if kw in u:
            return False
            
    # 2. 針對建物型態的再次過濾 (避免建物型態寫「工廠」但用途寫「住家用」的怪資料)
    if '工廠' in bt or '廠辦' in bt or '倉庫' in bt:
        return False

    # 3. 正面表列：通常保留 "住" 或 "商" (很多住辦混合)
    if '住' in u or '商' in u:
        return True
        
    return False

def generate_stats():
    print(f"1. 連接資料庫 {DB_FILE}...")
    conn = sqlite3.connect(DB_FILE)
    
    # 讀取必要欄位
    query = """
    SELECT district, total_price, unit_price, area, 
           building_type, main_usage, trade_date, room, age
    FROM houses
    WHERE district IS NOT NULL
    """
    df = pd.read_sql(query, conn)
    
    print(f"   共讀取 {len(df)} 筆原始資料")

    # ================= 資料清洗與過濾 =================
    print("2. 正在進行資料清洗與分類...")
    
    # 1. 產生簡化後的類別
    df['type_category'] = df['building_type'].apply(classify_building_type)
    
    # 2. 過濾非住宅 (這是統計準確的關鍵！)
    # 使用 apply 搭配 lambda 來同時檢查 usage 和 building_type
    mask = df.apply(lambda x: is_valid_residential(x['main_usage'], x['building_type']), axis=1)
    df_clean = df[mask].copy()
    
    print(f"   過濾非住宅/車位後，剩餘 {len(df_clean)} 筆有效交易資料")

    # 3. 處理日期
    df_clean['trade_date'] = pd.to_datetime(df_clean['trade_date'], errors='coerce')
    df_clean['year'] = df_clean['trade_date'].dt.year
    df_clean['month'] = df_clean['trade_date'].dt.month
    
    # 只統計 2012 ~ 2025 的資料 (過濾極端錯誤的年份)
    df_clean = df_clean[(df_clean['year'] >= 2012) & (df_clean['year'] <= 2025)]

    # ================= 製作表 1: 區域總覽 (Snapshot) =================
    # 用途：回答「哪一區比較貴？」「松山區公寓平均多少錢？」
    print("3. 計算：區域總覽 (stats_district_overview)...")
    
    overview_stats = df_clean.groupby(['district', 'type_category']).agg(
        avg_price_per_ping=('unit_price', 'mean'),
        median_price_per_ping=('unit_price', 'median'),
        avg_total_price=('total_price', 'mean'),
        median_total_price=('total_price', 'median'),
        avg_area=('area', 'mean'),
        avg_age=('age', 'mean'),
        min_total_price=('total_price', 'min'),
        max_total_price=('total_price', 'max'),
        tx_count=('total_price', 'count')
    ).reset_index()

    overview_stats = overview_stats.round(1)

    # ================= 製作表 2: 月度趨勢 (Monthly Trend) =================
    # 用途：畫折線圖
    print("4. 計算：月度趨勢 (stats_monthly_trend)...")
    
    monthly_stats = df_clean.groupby(['year', 'month', 'district', 'type_category']).agg(
        avg_price_per_ping=('unit_price', 'mean'),
        avg_total_price=('total_price', 'mean'),
        tx_count=('total_price', 'count')
    ).reset_index()

    # 增加 year_month 字串 (YYYY-MM)
    monthly_stats['year_month'] = monthly_stats['year'].astype(str) + '-' + \
                                  monthly_stats['month'].astype(str).str.zfill(2)
    
    monthly_stats = monthly_stats.round(1)

    # ================= 製作表 3: 年度趨勢 (Yearly Trend) =================
    # 用途：回答「去年跟今年比」
    print("5. 計算：年度趨勢 (stats_yearly_trend)...")

    yearly_stats = df_clean.groupby(['year', 'district', 'type_category']).agg(
        avg_price_per_ping=('unit_price', 'mean'),
        avg_total_price=('total_price', 'mean'),
        tx_count=('total_price', 'count')
    ).reset_index()
    
    yearly_stats = yearly_stats.round(1)

    # ================= 寫回資料庫 =================
    print("6. 寫入資料庫...")
    
    overview_stats.to_sql('stats_district_overview', conn, if_exists='replace', index=False)
    monthly_stats.to_sql('stats_monthly_trend', conn, if_exists='replace', index=False)
    yearly_stats.to_sql('stats_yearly_trend', conn, if_exists='replace', index=False)

    # 建立索引
    cursor = conn.cursor()
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ov_dist ON stats_district_overview (district, type_category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mo_date ON stats_monthly_trend (year, district)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_yr_date ON stats_yearly_trend (year, district)")
    
    conn.close()

    print("="*30)
    print("✅ 統計工程完成！資料庫新增了三張表：")
    print("1. stats_district_overview (各區行情總覽)")
    print("2. stats_monthly_trend (畫月線圖用)")
    print("3. stats_yearly_trend (快速回答年度比較)")
    print("-" * 30)
    print("分類範例檢查 (overview 前3筆):")
    print(overview_stats[['district', 'type_category', 'avg_price_per_ping', 'tx_count']].head(3))
    print("="*30)

if __name__ == "__main__":
    if os.path.exists(DB_FILE):
        generate_stats()
    else:
        print(f"❌ 找不到 {DB_FILE}")