import json
import os
from urllib.parse import urlparse

import requests
import streamlit as st

st.set_page_config(
    page_title="IF Starter Chatbot",
    page_icon="💬",
    layout="centered",
)

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful, clear, and thoughtful assistant. Answer directly, "
    "ask clarifying questions when needed, and use formatting that makes "
    "complex answers easy to follow."
)
MAX_MESSAGE_LENGTH = 12_000


def offline_reply(prompt: str) -> str:
    """Return a transparent, lightweight response when no AI service is used."""
    text = prompt.strip()
    lowered = text.lower()

    if any(word in lowered for word in ("hello", "hi", "hey", "good morning", "good evening")):
        return (
            "Hello! I’m running in offline demo mode, so I can’t generate answers "
            "like a connected AI model. You can still try the chat interface, or "
            "select **OpenAI-compatible API** in the sidebar to connect a model."
        )

    if any(word in lowered for word in ("brainstorm", "ideas", "idea for")):
        return (
            "I’m in offline demo mode, but here’s a simple way to get started:\n\n"
            "1. Describe the goal and who it is for.\n"
            "2. Generate a few different approaches.\n"
            "3. Compare them by effort, impact, and risk.\n"
            "4. Choose one small experiment to validate first.\n\n"
            f"Your starting point: “{text[:400]}”"
        )

    if any(word in lowered for word in ("plan", "steps", "roadmap", "how do i", "how to")):
        return (
            "I’m in offline demo mode, so I can’t reason about this in depth. "
            "A useful general approach is:\n\n"
            "1. Define the desired outcome.\n"
            "2. List constraints, resources, and open questions.\n"
            "3. Break the work into small, verifiable steps.\n"
            "4. Start with the highest-risk assumption.\n"
            "5. Review progress and adjust.\n\n"
            f"For your request — “{text[:400]}” — what outcome matters most?"
        )

    return (
        "I received your message, but this app is currently in **offline demo mode**. "
        "Offline replies are examples rather than AI-generated answers. To get a "
        "context-aware response, choose **OpenAI-compatible API** in the sidebar "
        "and provide your API settings.\n\n"
        f"Your message: “{text[:700]}”"
    )


def call_compatible_api(messages: list[dict], base_url: str, model: str, api_key: str) -> str:
    """Call a Chat Completions-compatible endpoint without saving credentials."""
    parsed = urlparse(base_url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Enter a valid API base URL beginning with https:// or http://.")

    url = base_url.strip().rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"model": model.strip(), "messages": messages},
        timeout=60,
    )

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if not response.ok:
        detail = payload.get("error", {}).get("message") if isinstance(payload, dict) else None
        detail = detail or f"The API returned HTTP {response.status_code}."
        raise RuntimeError(detail)

    try:
        answer = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("The API response did not contain a chat message.")

    if isinstance(answer, list):
        answer = "\n".join(
            part.get("text", "") for part in answer if isinstance(part, dict)
        )
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("The API returned an empty response.")
    return answer.strip()


def export_text(messages: list[dict]) -> str:
    lines = []
    for message in messages:
        label = "You" if message["role"] == "user" else "Assistant"
        lines.append(f"## {label}\n\n{message['content']}")
    return "\n\n---\n\n".join(lines)


if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("💬 IF Starter Chatbot")
st.caption("A simple, extensible chatbot starter project built with Streamlit.")

with st.sidebar:
    st.header("Settings")
    backend = st.radio(
        "Response mode",
        ["Offline demo", "OpenAI-compatible API"],
        help="Offline mode needs no credentials. API mode connects to a compatible chat endpoint.",
    )

    api_base_url = "https://api.openai.com/v1"
    api_model = "gpt-4o-mini"
    api_key = ""

    if backend == "OpenAI-compatible API":
        api_base_url = st.text_input(
            "API base URL",
            value="https://api.openai.com/v1",
            help="Use the API base URL, such as https://api.openai.com/v1.",
        )
        api_model = st.text_input("Model", value="gpt-4o-mini")
        api_key = st.text_input(
            "API key",
            type="password",
            value=os.environ.get("OPENAI_API_KEY", ""),
            help="Used for this Streamlit session only; it is not written to project files.",
        )
        st.caption("Your key is sent only to the API endpoint you specify.")

    system_prompt = st.text_area(
        "Assistant instructions",
        value=DEFAULT_SYSTEM_PROMPT,
        height=130,
        help="These instructions are sent as the system message in API mode.",
    )

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Clear chat", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
    with col_b:
        st.download_button(
            "Export chat",
            data=export_text(st.session_state.messages),
            file_name="chat-history.md",
            mime="text/markdown",
            use_container_width=True,
            disabled=not st.session_state.messages,
        )

    st.divider()
    if backend == "Offline demo":
        st.info("Offline demo mode is active. No external requests are made.")
    elif api_key.strip():
        st.success("API mode is ready. Your key remains in session memory.")
    else:
        st.warning("Add an API key to send messages in API mode.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Send a message", max_chars=MAX_MESSAGE_LENGTH)
if prompt:
    prompt = prompt.strip()
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                try:
                    if backend == "Offline demo":
                        answer = offline_reply(prompt)
                    elif not api_key.strip():
                        answer = "Add an API key in the sidebar to use API mode, or switch to Offline demo mode."
                    elif not api_model.strip():
                        answer = "Enter a model name in the sidebar before sending a message."
                    else:
                        api_messages = [{"role": "system", "content": system_prompt.strip() or DEFAULT_SYSTEM_PROMPT}]
                        api_messages.extend(st.session_state.messages[-30:])
                        answer = call_compatible_api(
                            api_messages,
                            api_base_url,
                            api_model,
                            api_key.strip(),
                        )
                except ValueError as exc:
                    answer = f"**Settings error:** {exc}"
                except RuntimeError as exc:
                    answer = f"**API error:** {exc}"
                except requests.RequestException as exc:
                    answer = (
                        "**Connection error:** The API request could not be completed. "
                        "Check the endpoint and your network, then try again. "
                        f"Details: {exc.__class__.__name__}."
                    )
                except Exception:
                    answer = "**Unexpected error:** The response could not be generated. Please check your settings and try again."
            st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
else:
    if not st.session_state.messages:
        st.markdown("#### Try a starter prompt")
        examples = [
            "Help me plan a small project",
            "Brainstorm ideas for a team activity",
            "How can I make a daily routine?",
        ]
        cols = st.columns(len(examples))
        for index, example in enumerate(examples):
            with cols[index]:
                if st.button(example, key=f"starter_{index}", use_container_width=True):
                    st.session_state.messages.append({"role": "user", "content": example})
                    st.rerun()

st.caption("Built with Streamlit · Chat history is kept in session memory and can be cleared at any time.")
