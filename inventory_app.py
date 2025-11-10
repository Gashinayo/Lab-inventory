import streamlit as st
import gspread 
import json 
import base64 
from oauth2client.service_account import ServiceAccountCredentials 
import pandas as pd 
from datetime import datetime

# --- 1. 앱의 기본 설정 ---
st.set_page_config(page_title="실험실 재고 관리기 v25", layout="wide")
st.title("🔬 실험실 재고 관리기 v25")
st.write("새 품목을 등록하고, 사용량을 기록하며, 재고 현황을 확인합니다.")

# --- 2. Google Sheets 인증 및 설정 ---
# (v23과 동일)
REAGENT_DB_NAME = "Reagent_DB"  
REAGENT_DB_TAB = "Master"       
USAGE_LOG_NAME = "Usage_Log"    
USAGE_LOG_TAB = "Log"           

# (1) 인증된 '클라이언트' 생성 (v23과 동일)
@st.cache_resource(ttl=600)
def get_gspread_client():
    try:
        scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        if 'gcp_json_base64' in st.secrets:
            base64_string = st.secrets["gcp_json_base64"]
            json_string = base64.b64decode(base64_string).decode("utf-8")
            creds_dict = json.loads(json_string) 
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_service_account_file('.streamlit/secrets.toml', scope)
        client = gspread.authorize(creds)
        return client, None
    except FileNotFoundError:
        return None, "로컬 Secrets 파일('.streamlit/secrets.toml')을 찾을 수 없습니다."
    except Exception as e:
        return None, f"Google 인증 실패: {e}"

# (2) 마스터 DB 로드 함수 (v23과 동일)
@st.cache_data(ttl=60) 
def load_reagent_db(_client):
    try:
        sh = _client.open(REAGENT_DB_NAME)
        sheet = sh.worksheet(REAGENT_DB_TAB)
        data = sheet.get_all_records()
        if not data:
            st.warning("마스터 시트(Reagent_DB)가 비어있습니다...")
            return pd.DataFrame(columns=["제품명", "Lot 번호", "최초 수량", "단위", "유통기한"])
        
        df = pd.DataFrame(data)
        
        required_cols = ["제품명", "Lot 번호", "최초 수량", "단위", "유통기한"]
        if not all(col in df.columns for col in required_cols):
             st.error(f"Reagent_DB 'Master' 탭에 {required_cols} 컬럼이 모두 필요합니다.")
             return pd.DataFrame(columns=required_cols)
        
        df['제품명'] = df['제품명'].astype(str)
        df['Lot 번호'] = df['Lot 번호'].astype(str)
        df['최초 수량'] = pd.to_numeric(df['최초 수량'], errors='coerce').fillna(0)
        df['유통기한'] = pd.to_datetime(df['유통기한'], errors='coerce') 
             
        return df
    except Exception as e:
        st.error(f"Reagent_DB 로드 실패: {e}")
        return pd.DataFrame(columns=["제품명", "Lot 번호", "최초 수량", "단위", "유통기한"])

# (3) 사용 기록(Log) 로드 함수 (v23과 동일)
@st.cache_data(ttl=60)
def load_usage_log(_client):
    try:
        sh = _client.open(USAGE_LOG_NAME)
        sheet = sh.worksheet(USAGE_LOG_TAB)
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=["제품명", "Lot 번호", "사용량"]) 
        
        df = pd.DataFrame(data)
        
        if "제품명" not in df.columns or "Lot 번호" not in df.columns or "사용량" not in df.columns:
             st.error("Usage_Log 'Log' 탭에 '제품명', 'Lot 번호', '사용량' 컬럼이 없습니다. (1행 헤더 확인)")
             return pd.DataFrame(columns=["제품명", "Lot 번호", "사용량"])
        
        df['제품명'] = df['제품명'].astype(str)
        df['Lot 번호'] = df['Lot 번호'].astype(str)
        df['사용량'] = pd.to_numeric(df['사용량'], errors='coerce').fillna(0)
             
        return df
    except Exception as e:
        st.error(f"Usage_Log 로드 실패: {e}")
        return pd.DataFrame(columns=["제품명", "Lot 번호", "사용량"])

# --- 3. 앱 실행 ---
client, auth_error_msg = get_gspread_client()

if auth_error_msg:
    st.error(auth_error_msg)
    st.warning("Secrets 설정, API 권한, 봇 초대를 확인하세요.")
    st.stop() 

tab1, tab2, tab3 = st.tabs(["📝 새 품목 등록", "📉 시약 사용", "📊 대시보드 (재고 현황)"])


# --- 4. 탭 1: 새 품목 등록 (v23과 동일) ---
with tab1:
    st.header("📝 새 시약/소모품 등록")
    # ... (v23 탭1 코드 전체 생략 - 동일) ...
    st.write(f"이 폼을 제출하면 **'{REAGENT_DB_NAME}'** 시트의 **'{REAGENT_DB_TAB}'** 탭에 저장됩니다.")
    st.divider()
    with st.form(key="new_item_form", clear_on_submit=True): 
        col1, col2 = st.columns(2)
        with col1:
            st.write("**필수 정보**")
            product_name = st.text_input("제품명*", help="예: DMEM, 10% FBS")
            cat_no = st.text_input("Cat. No.*", help="카탈로그 번호 (예: 11995-065)")
            lot_no = st.text_input("Lot 번호*")
        with col2:
            st.write("**수량 및 보관 정보**")
            initial_qty = st.number_input("최초 수량*", min_value=0.0, step=1.0, format="%.2f")
            unit = st.selectbox("단위*", ["mL", "L", "g", "kg", "개", "box", "kit"])
            location = st.text_input("보관 위치", help="예: 4도 냉장고 A-1 선반, -20도 냉동고 B-3 박스")
        st.divider()
        st.write("**기타 정보**")
        expiry_date = st.date_input("유통기한", datetime.now() + pd.DateOffset(years=1))
        registrant = st.text_input("등록자 이름*")
        submit_button = st.form_submit_button(label="✅ 신규 등록하기")
    if "form1_status" in st.session_state:
        if st.session_state.form1_status == "success": st.success(st.session_state.form1_message)
        else: st.error(st.session_state.form1_message)
        del st.session_state.form1_status
        del st.session_state.form1_message
    if submit_button:
        if not all([product_name, cat_no, lot_no, initial_qty > 0, registrant]):
            st.session_state.form1_status = "error"
            st.session_state.form1_message = "필수 항목(*)을 모두 입력해야 합니다. (최초 수량은 0보다 커야 함)"
        else:
            try:
                sh = client.open(REAGENT_DB_NAME)
                sheet = sh.worksheet(REAGENT_DB_TAB)
                log_data_list = [
                    product_name, cat_no, lot_no,
                    float(initial_qty), unit,
                    expiry_date.strftime("%Y-%m-%d"), 
                    location,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                    registrant
                ]
                sheet.append_row(log_data_list)
                st.session_state.form1_status = "success"
                st.session_state.form1_message = f"✅ **{product_name} (Lot: {lot_no})**가 마스터 시트에 성공적으로 등록되었습니다!"
                st.cache_data.clear() 
            except Exception as e:
                st.session_state.form1_status = "error"
                st.session_state.form1_message = f"Google Sheet 저장 실패: {e}"
        st.rerun()


# --- 5. 탭 2: 시약 사용 (v23과 동일) ---
with tab2:
    st.header("📉 시약 사용 기록")
    # ... (v23 탭2 코드 전체 생략 - 동일) ...
    st.write(f"이 폼을 제출하면 **'{USAGE_LOG_NAME}'** 시트의 **'{USAGE_LOG_TAB}'** 탭에 저장됩니다.")
    st.divider()
    df_db = load_reagent_db(client)
    df_log = load_usage_log(client) 
    if df_db.empty:
        st.error("마스터 DB(Reagent_DB)에 등록된 품목이 없습니다. '새 품목 등록' 탭에서 먼저 품목을 등록하세요.")
    else:
        st.subheader("1. 사용할 품목 선택")
        all_products = sorted(df_db['제품명'].dropna().unique())
        selected_product = st.selectbox("사용한 제품명*", options=all_products)
        if selected_product:
            available_lots = sorted(
                df_db[df_db['제품명'] == selected_product]['Lot 번호'].dropna().unique()
            )
            selected_lot = st.selectbox("Lot 번호*", options=available_lots)
        else:
            selected_lot = st.selectbox("Lot 번호*", options=["제품명을 먼저 선택하세요"])
        current_stock = 0.0 
        unit = ""
        if selected_product and selected_lot:
            try:
                item_info = df_db[
                    (df_db['제품명'] == selected_product) & 
                    (df_db['Lot 번호'] == selected_lot)
                ].iloc[0] 
                initial_stock = item_info['최초 수량']
                unit = item_info['단위']
                usage_df = df_log[
                    (df_log['제품명'] == selected_product) & 
                    (df_log['Lot 번호'] == selected_lot)
                ]
                total_usage = usage_df['사용량'].sum()
                current_stock = initial_stock - total_usage
                st.info(f"**현재 남은 재고:** {current_stock:.2f} {unit}")
            except (IndexError, TypeError, KeyError):
                st.warning("재고를 계산할 수 없습니다. (마스터DB/로그 확인)")
        st.divider()
        st.subheader("2. 사용 정보 입력")
        with st.form(key="usage_form", clear_on_submit=True):
            usage_qty = st.number_input("사용한 양*", min_value=0.0, step=1.0, format="%.2f")
            user = st.text_input("사용자 이름*")
            notes = st.text_area("비고 (실험명 등)")
            submit_usage_button = st.form_submit_button(label="📉 사용 기록하기")
        if "form2_status" in st.session_state:
            if st.session_state.form2_status == "success": st.success(st.session_state.form2_message)
            else: st.error(st.session_state.form2_message)
            del st.session_state.form2_status
            del st.session_state.form2_message
        if submit_usage_button:
            if not all([selected_product, selected_lot, usage_qty > 0, user]):
                st.session_state.form2_status = "error"
                st.session_state.form2_message = "필수 항목(*)을 모두 입력해야 합니다. (사용량은 0보다 커야 함)"
            elif float(usage_qty) > current_stock:
                shortage = float(usage_qty) - current_stock
                st.session_state.form2_status = "error"
                st.session_state.form2_message = f"⚠️ 재고 부족! 현재 재고({current_stock:.2f} {unit})보다 {shortage:.2f} {unit} 만큼 더 많이 입력했습니다."
            else:
                try:
                    sh_log = client.open(USAGE_LOG_NAME)
                    sheet_log = sh_log.worksheet(USAGE_LOG_TAB)
                    log_data_list = [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                        str(selected_product), 
                        str(selected_lot),     
                        float(usage_qty),      
                        user,
                        notes
                    ]
                    sheet_log.append_row(log_data_list)
                    st.session_state.form2_status = "success"
                    st.session_state.form2_message = f"✅ **{selected_product} (Lot: {selected_lot})** 사용 기록이 저장되었습니다!"
                    st.cache_data.clear() 
                except Exception as e:
                    st.session_state.form2_status = "error"
                    st.session_state.form2_message = f"Google Sheet 저장 실패: {e}"
            st.rerun()


# --- 6. 탭 3: 대시보드 (재고 현황) (v25 수정됨) ---
with tab3:
    st.header("📊 대시보드 (재고 현황)")

    if st.button("새로고침 (Refresh Data)"):
        st.cache_data.clear() 
        st.rerun()

    # 1. 데이터 로드 (v23과 동일)
    df_db = load_reagent_db(client)
    df_log = load_usage_log(client)

    if df_db.empty:
        st.warning("마스터 DB(Reagent_DB)에 등록된 품목이 없습니다.")
    else:
        # 2. 총 사용량 계산 (v23과 동일)
        if not df_log.empty:
            usage_summary = df_log.groupby(['제품명', 'Lot 번호'])['사용량'].sum().reset_index()
            usage_summary = usage_summary.rename(columns={'사용량': '총 사용량'})
            df_inventory = pd.merge(df_db, usage_summary, on=['제품명', 'Lot 번호'], how='left')
            df_inventory['총 사용량'] = df_inventory['총 사용량'].fillna(0) 
        else:
            df_inventory = df_db.copy()
            df_inventory['총 사용량'] = 0.0

        # 4. 현재 재고 및 비율 계산 (v23과 동일)
        df_inventory['현재 재고'] = df_inventory['최초 수량'] - df_inventory['총 사용량']
        df_inventory['재고 비율 (%)'] = df_inventory.apply(
            lambda row: (row['현재 재고'] / row['최초 수량']) * 100 if row['최초 수량'] > 0 else 0,
            axis=1
        )
        df_inventory['재고 비율 (%)'] = df_inventory['재고 비율 (%)'].clip(0) # (0 미만만 0으로 고정)

        # 5. 자동 알림 (v23과 동일)
        st.subheader("🚨 자동 알림")
        expiry_threshold_days = 30
        low_stock_threshold_percent = 20
        today = pd.to_datetime(datetime.now().date()) 
        df_inventory['유통기한'] = df_inventory['유통기한'].fillna(pd.NaT) 
        expiring_soon = df_inventory[
            (df_inventory['유통기한'] >= today) &
            (df_inventory['유통기한'] <= (today + pd.DateOffset(days=expiry_threshold_days)))
        ]
        expired = df_inventory[df_inventory['유통기한'] < today]
        if not expiring_soon.empty:
            st.warning(f"**유통기한 {expiry_threshold_days}일 이내 임박**")
            st.dataframe(expiring_soon[['제품명', 'Lot 번호', '유통기한', '보관 위치']], use_container_width=True)
        if not expired.empty:
            st.error(f"**유통기한 만료**")
            st.dataframe(expired[['제품명', 'Lot 번호', '유통기한', '보관 위치']], use_container_width=True)
        low_stock = df_inventory[
            (df_inventory['재고 비율 (%)'] <= low_stock_threshold_percent) &
            (df_inventory['현재 재고'] > 0) 
        ]
        out_of_stock = df_inventory[df_inventory['현재 재고'] <= 0]
        if not low_stock.empty:
            st.warning(f"**재고 부족 (권장 재고 {low_stock_threshold_percent}% 이하)**")
            st.dataframe(low_stock[['제품명', 'Lot 번호', '현재 재고', '단위', '재고 비율 (%)']], use_container_width=True)
        if not out_of_stock.empty:
            st.error(f"**재고 소진 (0 이하)**")
            st.dataframe(out_of_stock[['제품명', 'Lot 번호', '현재 재고', '단위']], use_container_width=True)
        if expiring_soon.empty and expired.empty and low_stock.empty and out_of_stock.empty:
            st.success("✅ 모든 재고가 양호합니다! (재고 20% 이상, 유통기한 30일 이상)")
        st.divider()

        # --- 6. 전체 재고 현황 (v25 수정됨) ---
        st.subheader("전체 재고 현황")
        
        display_columns = [
            "제품명", "Cat. No.", "Lot 번호", 
            "현재 재고", "단위", "최초 수량", "총 사용량",
            "재고 비율 (%)", "유통기한", "보관 위치", "등록자", "등록 날짜"
        ]
        available_columns = [col for col in display_columns if col in df_inventory.columns]
        
        if '유통기한' in available_columns:
            df_inventory['유통기한 (YYYY-MM-DD)'] = df_inventory['유통기한'].dt.strftime('%Y-%m-%d')
            available_columns[available_columns.index('유통기한')] = '유통기한 (YYYY-MM-DD)'
            
        # ▼▼▼ [수정됨] v25: style.applymap (빨간 텍스트)를 제외하고, style.bar (컬러 막대)만 사용 ▼▼▼
        
        st.dataframe(
            df_inventory[available_columns].style
            # (v23의 .applymap(style_current_stock) 기능 제거 -> 충돌 방지)
            .bar( # (v23 방식: 컬러 막대그래프)
                subset=['재고 비율 (%)'],
                align='left',
                cmap='RdYlGn', # Red-Yellow-Green colormap
                vmin=0, 
                vmax=100
            )
            .format({
                '현재 재고': '{:.2f}', 
                '총 사용량': '{:.0f}',  
                '재고 비율 (%)': '{:.1f}%' # (숫자 표시)
            }),
            
            use_container_width=True
        )
        # ▲▲▲ [수정됨] v25 ▲▲▲
