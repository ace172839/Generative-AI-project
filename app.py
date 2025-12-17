import streamlit as st
import pandas as pd
import altair as alt
import pydeck as pdk
from agent import HouseAgent

# ================= 頁面設定 =================
st.set_page_config(page_title="看房 AI 助手", page_icon="🏠", layout="centered")
st.title("🏠 台北房市看房 AI 助手")

# ================= 設定區：中英欄位對照表 =================
COLUMN_MAPPING = {
    # 核心欄位
    "trade_date": "交易日期",
    "city": "縣市",
    "district": "行政區",
    "address": "地址",
    "total_price": "總價(萬)",
    "unit_price": "單價(萬/坪)",
    "area": "坪數",
    "age": "屋齡(年)",
    "floor": "樓層",
    "total_floor": "總樓高",
    "building_type": "建物型態",
    "main_usage": "主要用途",
    
    # 格局
    "room": "房",
    "hall": "廳",
    "bath": "衛",
    
    # 統計與聚合欄位
    "type_category": "屋型分類",
    "avg_price_per_ping": "平均單價(萬/坪)",
    "avg_total_price": "平均總價(萬)",
    "median_price_per_ping": "中位數單價",
    "median_total_price": "中位數總價",
    "avg_area": "平均坪數",
    "avg_age": "平均屋齡",
    "min_total_price": "最低總價",
    "max_total_price": "最高總價",

    "tx_count": "成交筆數(熱度)", 
    "COUNT(*)": "成交筆數(熱度)",
    
    "tx_count": "交易量",
    "year": "年份",
    "year_month": "年月",
    "month": "月份",
    
    "AVG(avg_price_per_ping)": "平均單價",
    "AVG(total_price)": "平均總價",
    
    "latitude": "緯度",
    "longitude": "經度"
}

def get_label(col_name):
    if col_name in COLUMN_MAPPING:
        return COLUMN_MAPPING[col_name]
    clean_name = col_name.replace("AVG(", "").replace("SUM(", "").replace(")", "")
    return COLUMN_MAPPING.get(clean_name, col_name)

# ================= 初始化 =================
if "agent" not in st.session_state:
    with st.spinner("啟動 AI 核心中..."):
        st.session_state.agent = HouseAgent()

if "messages" not in st.session_state:
    st.session_state.messages = []

# ================= 地圖渲染函式 (維持不變) =================
def render_map_if_exists(chart_data):
    if not chart_data or "data" not in chart_data: return
    try:
        df = pd.DataFrame(chart_data["data"])
        
        # 資料前處理
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"], errors='coerce')
            df["year_filter"] = df["trade_date"].dt.year
        if "area" in df.columns:
            df["area"] = pd.to_numeric(df["area"], errors='coerce')
        if "age" in df.columns:
            df["age"] = pd.to_numeric(df["age"], errors='coerce')

        # 篩選器 UI
        with st.expander("🔍 地圖篩選條件 (點擊展開)", expanded=False):
            st.caption("調整下方條件以過濾地圖上的物件")
            f1, f2 = st.columns(2)
            
            selected_years = (2012, 2025)
            if "year_filter" in df.columns and not df["year_filter"].isnull().all():
                min_y = int(df["year_filter"].min())
                max_y = int(df["year_filter"].max())
                with f1:
                    selected_years = st.slider("📅 交易年份", min_y, max_y, (min_y, max_y))

            selected_types = []
            if "building_type" in df.columns:
                all_types = list(df["building_type"].unique())
                with f2:
                    selected_types = st.multiselect("🏠 房屋形態", all_types, default=all_types)

            f3, f4, f5 = st.columns(3)
            with f3: area_opt = st.radio("📐 坪數", ["全部", "40坪以下", "40坪以上"])
            with f4: age_opt = st.radio("🏗️ 屋齡", ["全部", "10年以下", "10-20年", "20年以上"])
            elevator_col = "elevator" if "elevator" in df.columns else "電梯"
            with f5:
                if elevator_col in df.columns: ele_opt = st.radio("🛗 電梯", ["全部", "有", "無"])
                else: ele_opt = "全部"

        # 執行過濾
        filtered_df = df.copy()
        if "year_filter" in filtered_df.columns:
            filtered_df = filtered_df[(filtered_df["year_filter"] >= selected_years[0]) & (filtered_df["year_filter"] <= selected_years[1])]
        if selected_types and "building_type" in filtered_df.columns:
            filtered_df = filtered_df[filtered_df["building_type"].isin(selected_types)]
        if "area" in filtered_df.columns:
            if area_opt == "40坪以下": filtered_df = filtered_df[filtered_df["area"] < 40]
            elif area_opt == "40坪以上": filtered_df = filtered_df[filtered_df["area"] >= 40]
        if "age" in filtered_df.columns:
            if age_opt == "10年以下": filtered_df = filtered_df[filtered_df["age"] < 10]
            elif age_opt == "10-20年": filtered_df = filtered_df[(filtered_df["age"] >= 10) & (filtered_df["age"] <= 20)]
            elif age_opt == "20年以上": filtered_df = filtered_df[filtered_df["age"] > 20]
        if ele_opt != "全部" and elevator_col in filtered_df.columns:
            filtered_df = filtered_df[filtered_df[elevator_col] == ele_opt]

        # 繪製地圖
        map_df = filtered_df.dropna(subset=["latitude", "longitude"])
        map_df = map_df.rename(columns={"latitude": "lat", "longitude": "lon"})
        
        if not map_df.empty:
            st.caption(f"📍 {chart_data.get('title', '物件分佈地圖')} (顯示 {len(map_df)} / {len(df)} 筆資料)")
            layer = pdk.Layer(
                "ScatterplotLayer",
                map_df,
                get_position=["lon", "lat"],
                get_color=[255, 75, 75, 160], 
                get_radius=15,
                pickable=True,      
                auto_highlight=True 
            )
            view_state = pdk.ViewState(
                latitude=map_df["lat"].mean(),
                longitude=map_df["lon"].mean(),
                zoom=14,
                pitch=0,
            )
            tooltip_html = """
                <b>{address}</b><br/>
                總價: <b>{total_price}</b> 萬<br/>
                單價: {unit_price} 萬/坪<br/>
                格局: {room}房 {hall}廳<br/>
                屋齡: {age} 年<br/>
                坪數: {area} 坪<br/>
                型態: {building_type}
            """
            st.pydeck_chart(pdk.Deck(map_style=None, initial_view_state=view_state, layers=[layer], tooltip={"html": tooltip_html}))
        else:
            st.warning("⚠️ 篩選條件過嚴，地圖上無符合物件。")
    except Exception as e:
        print(f"地圖繪製失敗: {e}")

# ================= [核心修正] 動態圖表渲染函式 =================
def render_chart(chart_data):
    if not chart_data or "data" not in chart_data: return
    try:
        df = pd.DataFrame(chart_data["data"])
        if df.empty: return

        title = chart_data.get("title", "統計圖表")
        
        with st.expander(f"📊 {title} (點擊展開可自訂圖表)", expanded=True):
            cols = list(df.columns)
            
            default_x = next((c for c in cols if "year_month" in c or "date" in c or "year" in c or "district" in c), cols[0])
            default_y = next((c for c in cols if "price" in c or "count" in c or "AVG" in c), cols[1] if len(cols)>1 else cols[0])
            
            # UI
            c1, c2, c3 = st.columns(3)
            with c1:
                chart_type = st.selectbox("圖表類型", ["長條圖 (Bar)", "折線圖 (Line)", "圓餅圖 (Pie)", "資料表 (Table)"], key=f"type_{title}")
            with c2:
                x_col = st.selectbox("X 軸 (類別/時間)", cols, index=cols.index(default_x), format_func=get_label, key=f"x_{title}")
            with c3:
                y_col = st.selectbox("Y 軸 (數值)", cols, index=cols.index(default_y), format_func=get_label, key=f"y_{title}")

            facet_col = st.selectbox("分圖表比較 (Facet)", ["無"] + cols, index=0, 
                                   format_func=lambda x: "無" if x == "無" else get_label(x), key=f"f_{title}")

            if chart_type == "資料表 (Table)":
                st.dataframe(df.rename(columns=COLUMN_MAPPING))
                return

            if "date" in x_col and x_col in df.columns:
                try: df[x_col] = pd.to_datetime(df[x_col])
                except: pass

            try: df = df.sort_values(by=x_col)
            except: pass

            # X 軸型態
            alt_type = ":Q"
            if "date" in x_col: alt_type = ":T"
            elif any(k in x_col for k in ["district", "type", "city", "floor", "year"]): alt_type = ":O"

            tooltips = [
                alt.Tooltip(x_col, title=get_label(x_col)),
                alt.Tooltip(y_col, title=get_label(y_col), format=",")
            ]
            
            encode_args = {
                "x": alt.X(f"{x_col}{alt_type}", title=get_label(x_col)), 
                "y": alt.Y(y_col, title=get_label(y_col)),
                "tooltip": tooltips
            }
            
            # 自動上色
            auto_color_col = None
            if "type_category" in df.columns: auto_color_col = "type_category"
            elif "building_type" in df.columns: auto_color_col = "building_type"
            elif "Bar" in chart_type or "Pie" in chart_type: auto_color_col = x_col

            if auto_color_col:
                encode_args["color"] = alt.Color(f"{auto_color_col}{':O' if 'year' in auto_color_col else ''}", title=get_label(auto_color_col))
                if auto_color_col != x_col:
                    tooltips.append(alt.Tooltip(auto_color_col, title=get_label(auto_color_col)))

            base = alt.Chart(df)
            if facet_col != "無":
                base = base.properties(height=200)

            if "Line" in chart_type:
                chart = base.mark_line(point=True).encode(**encode_args)
            elif "Bar" in chart_type:
                encode_args["x"] = alt.X(f"{x_col}{alt_type}", sort=None, title=get_label(x_col))
                chart = base.mark_bar().encode(**encode_args)
            elif "Pie" in chart_type:
                pie_color = auto_color_col if auto_color_col else x_col
                base = base.encode(
                    theta=alt.Theta(y_col, stack=True),
                    color=alt.Color(f"{pie_color}{alt_type}", title=get_label(pie_color)),
                    tooltip=tooltips
                )
                chart = base.mark_arc(outerRadius=120)

            # [關鍵修正] Facet 邏輯修正
            # 1. 移除 "Pie" not in chart_type 的限制
            # 2. 如果是圓餅圖，不使用 resolve_scale/axis (因為圓餅圖沒有 XY 軸)
            if facet_col != "無":
                chart = chart.facet(
                    row=alt.Row(facet_col, title=None, header=alt.Header(titleOrient="left", labelOrient="left", labelFontSize=12))
                )
                
                # 只有非圓餅圖才需要處理 XY 軸獨立的問題
                if "Pie" not in chart_type:
                    chart = chart.resolve_scale(y='independent').resolve_axis(x='independent')

            st.altair_chart(chart.interactive(), use_container_width=True)

    except Exception as e:
        st.error(f"圖表繪製失敗: {e}")

# ================= 聊天室邏輯 =================
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("chart_data"):
            render_map_if_exists(message["chart_data"])
            render_chart(message["chart_data"])

if prompt := st.chat_input("請輸入問題 (例如：台北市各區過去三年房價趨勢)"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("查詢中..."):
            response_data = st.session_state.agent.chat(prompt)
            st.markdown(response_data["text"])
            
            if response_data["chart_data"]:
                render_map_if_exists(response_data["chart_data"])
                render_chart(response_data["chart_data"])

    st.session_state.messages.append({
        "role": "assistant", 
        "content": response_data["text"],
        "chart_data": response_data.get("chart_data")
    })