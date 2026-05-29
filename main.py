from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import httpx
import json
from schemas import ChatMessage, ModelEnum


app = FastAPI()


@app.get("/")
def greet():
    return {"message": "Arise"}


@app.get("/models")
def list_language_models():
    url = "http://localhost:11434/api/tags"
    resp = httpx.get(url)
    models = [model["name"] for model in resp.json()["models"]]
    return models


@app.post("/chat")
def chat_with_language_model(model: ModelEnum, chat_message: ChatMessage):
    payload = {
        "model": model.value,
        "messages": [{"role": "user", "content": chat_message.message}],
        "stream": False,
    }

    url = "http://localhost:11434/api/chat"

    resp = httpx.post(url, json=payload)

    return {"message": resp.json()["message"]["content"]}


@app.post("/chat/stream")
def stream_chat_with_language_model(model: ModelEnum, chat_message: ChatMessage):
    payload = {
        "model": model.value,
        "messages": [{"role": "user", "content": chat_message.message}],
        "stream": True,
    }

    def generate():
        with httpx.stream(
            "POST", "http://localhost:11434/api/chat", json=payload, timeout=None
        ) as r:
            for line in r.iter_lines():
                if line:
                    data = json.loads(line)
                    if not data.get("done"):
                        yield data["message"]["content"]

    return StreamingResponse(generate(), media_type="text/plain")
