import json
import streamlit as st
import httpx


TOKEN_EXPLAINER = (
    "**How tokens are counted**\n\n"
    "- **Prompt tokens**: the prompt after the chat template is applied, including "
    "special tokens like `<start_of_turn>` and `<bos>`. That is why a tiny message still "
    "costs several tokens.\n"
    "- **Completion tokens**: tokens in the reply.\n"
    "- **Total tokens**: prompt + completion.\n"
    "- **Tokens / sec**: completion tokens ÷ generation time."
)


@st.dialog("Trace & Metrics", width="large")
def show_trace(trace):
    lvl = trace.get("level")
    if lvl:
        st.badge(f"Level {lvl['n']} · {lvl['name']}", icon=":material/stairs:", color="primary")

    p = trace["params"]
    st.caption(
        f"Model: {p['model']}  ·  temperature: {p['temperature']}  ·  max_tokens: {p['max_tokens']}"
    )

    st.caption("Messages array sent to the API")
    st.code(json.dumps(trace["prompt"], indent=2), language="json")
    if lvl and lvl["n"] == 1:
        st.caption("Level 1 sends only the latest message; prior turns are discarded.")

    s = trace["stats"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Prompt tokens", s["prompt_tokens"])
    c2.metric("Completion tokens", s["completion_tokens"])
    c3.metric("Total tokens", s["total_tokens"])

    c4, c5, c6 = st.columns(3)
    c4.metric("Tokens / sec", s["tokens_per_second"])
    ttft = s["time_to_first_token_s"]
    c5.metric("Time to first token", f"{ttft}s" if ttft is not None else "-")
    c6.metric("Total time", f"{s['total_duration_s']}s")

    st.markdown(TOKEN_EXPLAINER)


def assistant_footer(trace, key):
    if not trace:
        return
    badge, btn = st.columns([0.8, 0.2], vertical_alignment="center")
    lvl = trace.get("level")
    if lvl:
        badge.caption(f":material/stairs: Level {lvl['n']} · {lvl['name']}")
    if btn.button("", key=key, icon=":material/analytics:", help="Trace & metrics"):
        show_trace(trace)


def get_levels():
    try:
        resp = httpx.get("http://localhost:8000/levels")
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"ERROR: {e}")
    return [{"n": 1, "name": "Plain LLM", "available": True, "description": ""}]


def get_template(model):
    try:
        resp = httpx.get("http://localhost:8000/template", params={"model": model})
        if resp.status_code == 200:
            return resp.json()["template"]
    except Exception as e:
        print(f"ERROR: {e}")
    return ""


def get_models():
    try:
        resp = httpx.get("http://localhost:8000/models")
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"ERROR: {e}")
    return []


def get_model_response(messages, model, system, level, temperature, max_tokens):
    params = {"model": model, "level": level, "temperature": temperature, "max_tokens": max_tokens}
    payload = {"messages": messages, "system": system or None}
    try:
        resp = httpx.post(
            "http://localhost:8000/chat", params=params, json=payload, timeout=None
        )
    except Exception as e:
        print(f"ERROR: {e}")
        return None
    if resp.status_code == 200:
        return resp.json()
    return None


def stream_model_response(messages, model, system, level, temperature, max_tokens, holder):
    params = {"model": model, "level": level, "temperature": temperature, "max_tokens": max_tokens}
    payload = {"messages": messages, "system": system or None}

    with httpx.stream(
        "POST", "http://localhost:8000/chat/stream", params=params, json=payload, timeout=None
    ) as r:
        event = None
        for line in r.iter_lines():
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data = json.loads(line[len("data:"):].strip())
                if event == "meta":
                    holder["prompt"] = data["prompt"]
                    holder["params"] = data["params"]
                    holder["level"] = data.get("level")
                elif event == "token":
                    yield data["content"]
                elif event == "stats":
                    holder["stats"] = data
            elif line == "":
                event = None


with st.sidebar:
    st.title(":material/robot: Arise")

    levels = get_levels()
    available = [lv for lv in levels if lv["available"]]
    labels = {lv["n"]: f"Level {lv['n']}: {lv['name']}" for lv in levels}
    selected_level = st.selectbox(
        "Level", [lv["n"] for lv in available], format_func=lambda n: labels[n]
    )
    active = next(lv for lv in levels if lv["n"] == selected_level)
    st.caption(active["description"])

    st.divider()

    models = get_models()
    selected_model = st.selectbox("Select Model", models, label_visibility="collapsed")
    use_stream = st.toggle("Stream", value=True)
    system_prompt = st.text_area("System prompt", value="", placeholder="Empty by default")
    temperature = st.slider("Temperature", 0.0, 2.0, 0.8, 0.1)
    max_tokens = st.number_input("Max tokens", min_value=1, value=512, step=1)

    if selected_model:
        with st.expander("Chat template"):
            st.caption("Messages are rendered into this template before tokenizing.")
            st.code(get_template(selected_model), language="django")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

for i, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and message.get("trace"):
            assistant_footer(message["trace"], key=f"trace_{i}")

# React to user input
prompt = st.chat_input("What is up?")
if prompt:
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # The whole conversation is always sent; the level decides how much is used.
    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]

    with st.chat_message("assistant"):
        trace = None

        if use_stream:
            holder = {}
            response = st.write_stream(
                stream_model_response(
                    history, selected_model, system_prompt, selected_level, temperature, max_tokens, holder
                )
            )
            if "stats" in holder:
                trace = {
                    "prompt": holder["prompt"],
                    "level": holder.get("level"),
                    "params": holder["params"],
                    "stats": holder["stats"],
                }
        else:
            result = get_model_response(
                history, selected_model, system_prompt, selected_level, temperature, max_tokens
            )
            if result:
                response = result["message"]
                trace = {
                    "prompt": result["prompt"],
                    "level": result.get("level"),
                    "params": result["params"],
                    "stats": result["stats"],
                }
            else:
                response = "ERROR"
            st.markdown(response)

        if trace:
            assistant_footer(trace, key=f"trace_{len(st.session_state.messages)}")

    st.session_state.messages.append({"role": "assistant", "content": response, "trace": trace})
