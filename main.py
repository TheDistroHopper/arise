from fastapi import FastAPI
import httpx
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
