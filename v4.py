import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- 頁面配置 ---
st.set_page_config(page_title="專業級多股實時監控", layout="wide")
st.title("🚀 專業實時監控 (摘要含量能與趨勢資訊)")

# --- 核心運算函數 ---
def fetch_data(ticker, interval):
    try:
        # 抓取 2 天數據以確保指標計算穩定
        data = yf.download(ticker, period="2d", interval=interval, progress=False)
        if data.empty: return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except:
        return None

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    if loss.iloc[-1] == 0: return 100.0
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_vix_info():
    vix = fetch_data("^VIX", "2m")
    if vix is None or len(vix) < 2: return 20.0, 0.0
    curr_v = float(vix['Close'].iloc[-1])
    v_chg = curr_v - float(vix['Close'].iloc[-2])
    return curr_v, v_chg

def analyze_stock(df, v_chg, ema_fast_val, ema_slow_val):
    if df is None or len(df) < 25: return None, None
    
    # 1. 支撐壓力計算
    high_p, low_p, close_p = float(df['High'].max()), float(df['Low'].min()), float(df['Close'].iloc[-1])
    pivot = (high_p + low_p + close_p) / 3
    res_1, sup_1 = (2 * pivot) - low_p, (2 * pivot) - high_p

    # 2. 技術指標
    df['EMA_F'] = df['Close'].ewm(span=ema_fast_val, adjust=False).mean()
    df['EMA_S'] = df['Close'].ewm(span=ema_slow_val, adjust=False).mean()
    df['RSI'] = calculate_rsi(df['Close'])
    df['Vol_MA'] = df['Volume'].rolling(window=10).mean()
    
    last, prev = df.iloc[-1], df.iloc[-2]
    curr_p = float(last['Close'])
    
    # 3. 趨勢與量能判斷
    trend_type = "多頭 (Bullish)" if last['EMA_F'] > last['EMA_S'] else "空頭 (Bearish)"
    vol_ratio = float(last['Volume'] / last['Vol_MA']) if last['Vol_MA'] != 0 else 1.0
    
    if vol_ratio >= 2.0: vol_status = "🔥 爆量"
    elif vol_ratio >= 1.5: vol_status = "⚡ 放大"
    else: vol_status = "正常"

    # 4. 警報訊息
    msg = "趨勢穩定"
    alert_level = "success"
    
    # 交叉邏輯
    if prev['EMA_F'] <= prev['EMA_S'] and last['EMA_F'] > last['EMA_S']:
        msg = "↗️ 黃金交叉"; alert_level = "warning" if v_chg > 0.2 else "error"
    elif prev['EMA_F'] >= prev['EMA_S'] and last['EMA_F'] < last['EMA_S']:
        msg = "↘️ 死亡交叉"; alert_level = "error"
    elif curr_p >= res_1 * 0.998:
        msg = "🧱 接近壓力"; alert_level = "warning"

    info = {
        "price": curr_p,
        "day_pct": ((curr_p - df['Open'].iloc[-1]) / df['Open'].iloc[-1]) * 100,
        "rsi": float(last['RSI']),
        "vol_ratio": vol_ratio,
        "vol_status": vol_status,
        "trend": trend_type,
        "res": res_1, "sup": sup_1,
        "msg": msg, "alert_level": alert_level
    }
    return df, info

# --- 介面配置 ---
st.sidebar.header("監控參數")
symbols = [s.strip().upper() for s in st.sidebar.text_input("監控列表", "AAPL, NVDA, TSLA, 2330.TW").split(",")]
interval = st.sidebar.selectbox("頻率", ("1m", "2m", "5m"), index=0)
ema_f_v = st.sidebar.slider("快速 EMA", 5, 20, 9)
ema_s_v = st.sidebar.slider("慢速 EMA", 21, 50, 21)

placeholder = st.empty()

while True:
    with placeholder.container():
        # VIX 狀態
        v_val, v_chg = get_vix_info()
        v_col1, v_col2 = st.columns([1, 4])
        v_col1.metric("VIX 指數", f"{v_val:.2f}", f"{v_chg:.2f}", delta_color="inverse")
        with v_col2:
            st.info(f"系統環境：VIX {'上升中，建議保守' if v_chg > 0 else '平穩，有利技術面操作'}")

        # 1. 強化版即時警報摘要
        st.subheader("🔔 即時警報摘要 (含趨勢與量能)")
        cols = st.columns(len(symbols))
        stock_data_store = {}

        for idx, sym in enumerate(symbols):
            df_raw = fetch_data(sym, interval)
            df, info = analyze_stock(df_raw, v_chg, ema_f_v, ema_s_v)
            stock_data_store[sym] = (df, info)
            
            with cols[idx]:
                if info:
                    # 顯示狀態卡片
                    if info['alert_level'] == "error": st.error(f"**{sym} | {info['msg']}**")
                    elif info['alert_level'] == "warning": st.warning(f"**{sym} | {info['msg']}**")
                    else: st.success(f"**{sym} | 監控中**")
                    
                    # 注入關鍵資訊內容
                    st.markdown(f"**量能狀態:** {info['vol_status']}")
                    st.markdown(f"**趨勢:** {info['trend']}")
                    st.caption(f"RSI: {info['rsi']:.1f} | 價: {info['price']:.2f}")
                else:
                    st.write(f"{sym} 載入失敗")

        st.divider()
        
        # 2. 詳細圖表區
        for sym in symbols:
            df, info = stock_data_store[sym]
            if df is not None:
                with st.expander(f"查看 {sym} 詳情分析圖表", expanded=True):
                    c1, c2 = st.columns([1, 4])
                    with c1:
                        st.metric("當前價格", f"{info['price']:.2f}", f"{info['day_pct']:.2f}%")
                        st.write(f"壓力位: `{info['res']:.2f}`")
                        st.write(f"支撐位: `{info['sup']:.2f}`")
                    with c2:
                        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)
                        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K"), row=1, col=1)
                        fig.add_hline(y=info['res'], line_dash="dash", line_color="red", annotation_text="壓", row=1, col=1)
                        fig.add_hline(y=info['sup'], line_dash="dash", line_color="green", annotation_text="支", row=1, col=1)
                        fig.add_trace(go.Scatter(x=df.index, y=df['EMA_F'], name="Fast", line=dict(color='orange', width=1)), row=1, col=1)
                        
                        v_colors = ['red' if df['Close'].iloc[i] < df['Open'].iloc[i] else 'green' for i in range(len(df))]
                        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=v_colors), row=2, col=1)
                        fig.update_layout(height=350, margin=dict(t=0, b=0), xaxis_rangeslider_visible=False, showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)

        time.sleep(60)
        st.rerun()
