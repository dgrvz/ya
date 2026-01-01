from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import json
import google.generativeai as genai
from typing import List, Optional

# Импорт ролей
try:
    from .roles import PROMPTS
except ImportError:
    from roles import PROMPTS

app = FastAPI()

# Конфигурация Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("WARNING: GOOGLE_API_KEY is missing")

genai.configure(api_key=GOOGLE_API_KEY)

# Модель данных для запроса
class ChatMessage(BaseModel):
    role: str
    parts: List[str]

class AgentRequest(BaseModel):
    agent: str
    user_input: str
    history: List[dict] # История в формате Gemini

class AgentResponse(BaseModel):
    thought: str
    content: str
    next_agent: str
    code_snippet: Optional[str] = None

@app.post("/api/chat")
async def chat_handler(request: AgentRequest):
    if request.agent not in PROMPTS:
        raise HTTPException(status_code=400, detail="Unknown agent")

    # 1. Подготовка модели
    # Используем Pro, так как нужна сложная логика маршрутизации
    model = genai.GenerativeModel(
        'gemini-1.5-pro-latest',
        system_instruction=PROMPTS[request.agent],
        generation_config={"response_mime_type": "application/json"}
    )

    # 2. Формирование истории чата
    # Мы конвертируем историю из формата фронтенда в формат Gemini SDK
    # Примечание: В реальной системе историю нужно сжимать, если она огромная
    chat = model.start_chat(history=request.history)

    # 3. Добавление текущего ввода
    # Если это первый запуск (Producer), добавляем ввод пользователя
    # Если это передача хода, ввод может быть пустым, но контекст уже в истории
    message_to_send = request.user_input if request.user_input else f"Attention {request.agent}. Previous agent handed off work to you. Review history and execute your task."

    try:
        response = chat.send_message(message_to_send)
        response_json = json.loads(response.text)
        
        # Попытка извлечь код из контента, если он там есть (для превью)
        code_snippet = None
        content_text = response_json.get("content", "")
        if "```html" in content_text:
            try:
                code_snippet = content_text.split("```html")[1].split("```")[0]
            except:
                pass
        elif "<html>" in content_text:
             code_snippet = content_text

        return AgentResponse(
            thought=response_json.get("thought", "No thought provided"),
            content=response_json.get("content", "No content provided"),
            next_agent=response_json.get("next_agent", "Producer"), # Fallback to Producer
            code_snippet=code_snippet
        )

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)