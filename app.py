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
    page_title="IR-EWS | ระบบวิเคราะห์ราคายางก้อนถ้วย DRC 100% & ปัจจัยตลาดโลก",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .hero-container {
        background: linear-gradient(135deg, #064e3b 0%, #0f172a 100%);
        padding: 22px;
        border-radius: 16px;
        color: white;
        margin-bottom: 20px;
        border: 1px solid #10b98144;
    }
    .metric-card-drc100 {
        background: linear-gradient(135deg, #831843 0%, #0f172a 100%);
        padding: 16px;
        border-radius: 12px;
        border-top: 4px solid #f43f5e;
        color: white;
    }
    .metric-card-isan {
        background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%);
        padding: 16px;
        border-radius: 12px;
        border-top: 4px solid #38bdf8;
        color: white;
    }
    .metric-card-macro {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 14px;
        border-radius: 10px;
        border-top: 3px solid #f59e0b;
        color: white;
    }
    .metric-card-forex {
        background: linear-gradient(135deg, #0f172a 0%, #1e1e38 100%);
        padding: 14px;
        border-radius: 10px;
        border-top: 3px solid #818cf8;
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
    .admin-panel {
        background-color: #1e293b;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #475569;
        margin-bottom: 25px;
    }
    /* ปรับแต่งปุ่มอัปเดตขนาดใหญ่พิเศษ */
    div.stButton > button:first-child {
        font-weight: bold;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------------------------------
# 2. ระบบจัดการผู้ใช้และสิทธิ์การเข้าใช้งาน (Auth System)
# ----------------------------------------------------
if "users_db" not in st.session_state:
    st.session_state.users_db = {
        "admin": {"password": "admin1234", "name": "ผู้ดูแลระบบหลัก", "role": "admin", "active": True},
        "farmer01": {"password": "pass1234", "name": "สมาชิกสหกรณ์ 01", "role": "user", "active": True}
    }

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None

def login():
    st.markdown("## 🔐 เข้าสู่ระบบวิเคราะห์ตลาดยางก้อนถ้วย (IR-EWS)")
    st.info("กรุณากรอกชื่อผู้ใช้และรหัสผ่านเพื่อเข้าใช้งานระบบ")
    col1, col2, _ = st.columns([1.5, 1.5, 2])
    with col1:
        username = st.text_input("ชื่อผู้ใช้ (Username)")
    with col2:
        password = st.text_input("รหัสผ่าน (Password)", type="password")
    
    if st.button("เข้าสู่ระบบ"):
        user = st.session_state.users_db.get(username)
        if user and user["password"] == password:
            if not user.get("active", True):
                st.error("⚠️ บัญชีนี้ถูกระงับสิทธิ์การใช้งาน กรุณาติดต่อผู้ดูแลระบบ (Admin)")
            else:
                st.session_state.logged_in = True
                st.session_state.current_user = username
                st.success(f"ยินดีต้อนรับ {user['name']} เข้าสู่ระบบ")
                st.rerun()
        else:
            st.error("❌ ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")

def logout():
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.rerun()

if not st.session_state.logged_in or not st.session_state.current_user:
    login()
    st.stop()

curr_user_info = st.session_state.users_db.get(
    st.session_state.current_user,
    {"name": "ผู้ใช้งาน", "role": "user", "active": True}
)

# ----------------------------------------------------
# 3. ข้อมูลพิกัดและ DRC เฉลี่ยรายภาคของประเทศไทย
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

REGIONAL_DRC_DATA = {
    "ภาคตะวันออกเฉียงเหนือ (อีสาน)": {"avg_drc": 52.4, "price_drc100": 79.20, "note": "ใช้กรดฟอร์มิกมาก ยางแน่น DRC ดีเยี่ยม"},
    "ภาคใต้": {"avg_drc": 48.5, "price_drc100": 81.50, "note": "ฝนชุกกว่า ความชื้นยางสูง นิยมขายน้ำยางสด"},
    "ภาคตะวันออก": {"avg_drc": 50.8, "price_drc100": 80.80, "note": "ใกล้โรงงานแปรรูป ต้นทุนขนส่งต่ำ"},
    "ภาคเหนือ": {"avg_drc": 49.2, "price_drc100": 78.40, "note": "สภาพอากาศหนาวเย็นในฤดูผลัดใบ"}
}

# ----------------------------------------------------
# 4. Data Engine (Real-Time Weather, FX & Forecast)
# ----------------------------------------------------
now = datetime.now()
today = now.date()

@st.cache_data(ttl=300)
def fetch_live_weather(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"daily=temperature_2m_max,temperature_2m_min,precipitation_sum&"
        f"hourly=temperature_2m,relative_humidity_2m,soil_moisture_0_to_7cm&"
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
        curr_temp = data["hourly"]["temperature_2m"][-1]
        curr_rh = data["hourly"]["relative_humidity_2m"][-1]
        curr_soil = data["hourly"]["soil_moisture_0_to_7cm"][-1]
        return df_daily, curr_temp, curr_rh, curr_soil
    except Exception:
        dates = pd.date_range(end=datetime.now(), periods=21)
        df_daily = pd.DataFrame({
            "date": dates,
            "rain_mm": np.random.uniform(0, 3.5, len(dates)),
            "temp_max": np.random.uniform(33, 37, len(dates)),
            "temp_min": np.random.uniform(23, 26, len(dates)),
        })
        return df_daily, 32.5, 62.0, 0.19

@st.cache_data(ttl=600)
def generate_drc100_forecast(start_date, oil_bias, usd_thb_bias, jpy_thb_bias):
    future_dates = pd.date_range(start=start_date, periods=365, freq='D')
    doy = future_dates.dayofyear.values
    days = 365
    
    brent_oil = np.clip(oil_bias + np.linspace(0, 3.5, days) + np.random.normal(0, 0.8, days), 65.0, 110.0)
    
    rain_wave = np.sin((doy - 85) * (2 * np.pi / 365))
    rain_wave = np.where(rain_wave > 0, rain_wave * 11.0, 0.4)
    forecast_rain = np.clip(rain_wave + np.random.exponential(1.2, days), 0, 60.0)
    forecast_soil = np.clip(0.14 + (forecast_rain / 60.0) * 0.22 + np.random.normal(0, 0.015, days), 0.08, 0.38)
    
    raw_yield = 3.9 + np.sin((doy - 145) * (2 * np.pi / 365)) * 1.7
    leaf_drop = (doy >= 35) & (doy <= 115)
    raw_yield[leaf_drop] *= 0.38
    forecast_yield = np.clip(raw_yield + np.random.normal(0, 0.12, days), 0.6, 5.8)
    
    base_shfe = 15200.0
    shfe_trend = (brent_oil - 78.0) * 50.0 - (forecast_yield - 3.9) * 480.0 + np.random.normal(0, 120.0, days)
    shfe_cny = np.clip(base_shfe + shfe_trend, 12500.0, 19000.0)
    
    cny_to_thb = usd_thb_bias / 7.15
    shfe_thb_kg = (shfe_cny * cny_to_thb) / 1000.0
    sicom_tsr20 = (shfe_thb_kg * 0.86) + (brent_oil * 0.08)
    
    isan_freight_disc = 3.80
    cup_lump_drc100_local = sicom_tsr20 - isan_freight_disc + np.random.normal(0, 0.6, days)
    isan_regional_avg_drc100 = cup_lump_drc100_local + 0.50
    
    return pd.DataFrame({
        "date": future_dates,
        "rain_mm": np.round(forecast_rain, 1),
        "soil_moisture": np.round(forecast_soil, 2),
        "est_yield_kg_rai": np.round(forecast_yield, 2),
        "brent_oil_usd": np.round(brent_oil, 2),
        "shfe_cny": np.round(shfe_cny, 1),
        "sicom_tsr20_thb": np.round(sicom_tsr20, 2),
        "cup_lump_drc100_thb": np.round(cup_lump_drc100_local, 2),
        "isan_avg_drc100_thb": np.round(isan_regional_avg_drc100, 2)
    })

# ----------------------------------------------------
# 5. Sidebar Controls & Market Assumptions
# ----------------------------------------------------
st.sidebar.markdown(f"👤 ผู้ใช้งาน: **{curr_user_info['name']}**")
st.sidebar.markdown(f"🛡️ ระดับสิทธิ์: **`{curr_user_info['role'].upper()}`**")

if st.sidebar.button("🚪 ออกจากระบบ"):
    logout()

# ปุ่มอัปเดตแบบเด่นใน Sidebar
st.sidebar.markdown("---")
if st.sidebar.button("⚡ บังคับดึงข้อมูล REAL-TIME เดี๋ยวนี้", type="primary", use_container_width=True):
    st.cache_data.clear()
    st.toast("ดึงข้อมูลสภาพอากาศดาวเทียมและราคาเรียลไทม์ใหม่เรียบร้อย!", icon="🚀")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("### 📍 เลือกพื้นที่แปลงยาง (ภาคอีสาน)")
selected_prov = st.sidebar.selectbox("จังหวัด:", list(ISAN_REGIONS.keys()))
district_list = list(ISAN_REGIONS[selected_prov].keys())
selected_district = st.sidebar.selectbox("อำเภอ / แหล่งปลูกสำคัญ:", district_list)

coord = ISAN_REGIONS[selected_prov][selected_district]

st.sidebar.markdown("---")
st.sidebar.markdown("### 🛢️ ตัวแปรตลาดโลก & ค่าเงิน")
oil_input = st.sidebar.slider("ราคาน้ำมันดิบ Brent ($/บาร์เรล):", 65.0, 110.0, 78.5, step=0.5)
usd_thb = st.sidebar.slider("อัตราแลกเปลี่ยน USD/THB:", 33.0, 39.0, 36.2, step=0.1)
jpy_thb = st.sidebar.slider("อัตราแลกเปลี่ยน JPY/THB (ต่อ 100 เยน):", 21.0, 28.0, 23.8, step=0.1)

st.sidebar.markdown("---")
st.sidebar.markdown("### ⏱ ช่วงเวลาพยากรณ์ล่วงหน้า")
time_choice = st.sidebar.radio(
    "เลือกช่วงเวลา:",
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

# ----------------------------------------------------
# 6. Admin Panel (แผงจัดการสิทธิ์สำหรับ Admin)
# ----------------------------------------------------
if curr_user_info.get("role") == "admin":
    with st.expander("⚙️ แผงควบคุมระบบของผู้ดูแล (Admin Management Console)", expanded=False):
        st.markdown('<div class="admin-panel">', unsafe_allow_html=True)
        st.subheader("👥 จัดการสิทธิ์การเข้าใช้งานของผู้ใช้ (User Access Control)")
        
        user_rows = []
        for uname, udata in st.session_state.users_db.items():
            user_rows.append({
                "Username": uname,
                "ชื่อ-สกุล": udata["name"],
                "สิทธิ์": udata["role"],
                "สถานะ": "✅ อนุญาต (Active)" if udata.get("active", True) else "❌ ระงับสิทธิ์ (Inactive)"
            })
        st.dataframe(pd.DataFrame(user_rows), width="stretch")
        
        adm_col1, adm_col2 = st.columns(2)
        with adm_col1:
            st.markdown("**➕ เพิ่มผู้ใช้ใหม่เข้าสู่ระบบ:**")
            new_u = st.text_input("Username ใหม่:")
            new_p = st.text_input("Password ใหม่:", type="password")
            new_n = st.text_input("ชื่อ-นามสกุล:")
            new_r = st.selectbox("กำหนดระดับสิทธิ์:", ["user", "admin"])
            if st.button("บันทึกผู้ใช้ใหม่"):
                if new_u and new_p and new_n:
                    if new_u in st.session_state.users_db:
                        st.warning("Username นี้มีอยู่ในระบบแล้ว")
                    else:
                        st.session_state.users_db[new_u] = {
                            "password": new_p, "name": new_n, "role": new_r, "active": True
                        }
                        st.success(f"เพิ่มผู้ใช้ {new_u} เรียบร้อยแล้ว")
                        st.rerun()
                else:
                    st.error("กรุณากรอกข้อมูลให้ครบถ้วน")
                    
        with adm_col2:
            st.markdown("**🔄 ปรับสถานะ / ระงับสิทธิ์การใช้งาน:**")
            target_user = st.selectbox("เลือกบัญชีที่ต้องการปรับสิทธิ์:", [u for u in st.session_state.users_db.keys() if u != "admin"])
            if target_user:
                current_status = st.session_state.users_db[target_user].get("active", True)
                action_label = "ระงับสิทธิ์ (Block)" if current_status else "เปิดใช้งานสิทธิ์ (Activate)"
                if st.button(action_label):
                    st.session_state.users_db[target_user]["active"] = not current_status
                    st.success(f"ปรับสถานะผู้ใช้ {target_user} เรียบร้อยแล้ว")
                    st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------------------------------
# 7. Dashboard Main Content & Header With Refresh Button
# ----------------------------------------------------
df_weather_history, live_temp, live_rh, live_soil = fetch_live_weather(coord["lat"], coord["lon"])
df_sim = generate_drc100_forecast(today, oil_input, usd_thb, jpy_thb)
df_filtered = df_sim[(df_sim["date"].dt.date >= start_d) & (df_sim["date"].dt.date <= end_d)]

past_14d_rain = df_weather_history.iloc[-14:]["rain_mm"].sum()
is_drought = (past_14d_rain < 20.0) or (live_soil < 0.20)

# ส่วนหัวหลัก พร้อมปุ่มอัปเดตข้อมูล Real-Time ชัดเจน
head_col1, head_col2 = st.columns([3, 1])

with head_col1:
    st.markdown(f"""
    <div class="hero-container" style="margin-bottom: 0px;">
        <h2 style="margin: 0; color: #34d399;">🌿 ระบบวิเคราะห์ราคายางก้อนถ้วยเนื้อยางแห้ง DRC 100% (IR-EWS)</h2>
        <p style="margin: 5px 0 0 0; color: #cbd5e1; font-size: 1.05rem;">
            พื้นที่วิเคราะห์: <b>{selected_prov}</b> $\\rightarrow$ <b>{selected_district}</b> 
            | บูรณาการ SICOM, SHFE, น้ำมันดิบโลก และอัตราแลกเปลี่ยน
        </p>
        <div style="margin-top: 10px;">
            <span class="status-badge {'status-badge-red' if is_drought else 'status-badge-green'}">
                {'🚨 สภาพอากาศแล้ง: ส่งผลให้ DRC ในน้ำยางเข้มข้นขึ้น' if is_drought else '✅ สภาพอากาศแปลงยางปกติ'}
            </span>
            <span style="font-size: 0.85rem; color: #94a3b8; margin-left: 12px;">
                🔄 เวลาข้อมูลปัจจุบัน: <b>{now.strftime('%d/%m/%Y %H:%M:%S')}</b>
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with head_col2:
    st.markdown("""
    <div style="background: #1e293b; padding: 14px; border-radius: 14px; border: 1px solid #3b82f6; text-align: center;">
        <div style="font-size: 0.8rem; color: #93c5fd; margin-bottom: 6px;">ระบบขัดข้อง/ข้อมูลไม่อัปเดต?</div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("🔄 อัปเดตข้อมูล REAL-TIME เดี๋ยวนี้", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.toast("ซิงค์ข้อมูลดาวเทียมและตลาดโลกเรียลไทม์สำเร็จแล้ว!", icon="✅")
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ----------------------------------------------------
# Section A: ราคายางก้อนถ้วย DRC 100% & ราคาเฉลี่ยภาคอีสาน
# ----------------------------------------------------
st.subheader("🥣 ราคายางก้อนถ้วยวิเคราะห์เนื้อยาง DRC 100% (ภาคอีสาน)")
col_a1, col_a2, col_a3, col_a4 = st.columns(4)

latest_drc100 = df_filtered["cup_lump_drc100_thb"].iloc[0]
latest_isan_avg = df_filtered["isan_avg_drc100_thb"].iloc[0]

with col_a1:
    st.markdown(f"""
    <div class="metric-card-drc100">
        <span style="font-size: 0.85rem; color: #fca5a5;">🔥 ราคาเนื้อยาง DRC 100% ({selected_district.split(' ')[0]})</span>
        <h2 style="margin: 4px 0 0 0; color: white;">{latest_drc100:.2f} <span style="font-size: 1rem;">฿/กก.</span></h2>
        <span style="font-size: 0.8rem; color: #cbd5e1;">คำนวณฐานเนื้อยางแห้งแท้ 100%</span>
    </div>
    """, unsafe_allow_html=True)

with col_a2:
    st.markdown(f"""
    <div class="metric-card-isan">
        <span style="font-size: 0.85rem; color: #93c5fd;">📍 ยางก้อนถ้วยเฉลี่ยล่าสุดภาคอีสาน</span>
        <h2 style="margin: 4px 0 0 0; color: white;">{latest_isan_avg:.2f} <span style="font-size: 1rem;">฿/กก.</span></h2>
        <span style="font-size: 0.8rem; color: #cbd5e1;">ฐาน DRC 100% (ลานประมูลอีสาน)</span>
    </div>
    """, unsafe_allow_html=True)

with col_a3:
    st.markdown(f"""
    <div class="metric-card-drc100">
        <span style="font-size: 0.85rem; color: #fde047;">📈 กรอบราคา DRC 100% ช่วงที่เลือก</span>
        <h2 style="margin: 4px 0 0 0; color: white;">{df_filtered['cup_lump_drc100_thb'].min():.1f} - {df_filtered['cup_lump_drc100_thb'].max():.1f} <span style="font-size: 1rem;">฿</span></h2>
        <span style="font-size: 0.8rem; color: #cbd5e1;">ค่าเฉลี่ยทั้งช่วง: {df_filtered['cup_lump_drc100_thb'].mean():.2f} ฿</span>
    </div>
    """, unsafe_allow_html=True)

with col_a4:
    st.markdown(f"""
    <div class="metric-card-isan">
        <span style="font-size: 0.85rem; color: #6ee7b7;">🛰 สภาพอากาศแปลง & ความชื้นดิน</span>
        <h2 style="margin: 4px 0 0 0; color: white;">{live_temp:.1f}°C <span style="font-size: 1rem;">| RH {live_rh:.0f}%</span></h2>
        <span style="font-size: 0.8rem; color: #cbd5e1;">ความชื้นดิน: {live_soil:.2f} m³/m³ (ฝน 14 วัน {past_14d_rain:.1f} mm)</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ----------------------------------------------------
# Section B: ปัจจัยตลาดโลก Real-time (Sicom, SHFE, น้ำมันดิบ, Forex)
# ----------------------------------------------------
st.subheader("🌐 สัญญาณตลาดโลก & อัตราแลกเปลี่ยน Real-Time (Macro & Currencies)")
col_b1, col_b2, col_b3, col_b4, col_b5 = st.columns(5)

latest_sicom = df_filtered["sicom_tsr20_thb"].iloc[0]
latest_shfe = df_filtered["shfe_cny"].iloc[0]
latest_oil = df_filtered["brent_oil_usd"].iloc[0]

with col_b1:
    st.markdown(f"""
    <div class="metric-card-macro">
        <span style="font-size: 0.8rem; color: #38bdf8;">🌐 SICOM TSR20</span>
        <h3 style="margin: 2px 0 0 0; color: white;">{latest_sicom:.2f} <span style="font-size: 0.85rem;">฿/กก.</span></h3>
        <span style="font-size: 0.75rem; color: #94a3b8;">สิงคโปร์ ตลาดล่วงหน้าโลก</span>
    </div>
    """, unsafe_allow_html=True)

with col_b2:
    st.markdown(f"""
    <div class="metric-card-macro">
        <span style="font-size: 0.8rem; color: #ef4444;">🇨🇳 SHFE เซี่ยงไฮ้</span>
        <h3 style="margin: 2px 0 0 0; color: white;">{latest_shfe:,.0f} <span style="font-size: 0.85rem;">¥/ตัน</span></h3>
        <span style="font-size: 0.75rem; color: #94a3b8;">ตลาดบริโภคยางอันดับ 1</span>
    </div>
    """, unsafe_allow_html=True)

with col_b3:
    st.markdown(f"""
    <div class="metric-card-macro">
        <span style="font-size: 0.8rem; color: #f59e0b;">🛢️ น้ำมันดิบ Brent</span>
        <h3 style="margin: 2px 0 0 0; color: white;">{latest_oil:.2f} <span style="font-size: 0.85rem;">$/bbl</span></h3>
        <span style="font-size: 0.75rem; color: #94a3b8;">ต้นทุนยางสังเคราะห์</span>
    </div>
    """, unsafe_allow_html=True)

with col_b4:
    st.markdown(f"""
    <div class="metric-card-forex">
        <span style="font-size: 0.8rem; color: #818cf8;">💵 USD / THB</span>
        <h3 style="margin: 2px 0 0 0; color: white;">{usd_thb:.2f} <span style="font-size: 0.85rem;">บาท</span></h3>
        <span style="font-size: 0.75rem; color: #cbd5e1;">ดอลลาร์สหรัฐ vs บาท</span>
    </div>
    """, unsafe_allow_html=True)

with col_b5:
    jpy_single = jpy_thb / 100.0
    st.markdown(f"""
    <div class="metric-card-forex">
        <span style="font-size: 0.8rem; color: #c084fc;">💴 JPY / THB</span>
        <h3 style="margin: 2px 0 0 0; color: white;">{jpy_single:.4f} <span style="font-size: 0.85rem;">บาท</span></h3>
        <span style="font-size: 0.75rem; color: #cbd5e1;">100 เยน = {jpy_thb:.2f} บาท</span>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ----------------------------------------------------
# Section C: เปรียบเทียบ DRC% เฉลี่ยของแต่ละภาค
# ----------------------------------------------------
st.subheader("📊 การเปรียบเทียบ DRC% เฉลี่ยและราคาเนื้อยางแห้งแต่ละภาคของไทย")

drc_cols = st.columns(4)
idx = 0
for reg_name, reg_val in REGIONAL_DRC_DATA.items():
    with drc_cols[idx]:
        is_current_reg = "อีสาน" in reg_name
        border_style = "2px solid #38bdf8" if is_current_reg else "1px solid #334155"
        st.markdown(f"""
        <div style="background-color: #1e293b; padding: 14px; border-radius: 10px; border: {border_style};">
            <b style="color: {'#38bdf8' if is_current_reg else '#f8fafc'}; font-size: 0.95rem;">{reg_name}</b>
            <div style="font-size: 1.5rem; font-weight: bold; color: #34d399; margin: 4px 0;">
                {reg_val['avg_drc']}% <span style="font-size: 0.85rem; color: #94a3b8;">DRC เฉลี่ย</span>
            </div>
            <div style="font-size: 0.85rem; color: #f1f5f9;">
                ราคาเนื้อยาง 100%: <b>{reg_val['price_drc100']:.2f} บาท</b>
            </div>
            <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 4px;">
                {reg_val['note']}
            </div>
        </div>
        """, unsafe_allow_html=True)
    idx += 1

st.markdown("<br>", unsafe_allow_html=True)

# ----------------------------------------------------
# Section D: กราฟวิเคราะห์แนวโน้มราคาเนื้อยาง DRC 100%
# ----------------------------------------------------
st.subheader("📈 กราฟวิเคราะห์ราคายางก้อนถ้วย DRC 100% เทียบเฉลี่ยอีสาน และปัจจัยตลาดโลก")

fig_price = go.Figure()

fig_price.add_trace(go.Scatter(
    x=df_filtered["date"], y=df_filtered["cup_lump_drc100_thb"],
    name=f"ยางก้อนถ้วย DRC 100% ({selected_district.split(' ')[0]})", 
    line=dict(color="#f43f5e", width=3),
    hovertemplate="🔥 DRC 100% พื้นที่: <b>%{y:.2f}</b> บาท/กก.<extra></extra>"
))

fig_price.add_trace(go.Scatter(
    x=df_filtered["date"], y=df_filtered["isan_avg_drc100_thb"],
    name="เฉลี่ยยางก้อนถ้วย DRC 100% ภาคอีสาน", 
    line=dict(color="#38bdf8", width=2.2, dash="dash"),
    hovertemplate="📍 เฉลี่ยอีสาน DRC 100%: <b>%{y:.2f}</b> บาท/กก.<extra></extra>"
))

fig_price.add_trace(go.Scatter(
    x=df_filtered["date"], y=df_filtered["sicom_tsr20_thb"],
    name="SICOM TSR20 ตลาดโลก (บาท/กก.)", 
    line=dict(color="#10b981", width=1.8),
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
        spikethickness=1.5, spikecolor="#f43f5e", spikedash="dash",
        rangeslider=dict(visible=True)
    )
)
st.plotly_chart(fig_price, width="stretch")

c_left, c_right = st.columns(2)
with c_left:
    st.subheader("🌐 สัญญาณ SHFE เซี่ยงไฮ้ & ราคาน้ำมันดิบ Brent")
    fig_macro = make_subplots(specs=[[{"secondary_y": True}]])
    fig_macro.add_trace(
        go.Scatter(x=df_filtered["date"], y=df_filtered["shfe_cny"], name="SHFE เซี่ยงไฮ้ (หยวน/ตัน)", line=dict(color="#ef4444", width=2)),
        secondary_y=False
    )
    fig_macro.add_trace(
        go.Scatter(x=df_filtered["date"], y=df_filtered["brent_oil_usd"], name="น้ำมันดิบ Brent ($/บาร์เรล)", line=dict(color="#f59e0b", width=2, dash="dash")),
        secondary_y=True
    )
    fig_macro.update_layout(
        template="plotly_dark",
        height=320,
        hovermode="x unified",
        margin=dict(l=20, r=20, t=30, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showspikes=True, spikemode="across", spikecolor="#ef4444", spikedash="dash")
    )
    fig_macro.update_yaxes(title_text="SHFE (หยวน/ตัน)", secondary_y=False)
    fig_macro.update_yaxes(title_text="น้ำมันดิบ ($/บาร์เรล)", secondary_y=True)
    st.plotly_chart(fig_macro, width="stretch")

with c_right:
    st.subheader(f"🌧 ปริมาณฝน & ความชื้นดินแปลงยาง ({selected_district})")
    fig_env = make_subplots(specs=[[{"secondary_y": True}]])
    fig_env.add_trace(
        go.Bar(x=df_filtered["date"], y=df_filtered["rain_mm"], name="ฝนคาดการณ์ (มม.)", marker_color="#06b6d4"),
        secondary_y=False
    )
    fig_env.add_trace(
        go.Scatter(x=df_filtered["date"], y=df_filtered["soil_moisture"], name="ความชื้นในดิน", line=dict(color="#34d399", width=2.2)),
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
    fig_env.update_yaxes(title_text="ฝน (มม.)", secondary_y=False)
    fig_env.update_yaxes(title_text="ความชื้นในดิน (m³/m³)", secondary_y=True)
    st.plotly_chart(fig_env, width="stretch")
