import os
import pandas as pd
from pathlib import Path
import google.generativeai as genai
from flask import Flask, render_template_string, request, session, Response, json

# --- 1. Flask 앱 및 환경 설정 ---
app = Flask(__name__)
# Flask 세션을 사용하기 위한 시크릿 키 (실제 배포 시에는 강력한 값으로 변경하세요)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'a_very_secret_key_fallback')

# --- 2. API 키 설정 (Gemini) ---
try:
    # 환경 변수에서 API 키 불러오기 (Streamlit의 st.secrets와 유사)
    # 로컬 테스트 시: export GOOGLE_API_KEY="YOUR_API_KEY"
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("🚨 [Gemini API 키]가 환경 변수(GOOGLE_API_KEY)에 설정되지 않았습니다.")
        # 로컬 개발용 secrets.toml (Streamlit 방식)은 Flask에서 직접 읽지 않습니다.
        # 이 예제에서는 키가 없으면 실행을 중지합니다.
        raise ValueError("API 키 없음")
        
    genai.configure(api_key=api_key)
    print("✅ Gemini API 키 설정 완료")

except Exception as e:
    print(f"🚨 API 키 설정 실패: {e}")
    # 실제 운영 환경에서는 이 부분에서 앱 실행을 중지하거나, 
    # API 키가 필요한 기능을 비활성화해야 합니다.
    # raise


# --- 3. (중요) Excel 데이터 로딩 (앱 시작 시 1회 실행) ---
try:
    context_file = Path("cars_data.xlsx")
    if not context_file.exists():
        print("🚨 'cars_data.xlsx' 파일을 찾을 수 없습니다. app.py와 같은 위치에 만들어주세요.")
        raise FileNotFoundError("cars_data.xlsx 없음")

    df = pd.read_excel(context_file, engine="openpyxl")
    
    # '참고 자료'를 LLM이 이해하기 쉬운 텍스트로 변환
    CONTEXT_DATA = "--- [제트카 정보] ---\n\n"
    column_headers = df.columns.tolist()  

    for index, row in df.iterrows():
        CONTEXT_DATA += f"[{row[column_headers[0]]}]\n"
        for col_name in column_headers[1:]:
            CONTEXT_DATA += f"- {col_name}: {row[col_name]}\n"
        CONTEXT_DATA += "\n"
    
    CONTEXT_DATA += "--- [참고 자료 끝] ---"
    print("✅ 출고 가능 차량 로딩 완료!")

except Exception as e:
    print(f"🚨 출고 가능 차량 로딩 중 치명적 오류 발생: {e}")
    # 데이터 로딩 실패 시 앱 실행을 중지할 수 있습니다.
    # raise

# --- 4. 프롬프트 생성 로직 (원본 코드 재사용) ---
def build_final_prompt(user_prompt):
    # 원본 코드의 지시사항을 그대로 사용합니다.
    return f"""
{CONTEXT_DATA}

[사용자 질문]
{user_prompt}

[지시]
1. [사용자 질문]에 대한 답변을 **먼저** [jetcar 참고 자료]에서 찾아보세요.
2. 만약 [참고 자료]에 질문과 **관련된 정보(예: 특정 차량 정보)가 있다면**, 그 자료를 기반으로 정확하게 대답해 주세요.
3. 만약 [참고 자료]에 **답이 없거나 관련성이 낮다면** (예: "장기렌트카의 장점은 무엇인가요?" 또는 "제트카 회사는 어디에 있나요?" 같은 일반 상식 및 자료 외 질문), "제가 아는 정보 중에는 없습니다."라고 말하지 **말고**, **당신의 일반 지식을 활용하여 친절하게 답변해 주세요.**
4. 만약 사용자 질문이 차량번호(또는 차량명)만 입력하는 경우, [참고 자료]에서 그 차량을 찾아 아래 서식에 맞춰 요약해 주세요. 이 때 '이런 분들께 추천 !' 부분은 당신이 자료를 참고하여 창의적으로 직접 작성해야 합니다.
   (기존 서식 생략...)
   제조사 연식 차량명 신용 무관 전국 출고 

신용 무관 / 만 26세 이상 ~ 60세이하 / 운전경력 1년이상 / 전국탁송 

📌 차량정보
차량명: 
주행거리 : 
연식: 
연료 : 

✨ 적용옵션 

기본형

💸 렌트비용
보증금 80만원
정비 포함 여부 : 정비 미포함
탁송료 : 별도 

📆 12개월 만원

📆 24개월 만원

📆 36개월 만원

📆 48개월 만원

📆 60개월 만원


👍 이런 분들께 추천 ! 

✔️ 신용등급 상관없이 차량이 필요한 분

✔️ 짐 싣는 공간이 충분한 차량을 찾고 계시는 분

✔️  신용 걱정없이 빠르게 탁송 받아볼 수 있는 차량을 원하시는 분

📞 상담문의
카톡상담 : 카카오톡에 'JETCAR' 를 검색해주세요
홈페이지 방문 : 네이버 검색창에 '제트카'를 검색해주세요

5. 모든 답변은 질문한 사람이 사용한 언어로 대답해 주세요.
6. 처음 차량 추천을 요청하는 질문에는, 차량 한대당 한줄로 요약된 추천 리스트를 제공해 주세요.
7. 장기렌트와 상관없는 질문에는 장기렌트와 관련된 답변을 하지 마세요.
8. 추천 차량이 여러대일 경우, 각 차량의 주요 특징을 간단히 비교해 주세요.
9. 사용자가 특정 차량(예: "카니발")을 언급한 경우, 그 차량에 대한 상세 정보를 제공해 주세요.
10. 가격을 표시할 경우에는 가장 낮은 가격을 기준으로 안내해 주세요.
"""

# --- 5. Gemini 모델 및 채팅 로직 ---
# 모델은 요청이 올 때마다 초기화
model = genai.GenerativeModel('gemini-2.5-flash')

def get_gemini_response_stream(prompt, history):
    # genai 챗 세션은 'content' 대신 'parts'를 사용합니다.
    genai_history = []
    for msg in history:
        genai_history.append({
            "role": msg["role"],
            "parts": [msg["content"]]
        })

    chat = model.start_chat(history=genai_history)
    final_prompt = build_final_prompt(prompt)
    
    # 스트리밍 응답 반환
    return chat.send_message(final_prompt, stream=True)

# --- 6. HTML/CSS/JS 템플릿 (단일 파일로 관리) ---
# 이 HTML 템플릿은 Flask의 render_template_string을 통해 렌더링됩니다.
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚗 jetcar 챗봇 (Flask)</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        /* Inter 폰트 적용 및 기본 스타일 */
        body {
            font-family: 'Inter', sans-serif;
            background-color: #f3f4f6;
        }
        @import url('https://rsms.me/inter/inter.css');
        /* 스크롤바 스타일링 (선택 사항) */
        #chat-history::-webkit-scrollbar {
            width: 6px;
        }
        #chat-history::-webkit-scrollbar-thumb {
            background-color: #cbd5e1;
            border-radius: 3px;
        }
    </style>
</head>
<body class="flex flex-col items-center justify-center min-h-screen p-4">

    <div class="w-full max-w-2xl bg-white rounded-lg shadow-lg flex flex-col" style="height: 80vh;">
        <!-- 헤더 -->
        <div class="p-4 border-b">
            <h1 class="text-2xl font-bold text-center">🚗 jetcar 챗봇</h1>
            <p class="text-sm text-gray-500 text-center">Powered by Flask & Google Gemini</p>
        </div>

        <!-- 채팅 기록 (스크롤) -->
        <div id="chat-history" class="flex-1 p-4 overflow-y-auto space-y-4">
            <!-- 초기 메시지 -->
            <div class="flex justify-start">
                <div class="bg-gray-200 text-gray-900 p-3 rounded-lg max-w-xs">
                    <p>안녕하세요! 제트카 챗봇입니다. SUV, 카니발, 패밀리카 등 궁금한 점을 물어보세요!</p>
                </div>
            </div>
            <!-- 채팅 메시지가 여기에 동적으로 추가됩니다 -->
        </div>

        <!-- 입력 폼 -->
        <div class="p-4 border-t bg-gray-50">
            <form id="chat-form" class="flex space-x-2">
                <input
                    type="text"
                    id="chat-input"
                    class="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="SUV차량 추천해줘!"
                    autocomplete="off"
                >
                <button
                    type="submit"
                    id="submit-button"
                    class="px-4 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                    전송
                </button>
            </form>
        </div>
    </div>

    <script>
        const chatForm = document.getElementById('chat-form');
        const chatInput = document.getElementById('chat-input');
        const chatHistory = document.getElementById('chat-history');
        const submitButton = document.getElementById('submit-button');

        // 이전 채팅 기록을 Flask 세션에서 불러옵니다.
        let messages = {{ session.get('messages', []) | tojson }};

        // 페이지 로드 시 이전 대화 내용 렌더링
        window.onload = () => {
            for (const msg of messages) {
                addMessageToUI(msg.role, msg.content);
            }
            // 이전 메시지가 없으면 로딩 완료 알림 (선택 사항)
            if (messages.length === 0) {
                console.log("이전 대화 기록이 없습니다.");
            }
        };

        // UI에 메시지 추가 (스크롤 포함)
        function addMessageToUI(role, content) {
            const messageWrapper = document.createElement('div');
            messageWrapper.className = `flex ${role === 'user' ? 'justify-end' : 'justify-start'}`;
            
            const messageBubble = document.createElement('div');
            messageBubble.className = `p-3 rounded-lg max-w-lg ${
                role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-900'
            }`;
            
            // \n을 <br>로 변환하여 줄바꿈 처리
            messageBubble.innerHTML = content.replace(/\\n/g, '<br>');
            
            messageWrapper.appendChild(messageBubble);
            chatHistory.appendChild(messageWrapper);
            
            // 새 메시지 추가 시 맨 아래로 스크롤
            chatHistory.scrollTop = chatHistory.scrollHeight;
            return messageBubble; // AI 응답을 위해 버블 반환
        }

        // 폼 제출 이벤트 (비동기 처리)
        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const prompt = chatInput.value.trim();
            if (!prompt) return;

            // 1. UI에 사용자 메시지 추가
            addMessageToUI('user', prompt);
            chatInput.value = '';
            submitButton.disabled = true; // 전송 버튼 비활성화

            // 2. AI 응답용 빈 버블 생성 (로딩 표시)
            const aiBubble = addMessageToUI('assistant', '🚙💨');

            try {
                // 3. Flask 백엔드(/chat)로 스트리밍 요청
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: prompt }),
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let fullResponse = '';
                aiBubble.innerHTML = ''; // 로딩 표시 제거

                // 4. 스트림 데이터 실시간 처리
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    const chunk = decoder.decode(value, { stream: true });
                    fullResponse += chunk;
                    // \n을 <br>로 변환하여 실시간 줄바꿈
                    aiBubble.innerHTML = fullResponse.replace(/\\n/g, '<br>');
                    
                    // 스트림 중에도 스크롤 유지
                    chatHistory.scrollTop = chatHistory.scrollHeight;
                }
                
                // 스트림 종료 후, 최종 응답을 세션 동기화 엔드포인트로 전송
                // (Flask 세션은 /chat 엔드포인트에서 이미 처리되므로 이 로직은 선택 사항)
                // 이 예제에서는 /chat에서 세션 처리를 완료합니다.

            } catch (error) {
                console.error('AI 응답 중 오류:', error);
                aiBubble.innerHTML = 'AI 응답 중 오류가 발생했습니다. 다시 시도해 주세요.';
            } finally {
                submitButton.disabled = false; // 전송 버튼 활성화
            }
        });
    </script>
</body>
</html>
"""

# --- 7. Flask 라우트(Routes) 정의 ---

@app.route('/')
def home():
    """메인 페이지 렌더링. 세션에 'messages'가 없으면 초기화."""
    if 'messages' not in session:
        session['messages'] = []
    
    # HTML 템플릿 문자열을 렌더링합니다.
    return render_template_string(HTML_TEMPLATE)

@app.route('/chat', methods=['POST'])
def chat():
    """채팅 요청을 받아 스트리밍 응답을 반환합니다."""
    try:
        data = request.json
        user_prompt = data.get('prompt')
        if not user_prompt:
            return Response(json.dumps({"error": "No prompt provided"}), status=400, mimetype='application/json')

        # 현재 세션의 대화 기록 불러오기
        current_history = session.get('messages', [])
        
        # 스트림 응답을 위한 제너레이터 함수
        def generate_stream():
            try:
                # Gemini 스트림 생성
                response_stream = get_gemini_response_stream(user_prompt, current_history)
                
                full_ai_response = []
                for chunk in response_stream:
                    if chunk.text:
                        full_ai_response.append(chunk.text)
                        yield chunk.text
                
                # 스트림 종료 후, 전체 응답을 세션에 저장
                final_text = "".join(full_ai_response)
                
                # 세션 업데이트 (중요: session.modified = True가 필요할 수 있음)
                current_history.append({"role": "user", "content": user_prompt})
                current_history.append({"role": "assistant", "content": final_text})
                session['messages'] = current_history
                # session.modified = True # 리스트 등 변경 시 명시적 표시

            except Exception as e:
                print(f"스트리밍 중 오류: {e}")
                yield f"AI 응답 중 서버 오류가 발생했습니다: {e}"

        # Flask의 Streaming Response 반환
        return Response(generate_stream(), mimetype='text/plain')

    except Exception as e:
        print(f"채팅 요청 처리 중 오류: {e}")
        return Response(json.dumps({"error": str(e)}), status=500, mimetype='application/json')

# --- 8. Flask 앱 실행 ---
if __name__ == '__main__':
    # host='0.0.0.0'으로 설정하면 외부에서도 접속 가능합니다.
    app.run(debug=True, host='0.0.0.0', port=5001)