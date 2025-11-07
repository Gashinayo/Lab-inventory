import streamlit as st
import gspread 
import json 
import base64 
from google.oauth2.service_account import Credentials 
import pandas as pd 
from datetime import datetime

# --- 1. 앱의 기본 설정 ---
st.set_page_config(page_title="실험실 재고 관리기 v3", layout="wide")
st.title("🔬 실험실 재고 관리기 v3")
st.write("새 품목을 등록하고, 사용량을 기록하며, 재고 현황을 확인합니다.")

# --- 2. Google Sheets 인증 및 설정 ---
# (v2와 동일)
REAGENT_DB_NAME = "Reagent_DB"  
REAGENT_DB_TAB = "Master"       
USAGE_LOG_NAME = "Usage_Log"    
USAGE_LOG_TAB = "Log"           

# (1) 인증된 '클라이언트' 생성 (v2와 동일)
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
            creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        else:
            creds = Credentials.from_service_account_file('.streamlit/secrets.toml', scopes=scope)
        client = gspread.authorize(creds)
        return client, None
    except FileNotFoundError:
        return None, "로컬 Secrets 파일('.streamlit/secrets.toml')을 찾을 수 없습니다."
    except Exception as e:
        return None, f"Google 인증 실패: {e}"

# (2) 마스터 DB 로드 함수 (v2와 동일)
@st.cache_data(ttl=60) 
def load_reagent_db(_client):
    try:
        sh = _client.open(REAGENT_DB_NAME)
        sheet = sh.worksheet(REAGENT_DB_TAB)
        data = sheet.get_all_records()
        if not data:
            st.warning("마스터 시트(Reagent_DB)가 비어있습니다. '새 품목 등록' 탭에서 먼저 품목을 등록하세요.")
            return pd.DataFrame(columns=["제품명", "Lot 번호"])
        
        df = pd.DataFrame(data)
        
        # (v3: Cat. No. / Lot 번호를 문자열로 강제 변환 - int64 오류 방지)
        if "제품명" not in df.columns or "Lot 번호" not in df.columns:
             st.error("Reagent_DB 'Master' 탭에 '제품명' 또는 'Lot 번호' 컬럼이 없습니다.")
             return pd.DataFrame(columns=["제품명", "Lot 번호"])
        
        df['제품명'] = df['제품명'].astype(str)
        df['Lot 번호'] = df['Lot 번호'].astype(str)
             
        return df
    except Exception as e:
        st.error(f"Reagent_DB 로드 실패: {e}")
        return pd.DataFrame(columns=["제품명", "Lot 번호"])

# --- 3. 앱 실행 ---
client, auth_error_msg = get_gspread_client()

if auth_error_msg:
    st.error(auth_error_msg)
    st.warning("Secrets 설정, API 권한, 봇 초대를 확인하세요.")
    st.stop() 

tab1, tab2, tab3 = st.tabs(["📝 새 품목 등록", "📉 시약 사용", "📊 대시보드 (재고 현황)"])


# --- 4. 탭 1: 새 품목 등록 (v2와 동일) ---
with tab1:
    st.header("📝 새 시약/소모품 등록")
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

    if submit_button:
        if not all([product_name, cat_no, lot_no, initial_qty > 0, registrant]):
            st.error("필수 항목(*)을 모두 입력해야 합니다. (최초 수량은 0보다 커야 함)")
        else:
            try:
                sh = client.open(REAGENT_DB_NAME)
                sheet = sh.worksheet(REAGENT_DB_TAB)
                
                log_data_list = [
                    product_name, cat_no, lot_no,
                    float(initial_qty), unit,
                    expiry_date.strftime("%Y-%m-%d"), 
                    location,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # 등록 날짜
                    registrant
                ]
                
                sheet.append_row(log_data_list)
                st.success(f"✅ **{product_name} (Lot: {lot_no})**가 마스터 시트에 성공적으로 등록되었습니다!")
                st.cache_data.clear() 
            
            except gspread.exceptions.SpreadsheetNotFound:
                st.error(f"시트 파일 '{REAGENT_DB_NAME}'을(를) 찾을 수 없습니다. (이름/봇 초대 확인)")
            except gspread.exceptions.WorksheetNotFound:
                st.error(f"파일 '{REAGENT_DB_NAME}'에서 '{REAGENT_DB_TAB}' 탭을 찾을 수 없습니다! (탭 이름 확인)")
            except Exception as e:
                st.error(f"Google Sheet 저장 실패: {e}")


# --- 5. 탭 2: 시약 사용 (v3 수정됨) ---
with tab2:
    st.header("📉 시약 사용 기록")
    st.write(f"이 폼을 제출하면 **'{USAGE_LOG_NAME}'** 시트의 **'{USAGE_LOG_TAB}'** 탭에 저장됩니다.")
    st.divider()

    # (1) 마스터 DB에서 품목/Lot 목록 불러오기 (v3에서 .astype(str)로 수정됨)
    df_db = load_reagent_db(client)
    
    if df_db.empty:
        st.error("마스터 DB(Reagent_DB)에 등록된 품목이 없습니다. '새 품목 등록' 탭에서 먼저 품목을 등록하세요.")
    else:
        # (2) 폼 생성
        with st.form(key="usage_form", clear_on_submit=True):
            
            # (3) 동적 드롭다운
            all_products = sorted(df_db['제품명'].dropna().unique())
            
            # 1. 제품명 선택
            selected_product = st.selectbox("사용한 제품명*", options=all_products)
            
            # 2. Lot 번호 필터링
            if selected_product:
                available_lots = sorted(
                    df_db[df_db['제품명'] == selected_product]['Lot 번호'].dropna().unique()
                )
                selected_lot = st.selectbox("Lot 번호*", options=available_lots)
            else:
                selected_lot = st.selectbox("Lot 번호*", options=["제품명을 먼저 선택하세요"])

            st.divider()
            
            # 3. 사용 정보 입력
            usage_qty = st.number_input("사용한 양*", min_value=0.0, step=1.0, format="%.2f")
            user = st.text_input("사용자 이름*")
            notes = st.text_area("비고 (실험명 등)")

            submit_usage_button = st.form_submit_button(label="📉 사용 기록하기")

        if submit_usage_button:
            # (4) 유효성 검사
            if not all([selected_product, selected_lot, usage_qty > 0, user]):
                st.error("필수 항목(*)을 모두 입력해야 합니다. (사용량은 0보다 커야 함)")
            else:
                try:
                    # (5) Usage_Log 시트에 저장
                    sh_log = client.open(USAGE_LOG_NAME)
                    sheet_log = sh_log.worksheet(USAGE_LOG_TAB)
                    
                    # ▼▼▼ [수정됨] v3: int64 오류 방지를 위해 str() / float() 강제 변환 ▼▼▼
                    log_data_list = [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), # Timestamp
                        str(selected_product), # 문자열로 변환
                        str(selected_lot),     # 문자열로 변환 (핵심!)
                        float(usage_qty),      # float으로 변환
                        user,
                        notes
                    ]
                    # ▲▲▲ [수정됨] v3 ▲▲▲
                    
                    sheet_log.append_row(log_data_list)
                    st.success(f"✅ **{selected_product} (Lot: {selected_lot})** 사용 기록이 저장되었습니다!")
                    
                    st.cache_data.clear()

                except gspread.exceptions.SpreadsheetNotFound:
                    st.error(f"시트 파일 '{USAGE_LOG_NAME}'을(를) 찾을 수 없습니다. (이름/봇 초대 확인)")
                except gspread.exceptions.WorksheetNotFound:
                    st.error(f"파일 '{USAGE_LOG_NAME}'에서 '{USAGE_LOG_TAB}' 탭을 찾을 수 없습니다! (탭 이름 확인)")
                except Exception as e:
                    st.error(f"Google Sheet 저장 실패: {e}")


# --- 6. 탭 3: 대시보드 (재고 현황) ---
with tab3:
    st.header("📊 대시보드 (재고 현황)")
    st.warning("기능 개발 중입니다. (v4)")
