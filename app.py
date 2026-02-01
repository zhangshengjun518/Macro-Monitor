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
    page_title="全球宏观三流监控 (Real-time Flow)",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 保持你原有的 CSS 样式
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

st.title("⚡ 全球宏观“三流”监控 (资产负债表实时版)")
st.caption("数据源：FRED (美联储) & Yahoo Finance | 自动抓取最近3个月动态")

# ====================
# 2. 辅助函数
# ====================
def hex_to_rgba(hex_color, alpha=0.2):
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"

# ====================
# 3. 增强版数据引擎 (接入 FRED 实时流)
# ====================
@st.cache_data(ttl=3600*4) 
def get_data_live():
    data_store = {}
    with st.status("正在同步美联储及市场实时数据...", expanded=True) as status:
        
        # --- 阶段 1: 美联储资产负债表细分数据 (FRED 直连) ---
        status.write("📡 抓取美联储 H.4.1 细分指标...")
        # 新增细分指标：WCURCIR(流通货币), WRESBAL(准备金), WSHOMCB(国债), WSHMBS(MBS)
        fred_codes = {
            'WALCL': 'Fed_BS',      # 总资产
            'WTREGEN': 'TGA',       # 财政部存款
            'RRPONTSYD': 'ON_RRP',  # 隔夜逆回购
            'WRESBAL': 'Reserves',  # 银行准备金 (核心流量)
            'WSHOMCB': 'Treasury',  # 持有国债
            'WSHMBS': 'MBS'         # 持有MBS
        }
        
        for code, name in fred_codes.items():
            try:
                url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={code}"
                df = pd.read_csv(url, index_col=0, parse_dates=True)
                # 统一取最近 180 天确保覆盖 3个月+计算所需空间
                start_date = datetime.now() - timedelta(days=180)
                df = df[df.index >= start_date]
                # 对周度数据进行线性插值，以便与日度数据对齐
                data_store[name] = df.iloc[:, 0].resample('D').interpolate(method='time').dropna()
            except:
                st.error(f"无法获取 FRED 数据: {name}")

        # 计算：净流动性 (Net Liquidity) = 总资产 - TGA - 逆回购
        if all(k in data_store for k in ['Fed_BS', 'TGA', 'ON_RRP']):
            data_store['Net_Liquidity'] = data_store['Fed_BS'] - data_store['TGA'] - data_store['ON_RRP']

        # --- 阶段 2: 市场价格数据 (Yahoo) ---
        status.write("💰 抓取全球市场即时价格...")
        tickers = {
            "Gold": "GC=F", "DXY": "DX-Y.NYB", "CNH": "CNY=X", 
            "US10Y": "^TNX", "A50_HK": "2823.HK"
        }
        for key, symbol in tickers.items():
            try:
                df = yf.download(symbol, period="6m", progress=False, threads=False)
                if not df.empty:
                    series = df['Close'].iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else df['Close']
                    data_store[key] = series.dropna()
            except:
                st.error(f"无法获取 Yahoo 数据: {key}")

        status.update(label="✅ 实时数据链路同步成功!", state="complete", expanded=False)
    return data_store

data = get_data_live()

# ====================
# 4. 绘图函数 (保持原样)
# ====================
def plot_card(series, title_cn, title_en, color, lu_analysis, precision=2):
    if series is None or series.empty: return
    # 固定展示最近 90 天 (3个月)
    display = series.tail(90)
    curr = display.iloc[-1]
    prev = display.iloc[-2]
    delta = (curr - prev) / prev * 100
    
    fmt = f".{precision}f" if precision >= 2 else ",.0f"
    fmt_val = f"{curr:{fmt}}"
    d_col = "#FF5252" if delta < 0 else "#00E676"
    
    st.markdown(f"""
    <div class="full-card">
        <div class="card-title">{title_cn} <span>{title_en}</span></div>
        <div style="display:flex;">
            <div style="flex:1;">
                <div class="big-value" style="color:{color}">{fmt_val}</div>
                <div style="font-size:1.2rem; color:{d_col}; font-weight:bold;">{delta:.2f}%</div>
                <div class="lu-comment-box"><div class="lu-label">🎙️ 视角：</div><div class="lu-text">{lu_analysis}</div></div>
            </div>
            <div style="flex:2;"></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([1, 3])
    with c2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=display.index, y=display.values, mode='lines', 
            line=dict(color=color, width=2), 
            fill='tozeroy', fillcolor=hex_to_rgba(color, 0.2)
        ))
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0), height=250, 
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', 
            xaxis=dict(showgrid=True, gridcolor='#333'),
            yaxis=dict(showgrid=True, gridcolor='#333', side="right")
        )
        st.plotly_chart(fig, use_container_width=True)

# ====================
# 5. 板块展示
# ====================

# --- 板块 0: 流量监控 (Flow Monitor) ---
st.markdown('<div class="section-header">🌊 流量监控 (Flow Monitor)</div>', unsafe_allow_html=True)
col_f1, col_f2 = st.columns(2)
with col_f1:
    plot_card(data.get('Net_Liquidity'), "核心净流动性", "Net Liquidity", "#00E676", "计算公式：总资产 - TGA - RRP。这是支撑美股风险偏好的真实钱。")
with col_f2:
    plot_card(data.get('Reserves'), "银行准备金", "Bank Reserves", "#FFEA00", "银行体系的血液。若低于2.5万亿，市场将出现钱荒。")

# --- 板块 1: 资产负债表 (Quantity) ---
st.markdown('<div class="section-header">1. 资产规模 (Quantity)</div>', unsafe_allow_html=True)
c_q1, c_q2, c_q3 = st.columns(3)
with c_q1: plot_card(data.get('Fed_BS'), "美联储总资产", "Total Assets", "#6200EA", "扩表即放水，缩表即收水。", 0)
with c_q2: plot_card(data.get('Treasury'), "持有国债", "U.S. Treasuries", "#03A9F4", "美联储对政府债务的直接支持力度。", 0)
with c_q3: plot_card(data.get('MBS'), "持有房贷证券", "MBS", "#00BCD4", "对房地产市场的流动性支持。", 0)

c_q4, c_q5 = st.columns(2)
with c_q4: plot_card(data.get('TGA'), "财政部账户", "TGA Balance", "#D32F2F", "财政部在央行的余额，增加代表从市场抽水。", 0)
with c_q5: plot_card(data.get('ON_RRP'), "逆回购规模", "ON RRP", "#FF9100", "市场过剩资金的蓄水池。", 0)

# --- 板块 2 & 3: 流速与流向 (原有指标) ---
st.markdown('<div class="section-header">2. 价格与流速 (Velocity)</div>', unsafe_allow_html=True)
plot_card(data.get('Gold'), "现货黄金", "Spot Gold", "#FFD700", "信用货币的对立面。", 0)
plot_card(data.get('US10Y'), "10年美债收益率", "10Y Yield", "#FF5252", "全球定价之锚。", 2)

st.markdown('<div class="section-header">3. 汇率与流向 (Direction)</div>', unsafe_allow_html=True)
plot_card(data.get('CNH'), "离岸人民币", "USD/CNH", "#00E676", "跨境资本流动的晴雨表。", 4)
plot_card(data.get('DXY'), "美元指数", "DXY Index", "#448AFF", "美元强弱周期。", 2)
