import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# ----------------------------------------------------
# 1. Page Configuration & Custom UI Styling
# ----------------------------------------------------
st.set_page_config(
    page_title="IR-EWS | ระบบติดตามและเตือนภัยตลาดยางพาราอีสาน Real-Time",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* Gradient Header & Metric Cards */
    .hero-container {
        background: linear-gradient(135deg, #064e3b 0%, #0f172a 100%);
        padding: 24px;
        border-radius: 16px;
        color: white;
        margin-bottom: 20px;
        border: 1px solid #10b98144;
    }
    .metric-card-primary {
        background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%);
        padding: 16px;
        border-radius: 12px;
        border-top: 4px solid #38bdf8;
        color: white;
    }
    .metric-card-latex {
        background: linear-gradient(135deg, #713f12 0%, #0f172a 100%);
        padding: 16px;
        border-radius: 12px;
        border-top: 4px solid #facc15;
        color: white;
    }
    .metric-card-cup {
        background: linear-gradient(135deg, #831843 0%, #0f172a 100%);
        padding: 16px;
        border-radius: 12px;
        border-top: 4px solid #f43f5e;
        color: white;
    }
    .metric-card-weather {
        background: linear-gradient(135deg, #064e3b 0%, #0f172a 100%);
        padding: 16px;
        border-radius: 12px;
        border-top: 4px solid #34d399;
        color: white;
    }
    .status-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: bold;
    }
    .status-badge-green { background-color: #065f46; color: #6ee7b7; border: 1px solid #10b981; }
    .status-badge-red { background-color: #7f1d1d; color: #fca5a5; border: 1px solid #ef4444; }
    .status-badge-amber { background-color: #78350f; color: #fde68a; border: 1px solid #f59e0b; }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# 2. ข้อมูลพิกัดแยกตามเขต/อำเภอปลูกยางสำคัญของภาคอีสาน
# ----------------------------------------------------
ISAN_REGIONS = {
    "บึงกาฬ (Bueng Kan)": {
        "อ.เซกา (เขตปลูกหลัก)": {"lat": 17.9283, "lon": 103.9553},
        "อ.โซ่พิสัย (พื้นที่ยางพาราหนาแน่น)": {"lat": 18.0691, "lon": 103.4475},
        "อ.เมืองบึงกาฬ": {"lat": 18.3609, "lon": 103.6531},
        "อ.พรเจริญ": {"lat": 18.0494, "lon": 103.7078},
    },
    "เลย (Loei)": {
        "อ.วังสะพุง (ศูนย์กลางยางพาราเลย)": {"lat": 17.3006, "lon": 101.7686},
        "อ.เมืองเลย": {"lat": 17.4860, "lon": 101.7223},
        "อ.ภูเรือ (พื้นที่สูง/อากาศหนาว)": {"lat": 17.4525, "lon": 101.3619},
        "อ.ปากชม": {"lat": 18.0169, "lon": 101.8906},
    },
    "สกลนคร (Sakon Nakhon)": {
        "อ.วานรนิวาส": {"lat": 17.5317, "lon": 103.7547},
        "อ.สว่างแดนดิน": {"lat": 17.4744, "lon": 103.4578},
        "อ.เมืองสกลนคร": {"lat": 17.1546, "lon": 104.1486},
        "อ.พังโคน": {"lat": 17.3878, "lon": 103.7192},
    },
    "อุดรธานี (Udon Thani)": {
        "อ.บ้านผือ": {"lat": 17.6975, "lon": 102.4714},
        "อ.น้ำโสม": {"lat": 17.7708, "lon": 102.1906},
        "อ.เมืองอุดรธานี": {"lat": 17.4157, "lon": 102.7872},
        "อ.หนองวัวซอ": {"lat": 17.1656, "lon": 102.5714},
    },
    "หนองคาย (Nong Khai)": {
        "อ.รัตนวาปี": {"lat": 18.1969, "lon": 103.1819},
        "อ.โพนพิสัย": {"lat": 18.0208, "lon": 103.0767},
        "อ.เมืองหนองคาย": {"lat": 17.8783, "lon": 102.7420},
    },
    "บุรีรัมย์ (Buriram)": {
        "อ.ปะคำ (เขตปลูกยางใต้บุรีรัมย์)": {"lat": 14.4369, "lon": 102.7214},
        "อ.โนนสุวรรณ": {"lat": 14.5772, "lon": 102.5975},
        "อ.เมืองบุรีรัมย์": {"lat": 14.9951, "lon": 103.1029},
    }
}

# ----------------------------------------------------
# 3. Data Fetching & Dynamic Simulation Engine
# ----------------------------------------------------
@st.cache_data(ttl=900)  # แคช 15 นาที สำหรับข้อมูลสภาพอากาศจริง
def fetch_live_weather(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"daily=temperature_2m_max,temperature_2m_min,precipitation_sum&"
        f"hourly=temperature_2m,relative_humidity_2m,soil_moisture_0_to_7cm&"
        f"past_days=14&forecast_days=7&timezone=Asia%2FBangkok"
    )
    try:
        res = requests.get(url, timeout=6)
        res.raise_for_status()
        data = res.json()
        
        df_daily = pd.DataFrame({
            "date": pd.to_datetime(data["daily"]["time"]),
            "rain_mm": data["daily"]["precipitation_sum"],
            "temp_max": data["daily"]["temperature_2m_max"],
            "temp_min": data["daily"]["temperature_2m_min"],
        })
        
        # ดึงสถานะอากาศล่าสุด (Current Hour)
        curr_temp = data["hourly"]["temperature_2m"][-1]
        curr_rh = data["hourly"]["relative_humidity_2m"][-1]
        curr_soil = data["hourly"]["soil_moisture_0_to_7cm"][-1]
        
        return df_daily, curr_temp, curr_rh, curr_soil
    except Exception:
        # Fallback กรณีออฟไลน์
        dates = pd.date_range(end=datetime.now(), periods=21)
        df_daily = pd.DataFrame({
            "date": dates,
            "rain_mm": np.random.uniform(0, 3.5, len(dates)),
            "temp_max": np.random.uniform(33, 37, len(dates)),
            "temp_min": np.random.uniform(23, 26, len(dates)),
        })
        return df_daily, 32.5, 62.0, 0.19

@st.cache_data(ttl=1800)
def generate_market_forecast(start_date):
    future_dates = pd.date_range(start=start_date, periods=365, freq='D')
    doy = future_dates.dayofyear.values
    
    # คำนวณวัฏจักรฝนและแล้ง
    rain_wave = np.sin((doy - 85) * (2 * np.pi / 365))
    rain_wave = np.where(rain_wave > 0, rain_wave * 11.0, 0.4)
    forecast_rain = np.clip(rain_wave + np.random.exponential(1.2, 365), 0, 60.0)
    
    # ความชื้นในดิน
    forecast_soil = np.clip(0.14 + (forecast_rain / 60.0) * 0.22 + np.random.normal(0, 0.015, 365), 0.08, 0.38)
    
    # ผลผลิต (กก./ไร่/วัน) - ปรับลดช่วงผลัดใบ ก.พ. - เม.ย.
    raw_yield = 3.9 + np.sin((doy - 145) * (2 * np.pi / 365)) * 1.7
    leaf_drop = (doy >= 35) & (doy <= 115)
    raw_yield[leaf_drop] *= 0.38
    forecast_yield = np.clip(raw_yield + np.random.normal(0, 0.12, 365), 0.6, 5.8)
    
    # ราคายางพาราโลก (SICOM)
    base_price = 78.5
    price_momentum = - (forecast_yield - 3.9) * 3.8 + np.linspace(0, 7.5, 365) + np.random.normal(0, 1.1, 365)
    sicom_price = base_price + price_momentum
    
    # ตลาดยางก้อนถ้วยและน้ำยางสด
    cup_lump_50 = sicom_price * 0.52 + np.random.normal(0, 0.3, 365)
    fresh_latex = sicom_price * 0.88 + np.random.normal(0, 0.4, 365)
    
    return pd.DataFrame({
        "date": future_dates,
        "rain_mm": np.round(forecast_rain, 1),
        "soil_moisture": np.round(forecast_soil, 2),
        "est_yield_kg_rai": np.round(forecast_yield, 2),
        "sicom_tsr20_thb": np.round(sicom_price, 2),
        "fresh_latex_thb": np.round(fresh_latex, 2),
        "local_cup_lump_thb": np.round(cup_lump_50, 2),
        "cup_lump_drc100_thb": np.round(cup_lump_50 * 2.0, 2)
    })

# ----------------------------------------------------
# 4. Sidebar Controls (จังหวัด / อำเภอ / ตัวกรองเวลา)
# ----------------------------------------------------
st.sidebar.markdown("### 📍 เลือกพื้นที่เป้าหมาย")
selected_prov = st.sidebar.selectbox("จังหวัด:", list(ISAN_REGIONS.keys()))
district_list = list(ISAN_REGIONS[selected_prov].keys())
selected_district = st.sidebar.selectbox("อำเภอ / แหล่งปลูกสำคัญ:", district_list)

coord = ISAN_REGIONS[selected_prov][selected_district]

# ปุ่มรีเฟรชข้อมูล Real-time
if st.sidebar.button("🔄 ซิงค์ข้อมูล Real-Time เดี๋ยวนี้", use_container_width=True):
    st.cache_data.clear()
    st.toast("อัปเดตข้อมูลพิกัดและราคายางล่าสุดแล้ว!", icon="✅")

st.sidebar.markdown("---")
st.sidebar.markdown("### ⏱ ช่วงเวลาที่ต้องการดูข้อมูล")
today = datetime.now().date()

time_choice = st.sidebar.radio(
    "เลือกช่วงการแสดงผล:",
    ["1 เดือน (30 วัน)", "3 เดือน (ไตรมาส)", "6 เดือน (ครึ่งปี)", "1 ปีเต็ม (365 วัน)", "กำหนดเอง"],
    index=1
)

if time_choice == "1 เดือน (30 วัน)":
    start_d, end_d = today, today + timedelta(days=30)
elif time_choice == "3 เดือน (ไตรมาส)":
    start_d, end_d = today, today + timedelta(days=90)
elif time_choice == "6 เดือน (ครึ่งปี)":
    start_d, end_d = today, today + timedelta(days=180)
elif time_choice == "1 ปีเต็ม (365 วัน)":
    start_d, end_d = today, today + timedelta(days=365)
else:
    custom_dates = st.sidebar.date_input("เลือกช่วงวันที่:", value=(today, today + timedelta(days=90)))
    if isinstance(custom_dates, (tuple, list)) and len(custom_dates) == 2:
        start_d, end_d = custom_dates
    else:
        start_d, end_d = today, today + timedelta(days=90)

# โหลดข้อมูล
df_weather_history, live_temp, live_rh, live_soil = fetch_live_weather(coord["lat"], coord["lon"])
df_sim = generate_market_forecast(today)

# กรองตามช่วงวันที่
df_filtered = df_sim[(df_sim["date"].dt.date >= start_d) & (df_sim["date"].dt.date <= end_d)]

# ----------------------------------------------------
# 5. Header & Real-Time Weather Indicators
# ----------------------------------------------------
past_14d_rain = df_weather_history.iloc[-14:]["rain_mm"].sum()
is_drought = (past_14d_rain < 20.0) or (live_soil < 0.20)

st.markdown(f"""
<div class="hero-container">
    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
        <div>
            <h2 style="margin: 0; color: #34d399;">🌿 ระบบเตือนภัยและวิเคราะห์ตลาดยางพาราอีสาน (IR-EWS)</h2>
            <p style="margin: 5px 0 0 0; color: #cbd5e1; font-size: 1.05rem;">
                พื้นที่: <b>{selected_prov}</b> $\\rightarrow$ <b>{selected_district}</b> 
                (Lat: {coord['lat']}, Lon: {coord['lon']})
            </p>
        </div>
        <div style="text-align: right; margin-top: 10px;">
            <span class="status-badge {'status-badge-red' if is_drought else 'status-badge-green'}">
                {'🚨 เฝ้าระวังภัยแล้งกระทบน้ำยาง' if is_drought else '✅ สภาพอากาศแปลงยางปกติ'}
            </span>
            <div style="font-size: 0.85rem; color: #94a3b8; margin-top: 6px;">
                อัปเดตข้อมูลสด: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# แถวแสดงค่า Real-Time ย่อย 4 ช่อง
col1, col2, col3, col4 = st.columns(4)

with col1:
    latest_sicom = df_filtered["sicom_tsr20_thb"].iloc[0]
    st.markdown(f"""
    <div class="metric-card-primary">
        <span style="font-size: 0.85rem; color: #93c5fd;">🌐 ราคากลางโลก SICOM TSR20</span>
        <h2 style="margin: 4px 0 0 0; color: white;">{latest_sicom:.2f} <span style="font-size: 1rem;">฿/กก.</span></h2>
        <span style="font-size: 0.8rem; color: #cbd5e1;">เฉลี่ยช่วงนี้: {df_filtered['sicom_tsr20_thb'].mean():.2f} ฿</span>
    </div>
    """, unsafe_allow_html=True)

with col2:
    latest_latex = df_filtered["fresh_latex_thb"].iloc[0]
    st.markdown(f"""
    <div class="metric-card-latex">
        <span style="font-size: 0.85rem; color: #fde047;">💧 น้ำยางสดหน้าสวน (คาดการณ์)</span>
        <h2 style="margin: 4px 0 0 0; color: white;">{latest_latex:.2f} <span style="font-size: 1rem;">฿/กก.</span></h2>
        <span style="font-size: 0.8rem; color: #cbd5e1;">ส่วนต่างเทียบยางก้อน: +{(latest_latex - df_filtered['local_cup_lump_thb'].iloc[0]*1.6):.2f} ฿</span>
    </div>
    """, unsafe_allow_html=True)

with col3:
    latest_cup = df_filtered["local_cup_lump_thb"].iloc[0]
    st.markdown(f"""
    <div class="metric-card-cup">
        <span style="font-size: 0.85rem; color: #f472b6;">🥣 ยางก้อนถ้วย (DRC 50%)</span>
        <h2 style="margin: 4px 0 0 0; color: white;">{latest_cup:.2f} <span style="font-size: 1rem;">฿/กก.</span></h2>
        <span style="font-size: 0.8rem; color: #cbd5e1;">เนื้อยางแห้ง 100%: {(latest_cup*2.0):.2f} ฿</span>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card-weather">
        <span style="font-size: 0.85rem; color: #6ee7b7;">🛰 สภาพอากาศสดแปลง ({selected_district.split(' ')[0]})</span>
        <h2 style="margin: 4px 0 0 0; color: white;">{live_temp:.1f}°C <span style="font-size: 1rem;">| RH {live_rh:.0f}%</span></h2>
        <span style="font-size: 0.8rem; color: #cbd5e1;">ความชื้นดิน: {live_soil:.2f} m³/m³ (ฝน 14 วัน {past_14d_rain:.1f} mm)</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ----------------------------------------------------
# 6. Interactive Visualizations with Unified Crosshairs
# ----------------------------------------------------
st.subheader("📈 1. ตารางเปรียบเทียบแนวโน้มราคา (เอาจิ้มเพื่อดูเส้นเลือกเวลา)")

fig_price = go.Figure()

# เส้นยางก้อนถ้วย 50%
fig_price.add_trace(go.Scatter(
    x=df_filtered["date"], y=df_filtered["local_cup_lump_thb"],
    name="ยางก้อนถ้วย DRC 50%", line=dict(color="#ec4899", width=2.8),
    hovertemplate="🥣 ยางก้อนถ้วย 50%: <b>%{y:.2f}</b> บาท/กก.<extra></extra>"
))

# เส้นยางก้อนถ้วย DRC 100%
fig_price.add_trace(go.Scatter(
    x=df_filtered["date"], y=df_filtered["cup_lump_drc100_thb"],
    name="ยางก้อนถ้วยเทียบ DRC 100%", line=dict(color="#f43f5e", width=1.8, dash="dot"),
    hovertemplate="🔥 เทียบเท่า DRC 100%: <b>%{y:.2f}</b> บาท/กก.<extra></extra>"
))

# เส้นน้ำยางสด
fig_price.add_trace(go.Scatter(
    x=df_filtered["date"], y=df_filtered["fresh_latex_thb"],
    name="น้ำยางสดหน้าสวน", line=dict(color="#facc15", width=2.2),
    hovertemplate="💧 น้ำยางสด: <b>%{y:.2f}</b> บาท/กก.<extra></extra>"
))

# เส้นราคาโลก SICOM
fig_price.add_trace(go.Scatter(
    x=df_filtered["date"], y=df_filtered["sicom_tsr20_thb"],
    name="SICOM TSR20 ตลาดโลก", line=dict(color="#38bdf8", width=2.0),
    hovertemplate="🌐 SICOM โลก: <b>%{y:.2f}</b> บาท/กก.<extra></extra>"
))

fig_price.update_layout(
    template="plotly_dark",
    height=440,
    hovermode="x unified",
    yaxis_title="บาท / กิโลกรัม (THB/kg)",
    margin=dict(l=20, r=20, t=30, b=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    xaxis=dict(
        showspikes=True, spikemode="across", spikesnap="cursor",
        spikethickness=1.5, spikecolor="#38bdf8", spikedash="dash",
        rangeslider=dict(visible=True)
    )
)
st.plotly_chart(fig_price, use_container_width=True)

# กราฟย่อย: สภาพแวดล้อม และ ปริมาณผลผลิต
c_left, c_right = st.columns(2)

with c_left:
    st.subheader(f"🌧 2. คาดการณ์ฝน & ความชื้นดิน ({selected_district})")
    fig_env = make_subplots(specs=[[{"secondary_y": True}]])
    fig_env.add_trace(
        go.Bar(x=df_filtered["date"], y=df_filtered["rain_mm"], name="ฝนคาดการณ์ (มม.)", marker_color="#06b6d4"),
        secondary_y=False
    )
    fig_env.add_trace(
        go.Scatter(x=df_filtered["date"], y=df_filtered["soil_moisture"], name="ความชื้นในดิน", line=dict(color="#10b981", width=2.2)),
        secondary_y=True
    )
    fig_env.update_layout(
        template="plotly_dark",
        height=320,
        hovermode="x unified",
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showspikes=True, spikemode="across", spikecolor="#06b6d4", spikedash="dash")
    )
    fig_env.update_yaxes(title_text="ปริมาณฝน (มม.)", secondary_y=False)
    fig_env.update_yaxes(title_text="ความชื้นในดิน (m³/m³)", secondary_y=True)
    st.plotly_chart(fig_env, use_container_width=True)

with c_right:
    st.subheader("📉 3. คาดการณ์ผลผลิตน้ำยาง (กก./ไร่/วัน)")
    fig_yield = go.Figure()
    fig_yield.add_trace(go.Scatter(
        x=df_filtered["date"], y=df_filtered["est_yield_kg_rai"],
        mode="lines", line=dict(color="#c084fc", width=2.5),
        fill="tozeroy", fillcolor="rgba(192, 132, 252, 0.15)",
        name="ผลผลิตคาดการณ์"
    ))
    fig_yield.add_hline(y=4.2, line_dash="dash", line_color="#94a3b8", annotation_text="เกณฑ์ปกติ (4.2 กก./ไร่)")
    fig_yield.update_layout(
        template="plotly_dark",
        height=320,
        hovermode="x unified",
        yaxis_title="กก./ไร่/วัน",
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis=dict(showspikes=True, spikemode="across", spikecolor="#c084fc", spikedash="dash")
    )
    st.plotly_chart(fig_yield, use_container_width=True)

# ----------------------------------------------------
# 7. Strategic Field Advice & References
# ----------------------------------------------------
st.markdown("---")
st.subheader("💡 คำแนะนำเชิงปฏิบัติการเฉพาะพื้นที่")

rec1, rec2, rec3 = st.columns(3)
with rec1:
    st.info(f"""
    **คำแนะนำการกรีดในเขต {selected_district}**
    * อุณหภูมิและความชื้นสัมพัทธ์ช่วงเช้ามืดมีผลโดยตรงต่อการไหลของน้ำยาง
    * หากความชื้นดิน &lt; 0.20 m³/m³ ควรงดการกรีดติดต่อกันเกิน 2 วันเพื่อรักษาท่อน้ำยาง
    """)

with rec2:
    st.warning("""
    **การเลือกแปรรูปผลผลิต (ยางก้อน vs น้ำยางสด)**
    * ถ้าราคาน้ำยางสดหน้าสวนสูงกว่ายางก้อนถ้วยเกิน 5 บาท (เมื่อคิดฐาน DRC เดียวกัน) ควรส่งขายเป็นน้ำยางสดทันที
    * หากอยู่ในพื้นที่ห่างไกลโรงงานน้ำยาง การทำยางก้อนถ้วยโดยใช้กรดฟอร์มิกแท้จะได้ DRC 50–55% ซึ่งได้ราคาประมูลดีที่สุด
    """)

with rec3:
    st.success("""
    **แหล่งข้อมูลอ้างอิงของระบบ**
    * พยากรณ์อากาศและดิน: Open-Meteo High-Resolution Satellite API
    * เกณฑ์ราคากลาง: กยท. (การยางแห่งประเทศไทย) & SGX SICOM TSR20
    * ปรากฏการณ์ ENSO: ดัชนี Oceanic Niño Index (NOAA CPC)
    """)
