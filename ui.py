import streamlit as st
import httpx


def get_models():
    try:
        resp = httpx.get("http://localhost:8000/models")
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"ERROR: {e}")
    return []


def get_model_response(prompt: str, model: str):
    try:
        params = {"model": model}
        payload = {"message": prompt}
        resp = httpx.post(
            "http://localhost:8000/chat", params=params, json=payload, timeout=None
        )
    except Exception as e:
        resp = None
        print(f"ERROR: {e}")
    if resp and resp.status_code == 200:
        return resp.json()["message"]
    return "ERROR"


def stream_model_response(prompt: str, model: str):
    params = {"model": model}
    payload = {"message": prompt}
    with httpx.stream(
        "POST",
        "http://localhost:8000/chat/stream",
        params=params,
        json=payload,
        timeout=None,
    ) as r:
        for chunk in r.iter_text():
            yield chunk


with st.sidebar:
    st.title(":material/robot: Arise")
    models = get_models()
    selected_model = st.selectbox("Select Model", models, label_visibility="collapsed")
    use_stream = st.toggle("Stream", value=True)

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# React to user input
prompt = st.chat_input("What is up?")
if prompt:
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        if use_stream:
            response = st.write_stream(stream_model_response(prompt, selected_model))
        else:
            response = get_model_response(prompt, selected_model)
            st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
