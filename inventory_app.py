sh = _client.open(REAGENT_DB_NAME)
        sheet = sh.worksheet(REAGENT_DB_TAB)
        data = sheet.get_all_records()
        if not data:
            st.warning("마스터 시트(Reagent_DB)가 비어있습니다. '새 품목 등록' 탭에서 먼저 품목을 등록하세요.")
            return pd.DataFrame(columns=["제품명", "Lot 번호", "최초 수량", "단위"])
        
        df = pd.DataFrame(data)
        
        if "제품명" not in df.columns or "Lot 번호" not in df.columns:
             st.error("Reagent_DB 'Master' 탭에 '제품명' 또는 'Lot 번호' 컬럼이 없습니다.")
             return pd.DataFrame(columns=["제품명", "Lot 번호", "최초 수량", "단위"])
        
        df['제품명'] = df['제품명'].astype(str)
        df['Lot 번호'] = df['Lot 번호'].astype(str)
        df['최초 수량'] = pd.to_numeric(df['최초 수량'], errors='coerce').fillna(0)
             
        return df
    except Exception as e:
        st.error(f"Reagent_DB 로드 실패: {e}")
        return pd.DataFrame(columns=["제품명", "Lot 번호", "최초 수량", "단위"])

# (3) 사용 기록(Log) 로드 함수 (v6와 동일)
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


# --- 4. 탭 1: 새 품목 등록 (v6와 동일) ---
with tab1:
    st.header("📝 새 시약/소모품 등록")
    st.write(f"이 폼을 제출하면 **'{REAGENT_DB_NAME}'** 시트의 **'{REAGENT_DB_TAB}'** 탭에 저장됩니다.")
    st.divider()

    with st.form(key="new_item_form"): # (clear_on_submit=False)
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
            except Exception as e:
                st.error(f"Google Sheet 저장 실패: {e}")


# --- 5. 탭 2: 시약 사용 (v7 수정됨) ---
with tab2:
    st.header("📉 시약 사용 기록")
    st.write(f"이 폼을 제출하면 **'{USAGE_LOG_NAME}'** 시트의 **'{USAGE_LOG_TAB}'** 탭에 저장됩니다.")
    st.divider()

    # (1) 마스터 DB와 사용기록 Log 모두 불러오기 (v6와 동일)
    df_db = load_reagent_db(client)
    df_log = load_usage_log(client) 
    
    if df_db.empty:
        st.error("마스터 DB(Reagent_DB)에 등록된 품목이 없습니다. '새 품목 등록' 탭에서 먼저 품목을 등록하세요.")
    else:
        
        # ▼▼▼ [수정됨] v7: 폼 바깥으로 드롭다운 이동 ▼▼▼
        st.subheader("1. 사용할 품목 선택")
        
        # (2) 동적 드롭다운
        all_products = sorted(df_db['제품명'].dropna().unique())
        selected_product = st.selectbox("사용한 제품명*", options=all_products)
        
        if selected_product:
            # (제품명에 따라 Lot 번호를 정확히 필터링)
            available_lots = sorted(
                df_db[df_db['제품명'] == selected_product]['Lot 번호'].dropna().unique()
            )
            selected_lot = st.selectbox("Lot 번호*", options=available_lots)
        else:
            selected_lot = st.selectbox("Lot 번호*", options=["제품명을 먼저 선택하세요"])

        # (3) 현재 재고 자동 계산 표시
        current_stock = 0.0 # (기본값)
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
        # ▲▲▲ [수정됨] v7: 폼 바깥으로 드롭다운 이동 끝 ▲▲▲


        # (4) 폼 생성 (사용량, 사용자, 비고만 입력)
        st.subheader("2. 사용 정보 입력")
        
        with st.form(key="usage_form"): # (clear_on_submit=False)
            
            usage_qty = st.number_input("사용한 양*", min_value=0.0, step=1.0, format="%.2f")
            user = st.text_input("사용자 이름*")
            notes = st.text_area("비고 (실험명 등)")

            submit_usage_button = st.form_submit_button(label="📉 사용 기록하기")

        if submit_usage_button:
            # (5) 유효성 검사
            if not all([selected_product, selected_lot, usage_qty > 0, user]):
                st.error("필수 항목(*)을 모두 입력해야 합니다. (사용량은 0보다 커야 함)")
            
            # (v6 재고 검증 로직)
            elif float(usage_qty) > current_stock:
                shortage = float(usage_qty) - current_stock
                st.error(f"⚠️ 재고 부족! 현재 재고({current_stock:.2f} {unit})보다 {shortage:.2f} {unit} 만큼 더 많이 입력했습니다.")
            
            else:
                # (6) Usage_Log 시트에 저장
                try:
                    sh_log = client.open(USAGE_LOG_NAME)
                    sheet_log = sh_log.worksheet(USAGE_LOG_TAB)
                    
                    log_data_list = [
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                        str(selected_product), # 폼 바깥에서 선택된 값
                        str(selected_lot),     # 폼 바깥에서 선택된 값
                        float(usage_qty),      
                        user,
                        notes
                    ]
                    
                    sheet_log.append_row(log_data_list)
                    st.success(f"✅ **{selected_product} (Lot: {selected_lot})** 사용 기록이 저장되었습니다!")
                    
                    st.cache_data.clear() # (데이터 캐시 지우기 -> 재고 즉시 반영)

                except gspread.exceptions.SpreadsheetNotFound:
                    st.error(f"시트 파일 '{USAGE_LOG_NAME}'을(를) 찾을 수 없습니다. (이름/봇 초대 확인)")
                except gspread.exceptions.WorksheetNotFound:
                    st.error(f"파일 '{USAGE_LOG_NAME}'에서 '{USAGE_LOG_TAB}' 탭을 찾을 수 없습니다! (탭 이름 확인)")
                except Exception as e:
                    st.error(f"Google Sheet 저장 실패: {e}")


# --- 6. 탭 3: 대시보드 (재고 현황) ---
with tab3:
    st.header("📊 대시보드 (재고 현황)")
    st.warning("기능 개발 중입니다. (v7)")
