import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

# ====================
# 1. 页面配置 (复刻原有)
# ====================
st.set_page_config(
    page_title="全球宏观三流监控 (资产负债表深度穿透版)",
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

st.title("⚡ 全球宏观“三流”监控 (资产负债表穿透版)")
st.caption("全量指标保留 | 深度穿透资产负债表 | 实时数据流")

# ====================
# 2. 辅助函数 (复刻原有)
# ====================
def hex_to_rgba(hex_color, alpha=0.2):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return f"rgba({r}, {g}, {b}, {alpha})"
    return hex_color

# ====================
# 3. 增强型数据引擎 (稳定+全量)
# ====================
@st.cache_data(ttl=3600*2) 
def get_macro_data():
    data_store = {}
    with st.status("正在建立全球宏观链路...", expanded=True) as status:
        # --- 阶段 1: FRED 资产负债表细分 (实时穿透) ---
        status.write("📡 穿透圣路易斯联储 (FRED)...")
        # WALCL:总资产, WTREGEN:TGA, RRPONTSYD:逆回购, WRESBAL:准备金, WSHOMCB:国债, WSHMBS:MBS
        fred_codes = {
            'WALCL': 'Fed_BS', 'WTREGEN': 'TGA', 'RRPONTSYD': 'ON_RRP',
            'WRESBAL': 'Reserves', 'WSHOMCB': 'Fed_Treasury', 'WSHMBS': 'Fed_MBS',
            'SOFR': 'SOFR', 'DFF': 'Fed_Funds', 'T10Y2Y': 'Yield_Curve'
        }
        for code, name in fred_codes.items():
            try:
                url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={code}"
                df = pd.read_csv(url, index_col=0, parse_dates=True)
                data_store[name] = df.iloc[:, 0].resample('D').interpolate(method='time', limit=5).dropna()
            except: pass

        # --- 阶段 2: Yahoo 市场数据 (复刻全量) ---
        status.write("💰 连接全球市场数据 (Yahoo)...")
        tickers = {
            "Gold": "GC=F", "Oil": "CL=F", "Copper": "HG=F",
            "DXY": "DX-Y.NYB", "CNH": "CNY=X", "US10Y": "^TNX", 
            "A50_HK": "2823.HK"
        }
        for key, symbol in tickers.items():
            try:
                df = yf.download(symbol, period="1y", progress=False, threads=False)
                if not df.empty:
                    series = df['Close'].iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else df['Close']
                    data_store[key] = series.dropna()
            except: pass

        # 计算原有比率指标
        if 'Gold' in data_store and 'Oil' in data_store:
            c = data_store['Gold'].index.intersection(data_store['Oil'].index)
            data_store['Gold_Oil'] = data_store['Gold'].loc[c] / data_store['Oil'].loc[c]
        
        # 计算新增流量指标：净流动性
        if all(k in data_store for k in ['Fed_BS', 'TGA', 'ON_RRP']):
            data_store['Net_Liquidity'] = data_store['Fed_BS'] - data_store['TGA'] - data_store['ON_RRP']

        status.update(label="✅ 全量数据同步完成!", state="complete", expanded=False)
    return data_store

data = get_macro_data()

# ====================
# 4. 绘图函数 (复刻原有 + 一行一图逻辑)
# ====================
def plot_full_card(series, title_cn, title_en, color, lu_analysis, precision=2, is_large=False):
    if series is None or series.empty: return
    display = series.tail(90)
    curr = display.iloc[-1]
    prev = display.iloc[-2]
    delta = (curr - prev) / prev * 100
    
    fmt = f".{precision}f" if precision >= 2 else (",.0f" if curr > 1000 else ",.2f")
    fmt_val = f"{curr:{fmt}}"
    d_col = "#FF5252" if delta < 0 else "#00E676"
    
    # 容器渲染
    st.markdown(f"""
    <div class="full-card">
        <div class="card-title">{title_cn} <span>{title_en}</span></div>
        <div style="display:flex; flex-wrap: wrap;">
            <div style="flex:1; min-width: 250px;">
                <div class="big-value" style="color:{color}">{fmt_val}</div>
                <div style="font-size:1.2rem; color:{d_col}; font-weight:bold;">{delta:.2f}%</div>
                <div class="lu-comment-box">
                    <div class="lu-label">🎙️ 视角：</div>
                    <div class="lu-text">{lu_analysis}</div>
                </div>
            </div>
            <div style="flex:2.5; min-width: 500px; height: 350px;" id="chart_{title_en.replace(' ','_')}">
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 绘制图表 (强制一行一图感观)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=display.index, y=display.values, mode='lines', 
        line=dict(color=color, width=3), 
        fill='tozeroy', fillcolor=hex_to_rgba(color, 0.15)
    ))
    fig.update_layout(
        margin=dict(l=0, r=0, t=20, b=0), height=350, 
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
        xaxis=dict(showgrid=True, gridcolor='#333'),
        yaxis=dict(showgrid=True, gridcolor='#333', side="right", tickformat=f".{precision}f")
    )
    st.plotly_chart(fig, use_container_width=True)

# ====================
# 5. 页面渲染 (严格排版)
# ====================

# --- 概览栏 ---
st.markdown("### 📝 实时盘面核心")
c1, c2, c3, c4 = st.columns(4)
if 'Gold' in data: c1.metric("黄金 (Gold)", f"${data['Gold'].iloc[-1]:,.0f}", f"{(data['Gold'].iloc[-1]/data['Gold'].iloc[-2]-1)*100:.2f}%")
if 'DXY' in data: c2.metric("美元 (DXY)", f"{data['DXY'].iloc[-1]:.2f}", f"{(data['DXY'].iloc[-1]/data['DXY'].iloc[-2]-1)*100:.2f}%")
if 'CNH' in data: c3.metric("人民币 (CNH)", f"{data['CNH'].iloc[-1]:.4f}", f"{(data['CNH'].iloc[-1]/data['CNH'].iloc[-2]-1)*100:.4f}%", delta_color="inverse")
if 'Fed_BS' in data: c4.metric("美联储规模", f"${data['Fed_BS'].iloc[-1]/1e6:.2f}T", f"{(data['Fed_BS'].iloc[-1]-data['Fed_BS'].iloc[-2])/1e6:.3f}T")

# --- 板块 0: 流量监控 (Flow Monitor) ---
st.markdown('<div class="section-header">🌊 流量监控 (Flow Monitor)</div>', unsafe_allow_html=True)
plot_full_card(data.get('Net_Liquidity'), "核心净流动性", "Net Liquidity", "#00E676", "真正流入金融系统的活钱，是所有资产的发动机。", 0)

# --- 板块 1: 资产负债表总额 & 资产端 ---
st.markdown('<div class="section-header">1. 资产端穿透 (Quantity - Assets)</div>', unsafe_allow_html=True)
plot_full_card(data.get('Fed_BS'), "美联储总资产", "Total Assets", "#FFD700", "扩表代表购买，缩表代表抛售或到期收钱。", 0)
plot_full_card(data.get('Fed_Treasury'), "持有美国国债", "Treasury Holdings", "#03A9F4", "美联储最核心的资产，反映其对国债市场的支撑。", 0)
plot_full_card(data.get('Fed_MBS'), "持有房贷证券", "MBS Holdings", "#00BCD4", "反映对房地产市场的流动性支持。", 0)

# --- 板块 2: 负债端穿透 ---
st.markdown('<div class="section-header">2. 负债端穿透 (Quantity - Liabilities)</div>', unsafe_allow_html=True)
plot_full_card(data.get('Reserves'), "银行体系准备金", "Reserve Balances", "#FF5252", "银行存放在美联储的钱，流动性的终端水位。", 0)
plot_full_card(data.get('TGA'), "财政部账户", "TGA Balance", "#AA00FF", "美国政府的钱包，余额越高，市场流动的钱越少。", 0)
plot_full_card(data.get('ON_RRP'), "隔夜逆回购规模", "ON RRP", "#FF9100", "市场的溢出资金，跌至零点意味着流动性枯竭警报。", 0)

# --- 板块 3: 原有流速指标 ---
st.markdown('<div class="section-header">3. 流速与定价 (Velocity)</div>', unsafe_allow_html=True)
plot_full_card(data.get('Gold'), "现货黄金", "Spot Gold", "#FFD700", "美元信用的反向指标。", 0)
plot_full_card(data.get('Gold_Oil'), "金油比", "Gold/Oil Ratio", "#FBC02D", "严重衰退预警指标 (>30)。", 2)
plot_full_card(data.get('US10Y'), "10年美债收益率", "US 10Y Yield", "#FF5252", "全球资产定价之锚。", 2)

# --- 板块 4: 原有流向指标 ---
st.markdown('<div class="section-header">4. 汇率与流向 (Direction)</div>', unsafe_allow_html=True)
plot_full_card(data.get('CNH'), "在岸人民币", "USD/CNY", "#00E676", "关注小数点后4位的博弈。", 4)
plot_full_card(data.get('DXY'), "美元指数", "DXY Index", "#64DD17", "美元周期的晴雨表。", 2)
plot_full_card(data.get('A50_HK'), "安硕A50 (港)", "2823.HK", "#AA00FF", "外资对中国核心资产的态度。", 2)
