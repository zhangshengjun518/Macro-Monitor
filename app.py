import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

# ====================
# 1. 页面配置与美化
# ====================
st.set_page_config(page_title="Fed Balance Sheet Monitor", layout="wide")

st.markdown("""
<style>
    .reportview-container { background: #0E1117; }
    .metric-card {
        background: #161b22; border-radius: 10px; padding: 20px;
        border: 1px solid #30363d; margin-bottom: 20px;
    }
    .indicator-title {
        font-size: 24px; color: #58a6ff; font-weight: bold;
        border-left: 5px solid #58a6ff; padding-left: 15px; margin: 30px 0 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ====================
# 2. 极速并发数据引擎
# ====================
@st.cache_data(ttl=3600)
def fetch_all_data():
    # 核心指标定义
    fred_map = {
        'WALCL': '总资产 (Total Assets)',
        'WSHOMCB': '资产端：持有国债 (Treasuries)',
        'WSHMBS': '资产端：持有房贷证券 (MBS)',
        'WRESBAL': '负债端：银行准备金 (Reserves)',
        'WTREGEN': '负债端：财政部账户 (TGA)',
        'RRPONTSYD': '负债端：逆回购 (ON RRP)'
    }
    
    def get_fred_csv(code):
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={code}"
        df = pd.read_csv(url, index_col=0, parse_dates=True)
        return df.iloc[:, 0].tail(90) # 只取最近3个月

    results = {}
    # 使用线程池并发抓取，大幅提升速度
    with ThreadPoolExecutor(max_workers=6) as executor:
        future_to_code = {executor.submit(get_fred_csv, code): name for code, name in fred_map.items()}
        for future in future_to_code:
            name = future_to_code[future]
            try:
                results[name] = future.result()
            except:
                results[name] = pd.Series()
    return results

# ====================
# 3. 绘图标准件 (单行大图)
# ====================
def draw_large_chart(series, name, color):
    if series.empty:
        st.warning(f"无法获取 {name} 的实时数据")
        return

    curr_val = series.iloc[-1] / 1e6  # 转换为万亿美元
    prev_val = series.iloc[-2] / 1e6
    delta = curr_val - prev_val
    
    st.markdown(f'<div class="indicator-title">{name}</div>', unsafe_allow_html=True)
    
    # 指标卡片
    c1, c2 = st.columns([1, 4])
    with c1:
        st.metric("当前数值", f"{curr_val:.3f} T", f"{delta:.4f} T")
        st.caption("单位：万亿美元 (Trillions)")
    
    # 大图展示
    with c2:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=series.index, y=series.values/1e6,
            mode='lines+markers',
            line=dict(color=color, width=3),
            fill='tozeroy',
            fillcolor=f"rgba({int(color[1:3],16)}, {int(color[3:5],16)}, {int(color[5:7],16)}, 0.1)"
        ))
        fig.update_layout(
            height=350, margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor='#333', side="right", title="Trillions $")
        )
        st.plotly_chart(fig, use_container_width=True)

# ====================
# 4. 主逻辑排版
# ====================
st.title("🏦 美联储资产负债表深度穿透 (极速版)")
st.info("数据每小时更新一次 | 采用多线程并发抓取技术")

with st.spinner("正在穿透 FED 数据库..."):
    data_map = fetch_all_data()

# --- 第一部分：总规模 ---
st.header("一、 资产负债表总规模")
draw_large_chart(data_map['总资产 (Total Assets)'], "美联储资产总规模", "#FFD700")

# --- 第二部分：资产端 (Money Out) ---
st.header("二、 资产端细分 (美联储买了什么)")
draw_large_chart(data_map['资产端：持有国债 (Treasuries)'], "美国国债持有量", "#00E676")
draw_large_chart(data_map['资产端：持有房贷证券 (MBS)'], "MBS 抵押支持证券持有量", "#00B0FF")

# --- 第三部分：负债端 (Money In) ---
st.header("三、 负债端细分 (钱流向了哪里)")
draw_large_chart(data_map['负债端：银行准备金 (Reserves)'], "银行体系准备金 (流动性核心)", "#FF5252")
draw_large_chart(data_map['负债端：财政部账户 (TGA)'], "政府账户余额 (TGA)", "#AA00FF")
draw_large_chart(data_map['负债端：逆回购 (ON RRP)'], "隔夜逆回购规模 (过剩资金)", "#FF9100")

# --- 第四部分：流量监控看板 ---
st.header("四、 流量监控 (Flow Monitor)")
# 计算净流动性
if not data_map['总资产 (Total Assets)'].empty:
    net_liq = data_map['总资产 (Total Assets)'] - data_map['负债端：财政部账户 (TGA)'] - data_map['负债端：逆回购 (ON RRP)']
    draw_large_chart(net_liq, "核心净流动性 (Net Liquidity)", "#FFFFFF")
    st.markdown("> **公式：净流动性 = 总资产 - TGA - 逆回购**。该指标与标普500走势高度正相关。")
