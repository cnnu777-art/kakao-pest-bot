"""
카카오톡 병해충 진단 챗봇 Flask 서버 (Gemini 버전)
===================================================
설치: pip install flask google-generativeai gunicorn
실행: python app.py
"""

import os
import google.generativeai as genai
from flask import Flask, request, jsonify
import requests
import base64

app = Flask(__name__)
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")


# ─────────────────────────────────────────────
# Gemini Vision 진단 함수
# ─────────────────────────────────────────────
def diagnose_image(image_url: str) -> str:
    try:
        # 이미지 다운로드
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(image_url, headers=headers, timeout=10)
        image_data = base64.b64encode(resp.content).decode("utf-8")
        mime_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]

        prompt = """당신은 농촌진흥청 NCPMS 기준의 농업 병해충 전문 AI입니다.
사진을 보고 아래 형식으로만 답변하세요.

🌱 진단 결과
병해충: [이름 또는 '정상']
신뢰도: [0~100]%
심각도: [낮음/중간/높음/없음]

📋 상태 설명
[2~3문장 설명]

💊 권장 조치
1. [조치1]
2. [조치2]
3. [조치3]

⚠️ 주의사항
[주의사항. 없으면 '특이사항 없음']"""

        response = model.generate_content([
            prompt,
            {"mime_type": mime_type, "data": image_data}
        ])
        return response.text.strip()

    except Exception as e:
        print(f"이미지 진단 오류: {str(e)}")
        return "⚠️ 사진 분석 중 오류가 발생했어요. 다시 시도해 주세요."


def answer_text(utterance: str) -> str:
    try:
        prompt = f"""당신은 친근한 농업 병해충 전문 AI입니다.
병해충과 무관한 질문엔 '저는 병해충 진단 전문이에요! 작물 사진을 보내주시면 바로 진단해드려요 🌱'라고만 답하세요.
질문: {utterance}"""
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return "저는 병해충 진단 전문이에요! 작물 사진을 보내주시면 바로 진단해드려요 🌱"


# ─────────────────────────────────────────────
# 카카오 응답 형식
# ─────────────────────────────────────────────
def kakao_text(text: str) -> dict:
    return {"version": "2.0", "template": {"outputs": [{"simpleText": {"text": text}}]}}


def kakao_result(text: str) -> dict:
    return {
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": text}}],
            "quickReplies": [
                {"label": "📸 다른 사진 진단", "action": "message", "messageText": "진단 시작"},
                {"label": "💊 방제약 추천", "action": "message", "messageText": "방제약 추천"},
                {"label": "📖 사용법", "action": "message", "messageText": "사용법"},
            ]
        }
    }


# ─────────────────────────────────────────────
# 이미지 URL 추출
# ─────────────────────────────────────────────
def extract_image_url(body: dict) -> str:
    utterance = body.get("userRequest", {}).get("utterance", "")
    params = body.get("action", {}).get("params", {})
    detail_params = body.get("action", {}).get("detailParams", {})

    if "image" in params:
        return params["image"]
    if "secureImage" in params:
        return params["secureImage"]
    for key, val in detail_params.items():
        if isinstance(val, dict) and "value" in val:
            v = val["value"]
            if isinstance(v, str) and v.startswith("http"):
                return v
    if utterance.startswith("http"):
        return utterance
    return None


# ─────────────────────────────────────────────
# 웹훅
# ─────────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        body = request.get_json(force=True)
        utterance = body.get("userRequest", {}).get("utterance", "").strip()
        image_url = extract_image_url(body)

        if image_url:
            result = diagnose_image(image_url)
            return __import__('flask').jsonify(kakao_result(result))

        if utterance in ["시작", "안녕", "안녕하세요", "도움말"]:
            return __import__('flask').jsonify(kakao_text(
                "안녕하세요! 🌱 농작물 병해충 AI 진단 챗봇입니다.\n\n"
                "📸 병든 작물 사진을 전송하시면\n"
                "10초 내에 진단 결과를 알려드려요!\n\n"
                "• 병해충 종류 진단\n"
                "• 감염 심각도 분석\n"
                "• 방제 방법 추천"
            ))

        if utterance == "사용법":
            return __import__('flask').jsonify(kakao_text(
                "📖 사용법\n\n"
                "1️⃣ 병든 잎·줄기·열매 가까이 촬영\n"
                "2️⃣ 이 채팅창에 사진 전송\n"
                "3️⃣ 10초 내 AI 진단 결과 수신\n\n"
                "💡 병반이 선명할수록 정확도가 높아요!"
            ))

        if utterance in ["방제약 추천", "진단 시작"]:
            return __import__('flask').jsonify(kakao_text(
                "📸 병든 작물 사진을 보내주시면 바로 진단해드릴게요!"
            ))

        return __import__('flask').jsonify(kakao_text(answer_text(utterance)))

    except Exception as e:
        print(f"오류: {str(e)}")
        return __import__('flask').jsonify(kakao_text("⚠️ 오류가 발생했어요. 다시 시도해 주세요."))


@app.route("/health", methods=["GET"])
def health():
    return __import__('flask').jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(debug=False, host="0.0.0.0", port=port)
