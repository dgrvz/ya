from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import json
import google.generativeai as genai
from typing import List, Optional

# --- FIX IMPORTS FOR VERCEL ---
import sys
try:
    # Пытаемся импортировать локально (когда запускаем python api/index.py)
    from .roles import PROMPTS
except ImportError:
    # Пытаемся импортировать в облаке (Vercel добавляет api/ в path)
    try:
        from roles import PROMPTS
    except ImportError:
        # Фоллбэк: добавляем текущую директорию в path
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from roles import PROMPTS
# ------------------------------

app = FastAPI()

# Конфигурация Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

genai.configure(api_key=GOOGLE_API_KEY)

class AgentRequest(BaseModel):
    agent: str
    user_input: str
    history: List[dict]

class AgentResponse(BaseModel):
    thought: str
    content: str
    next_agent: str
    code_snippet: Optional[str] = None

@app.post("/api/chat")
async def chat_handler(request: AgentRequest):
    if not GOOGLE_API_KEY:
        raise HTTPException(status_code=500, detail="GOOGLE_API_KEY not set on Vercel Environment Variables")

    if request.agent not in PROMPTS:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {request.agent}")

    # Используем модель
    model = genai.GenerativeModel(
        'gemini-1.5-pro-latest',
        system_instruction=PROMPTS[request.agent],
        generation_config={"response_mime_type": "application/json"}
    )

    try:
        # Формируем историю. Важно: Gemini API требует чередование user/model
        # Если история пустая или битая, начинаем новую
        history_payload = request.history if request.history else []
        
        chat = model.start_chat(history=history_payload)
        
        message_to_send = request.user_input if request.user_input else f"Attention {request.agent}. Proceed with your task based on context."

        response = chat.send_message(message_to_send)
        
        # Парсинг ответа
        try:
            response_json = json.loads(response.text)
        except json.JSONDecodeError:
            # Если модель вернула не чистый JSON (бывает редко)
            response_json = {
                "thought": "Error parsing JSON",
                "content": response.text,
                "next_agent": "Producer"
            }
        
        # Извлечение кода
        code_snippet = None
        content_text = response_json.get("content", "")
        if "```html" in content_text:
            code_snippet = content_text.split("```html")[1].split("```")[0]
        elif "<!DOCTYPE html>" in content_text:
             code_snippet = content_text

        return AgentResponse(
            thought=response_json.get("thought", "Thinking..."),
            content=response_json.get("content", ""),
            next_agent=response_json.get("next_agent", "Producer"),
            code_snippet=code_snippet
        )

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))