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
    "parking_count": "車位數",
    "elevator": "電梯",
    "management_org": "管委會",
    
    # 統計欄位
    "type_category": "屋型分類",
    "avg_price_per_ping": "平均單價",
    "tx_count": "交易量",
    "year_month": "年月",
    "max_price": "最高價",
    "min_price": "最低價",
    
    # 系統欄位 (通常不顯示，但若顯示就翻一下)
    "latitude": "緯度",
    "longitude": "經度"
}

# ================= 初始化 =================
if "agent" not in st.session_state:
    with st.spinner("啟動中..."):
        st.session_state.agent = HouseAgent()

if "messages" not in st.session_state:
    st.session_state.messages = []

# ================= 1. 地圖渲染函式 =================
def render_map_if_exists(chart_data):
    """ 檢查資料中是否有經緯度，若有則畫出互動式地圖 (Pydeck) """
    if not chart_data or "data" not in chart_data: return
    
    try:
        df = pd.DataFrame(chart_data["data"])
        
        if "latitude" in df.columns and "longitude" in df.columns:
            map_df = df.dropna(subset=["latitude", "longitude"])
            map_df = map_df.rename(columns={"latitude": "lat", "longitude": "lon"})
            
            if not map_df.empty:
                st.caption(f"📍 {chart_data.get('title', '物件分佈地圖')} (滑鼠移動到點上可看詳情)")
                
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
                    zoom=15,
                    pitch=0,
                )

                tooltip_html = """
                    <b>{address}</b><br/>
                    總價: <b>{total_price}</b> 萬<br/>
                    單價: {unit_price} 萬/坪<br/>
                    格局: {room}房 {hall}廳<br/>
                    屋齡: {age} 年<br/>
                    型態: {building_type}
                """

                st.pydeck_chart(pdk.Deck(
                    map_style=None,
                    initial_view_state=view_state,
                    layers=[layer],
                    tooltip={"html": tooltip_html}
                ))

    except Exception as e:
        print(f"地圖繪製失敗: {e}")

# ================= 2. 圖表渲染函式 (修正：全欄位顯示 + 中文標題) =================
def render_chart(chart_data):
    if not chart_data or "data" not in chart_data: return
    try:
        df = pd.DataFrame(chart_data["data"])
        if df.empty: return

        v_type = chart_data.get("visual_type", "table")
        cols = chart_data.get("columns", [])
        
        # --- [修正點] 表格模式：顯示完整資料並翻譯欄位 ---
        if v_type == "table":
            st.caption(f"📋 {chart_data.get('title', '資料列表')}")
            
            # 1. 重新命名欄位 (使用 mapping)
            # rename 只會改有定義在 mapping 裡的，沒定義到的保持原樣 (英文)
            display_df = df.rename(columns=COLUMN_MAPPING)
            
            # 2. 調整欄位順序 (讓重要的排前面，如果有這些欄位的話)
            priority_cols = ["交易日期", "行政區", "地址", "總價(萬)", "單價(萬/坪)", "坪數", "屋型分類", "建物型態", "屋齡(年)", "房", "廳", "衛"]
            # 找出目前 df 裡實際有的欄位
            existing_cols = display_df.columns.tolist()
            # 排序：先排優先的，剩下的排後面
            sorted_cols = [c for c in priority_cols if c in existing_cols] + [c for c in existing_cols if c not in priority_cols]
            
            # 3. 顯示 Dataframe
            st.dataframe(display_df[sorted_cols])
            return

        # --- 統計圖表模式 ---
        title = chart_data.get("title", "統計圖表")
        st.caption(f"📊 {title}")
        
        if len(cols) >= 2:
            x_col, y_col = cols[0], cols[1]
            
            # 判斷是否有多線分類
            color_col = None
            if "type_category" in df.columns:
                color_col = "type_category"
            elif len(cols) > 2:
                color_col = cols[2]

            # 準備中文 Tooltip
            tooltips = [
                alt.Tooltip(x_col, title=COLUMN_MAPPING.get(x_col, x_col)),
                alt.Tooltip(y_col, title=COLUMN_MAPPING.get(y_col, y_col), format=",")
            ]
            if color_col:
                tooltips.append(alt.Tooltip(color_col, title=COLUMN_MAPPING.get(color_col, "分類")))

            # 繪圖參數
            encode_args = {
                "x": alt.X(x_col, title=COLUMN_MAPPING.get(x_col, x_col)),
                "y": alt.Y(y_col, title=COLUMN_MAPPING.get(y_col, y_col)),
                "tooltip": tooltips
            }
            if color_col:
                encode_args["color"] = alt.Color(color_col, title=COLUMN_MAPPING.get(color_col, "分類"))

            if v_type == "line_chart":
                chart = alt.Chart(df).mark_line(point=True).encode(**encode_args).interactive()
                st.altair_chart(chart, use_container_width=True)
                
            elif v_type == "bar_chart":
                # Bar chart x軸通常不用 sort
                encode_args["x"] = alt.X(x_col, sort=None, title=COLUMN_MAPPING.get(x_col, x_col))
                chart = alt.Chart(df).mark_bar().encode(**encode_args).interactive()
                st.altair_chart(chart, use_container_width=True)
        else:
            # Fallback
            st.dataframe(df.rename(columns=COLUMN_MAPPING))

    except Exception as e:
        st.error(f"圖表繪製失敗: {e}")

# ================= 3. 聊天室邏輯 =================
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("chart_data"):
            render_map_if_exists(message["chart_data"])
            render_chart(message["chart_data"])

if prompt := st.chat_input("請輸入問題 (例如：中正區3000萬以內的房子)"):
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