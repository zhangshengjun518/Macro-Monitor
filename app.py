import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

# ====================
# 1. 页面配置
# ====================
st.set_page_config(
    page_title="全球宏观三流监控 (Cloud Stable)",
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

st.title("⚡ 全球宏观“三流”监控 (稳定版)")
st.caption("单线程加载 | 确保稳定性 | 永久在线")

# ====================
# 2. 数据引擎 (单线程·不卡顿版)
# ====================
@st.cache_data(ttl=3600*4) 
def get_data_stable():
    data_store = {}
    
    # --- 阶段 1: 美联储数据 (FRED) ---
    # 使用 st.status 显示详细进度，让用户知道没卡死
    with st.status("正在建立金融数据链路...", expanded=True) as status:
        
        status.write("📡 连接圣路易斯联储 (FRED)...")
        codes = {'WTREGEN': 'TGA', 'RRPONTSYD': 'ON_RRP', 'WALCL': 'Fed_BS', 'SOFR': 'SOFR', 'DFF': 'Fed_Funds', 'T10Y2Y': 'Yield_Curve'}
        for code_fred, name_internal in codes.items():
            try:
                # 直连 CSV，最快最稳
                url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={code_fred}"
                df = pd.read_csv(url, index_col=0, parse_dates=True)
                start_date = datetime.now() - timedelta(days=365*2) # 取2年
                df = df[df.index >= start_date]
                data_store[name_internal] = df.iloc[:, 0].resample('D').interpolate(method='time', limit=5).dropna()
            except Exception as e:
                print(f"Error fetching {name_internal}: {e}")
        
        # 计算压力指标
        if 'SOFR' in data_store and 'Fed_Funds' in data_store:
            s1, s2 = data_store['SOFR'], data_store['Fed_Funds']
            idx = s1.index.intersection(s2.index)
            data_store['Liquidity_Stress'] = (s1.loc[idx] - s2.loc[idx]) * 100

        status.write("💰 连接全球市场数据 (Yahoo)...")
        # --- 阶段 2: 市场数据 (Yahoo) ---
        tickers = {
            "Gold": "GC=F", "Oil": "CL=F", "Copper": "HG=F",
            "DXY": "DX-Y.NYB", "CNH": "CNY=X", "US10Y": "^TNX", 
            "A50_HK": "2823.HK"
        }
        
        # 逐个下载，避免并发导致内存溢出
        for key, symbol in tickers.items():
            try:
                # 显式关闭多线程 threads=False
                df = yf.download(symbol, period="1y", progress=False, threads=False)
                if not df.empty:
                    # 处理多层索引问题 (yfinance 新版特性)
                    if isinstance(df.columns, pd.MultiIndex):
                        series = df['Close'].iloc[:, 0].dropna()
                    else:
                        series = df['Close'].dropna()
                    
                    # 去死线
                    if len(series) > 5 and series.tail(5).std() == 0:
                        last_val = series.iloc[-1]
                        diff_idx = series[series != last_val].last_valid_index()
                        if diff_idx: series = series[:diff_idx]
                    
                    data_store[key] = series
            except Exception as e:
                print(f"Error fetching {key}: {e}")

        # 计算衍生指标
        if 'Gold' in data_store and 'Oil' in data_store:
            c = data_store['Gold'].index.intersection(data_store['Oil'].index)
            data_store['Gold_Oil'] = data_store['Gold'].loc[c] / data_store['Oil'].loc[c]

        status.update(label="✅ 数据同步完成!", state="complete", expanded=False)
    
    return data_store

# 执行数据获取
data = get_data_stable()

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
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([1, 3])
    with c2:
        fig = go.Figure()
        y_min, y_max = display.min(), display.max()
        diff = y_max - y_min
        padding = 0.0005 if (precision == 4 and diff < 0.05) else diff * 0.1
        
        # 修复颜色Hex格式
        fill_color_fixed = f"{color}33" 

        fig.add_trace(go.Scatter(
            x=display.index, y=display.values, mode='lines', 
            line=dict(color=color, width=2), 
            fill='tozeroy', fillcolor=fill_color_fixed
        ))
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0), height=300, 
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
            xaxis=dict(showgrid=True, gridcolor='#333', tickformat="%Y-%m-%d"), 
            yaxis=dict(showgrid=True, gridcolor='#333', range=[y_min-padding, y_max+padding], side="right", tickformat=f".{precision}f")
        )
        st.plotly_chart(fig, use_container_width=True)

# 渲染概览
st.markdown("### 📝 核心指标概览")
col1, col2, col3 = st.columns(3)
if 'Gold' in data: 
    with col1: st.metric("黄金 (Gold)", f"${data['Gold'].iloc[-1]:,.0f}", f"{(data['Gold'].iloc[-1]/data['Gold'].iloc[-2]-1)*100:.2f}%")
if 'DXY' in data: 
    with col2: st.metric("美元 (DXY)", f"{data['DXY'].iloc[-1]:.2f}", f"{(data['DXY'].iloc[-1]/data['DXY'].iloc[-2]-1)*100:.2f}%")
if 'CNH' in data: 
    with col3: st.metric("人民币 (CNY)", f"{data['CNH'].iloc[-1]:.4f}", f"{(data['CNH'].iloc[-1]/data['CNH'].iloc[-2]-1)*100:.4f}%", delta_color="inverse")

# 详细图表
st.markdown('<div class="section-header">1. 流量 (Quantity)</div>', unsafe_allow_html=True)
plot_card(data.get('TGA'), "财政部账户", "TGA Balance", "#00B0FF", "TGA水位变化体现财政部对流动性的态度。", 0)
plot_card(data.get('ON_RRP'), "逆回购规模", "ON RRP", "#2962FF", "美元蓄水池，跌破2000亿即为枯竭警报。", 0)
plot_card(data.get('Fed_BS'), "美联储资产负债表", "Fed Balance Sheet", "#6200EA", "央行底仓，曲线向下代表QT缩表。", 0)

st.markdown('<div class="section-header">2. 流速 (Velocity)</div>', unsafe_allow_html=True)
plot_card(data.get('Gold'), "现货黄金", "Spot Gold", "#FFD700", "美元信用的反向指标。", 0)
plot_card(data.get('Gold_Oil'), "金油比", "Gold/Oil Ratio", "#FBC02D", "严重衰退预警指标 (>30)。", 2)
plot_card(data.get('US10Y'), "10年美债", "US 10Y Yield", "#FF5252", "全球资产定价之锚。", 2)

st.markdown('<div class="section-header">3. 流向 (Direction)</div>', unsafe_allow_html=True)
plot_card(data.get('CNH'), "在岸人民币", "USD/CNY", "#00E676", "关注小数点后4位的微观博弈。", 4)
plot_card(data.get('DXY'), "美元指数", "DXY Index", "#64DD17", "美元周期的晴雨表。", 2)
plot_card(data.get('A50_HK'), "安硕A50 (港)", "2823.HK", "#AA00FF", "外资对中国核心资产的态度。", 2)
