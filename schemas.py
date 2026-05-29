from enum import Enum
from pydantic import BaseModel
import httpx

url = "http://localhost:11434/api/tags"
resp = httpx.get(url)

language_models = {
    model["name"].replace(":", "_").replace(".", "_").replace("-", "_"): model["name"]
    for model in resp.json()["models"]
}

ModelEnum = Enum("ModelEnum", language_models, type=str)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    system: str | None = None
