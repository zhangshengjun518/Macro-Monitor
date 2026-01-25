import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_datareader.data as web
import plotly.graph_objects as go
from datetime import datetime, timedelta
import concurrent.futures
import numpy as np

# ====================
# 1. 页面配置
# ====================
st.set_page_config(
    page_title="全球宏观三流监控 (Cloud)",
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

st.title("⚡ 全球宏观“三流”监控 (Cloud Ver)")
st.caption("自动实时更新 | 卢麒元视角 | 永久在线")

# ====================
# 2. 数据引擎 (云端适配版)
# ====================
# 在云端，我们使用 Streamlit 原生缓存，不再用 pickle 文件
@st.cache_data(ttl=3600*4) # 设置缓存4小时，4小时后有人访问会自动重新下载
def get_data():
    def fetch_fred(start, end):
        codes = {'WTREGEN': 'TGA', 'RRPONTSYD': 'ON_RRP', 'WALCL': 'Fed_BS', 'SOFR': 'SOFR', 'DFF': 'Fed_Funds', 'T10Y2Y': 'Yield_Curve'}
        try:
            df = web.DataReader(list(codes.keys()), 'fred', start, None)
            df.rename(columns=codes, inplace=True)
            clean = {}
            for c in df.columns: 
                clean[c] = df[c].resample('D').interpolate(method='time', limit=2).dropna()
            if 'SOFR' in clean and 'Fed_Funds' in clean:
                s1, s2 = clean['SOFR'], clean['Fed_Funds']
                idx = s1.index.intersection(s2.index)
                clean['Liquidity_Stress'] = (s1.loc[idx] - s2.loc[idx]) * 100
            return clean
        except: return {}

    def fetch_market(start, end):
        tickers = {
            "Gold": "GC=F", "Oil": "CL=F", "Copper": "HG=F",
            "DXY": "DX-Y.NYB", "CNH": "CNY=X", "US10Y": "^TNX", 
            "A50_HK": "2823.HK"
        }
        try:
            # 始终抓取最近1年，确保数据新鲜
            df = yf.download(list(tickers.values()), period="1y", group_by='ticker', threads=True, progress=False)
            data = {}
            for key, symbol in tickers.items():
                if symbol in df.columns.levels[0]:
                    series = df[symbol]['Close'].dropna()
                    # 去死线
                    if len(series) > 5 and series.tail(5).std() == 0:
                        last_val = series.iloc[-1]
                        diff_idx = series[series != last_val].last_valid_index()
                        if diff_idx: series = series[:diff_idx]
                    data[key] = series
            return data
        except: return {}

    # 并行下载
    new_data = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as exc:
        f1 = exc.submit(fetch_fred, datetime.now()-timedelta(days=365), None)
        f2 = exc.submit(fetch_market, None, None)
        new_data.update(f1.result())
        new_data.update(f2.result())

    # 计算衍生指标
    if 'Gold' in new_data and 'Oil' in new_data:
        c = new_data['Gold'].index.intersection(new_data['Oil'].index)
        new_data['Gold_Oil'] = new_data['Gold'].loc[c] / new_data['Oil'].loc[c]
    
    return new_data

# 获取数据
data_load_state = st.text('正在从全球金融节点同步数据...')
data = get_data()
data_load_state.text('')

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
    """, unsafe_allow_html=True) # 这里简化了HTML结构以便云端快速渲染，实际绘图代码如下

    c1, c2 = st.columns([1, 3])
    with c2:
        fig = go.Figure()
        y_min, y_max = display.min(), display.max()
        diff = y_max - y_min
        padding = 0.0005 if (precision == 4 and diff < 0.05) else diff * 0.1
        
        fig.add_trace(go.Scatter(
            x=display.index, y=display.values, mode='lines', 
            line=dict(color=color, width=2), 
            fill='tozeroy', fillcolor=f"rgba{color[1:]}20"
        ))
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0), height=300, 
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
            xaxis=dict(showgrid=True, gridcolor='#333', tickformat="%Y-%m-%d"), 
            yaxis=dict(showgrid=True, gridcolor='#333', range=[y_min-padding, y_max+padding], side="right", tickformat=f".{precision}f")
        )
        st.plotly_chart(fig, use_container_width=True)

# 渲染逻辑 (简化版，直接调用核心指标)
st.markdown("### 📝 核心指标概览")
col1, col2, col3 = st.columns(3)
if 'Gold' in data: 
    with col1: st.metric("黄金 (Gold)", f"${data['Gold'].iloc[-1]:,.0f}", f"{(data['Gold'].iloc[-1]/data['Gold'].iloc[-2]-1)*100:.2f}%")
if 'DXY' in data: 
    with col2: st.metric("美元 (DXY)", f"{data['DXY'].iloc[-1]:.2f}", f"{(data['DXY'].iloc[-1]/data['DXY'].iloc[-2]-1)*100:.2f}%")
if 'CNH' in data: 
    with col3: st.metric("人民币 (CNY)", f"{data['CNH'].iloc[-1]:.4f}", f"{(data['CNH'].iloc[-1]/data['CNH'].iloc[-2]-1)*100:.4f}%", delta_color="inverse")

# 详细图表
plot_card(data.get('TGA'), "财政部账户", "TGA Balance", "#00B0FF", "TGA水位变化体现财政部对流动性的态度。", 0)
plot_card(data.get('Gold'), "现货黄金", "Spot Gold", "#FFD700", "美元信用的反向指标。", 0)
plot_card(data.get('CNH'), "在岸人民币", "USD/CNY", "#00E676", "关注小数点后4位的微观博弈。", 4)