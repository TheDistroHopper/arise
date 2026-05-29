from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import httpx
import json
import time
from schemas import ChatMessage, ModelEnum


app = FastAPI()

OLLAMA = "http://localhost:11434"


@app.get("/")
def greet():
    return {"message": "Arise"}


@app.get("/models")
def list_language_models():
    resp = httpx.get(f"{OLLAMA}/api/tags")
    return [model["name"] for model in resp.json()["models"]]


_template_cache = {}


def get_template(model_name):
    if model_name not in _template_cache:
        try:
            resp = httpx.post(f"{OLLAMA}/api/show", json={"model": model_name})
            _template_cache[model_name] = resp.json().get("template", "")
        except Exception:
            _template_cache[model_name] = ""
    return _template_cache[model_name]


@app.get("/template")
def model_template(model: ModelEnum):
    return {"template": get_template(model.value)}


def build_payload(model, chat_message, temperature, max_tokens, stream):
    messages = []
    if chat_message.system:
        messages.append({"role": "system", "content": chat_message.system})
    messages.append({"role": "user", "content": chat_message.message})
    return {
        "model": model.value,
        "messages": messages,
        "stream": stream,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }


def compute_stats(data, ttft_s):
    # Ollama reports all durations in nanoseconds.
    eval_count = data.get("eval_count", 0)
    eval_duration = data.get("eval_duration", 0)
    prompt_eval_count = data.get("prompt_eval_count", 0)
    tokens_per_second = eval_count / (eval_duration / 1e9) if eval_duration else 0
    return {
        "prompt_tokens": prompt_eval_count,
        "completion_tokens": eval_count,
        "total_tokens": prompt_eval_count + eval_count,
        "tokens_per_second": round(tokens_per_second, 2),
        "time_to_first_token_s": round(ttft_s, 3) if ttft_s is not None else None,
        "total_duration_s": round(data.get("total_duration", 0) / 1e9, 3),
        "load_duration_s": round(data.get("load_duration", 0) / 1e9, 3),
        "prompt_eval_duration_s": round(data.get("prompt_eval_duration", 0) / 1e9, 3),
        "eval_duration_s": round(eval_duration / 1e9, 3),
    }


@app.post("/chat")
def chat_with_language_model(
    chat_message: ChatMessage,
    model: ModelEnum,
    temperature: float = 0.8,
    max_tokens: int = 512,
):
    payload = build_payload(model, chat_message, temperature, max_tokens, stream=False)

    resp = httpx.post(f"{OLLAMA}/api/chat", json=payload, timeout=None)
    data = resp.json()

    ttft = (data.get("load_duration", 0) + data.get("prompt_eval_duration", 0)) / 1e9

    return {
        "message": data["message"]["content"],
        "prompt": payload["messages"],
        "params": {"model": model.value, "temperature": temperature, "max_tokens": max_tokens},
        "stats": compute_stats(data, ttft),
    }


@app.post("/chat/stream")
def stream_chat_with_language_model(
    chat_message: ChatMessage,
    model: ModelEnum,
    temperature: float = 0.8,
    max_tokens: int = 512,
):
    payload = build_payload(model, chat_message, temperature, max_tokens, stream=True)

    def sse(event, data):
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    def generate():
        yield sse(
            "meta",
            {
                "prompt": payload["messages"],
                "params": {"model": model.value, "temperature": temperature, "max_tokens": max_tokens},
            },
        )

        start = time.perf_counter()
        ttft = None

        with httpx.stream("POST", f"{OLLAMA}/api/chat", json=payload, timeout=None) as r:
            for line in r.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if data.get("done"):
                    yield sse("stats", compute_stats(data, ttft))
                else:
                    if ttft is None:
                        ttft = time.perf_counter() - start
                    yield sse("token", {"content": data["message"]["content"]})

    return StreamingResponse(generate(), media_type="text/event-stream")
