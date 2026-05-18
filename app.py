import streamlit as st
import pandas as pd
import io
import re
import time
from datetime import datetime
import plotly.express as px 
# from streamlit_oauth import OAuth2Component  <-- 要用 Google 登入時再把這行註解拿掉

# 🌟 1. 設定網頁標題與大版面
st.set_page_config(page_title="月報數據提取系統", layout="wide")

# ==========================================
# 🛠️ 共用資料處理函式區 (預先載入引擎)
# ==========================================
def process_data(results_list):
    if not results_list: return None
    df = pd.DataFrame(results_list)
    wheel_cols = [col for col in df.columns if any(x in col for x in ['A1', 'B1', 'A2', 'B2', 'A3', 'B3', 'A4', 'B4'])]

    if wheel_cols:
        df['本車最小輪徑'] = df[wheel_cols].min(axis=1)
        def get_clean_car_name(col_name):
            if 'DM1' in col_name: return 'DM1'
            elif 'DM2' in col_name or 'M2' in col_name: return 'M2_DM2'
            elif 'T' in col_name: return 'T'
            return col_name.split('_')[0]

        for col in wheel_cols:
            axis_name = None
            if 'A1' in col: axis_name, b_col = "軸1", col.replace('A1', 'B1')
            elif 'A2' in col: axis_name, b_col = "軸2", col.replace('A2', 'B2')
            elif 'A3' in col: axis_name, b_col = "軸3", col.replace('A3', 'B3')
            elif 'A4' in col: axis_name, b_col = "軸4", col.replace('A4', 'B4')
            if axis_name and b_col in df.columns:
                clean_car = get_clean_car_name(col)
                min_col = f"{clean_car}_{axis_name}"
                temp_min = df[[col, b_col]].min(axis=1)
                df[min_col] = df[min_col].combine_first(temp_min) if min_col in df.columns else temp_min

    if '車號' in df.columns: df = df.sort_values(by='車號', ascending=True)
    return df

def transform_to_3_rows(df):
    if df is None or df.empty: return df
    new_rows = []
    for _, row in df.iterrows():
        base = {
            "車號": row.get("車號", ""), "工單編號": row.get("工單編號", ""),
            "工項名稱": row.get("工項名稱", ""), "檢查結束日期": row.get("檢查結束日期", ""),
            "檢修里程": row.get("檢修里程", ""), "本車最小輪徑": row.get("本車最小輪徑", "")
        }
        
        dm1 = base.copy()
        dm1["車廂"], dm1["軸1"], dm1["軸2"], dm1["軸3"], dm1["軸4"], dm1[" "] = "DM1", row.get("DM1_軸1", ""), row.get("DM1_軸2", ""), row.get("DM1_軸3", ""), row.get("DM1_軸4", ""), ""
        
        t = base.copy()
        t["工單編號"] = t["工項名稱"] = t["檢查結束日期"] = t["檢修里程"] = t["本車最小輪徑"] = ""
        t["車廂"], t["軸1"], t["軸2"], t["軸3"], t["軸4"], t[" "] = "T", row.get("T_軸1", ""), row.get("T_軸2", ""), row.get("T_軸3", ""), row.get("T_軸4", ""), ""
        
        m2 = base.copy()
        m2["工單編號"] = m2["工項名稱"] = m2["檢查結束日期"] = m2["檢修里程"] = m2["本車最小輪徑"] = ""
        m2["車廂"], m2["軸1"], m2["軸2"], m2["軸3"], m2["軸4"], m2[" "] = "M2_DM2", row.get("M2_DM2_軸1", ""), row.get("M2_DM2_軸2", ""), row.get("M2_DM2_軸3", ""), row.get("M2_DM2_軸4", ""), ""

        for col in df.columns:
            if col in base.keys() or any(x in col for x in ["_軸1", "_軸2", "_軸3", "_軸4"]): continue
            if "DM1" in col: dm1[col] = row[col]
            elif "T" in col: t[col] = row[col]
            elif "M2" in col or "DM2" in col: m2[col] = row[col]
            else: dm1[col] = row[col]
            
        new_rows.extend([dm1, t, m2])
        
    new_df = pd.DataFrame(new_rows)
    front_cols = ["車號", "工單編號", "工項名稱", "檢查結束日期", "檢修里程", "車廂", "本車最小輪徑", "軸1", "軸2", "軸3", "軸4", " "]
    exist_front = [c for c in front_cols if c in new_df.columns]
    other_cols = [c for c in new_df.columns if c not in exist_front]
    return new_df[exist_front + other_cols]

def create_min_wheel_chart(df, model_name):
    df['本車最小輪徑'] = pd.to_numeric(df['本車最小輪徑'], errors='coerce')
    df_plot = df.dropna(subset=['本車最小輪徑'])
    if df_plot.empty: return None

    fig = px.bar(df_plot, x='車號', y='本車最小輪徑', title=f"{model_name} 電聯車輪徑值",
                 labels={'本車最小輪徑': '輪徑單位:mm', '車號': '車組編號'}, text_auto='.0f')
    fig.update_yaxes(range=[770, 850])
    fig.add_hline(y=788, line_dash="dash", line_color="green")
    fig.add_hline(y=782, line_dash="dash", line_color="orange")
    fig.add_hline(y=775, line_dash="dash", line_color="red")
    fig.update_layout(xaxis_type='category', xaxis_tickangle=-45)
    return fig

# ==========================================
# 🔐 畫面一：首頁暨登入畫面
# ==========================================
if "token" not in st.session_state:
    st.markdown("<h1 style='text-align: center; margin-top: 10vh;'>🚂 月報數據提取系統</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray; margin-bottom: 5vh;'>請先登入以繼續使用系統功能</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([4, 3, 4])
    with col2:
        st.info("🔒 系統需授權使用")
        
        if st.button("🚀 (開發測試) 點此模擬登入", use_container_width=True):
            st.session_state.token = "dev_mode_token"
            st.rerun()
            
    st.stop() 

# ==========================================
# 🏠 畫面二：登入後的大廳與導覽列
# ==========================================
# 頂部狀態列
status_col, logout_col = st.columns([9, 1])
with status_col:
    st.success("✅ 身分驗證成功，歡迎使用系統！")
with logout_col:
    if st.button("🚪 登出系統"):
        st.session_state.clear() 
        st.rerun()
st.divider()

# 側邊欄：功能選單
st.sidebar.header("⚙️ 系統功能導覽")
app_mode = st.sidebar.radio("請選擇作業模式", ["🏠 系統總覽 (Home)", "🔍 輪徑資料提取", "🛠️ 其他資料提取 (規劃中)"])
st.sidebar.divider()
st.sidebar.info("📌 目前上線功能：\n1. 輪徑資料提取\n2. 輪徑(各軸)最小值及佔比圖表計算")

# 🌟 新增：在側邊欄最下方加入版本資訊
st.sidebar.markdown("<br><br><br>", unsafe_allow_html=True) # 往下推一點，排版更好看
st.sidebar.caption("🔖 **系統版本：V 2.0.0**")
st.sidebar.caption("📅 **更新日期：2026/05/19**")

# ==========================================
# 🚀 畫面路由：根據使用者的選擇顯示對應功能
# ==========================================

# --- 模式 A：系統總覽大廳 ---
if app_mode == "🏠 系統總覽 (Home)":
    st.title("🏠 歡迎來到系統總覽")
    st.markdown("👈 **請從左側導覽列選擇您要執行的功能。**")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("#### 🔍 輪徑資料提取 (已上線)\n上傳行動檢修平台之 ISO 表單(EXCEL)，系統將自動為您完成輪徑提取、最小值判斷、產生圖表...等。")
    with col2:
        st.warning("#### 🛠️ 其他資料提取 (規劃中)\n未來擴充功能，將針對其他資料的表單進行客製化的資料提取。")

# --- 模式 B：修護資料提取 (開發中) ---
elif app_mode == "🛠️ 其他資料提取 (規劃中)":
    st.title("🛠️ 其他資料提取系統")
    st.info("🚧 此模組正在規劃建置中，未來將支援不同資料來源的格式，敬請期待！")

# --- 模式 C：預檢輪徑提取 (主要核心功能) ---
elif app_mode == "🔍 輪徑資料提取":
    st.title("📊 月報數據自動化提取 (預檢)")
    st.markdown("請上傳從行動檢修平台下載的 ISO 表單(Excel)，系統將自動提取、運算並產生提取總表。")
    
    uploaded_files = st.file_uploader("📂 拖曳或選擇多份 Excel 檔案", type=["xlsx"], accept_multiple_files=True)

    if "is_processed" not in st.session_state:
        st.session_state.is_processed = False

    if uploaded_files:
        if st.button("🚀 開始提取資料", use_container_width=True):
            start_time = time.time()
            with st.spinner('資料高速提取中...'):
                results_371, results_381 = [], []
                progress_bar = st.progress(0)

                for i, file in enumerate(uploaded_files):
                    if file.name.startswith("~$"): continue
                    df_raw = pd.read_excel(file, header=None, engine='calamine')
                    file_data = {"車號": None, "工單編號": None, "工項名稱": None, "檢查結束日期": None, "檢修里程": None}

                    for row_idx in range(len(df_raw)):
                        for col_idx in range(len(df_raw.columns)):
                            cell = str(df_raw.iloc[row_idx, col_idx]).strip()
                            if cell == "工單編號": file_data["工單編號"] = df_raw.iloc[row_idx, col_idx + 1]
                            elif cell == "車號/最小成本單位": file_data["車號"] = str(df_raw.iloc[row_idx, col_idx + 1]).strip()
                            elif cell == "工項名稱": 
                                raw_name = str(df_raw.iloc[row_idx, col_idx + 1])
                                match = re.search(r'_([^_]+\([^)]+\))', raw_name)
                                file_data["工項名稱"] = match.group(1) if match else raw_name
                            elif cell == "檢查結束日期":
                                raw_date = df_raw.iloc[row_idx, col_idx + 1]
                                try: file_data["檢查結束日期"] = pd.to_datetime(raw_date).strftime("%m/%d")
                                except: file_data["檢查結束日期"] = raw_date
                                
                            elif "里程" in cell:
                                val = df_raw.iloc[row_idx, col_idx + 1]
                                if (pd.isna(val) or str(val).strip() == "") and col_idx + 2 < len(df_raw.columns):
                                    val = df_raw.iloc[row_idx, col_idx + 2]
                                try:
                                    clean_val = re.sub(r'[^\d]', '', str(val))
                                    if clean_val: file_data["檢修里程"] = int(clean_val)
                                except: file_data["檢修里程"] = val

                    df_table = pd.read_excel(file, header=2, engine='calamine')
                    check_cols = [c for c in df_table.columns if '檢查結果' in str(c)]
                    if check_cols:
                        target_rows = df_table[df_table['進階分類'].str.contains(r'車輪組-[Cc]|斷電[Cc]|頂昇斷電[Dd]|車下-[Cc]|頂昇斷電[Aa]|車下-[Bb]', regex=True, na=False) & 
                                               df_table['檢查項目'].str.contains(r'車輪直徑|車輪輪徑', regex=True, na=False)]
                        for _, row in target_rows.iterrows():
                            try:
                                val = float(row[check_cols[0]])
                                if pd.notna(val): file_data[f"{row['進階分類']}_{row['檢查項目']}"] = val
                            except: pass

                    if '371' in file.name: results_371.append(file_data)
                    elif '381' in file.name: results_381.append(file_data)
                    progress_bar.progress((i + 1) / len(uploaded_files))

                st.session_state.df_371 = process_data(results_371)
                st.session_state.df_381 = process_data(results_381)
                st.session_state.time_msg = f"✅ 成功處理 {len(uploaded_files)} 份檔案，共耗時 {time.time() - start_time:.1f} 秒！"
                st.session_state.is_processed = True
                st.rerun()

    if st.session_state.get("is_processed"):
        st.success(st.session_state.time_msg)
        
        tab1, tab2 = st.tabs(["🚆 371型 提取結果", "🚆 381型 提取結果"])
        
        def render_result_tab(raw_df, model_name):
            if raw_df is not None and not raw_df.empty:
                raw_df['本車最小輪徑'] = pd.to_numeric(raw_df['本車最小輪徑'], errors='coerce')
                valid_df = raw_df.dropna(subset=['本車最小輪徑'])
                total_cars = len(valid_df)
                
                if total_cars > 0:
                    green = len(valid_df[valid_df['本車最小輪徑'] >= 788])
                    yellow = len(valid_df[(valid_df['本車最小輪徑'] >= 782) & (valid_df['本車最小輪徑'] < 788)])
                    red = len(valid_df[valid_df['本車最小輪徑'] < 782])
                    
                    col_chart, col_stats = st.columns([7, 3])
                    with col_chart:
                        fig = create_min_wheel_chart(raw_df, model_name)
                        st.plotly_chart(fig, use_container_width=True)
                    with col_stats:
                        st.markdown("<br><br>", unsafe_allow_html=True)
                        st.markdown(f"### 🚥 磨耗等級佔比")
                        st.markdown(f"**🟢 綠燈 (788~850mm):** {green}台 ({green/total_cars*100:.1f}%)")
                        st.markdown(f"**🟡 黃燈 (782~787mm):** {yellow}台 ({yellow/total_cars*100:.1f}%)")
                        st.markdown(f"**🔴 紅燈 (775~781mm):** {red}台 ({red/total_cars*100:.1f}%)")
                        if red > 0: st.error(f"⚠️ 注意：有 {red} 台車低於紅燈下限！")
                
                st.divider()
                ui_df = transform_to_3_rows(raw_df)
                st.subheader(f"📋 {model_name} 提取表")
                st.dataframe(ui_df)
                
                buf = io.BytesIO()
                ui_df.to_excel(buf, index=False)
                st.download_button(
                    label=f"📥 下載 {model_name} 提取表 (Excel)",
                    data=buf.getvalue(),
                    file_name=f"{model_name}_提取表_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.ms-excel"
                )
            else:
                st.info(f"本次上傳未包含 {model_name} 的資料。")

        with tab1: render_result_tab(st.session_state.get("df_371"), "371型")
        with tab2: render_result_tab(st.session_state.get("df_381"), "381型")