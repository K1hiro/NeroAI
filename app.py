from time import perf_counter

import streamlit as st

from llm_backend import generate_reply


st.set_page_config(page_title="NeroAI", page_icon="🤖")

st.title("🤖 NeroAI")
st.caption("A local AI chatbot powered by Ollama and Qwen3")

if "messages" not in st.session_state:
    st.session_state.messages = []

if st.button("New chat"):
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

user_message = st.chat_input("Ask me anything...")

if user_message:
    with st.chat_message("user"):
        st.write(user_message)

    with st.chat_message("assistant"):
        with st.spinner("NeroAI is thinking..."):
            try:
                start_time = perf_counter()

                reply = generate_reply(
                    user_message,
                    history=st.session_state.messages,
                )

                elapsed_seconds = perf_counter() - start_time

                if not reply or not reply.strip():
                    raise ValueError(
                        "The model returned an empty response."
                    )

            except Exception:
                st.error(
                    "Unable to generate a response. "
                    "Make sure Ollama is running and the model is available."
                )

            else:
                st.write(reply)
                st.caption(
                    f"Response time: {elapsed_seconds:.2f} seconds"
                )

                st.session_state.messages.extend([
                    {"role": "user", "content": user_message},
                    {"role": "assistant", "content": reply},
                ])