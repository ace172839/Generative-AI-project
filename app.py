import streamlit as st
import pandas as pd
import altair as alt
from agent import HouseAgent

# ================= 頁面設定 =================
st.set_page_config(page_title="看房 AI 助手", page_icon="🏠", layout="centered")
st.title("🏠 台北房市看房 AI 助手")

# ================= 初始化 =================
if "agent" not in st.session_state:
    with st.spinner("啟動中..."):
        st.session_state.agent = HouseAgent()

if "messages" not in st.session_state:
    st.session_state.messages = []

# ================= 1. 地圖渲染函式 (新增!) =================
def render_map_if_exists(chart_data):
    """ 檢查資料中是否有經緯度，若有則畫地圖 """
    if not chart_data or "data" not in chart_data: return
    
    try:
        df = pd.DataFrame(chart_data["data"])
        # 檢查關鍵欄位
        if "latitude" in df.columns and "longitude" in df.columns:
            # 去除無效座標
            map_df = df.dropna(subset=["latitude", "longitude"])
            if not map_df.empty:
                st.caption(f"📍 {chart_data.get('title', '物件分佈地圖')}")
                # Streamlit map 需要欄位名稱為 lat/lon
                map_df = map_df.rename(columns={"latitude": "lat", "longitude": "lon"})
                st.map(map_df, size=20, color='#FF4B4B')
    except Exception as e:
        # 地圖畫失敗不影響主流程，靜默處理或印 log
        print(f"地圖繪製失敗: {e}")

# ================= 2. 圖表渲染函式 (保持原本的高級互動版) =================
def render_chart(chart_data):
    if not chart_data or "data" not in chart_data: return
    try:
        df = pd.DataFrame(chart_data["data"])
        if df.empty: return

        v_type = chart_data.get("visual_type", "table") # 預設為表格
        cols = chart_data.get("columns", [])
        
        # 如果只有經緯度沒有其他數據，或者類型是 table，直接顯示表格
        if v_type == "table":
            st.caption(f"📋 {chart_data.get('title', '資料列表')}")
            st.dataframe(df)
            return

        # (以下 Altair 繪圖邏輯保持不變，省略以節省篇幅...)
        # 請保留上一版完整的 render_chart Altair 邏輯
        # 為了完整性，這裡放簡化版示意，請用上一版的 render_chart 替換這裡
        title = chart_data.get("title", "統計圖表")
        st.caption(f"📊 {title}")
        
        if len(cols) >= 2:
            x_col, y_col = cols[0], cols[1]
            # 簡單繪圖 (若您需要上一版的高級互動，請將其貼回此處)
            if v_type == "line_chart":
                st.line_chart(df.set_index(x_col)[y_col])
            elif v_type == "bar_chart":
                st.bar_chart(df.set_index(x_col)[y_col])
            else:
                st.dataframe(df)
        else:
            st.dataframe(df)

    except Exception as e:
        st.error(f"圖表繪製失敗: {e}")

# ================= 3. 聊天室邏輯 (修改呼叫順序) =================

# 顯示歷史訊息
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("chart_data"):
            # 先畫地圖 (因為地圖比較直觀)
            render_map_if_exists(message["chart_data"])
            # 再畫統計圖表或表格
            render_chart(message["chart_data"])

# 接收輸入
if prompt := st.chat_input("請輸入問題 (例如：民權東路五段的房子)"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("查詢中..."):
            response_data = st.session_state.agent.chat(prompt)
            
            st.markdown(response_data["text"])
            
            if response_data["chart_data"]:
                # 1. 嘗試畫地圖
                render_map_if_exists(response_data["chart_data"])
                # 2. 畫圖表或表格
                render_chart(response_data["chart_data"])

    st.session_state.messages.append({
        "role": "assistant", 
        "content": response_data["text"],
        "chart_data": response_data.get("chart_data")
    })