import streamlit as st
# from streamlit_oauth import OAuth2Component  <-- 加上 # 暫時停用
import pandas as pd
import io
import re
from datetime import datetime
import plotly.express as px # 🌟 新增：繪圖套件

# 🌟 1. 設定網頁標題與大版面
st.set_page_config(page_title="月報數據自動化提取", layout="wide")

# ==========================================
# 🔐 企業級 Google SSO 登入系統 (在 Colab 測試時暫時關閉)
# ==========================================
# CLIENT_ID = st.secrets["google_oauth"]["client_id"]
# CLIENT_SECRET = st.secrets["google_oauth"]["client_secret"]
# REDIRECT_URI = st.secrets["google_oauth"]["redirect_uri"]
# AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
# TOKEN_URL = "https://oauth2.googleapis.com/token"
# REVOKE_TOKEN_URL = "https://oauth2.googleapis.com/revoke"

# oauth2 = OAuth2Component(CLIENT_ID, CLIENT_SECRET, AUTHORIZE_URL, TOKEN_URL, REVOKE_TOKEN_URL)

# if "token" not in st.session_state:
#     st.title("🚂 月報數據自動化提取")
#     st.warning("🔒 本系統需授權使用(請洽開發者)，請使用已授權的 Google 帳號登入。")
#     result = oauth2.authorize_button("使用 Google 帳號登入", "https://www.google.com.tw/favicon.ico", REDIRECT_URI, "openid email profile")
#     if result and "token" in result:
#         st.session_state.token = result.get("token")
#         st.rerun()
#     st.stop()

# status_col, logout_col = st.columns([8, 2])
# with status_col:
#     st.success("✅ 身分驗證成功，歡迎使用系統！")
# with logout_col:
#     if st.button("🚪 登出系統"):
#         del st.session_state.token
#         st.rerun()
# st.divider()

# 🌟 主頁面標題
st.title("📊 月報數據自動化提取")
st.markdown("請上傳從行動檢修平台下載的 Excel 原始表單，系統將自動提取、運算並產生提取總表。")

# 🌟 側邊欄資訊
st.sidebar.header("⚙️ 系統資訊")
st.sidebar.info("功能：輪徑資料提取、輪徑最小值計算(含圖表產出)、單軸輪徑比較")

# 🌟 檔案上傳區
uploaded_files = st.file_uploader("📂 拖曳或選擇多份 Excel 檔案", type=["xlsx"], accept_multiple_files=True)

# --- 資料處理引擎 ---
def process_data(results_list):
    if not results_list:
        return None

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

    if '車號' in df.columns:
        df = df.sort_values(by='車號', ascending=True)

    base_cols = ["車號", "工單編號", "工項名稱", "檢查結束日期"]
    exist_base_cols = [c for c in base_cols if c in df.columns]
    dynamic_cols = [c for c in df.columns if c not in exist_base_cols]

    def custom_sort_logic(col_name):
        if '最小輪徑' in col_name: return (0, 0, 0, 0, col_name)
        block_weight = 1 if '軸' in col_name else 2
        car_weight = 1 if 'DM1' in col_name else 2 if 'T' in col_name else 3 if any(x in col_name for x in ['M2', 'DM2']) else 50
        item_weight = int(re.search(r'\d', col_name[-2:]).group()) if re.search(r'\d', col_name[-2:]) else 50
        ab_weight = 1 if 'B' in col_name else 0
        return (block_weight, car_weight, item_weight, ab_weight, col_name)

    sorted_dynamic_cols = sorted(dynamic_cols, key=custom_sort_logic)
    return df[exist_base_cols + sorted_dynamic_cols]


# --- 🌟 新增：生成最小輪徑互動長條圖 Function ---
def create_min_wheel_chart(df, model_name):
    if df is None or '車號' not in df.columns or '本車最小輪徑' not in df.columns:
        return None

    # 確保資料為數值並過濾掉空值
    df['本車最小輪徑'] = pd.to_numeric(df['本車最小輪徑'], errors='coerce')
    df_plot = df.dropna(subset=['本車最小輪徑'])

    if df_plot.empty:
        return None

    # 建立長條圖
    fig = px.bar(df_plot, 
                 x='車號', 
                 y='本車最小輪徑', 
                 title=f"{model_name} 電聯車輪徑值",
                 labels={'本車最小輪徑': '輪徑單位:mm', '車號': '車組編號'},
                 text_auto='.1f')

    # 設定 Y 軸範圍 (770~850)
    fig.update_yaxes(range=[770, 850])

    # 新增三條對照標準線 (對齊你的報告截圖標準)
    fig.add_hline(y=788, line_dash="dash", line_color="green", annotation_text="綠燈等級 (788mm)", annotation_position="top left")
    fig.add_hline(y=782, line_dash="dash", line_color="orange", annotation_text="黃燈等級 (782mm)", annotation_position="top left")
    fig.add_hline(y=775, line_dash="dash", line_color="red", annotation_text="紅燈等級 (775mm)", annotation_position="top left")

    # 優化 X 軸顯示
    fig.update_layout(xaxis_type='category', xaxis_tickangle=-45)

    return fig


# --- 執行邏輯 ---
if uploaded_files:
    if st.button("🚀 開始提取資料"):
        with st.spinner('資料提取中...'):
            results_371, results_381 = [], []
            progress_bar = st.progress(0)

            for i, file in enumerate(uploaded_files):
                if file.name.startswith("~$"): continue
                
                # 讀取 Excel
                df_raw = pd.read_excel(file, header=None, engine='calamine')
                file_data = {"車號": None, "工單編號": None, "工項名稱": None, "檢查結束日期": None}

                # 提取表頭資訊
                for row_idx in range(len(df_raw)):
                    for col_idx in range(len(df_raw.columns)):
                        cell = str(df_raw.iloc[row_idx, col_idx]).strip()
                        if cell == "工單編號": file_data["工單編號"] = df_raw.iloc[row_idx, col_idx + 1]
                        elif cell == "車號/最小成本單位": file_data["車號"] = str(df_raw.iloc[row_idx, col_idx + 1]).strip()
                        elif cell == "工項名稱": file_data["工項名稱"] = df_raw.iloc[row_idx, col_idx + 1]
                        elif cell == "檢查結束日期":
                            raw_date = df_raw.iloc[row_idx, col_idx + 1]
                            file_data["檢查結束日期"] = raw_date.strftime("%m/%d") if isinstance(raw_date, datetime) else raw_date

                # 提取數值資料
                df_table = pd.read_excel(file, header=2, engine='calamine')
                check_cols = [c for c in df_table.columns if '檢查結果' in str(c)]
                if check_cols:
                    target_rows = df_table[df_table['進階分類'].str.contains(r'車輪組-[Cc]|斷電[Cc]|頂昇斷電[Dd]|車下-[Cc]|頂昇斷電-[Aa]|車下-[Bb]', regex=True, na=False) & 
                                           df_table['檢查項目'].str.contains(r'直徑|輪徑', regex=True, na=False)]
                    for _, row in target_rows.iterrows():
                        try:
                            val = float(row[check_cols[0]])
                            if pd.notna(val): file_data[f"{row['進階分類']}_{row['檢查項目']}"] = val
                        except: pass

                if '371' in file.name: results_371.append(file_data)
                elif '381' in file.name: results_381.append(file_data)
                progress_bar.progress((i + 1) / len(uploaded_files))

            # 🌟 顯示結果
            for model_name, data in [("371型", results_371), ("381型", results_381)]:
                res_df = process_data(data)
                if res_df is not None:
                    st.subheader(f"📊 {model_name} 提取結果預覽")
                    st.dataframe(res_df)
                    
                    buf = io.BytesIO()
                    res_df.to_excel(buf, index=False)
                    st.download_button(
                        label=f"📥 下載 {model_name} 輪徑提取表",
                        data=buf.getvalue(),
                        file_name=f"{model_name}_提取結果_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.ms-excel"
                    )

                    # 🌟 新增：在下載按鈕下方顯示圖表
                    fig = create_min_wheel_chart(res_df, model_name)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)

            st.success("✅ 所有檔案處理完成！")