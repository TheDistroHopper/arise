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
        resp = httpx.post("http://localhost:8000/chat", params=params, json=payload)
    except Exception as e:
        resp = None
        print(f"ERROR: {e}")
    if resp and resp.status_code == 200:
        return resp.json()["message"]
    return "ERROR"


with st.sidebar:
    st.title(":material/robot: Arise")
    models = get_models()
    selected_model = st.selectbox("Select Model", models, label_visibility="collapsed")

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

    response = get_model_response(prompt, selected_model)
    with st.chat_message("assistant"):
        st.markdown(response)
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response})
