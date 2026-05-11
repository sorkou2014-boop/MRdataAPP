import streamlit as st
from streamlit_oauth import OAuth2Component
import pandas as pd
import io
import re
from datetime import datetime

# 🌟 設定網頁標題與大版面 (必須在程式碼最頂端)
st.set_page_config(page_title="月報數據自動化整理器", layout="wide")

# ==========================================
# 🔐 企業級 Google SSO 登入系統
# ==========================================
# 從 Streamlit 雲端保險箱安全讀取金鑰
CLIENT_ID = st.secrets["google_oauth"]["client_id"]
CLIENT_SECRET = st.secrets["google_oauth"]["client_secret"]
REDIRECT_URI = st.secrets["google_oauth"]["redirect_uri"]

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_TOKEN_URL = "https://oauth2.googleapis.com/revoke"

# 建立驗證物件
oauth2 = OAuth2Component(CLIENT_ID, CLIENT_SECRET, AUTHORIZE_URL, TOKEN_URL, REVOKE_TOKEN_URL)

# 檢查使用者是否已經登入 (有沒有取得 token)
if "token" not in st.session_state:
    st.title("🚂 月報數據自動化整理器")
    st.warning("🔒 本系統需授權使用(請洽開發者)，請使用已授權的 Google 帳號登入。")
    
    # 產生 Google 登入按鈕
    result = oauth2.authorize_button(
        name="使用 Google 帳號登入",
        icon="https://www.google.com.tw/favicon.ico",
        redirect_uri=REDIRECT_URI,
        scope="openid email profile"
    )
    
    if result and "token" in result:
        # 登入成功，將憑證存入網頁記憶體並重新整理畫面
        st.session_state.token = result.get("token")
        st.rerun()
else:
    # ===== 登入成功後才會顯示的畫面 =====
    col1, col2 = st.columns([8, 2])
    with col1:
        st.success("✅ 身分驗證成功，歡迎使用系統！")
    with col2:
        if st.button("🚪 登出系統"):
            del st.session_state.token
            st.rerun()
            
    st.divider()

# 🌟 設定網頁標題與大版面
st.set_page_config(page_title="MRdataAPP", layout="wide")

st.title("🚂 月報數據自動化整理器")
st.markdown("請上傳從行動撿些平台系統下載的 Excel 原始表單，系統將自動提取、運算並產生分析總表。")

# 🌟 網頁左側設定區
st.sidebar.header("⚙️ 其他")
st.sidebar.info("輪徑資料提取功能-最小值、單軸輪徑比較")

# 🌟 檔案上傳區 (取代原本的 Google Drive 路徑)
uploaded_files = st.file_uploader("📂 拖曳或選擇多份 Excel 檔案", type=["xlsx"], accept_multiple_files=True)

# 這裡放入你已經寫好的完美資料處理引擎 (稍作修改以適應網頁)
def process_data(results_list):
    if len(results_list) == 0:
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
            if 'A1' in col:
                b_col = col.replace('A1', 'B1')
                axis_name = "軸1"
            elif 'A2' in col:
                b_col = col.replace('A2', 'B2')
                axis_name = "軸2"
            elif 'A3' in col:
                b_col = col.replace('A3', 'B3')
                axis_name = "軸3"
            elif 'A4' in col:
                b_col = col.replace('A4', 'B4')
                axis_name = "軸4"

            if axis_name and b_col in df.columns:
                clean_car = get_clean_car_name(col)
                min_col = f"{clean_car}_{axis_name}"
                temp_min = df[[col, b_col]].min(axis=1)

                if min_col in df.columns:
                    df[min_col] = df[min_col].combine_first(temp_min)
                else:
                    df[min_col] = temp_min

    if '車號' in df.columns:
        df = df.sort_values(by='車號', ascending=True)

    base_cols = ["車號", "工單編號", "工項名稱", "檢查結束日期"]
    exist_base_cols = [c for c in base_cols if c in df.columns]
    dynamic_cols = [c for c in df.columns if c not in exist_base_cols]

    def custom_sort_logic(col_name):
        if '最小輪徑' in col_name: return (0, 0, 0, 0, col_name)
        block_weight = 1 if '軸' in col_name else 2

        car_weight = 50
        if 'DM1' in col_name: car_weight = 1
        elif 'T' in col_name: car_weight = 2
        elif 'M2' in col_name or 'DM2' in col_name: car_weight = 3

        item_weight = 50
        if '1' in col_name[-2:]: item_weight = 1
        elif '2' in col_name[-2:]: item_weight = 2
        elif '3' in col_name[-2:]: item_weight = 3
        elif '4' in col_name[-2:]: item_weight = 4

        ab_weight = 0
        if 'B' in col_name: ab_weight = 1
        return (block_weight, car_weight, item_weight, ab_weight, col_name)

    sorted_dynamic_cols = sorted(dynamic_cols, key=custom_sort_logic)
    final_cols = exist_base_cols + sorted_dynamic_cols
    return df[final_cols]

# 🌟 啟動按鈕與執行邏輯
if uploaded_files:
    if st.button("🚀 開始分析資料"):
        with st.spinner('資料提取與運算中，請稍候...'):
            results_371 = []
            results_381 = []

            # 進度條設定
            progress_bar = st.progress(0)
            total_files = len(uploaded_files)

            for i, file in enumerate(uploaded_files):
                filename = file.name
                if filename.startswith("~$"): continue

                file_data = {
                    "車號": None, "工單編號": None,
                    "工項名稱": None, "檢查結束日期": None
                }

                # Streamlit 直接讀取上傳的記憶體檔案
                df_raw = pd.read_excel(file, header=None, engine='calamine')

                for row_idx in range(len(df_raw)):
                    for col_idx in range(len(df_raw.columns)):
                        cell_value = str(df_raw.iloc[row_idx, col_idx]).strip()
                        if cell_value == "工單編號": file_data["工單編號"] = df_raw.iloc[row_idx, col_idx + 1]
                        elif cell_value == "車號/最小成本單位": file_data["車號"] = str(df_raw.iloc[row_idx, col_idx + 1]).strip()
                        elif cell_value == "工項名稱": file_data["工項名稱"] = df_raw.iloc[row_idx, col_idx + 1]
                        elif cell_value == "檢查結束日期":
                            raw_date = df_raw.iloc[row_idx, col_idx + 1]
                            if isinstance(raw_date, datetime): file_data["檢查結束日期"] = raw_date.strftime("%m/%d")
                            elif isinstance(raw_date, str) and "-" in raw_date:
                                try: file_data["檢查結束日期"] = pd.to_datetime(raw_date).strftime("%m/%d")
                                except: file_data["檢查結束日期"] = raw_date
                            else: file_data["檢查結束日期"] = raw_date

                df_table = pd.read_excel(file, header=2, engine='calamine')
                check_result_cols = [col for col in df_table.columns if '檢查結果' in str(col)]
                if len(check_result_cols) > 0:
                    col_name = check_result_cols[0]
                    cond_cat = df_table['進階分類'].str.contains(r'車輪組-[Cc]|斷電[Cc]|頂昇斷電[Dd]|車下-[Cc]|頂昇斷電-[Aa]|車下-[Bb]', regex=True, na=False)
                    cond_item = df_table['檢查項目'].str.contains(r'直徑|輪徑', regex=True, na=False)
                    target_rows = df_table[cond_cat & cond_item]
                    for index, row in target_rows.iterrows():
                        category = str(row['進階分類']).strip()
                        item = str(row['檢查項目']).strip()
                        val = row[col_name]
                        try:
                            num_val = float(val)
                            if pd.notna(num_val): file_data[f"{category}_{item}"] = num_val
                        except (ValueError, TypeError): pass

                if '371' in filename: results_371.append(file_data)
                elif '381' in filename: results_381.append(file_data)

                # 更新進度條
                progress_bar.progress((i + 1) / total_files)

            st.success(f"✅ 成功處理 {total_files} 份檔案！")

            # 🌟 產出 371 型結果與下載按鈕
            df_371 = process_data(results_371)
            if df_371 is not None:
                st.subheader("📊 371型 分析結果預覽")
                st.dataframe(df_371) # 顯示互動式表格

                # 建立虛擬檔案讓使用者下載 (不存入硬碟)
                buffer_371 = io.BytesIO()
                df_371.to_excel(buffer_371, index=False)
                st.download_button(
                    label="📥 下載 371型 輪徑分析總表 (Excel)",
                    data=buffer_371.getvalue(),
                    file_name=f"371型_輪徑分析結果_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.ms-excel"
                )

            # 🌟 產出 381 型結果與下載按鈕
            df_381 = process_data(results_381)
            if df_381 is not None:
                st.subheader("📊 381型 分析結果預覽")
                st.dataframe(df_381)

                buffer_381 = io.BytesIO()
                df_381.to_excel(buffer_381, index=False)
                st.download_button(
                    label="📥 下載 381型 輪徑分析總表 (Excel)",
                    data=buffer_381.getvalue(),
                    file_name=f"381型_輪徑分析結果_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.ms-excel"
                )
