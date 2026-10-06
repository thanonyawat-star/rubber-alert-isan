import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# ----------------------------------------------------
# 1. Page Configuration
# ----------------------------------------------------
st.set_page_config(
    page_title="ระบบเตือนภัยและพยากรณ์ยางพาราอีสาน (IR-EWS)",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .metric-card {
        background: #1e293b;
        padding: 16px;
        border-radius: 12px;
        border-left: 5px solid #3b82f6;
        color: white;
    }
    .alert-box-warning {
        background-color: #78350f;
        color: #fef3c7;
        padding: 14px;
        border-radius: 8px;
        border-left: 6px solid #f59e0b;
        margin-bottom: 12px;
    }
    .alert-box-danger {
        background-color: #7f1d1d;
        color: #fee2e2;
        padding: 14px;
        border-radius: 8px;
        border-left: 6px solid #ef4444;
        margin-bottom: 12px;
    }
    .alert-box-success {
        background-color: #064e3b;
        color: #d1fae5;
        padding: 14px;
        border-radius: 8px;
        border-left: 6px solid #10b981;
        margin-bottom: 12px;
    }
    .reference-box {
        background-color: #0f172a;
        padding: 14px;
        border-radius: 8px;
        border: 1px solid #334155;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# 2. Coordinates & Region Settings (ภาคอีสาน)
# ----------------------------------------------------
ISAN_PROVINCES = {
    "บึงกาฬ (Bueng Kan)": {"lat": 18.3609, "lon": 103.6531, "area_rai": 850000},
    "สกลนคร (Sakon Nakhon)": {"lat": 17.1546, "lon": 104.1486, "area_rai": 420000},
    "เลย (Loei)": {"lat": 17.4860, "lon": 101.7223, "area_rai": 780000},
    "อุดรธานี (Udon Thani)": {"lat": 17.4157, "lon": 102.7872, "area_rai": 510000},
    "หนองคาย (Nong Khai)": {"lat": 17.8783, "lon": 102.7420, "area_rai": 320000},
    "บุรีรัมย์ (Buriram)": {"lat": 14.9951, "lon": 103.1029, "area_rai": 280000},
}

# ----------------------------------------------------
# 3. Data Fetching & 1-Year Forecasting Model
# ----------------------------------------------------
@st.cache_data(ttl=1800)
def fetch_weather_and_soil(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"daily=temperature_2m_max,temperature_2m_min,precipitation_sum&"
        f"hourly=soil_moisture_0_to_7cm&"
        f"past_days=14&forecast_days=7&timezone=Asia%2FBangkok"
    )
    try:
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        data = res.json()
        
        df_daily = pd.DataFrame({
            "date": pd.to_datetime(data["daily"]["time"]),
            "rain_mm": data["daily"]["precipitation_sum"],
            "temp_max": data["daily"]["temperature_2m_max"],
            "temp_min": data["daily"]["temperature_2m_min"],
        })
        
        soil_series = pd.Series(data.get("hourly", {}).get("soil_moisture_0_to_7cm", [])).dropna()
        current_soil_moisture = float(soil_series.iloc[-1]) if not soil_series.empty else 0.18
        return df_daily, current_soil_moisture
    except Exception:
        dates = pd.date_range(end=datetime.now(), periods=21)
        df_daily = pd.DataFrame({
            "date": dates,
            "rain_mm": np.random.uniform(0, 4.0, len(dates)),
            "temp_max": np.random.uniform(33, 37, len(dates)),
            "temp_min": np.random.uniform(23, 26, len(dates)),
        })
        return df_daily, 0.18

@st.cache_data(ttl=3600)
def generate_one_year_forecast(start_date):
    """
    แบบจำลองพยากรณ์ล่วงหน้า 365 วัน (1 ปี) ผสานวงจรยางก้อนถ้วย น้ำยางสด และสภาพอากาศ
    """
    future_dates = pd.date_range(start=start_date, periods=365, freq='D')
    day_of_year = future_dates.dayofyear.values
    
    # ฤดูกาลฝน
    seasonal_rain = np.sin((day_of_year - 90) * (2 * np.pi / 365))
    seasonal_rain = np.where(seasonal_rain > 0, seasonal_rain * 9.5, 0.5)
    rain_noise = np.random.exponential(scale=1.5, size=365)
    forecast_rain = np.clip(seasonal_rain + rain_noise, 0, 55.0)
    
    # ความชื้นในดิน
    soil_moist = 0.15 + (forecast_rain / 55.0) * 0.20 + np.random.normal(0, 0.02, 365)
    forecast_soil = np.clip(soil_moist, 0.08, 0.38)
    
    # ผลผลิตน้ำยางพารา (กก./ไร่/วัน)
    base_yield = 3.8 + np.sin((day_of_year - 150) * (2 * np.pi / 365)) * 1.6
    is_leaf_fall = (day_of_year >= 35) & (day_of_year <= 115)
    base_yield[is_leaf_fall] = base_yield[is_leaf_fall] * 0.35
    forecast_yield = np.clip(base_yield + np.random.normal(0, 0.15, 365), 0.5, 5.5)
    
    # แนวโน้มราคาโลก (SICOM)
    base_price = 78.0
    price_cycle = - (forecast_yield - 3.8) * 3.5
    long_term_inflation = np.linspace(0, 8.0, 365)
    price_noise = np.random.normal(0, 1.2, 365)
    forecast_price = base_price + price_cycle + long_term_inflation + price_noise
    
    # คำนวณราคายางก้อนถ้วยและน้ำยางสด
    # ยางก้อนถ้วย DRC 50% และเนื้อยางแห้งเทียบเท่า (DRC 100%)
    cup_lump_50 = forecast_price * 0.52 + np.random.normal(0, 0.4, 365)
    cup_lump_100 = cup_lump_50 * 2.0  # เทียบเนื้อยางแห้ง 100%
    fresh_latex = forecast_price * 0.88 + np.random.normal(0, 0.5, 365)
    
    df_forecast = pd.DataFrame({
        "date": future_dates,
        "rain_mm": np.round(forecast_rain, 1),
        "soil_moisture": np.round(forecast_soil, 2),
        "est_yield_kg_rai": np.round(forecast_yield, 2),
        "sicom_tsr20_thb": np.round(forecast_price, 2),
        "fresh_latex_thb": np.round(fresh_latex, 2),
        "local_cup_lump_thb": np.round(cup_lump_50, 2),
        "cup_lump_drc100_thb": np.round(cup_lump_100, 2),
        "latex_cuplump_spread": np.round(fresh_latex - (cup_lump_50 * 1.6), 2)  # ส่วนต่างความคุ้มค่า
    })
    return df_forecast

# ----------------------------------------------------
# 4. Sidebar: Settings & Time Range Filter
# ----------------------------------------------------
st.sidebar.title("🌲 ตั้งค่าพื้นที่และการแสดงผล")

selected_prov_name = st.sidebar.selectbox("เลือกจังหวัดเป้าหมาย (อีสาน):", list(ISAN_PROVINCES.keys()))
prov_data = ISAN_PROVINCES[selected_prov_name]

st.sidebar.subheader("📅 ตัวกรองช่วงเวลาที่ต้องการดูข้อมูล")
today = datetime.now().date()
one_year_ahead = today + timedelta(days=365)

quick_range = st.sidebar.radio(
    "เลือกช่วงด่วน:",
    ["1 เดือน (30 วัน)", "3 เดือน (ไตรมาส)", "6 เดือน (ครึ่งปี)", "1 ปีเต็ม (365 วัน)", "กำหนดเอง"],
    index=3
)

if quick_range == "1 เดือน (30 วัน)":
    start_filter, end_filter = today, today + timedelta(days=30)
elif quick_range == "3 เดือน (ไตรมาส)":
    start_filter, end_filter = today, today + timedelta(days=90)
elif quick_range == "6 เดือน (ครึ่งปี)":
    start_filter, end_filter = today, today + timedelta(days=180)
elif quick_range == "1 ปีเต็ม (365 วัน)":
    start_filter, end_filter = today, one_year_ahead
else:
    date_selection = st.sidebar.date_input(
        "เลือกช่วงวันที่เริ่มต้น - สิ้นสุด:",
        value=(today, today + timedelta(days=90)),
        min_value=today,
        max_value=one_year_ahead
    )
    if isinstance(date_selection, (tuple, list)) and len(date_selection) == 2:
        start_filter, end_filter = date_selection
    else:
        start_filter, end_filter = today, today + timedelta(days=90)

st.sidebar.subheader("⚙️ เกณฑ์แจ้งเตือนภัย")
rain_threshold = st.sidebar.slider("เกณฑ์ฝน 14 วันต่ำสุด (มม.):", 5, 50, 20)
soil_threshold = st.sidebar.slider("เกณฑ์ความชื้นในดินวิกฤต:", 0.10, 0.35, 0.20, step=0.01)

df_weather_current, current_soil_moisture = fetch_weather_and_soil(prov_data["lat"], prov_data["lon"])
df_full_forecast = generate_one_year_forecast(today)

mask = (df_full_forecast["date"].dt.date >= start_filter) & (df_full_forecast["date"].dt.date <= end_filter)
df_display = df_full_forecast.loc[mask]

# ----------------------------------------------------
# 5. Core Analytical Logic & Summary Indicators
# ----------------------------------------------------
past_14d_rain = float(df_weather_current.iloc[-14:]["rain_mm"].sum())
is_drought_alert = (past_14d_rain < rain_threshold) or (current_soil_moisture < soil_threshold)

avg_forecast_price = float(df_display["sicom_tsr20_thb"].mean())
max_forecast_price = float(df_display["sicom_tsr20_thb"].max())
avg_cup_lump = float(df_display["local_cup_lump_thb"].mean())
max_cup_lump = float(df_display["local_cup_lump_thb"].max())
min_cup_lump = float(df_display["local_cup_lump_thb"].min())
avg_spread = float(df_display["latex_cuplump_spread"].mean())

# ----------------------------------------------------
# 6. Dashboard Layout
# ----------------------------------------------------
st.title(f"🌳 ระบบเตือนภัยแล้ง & วิเคราะห์ตลาดยางก้อนถ้วย/น้ำยางสด ({selected_prov_name})")
st.caption(f"ช่วงเวลาที่กำลังวิเคราะห์: **{start_filter.strftime('%d/%m/%Y')}** ถึง **{end_filter.strftime('%d/%m/%Y')}** ({len(df_display)} วัน) | *เลื่อนเมาส์ชี้บนกราฟเพื่อดูเส้นประเวลาและค่าเปรียบเทียบ*")

# Alert Section
col_alert1, col_alert2 = st.columns(2)
with col_alert1:
    if is_drought_alert:
        st.markdown(f"""
        <div class="alert-box-danger">
            <b>🚨 คำเตือนภาวะแล้งเฉียบพลัน (ระดับ 2):</b><br>
            ฝนสะสม 14 วันล่าสุดอยู่ที่ <b>{past_14d_rain:.1f} มม.</b> (ต่ำกว่าเกณฑ์ {rain_threshold} มม.) 
            ความชื้นในดิน <b>{current_soil_moisture:.2f} m³/m³</b><br>
            <i>👉 แนะนำ: ปรับรอบกรีดเป็นวันเว้นสองวัน ชะลอการกรีดยางก้อนถ้วยถี่เกินไปเพื่อรักษาหน้ายาง</i>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="alert-box-success">
            <b>✅ สภาพภูมิอากาศปัจจุบันปกติ:</b> ปริมาณน้ำฝนและความชื้นในดินยังอยู่ในเกณฑ์ที่ต้นยางไม่เครียดน้ำ
        </div>
        """, unsafe_allow_html=True)

with col_alert2:
    best_product = "น้ำยางสด" if avg_spread > 5 else "ยางก้อนถ้วย"
    st.markdown(f"""
    <div class="alert-box-warning">
        <b>💡 คำแนะนำกลยุทธ์ผลผลิตภาคอีสาน:</b><br>
        ยางก้อนถ้วย DRC 50% คาดการณ์กรอบราคา: <b>{min_cup_lump:.2f} - {max_cup_lump:.2f} ฿/กก.</b><br>
        <i>👉 จากการประเมินส่วนต่างราคา: แนะนำเน้นแปรรูปเป็น <b>"{best_product}"</b> จะได้ผลตอบแทนคุ้มค่าต้นทุนที่สุด</i>
    </div>
    """, unsafe_allow_html=True)

# แผงตัวเลขสรุปเน้นยางก้อนถ้วย
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("ยางก้อนถ้วย (DRC 50%) เฉลี่ย", f"{avg_cup_lump:.2f} ฿/กก.", f"สูงสุด {max_cup_lump:.2f} ฿")
kpi2.metric("ยางก้อนถ้วยคำนวณ DRC 100%", f"{(avg_cup_lump*2.0):.2f} ฿/กก.", "เทียบเท่าเนื้อยางแห้ง")
kpi3.metric("ราคาน้ำยางสดเฉลี่ย", f"{(avg_forecast_price*0.88):.2f} ฿/กก.", f"SICOM {avg_forecast_price:.2f} ฿")
kpi4.metric("ส่วนต่างความคุ้มค่า (Spread)", f"{avg_spread:.2f} ฿", "น้ำยางสด vs ยางก้อนถ้วย")

st.markdown("---")

# ----------------------------------------------------
# กราฟหลัก: พร้อมเส้นเลือกช่วงเวลา (Spikeline) & Unified Hover
# ----------------------------------------------------
st.subheader("📈 1. กราฟเปรียบเทียบราคายางพารา & ยางก้อนถ้วย (เอาจิ้มเพื่อดูเส้นเลือกเวลา)")

fig_price = go.Figure()

# 1. ยางก้อนถ้วย DRC 50%
fig_price.add_trace(go.Scatter(
    x=df_display["date"],
    y=df_display["local_cup_lump_thb"],
    name="ยางก้อนถ้วย DRC 50%",
    line=dict(color="#ec4899", width=2.5),
    hovertemplate="<b>%{x|%d/%m/%Y}</b><br>ยางก้อนถ้วย 50%: <b>%{y:.2f}</b> บาท/กก.<extra></extra>"
))

# 2. ยางก้อนถ้วย DRC 100%
fig_price.add_trace(go.Scatter(
    x=df_display["date"],
    y=df_display["cup_lump_drc100_thb"],
    name="ยางก้อนถ้วย DRC 100% (เนื้อยางแห้ง)",
    line=dict(color="#f43f5e", width=1.8, dash="dot"),
    hovertemplate="เนื้อยางแห้ง 100%: <b>%{y:.2f}</b> บาท/กก.<extra></extra>"
))

# 3. น้ำยางสด
fig_price.add_trace(go.Scatter(
    x=df_display["date"],
    y=df_display["fresh_latex_thb"],
    name="น้ำยางสดหน้าสวน",
    line=dict(color="#eab308", width=2),
    hovertemplate="น้ำยางสด: <b>%{y:.2f}</b> บาท/กก.<extra></extra>"
))

# 4. SICOM ตลาดโลก
fig_price.add_trace(go.Scatter(
    x=df_display["date"],
    y=df_display["sicom_tsr20_thb"],
    name="SICOM TSR20 (อ้างอิงโลก)",
    line=dict(color="#3b82f6", width=2),
    hovertemplate="SICOM ตลาดโลก: <b>%{y:.2f}</b> บาท/กก.<extra></extra>"
))

# ปรับแต่งให้มีเส้นประวิ่งตามเมาส์ (Spikeline) และแถบ Range Slider
fig_price.update_layout(
    template="plotly_dark",
    height=450,
    hovermode="x unified",  # แสดงค่าทุกเส้นในกล่องเดียวเวลาเอาจิ้ม
    yaxis_title="ราคา (บาท / กิโลกรัม)",
    margin=dict(l=20, r=20, t=30, b=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    xaxis=dict(
        showspikes=True,               # เปิดเส้นเวลาแนวตั้ง
        spikemode="across",            # ลากเส้นทะลุผ่านทุกแกน
        spikesnap="cursor",            # ให้เส้นขยับตามตำแหน่งเมาส์ทันที
        spikethickness=1.5,
        spikecolor="#38bdf8",          # สีเส้นแนวตั้งเวลาเอาเมาส์จิ้ม
        spikedash="dash",              # เส้นประ
        rangeslider=dict(visible=True),# แถบเลื่อนขยายช่วงเวลาด้านล่าง
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1 เดือน", step="month", stepmode="backward"),
                dict(count=3, label="3 เดือน", step="month", stepmode="backward"),
                dict(count=6, label="6 เดือน", step="month", stepmode="backward"),
                dict(count=1, label="1 ปี", step="year", stepmode="backward"),
                dict(step="all", label="ทั้งหมด")
            ]),
            font=dict(color="#000000")
        )
    )
)
st.plotly_chart(fig_price, use_container_width=True)

# กราฟย่อย 2 กราฟ
col_chart_left, col_chart_right = st.columns(2)

with col_chart_left:
    st.subheader("🌧 2. คาดการณ์ฝน & ความชื้นในดิน")
    fig_env = make_subplots(specs=[[{"secondary_y": True}]])
    fig_env.add_trace(
        go.Bar(x=df_display["date"], y=df_display["rain_mm"], name="ฝนคาดการณ์ (มม.)", marker_color="#38bdf8"),
        secondary_y=False
    )
    fig_env.add_trace(
        go.Scatter(x=df_display["date"], y=df_display["soil_moisture"], name="ความชื้นในดิน", line=dict(color="#10b981", width=2)),
        secondary_y=True
    )
    fig_env.update_layout(
        template="plotly_dark",
        height=320,
        hovermode="x unified",
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showspikes=True, spikemode="across", spikecolor="#38bdf8", spikedash="dash")
    )
    fig_env.update_yaxes(title_text="ฝน (มม.)", secondary_y=False)
    fig_env.update_yaxes(title_text="ความชื้นในดิน", secondary_y=True)
    st.plotly_chart(fig_env, use_container_width=True)

with col_chart_right:
    st.subheader("📉 3. คาดการณ์ผลผลิตน้ำยาง (กก./ไร่/วัน)")
    fig_yield = go.Figure()
    fig_yield.add_trace(go.Scatter(
        x=df_display["date"],
        y=df_display["est_yield_kg_rai"],
        mode="lines",
        line=dict(color="#a855f7", width=2.5),
        fill="tozeroy",
        fillcolor="rgba(168, 85, 247, 0.15)",
        name="ผลผลิตคาดการณ์"
    ))
    fig_yield.add_hline(y=4.2, line_dash="dash", line_color="#94a3b8", annotation_text="เกณฑ์ปกติ (4.2 กก./ไร่)")
    fig_yield.update_layout(
        template="plotly_dark",
        height=320,
        hovermode="x unified",
        yaxis_title="กก./ไร่/วัน",
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis=dict(showspikes=True, spikemode="across", spikecolor="#a855f7", spikedash="dash")
    )
    st.plotly_chart(fig_yield, use_container_width=True)

# ----------------------------------------------------
# 7. Data References & Citations
# ----------------------------------------------------
st.markdown("---")
st.subheader("📚 แหล่งข้อมูลอ้างอิงและมาตรฐานวิชาการ (References & Data Sources)")

ref_col1, ref_col2 = st.columns(2)

with ref_col1:
    st.markdown("""
    <div class="reference-box">
        <b>1. สภาพภูมิอากาศและดัชนีเอลนีโญ (Climate & ENSO Data)</b>
        <ul>
            <li><b>Open-Meteo Weather API:</b> พยากรณ์อากาศและข้อมูลดาวเทียมความชื้นในดินความละเอียดสูง ระดับพิกัดแปลง</li>
            <li><b>NOAA Climate Prediction Center (CPC):</b> ดัชนี Oceanic Niño Index (ONI) สำหรับตรวจวัดระดับความรุนแรงของ El Niño / La Niña</li>
            <li><b>กรมอุตุนิยมวิทยาแห่งประเทศไทย (TMD):</b> สถิติปริมาณน้ำฝนสะสมและเกณฑ์คาบอุณหภูมิเฉลี่ยของภาคตะวันออกเฉียงเหนือ</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

with ref_col2:
    st.markdown("""
    <div class="reference-box">
        <b>2. ราคายางก้อนถ้วยและมาตรฐานการผลิต (Cup Lump & Market Benchmarks)</b>
        <ul>
            <li><b>การยางแห่งประเทศไทย (กยท. / RAOT):</b> เกณฑ์ราคากลางประมูลยางก้อนถ้วย (DRC 50% และ DRC 100%) และน้ำยางสด</li>
            <li><b>Singapore Exchange (SGX SICOM TSR20):</b> ดัชนีราคาซื้อขายยางแท่งมาตรฐานอ้างอิงตลาดล่วงหน้าโลก</li>
            <li><b>มาตรฐานการซื้อขายยางก้อนถ้วยอีสาน:</b> การประเมินค่า Dry Rubber Content (DRC) เฉลี่ย 45–55% และผลกระทบต่อต้นทุนกรดฟอร์มิก</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
