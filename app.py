import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import concurrent.futures
import numpy as np

# ====================
# 1. 页面配置
# ====================
st.set_page_config(
    page_title="全球宏观三流监控 (Cloud Pro)",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp {background-color: #0E1117;}
    .full-card {
        background-color: #1E1E1E; border: 1px solid #444; border-radius: 12px;
        padding: 25px; margin-bottom: 30px; box-shadow: 0 6px 12px rgba(0,0,0,0.4);
    }
    .card-title { font-size: 1.8rem; color: #FFD700; font-weight: bold; }
    .card-title span { font-size: 1.0rem; color: #888; margin-left: 15px; }
    .big-value { font-size: 2.8rem; font-weight: bold; color: #FFF; margin: 10px 0; font-family: 'Roboto Mono', monospace; }
    .lu-comment-box { background-color: #262730; border-left: 5px solid #D32F2F; padding: 15px; margin-top: 15px; border-radius: 5px; }
    .lu-label { color: #FF5252; font-weight: bold; font-size: 0.9rem; margin-bottom: 5px; }
    .lu-text { color: #E0E0E0; font-size: 1.0rem; line-height: 1.5; }
    .section-header { font-size: 2.0rem; color: #00E676; border-bottom: 2px solid #333; padding-bottom: 10px; margin-top: 50px; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

st.title("⚡ 全球宏观“三流”监控 (Cloud Fixed)")
st.caption("自动实时更新 | 卢麒元视角 | 永久在线")

# ====================
# 2. 数据引擎 (直连修复版)
# ====================
@st.cache_data(ttl=3600*4) 
def get_data():
    # 2.1 FRED 数据 (改用直连 CSV，避开 pandas_datareader 报错)
    def fetch_fred():
        codes = {'WTREGEN': 'TGA', 'RRPONTSYD': 'ON_RRP', 'WALCL': 'Fed_BS', 'SOFR': 'SOFR', 'DFF': 'Fed_Funds', 'T10Y2Y': 'Yield_Curve'}
        clean = {}
        for code_fred, name_internal in codes.items():
            try:
                # 直接读取圣路易斯联储 CSV 接口，稳定且无需额外库
                url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={code_fred}"
                df = pd.read_csv(url, index_col=0, parse_dates=True)
                # 只取最近1年，提高速度
                start_date = datetime.now() - timedelta(days=365)
                df = df[df.index >= start_date]
                clean[name_internal] = df.iloc[:, 0].resample('D').interpolate(method='time', limit=2).dropna()
            except: pass
            
        if 'SOFR' in clean and 'Fed_Funds' in clean:
            s1, s2 = clean['SOFR'], clean['Fed_Funds']
            idx = s1.index.intersection(s2.index)
            clean['Liquidity_Stress'] = (s1.loc[idx] - s2.loc[idx]) * 100
        return clean

    # 2.2 市场数据 (Yahoo)
    def fetch_market():
        tickers = {
            "Gold": "GC=F", "Oil": "CL=F", "Copper": "HG=F",
            "DXY": "DX-Y.NYB", "CNH": "CNY=X", "US10Y": "^TNX", 
            "A50_HK": "2823.HK"
        }
        try:
            df = yf.download(list(tickers.values()), period="1y", group_by='ticker', threads=True, progress=False)
            data = {}
            for key, symbol in tickers.items():
                if symbol in df.columns.levels[0]:
                    series = df[symbol]['Close'].dropna()
                    # 去死线逻辑
                    if len(series) > 5 and series.tail(5).std() == 0:
                        last_val = series.iloc[-1]
                        diff_idx = series[series != last_val].last_valid_index()
                        if diff_idx: series = series[:diff_idx]
                    data[key] = series
            return data
        except: return {}

    # 并行执行
    new_data = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as exc:
        f1 = exc.submit(fetch_fred)
        f2 = exc.submit(fetch_market)
        new_data.update(f1.result())
        new_data.update(f2.result())

    # 衍生计算
    if 'Gold' in new_data and 'Oil' in new_data:
        c = new_data['Gold'].index.intersection(new_data['Oil'].index)
        new_data['Gold_Oil'] = new_data['Gold'].loc[c] / new_data['Oil'].loc[c]
    
    return new_data

# 加载数据
with st.spinner('正在同步全球金融数据...'):
    data = get_data()

# ====================
# 3. 绘图与展示
# ====================
def plot_card(series, title_cn, title_en, color, lu_analysis, precision=2):
    if series is None or series.empty: return
    display = series.tail(90)
    curr = display.iloc[-1]
    prev = display.iloc[-2] if len(display) > 1 else curr
    delta = (curr - prev) / prev * 100
    
    fmt = f".{precision}f" if precision == 4 else (",.0f" if curr > 1000 else ",.2f")
    fmt_val = f"{curr:{fmt}}"
    d_col = "#FF5252" if delta < 0 else "#00E676"
    
    # HTML 卡片结构
    st.markdown(f"""
    <div class="full-card">
        <div class="card-title">{title_cn} <span>{title_en}</span></div>
        <div style="display:flex;">
            <div style="flex:1;">
                <div class="big-value" style="color:{color}">{fmt_val}</div>
                <div style="font-size:1.2rem; color:{d_col}; font-weight:bold;">{delta:.2f}%</div>
                <div class="lu-comment-box"><div class="lu-label">🎙️ 卢麒元视角：</div><div class="lu-text">{lu_analysis}</div></div>
            </div>
            <div style="flex:2;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Plotly 绘图
    c1, c2 = st.columns([1, 3])
    with c2:
        fig = go.Figure()
        y_min, y_max = display.min(), display.max()
        diff = y_max - y_min
        
        # 动态 padding
        padding = 0.0005 if (precision == 4 and diff < 0.05) else diff * 0.1
        
        # 【关键修复】使用标准的 Hex+Alpha 格式 (例如 #FF000033)
        # 只要在 color 字符串后面加 '3
