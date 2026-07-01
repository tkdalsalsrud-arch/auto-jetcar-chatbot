import streamlit as st
import google.generativeai as genai
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 0. 페이지 설정 및 디자인 ---
st.set_page_config(page_title="JETCAR 직원 지원 시스템", page_icon="🏎️")

st.markdown("""
<style>
    div[data-testid="chat-message-container"] { border-radius: 10px; padding: 10px 14px; margin-bottom: 10px; }
    div[data-testid="chat-message-container"]:has(div[data-testid="stChatMessageContent-user"]) { background-color: #F0F2F6; color: #333; }
    div[data-testid="chat-message-container"]:has(div[data-testid="stChatMessageContent-assistant"]) { background-color: #4A90E2; color: white; }
</style>
""", unsafe_allow_html=True)

# --- 1. 키워드 데이터 정의 ---
KEYWORDS_CONDITION = ["무심사장기렌트카","무심사렌트카","신용불량자중고차","신용회복장기렌트","신용회복중장기렌트","신용회복중중중고차","연체자중고차","장기렌트카신용","저신용렌트카","저신용자장기렌트","저신용자장기렌트카","저신용장기렌트카","중고장기렌터카","중고장기렌트","중고장기렌트카","중고차장기렌트","중고차렌트","중고차렌트카","자동차1년렌트","1년렌트카","1년장기렌트","개인회생렌탈","개인회생자장기렌트","개인회생장기렌트"]
KEYWORDS_LOCATION_BIZ = ["개인사업렌트카","개인사업자렌트","개인사업자장기렌트","법인렌터카","법인렌트","법인렌트견적","법인렌트카","법인장기렌터카","법인장기렌트","법인장기렌트견적","법인장기렌트카","법인장기렌트카견적","법인차량렌트","사업자렌트","사업자렌트카","사업자장기렌트","신규법인장기렌트"]
CAR_MODELS = ["모닝", "레이", "니로", "스토닉", "셀토스", "스포티지", "쏘렌토", "모하비", "카니발", "EV3", "EV4", "EV6", "EV9", "G70", "G80", "G90", "GV60", "GV70", "GV80", "GV90", "EQ900", "SM3", "SM5", "SM6", "SM7", "XM3", "QM5", "QM6", "그랑콜레오스", "아르카나", "QM3", "티볼리", "토레스", "액티언", "렉스턴", "코란도", "스파크", "트랙스", "트레일블레이저", "A클래스", "C클래스", "E클래스", "S클래스", "GLC클래스", "GLE클래스", "CLA클래스", "CLE클래스", "CLS클래스", "EQ", "X1", "X3", "X4", "X5", "X6", "X7", "1시리즈", "3시리즈", "5시리즈", "7시리즈", "GT", "i3", "i4", "i5", "i7", "ix", "아테온", "티구안", "골프", "제타"]

LOG_SHEET_ID = "1DsZRoLIQ4G3Tk-27PZs9giMrTgH-KLh_cgYbOJJd_1s"

def get_client_ip():
    try:
        headers = st.context.headers
        forwarded = headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return headers.get("X-Real-Ip", "알 수 없음")
    except Exception:
        return "알 수 없음"

def log_user_input(user_input):
    try:
        import json
        creds_info = json.loads(st.secrets["SERVICE_ACCOUNT_JSON"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        client = gspread.authorize(creds)
        worksheet = client.open_by_key(LOG_SHEET_ID).get_worksheet(0)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ip = get_client_ip()
        worksheet.append_row([now, user_input, ip])
    except Exception:
        pass

# --- 2. API 설정 및 데이터 로드 ---
try:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
except Exception as e:
    st.error("🚨 API 키 오류: .streamlit/secrets.toml 파일을 확인해주세요.")
    st.stop()

@st.cache_data(ttl=300)
def load_car_data():
    try:
        import json
        creds_info = json.loads(st.secrets["SERVICE_ACCOUNT_JSON"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        client = gspread.authorize(creds)
        sheet_id = st.secrets["SHEET_ID"]
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.get_worksheet(0)
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        return df, None
    except Exception as e:
        return None, f"🚨 구글시트 로드 중 오류 발생: {e}"

df_cars, error_msg = load_car_data()
if error_msg: st.error(error_msg); st.stop()

# --- 3. 세션 관리 ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "제트카 직원 전용 시스템입니다. 찾으시는 차량명이나 차량번호를 입력해주세요."}]

# --- 4. 응답 생성 함수 ---
def generate_ai_response(user_input):
    log_user_input(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"): st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("데이터 분석 및 서식 구성 중..."):
            try:
                car_text_context = df_cars.to_string(index=False)
                
                system_prompt = f"""
                당신은 제트카(JETCAR) 상담 직원을 돕는 AI 비서입니다.
                제공된 [차량 현황 데이터]를 기반으로 답변하세요.

                [데이터]
                {car_text_context}

                [필수 지시 사항 - 절대 누락 금지]
                1. 차량 제목 형식:
                   형식: **[전국] 차량명 (분류1 / 분류2 / 분류3) 최고가개월수 연식 연료 구동방식 인승**
                   - [구동방식 조건부 출력]: 
                     데이터에 'AWD' 또는 '4WD'라는 단어가 포함되어 있다면 해당 단어를 그대로 유지하고, 그 뒤에 "2WD"를 절대 붙이지 마세요.
                     만약 데이터에 'AWD'나 '4WD'가 전혀 없다면, 수동으로 "2WD"를 제목 끝에 붙여야 합니다.
                   - 인승: 데이터에 명시된 인승을 적되, 없으면 "5인승"을 기본으로 붙이세요.
                   - 차량명 자체에 금액을 표시하지 마세요.
                   - 연식 숫자 뒤에는 반드시 "연식" 단어를 붙이세요. (예: 2023연식)

                2. 3단 키워드 조합 규칙:
                   - 분류1 (조건): {KEYWORDS_CONDITION} 중 선택. (주행거리 30KM 이하 신차급 차량은 '중고차' 단어 포함 키워드 선택 금지)
                   - 분류2 (지역/사업자): {KEYWORDS_LOCATION_BIZ} 중 선택.
                   - 분류3 (모델): 차량명에서 {CAR_MODELS} 중 일치하는 모델 추출 후 '모델명장기렌트카'로 표기.

                3. 렌트비용 안내 (데이터 기반 가변 출력):
                   - 엑셀 데이터에서 해당 차량의 모든 개월수와 금액 컬럼을 찾아 한 줄씩 표시하세요.
                   - 형식:
                   💸 렌트비용
                   보증금 80만원
                   정비 포함 여부 : 정비 미포함
                   탁송료 : 별도 

                   📆 (데이터 개월수) (해당 금액)만원

                4. 상세 서식 예시:
                   📌 차량정보
                   차량명: 
                   주행거리 : 
                   연식: 
                   연료 : 

                   ✨ 적용옵션: 기본형

                   (위 렌트비용 섹션)

                   👍 이런 분들께 추천 ! 
                   ✔️ (데이터 기반 추천 사유 3가지)

                   📞 상담문의
                   카톡상담 : 카카오톡에 'JETCAR' 를 검색해주세요
                   홈페이지 방문 : https://www.jetcar.co.kr/
                   네이버 채팅 문의도 환영합니다!

                5. 상세서식예시에서 각내용 줄바꿈 잘해야합니다.
                6. 정비는 무조건 불포함입니다.
                """
                
                # 모델명은 실제 사용 가능한 gemini-1.5-flash 등을 권장합니다.
                model = genai.GenerativeModel('gemini-3.1-flash-lite')
                response = model.generate_content(f"{system_prompt}\n\n직원 질문: {user_input}")
                
                ai_response = response.text
                st.markdown(ai_response)
                st.session_state.messages.append({"role": "assistant", "content": ai_response})
            except Exception as e: 
                st.error(f"오류가 발생했습니다: {e}")

# --- 5. UI 메인 ---
st.title("🚗 JETCAR 스마트 상담 비서")
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

if prompt := st.chat_input("차량명이나 번호를 입력하세요."):
    generate_ai_response(prompt)


