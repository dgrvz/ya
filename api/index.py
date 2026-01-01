from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import json
import sys
import google.generativeai as genai
from typing import List, Optional

# --- IMPORT ROLES FIX ---
try:
    from roles import PROMPTS
except ImportError:
    try:
        from .roles import PROMPTS
    except ImportError:
        sys.path.append(os.path.dirname(os.path.abspath(file)))
        from roles import PROMPTS
# ------------------------

app = FastAPI()

# Читаем HTML файл в память, чтобы не возиться с путями к статике в Vercel
try:
    # Пытаемся найти index.html в разных местах (локально vs vercel)
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(file)))
    public_path = os.path.join(base_path, 'public', 'index.html')
    
    if not os.path.exists(public_path):
        # Fallback для Vercel структуры, если public лежит рядом с api
        public_path = os.path.join(os.path.dirname(os.path.abspath(file)), '..', 'public', 'index.html')

    with open(public_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
except Exception as e:
    html_content = f"<h1>Error loading frontend: {str(e)}</h1>"

# --- ГЛАВНАЯ СТРАНИЦА (FRONTEND) ---
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return html_content

# --- API ENDPOINT ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

class AgentRequest(BaseModel):
    agent: str
    user_input: str
    history: List[dict]

@app.post("/api/chat")
async def chat_handler(request: AgentRequest):
    if not GOOGLE_API_KEY:
        return JSONResponse(status_code=500, content={"error": "API Key not set"})

    if request.agent not in PROMPTS:
        return JSONResponse(status_code=400, content={"error": f"Unknown agent: {request.agent}"})

    model = genai.GenerativeModel(
        'gemini-1.5-pro-latest',
        system_instruction=PROMPTS[request.agent],
        generation_config={"response_mime_type": "application/json"}
    )

    try:
        chat = model.start_chat(history=request.history or [])
        msg = request.user_input if request.user_input else f"Proceed with task. Context is in history."
        response = chat.send_message(msg)
        
        try:
            data = json.loads(response.text)
        except:
            data = {"thought": "Parsing Error", "content": response.text, "next_agent": "Producer"}

        # Extract Code
        code = None
        if "
            code = data["content"].split("
html")[1].split("```")[0]

        return {
            "thought": data.get("thought"),
            "content": data.get("content"),
            "next_agent": data.get("next_agent", "Producer"),
            "code_snippet": code
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})