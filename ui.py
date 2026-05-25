import streamlit as st
import httpx


def get_greeting():
    try:
        resp = httpx.get("http://localhost:8000/")
    except Exception as e:
        resp = None
        print(f"ERROR: {e}")
    if resp and resp.status_code == 200:
        return resp.json()["message"]
    return "ERROR"


st.title("Arise")
msg = get_greeting()
if not msg == "ERROR":
    st.badge("Let's warm up", icon=":material/check:", color="green")
else:
    st.badge(
        "It seems you are down. Get some rest.", icon=":material/sleep:", color="red"
    )
