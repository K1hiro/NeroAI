# NeroAI

A local AI chatbot built with Python, Ollama, and Qwen3 4B Instruct.

## Features

- Streamlit web interface
- Conversation history within the current session
- New chat button to reset the conversation
- Reusable Python backend
- English-language responses
- Response time displayed for the newest answer
- Model context limited to the latest 20 history messages

## Architecture

Streamlit → Python backend → Ollama → Qwen3

The interface handles user interaction and session history.
The backend sends messages to Ollama and returns model responses.

Development and testing currently run on a MacBook Air M5.

## Project Structure

- `app.py` — Streamlit interface, session history, and response timing
- `llm_backend.py` — communication with Ollama
- `requirements.txt` — Python dependencies and versions
- `.gitignore` — files excluded from Git
- `README.md` — project documentation

## Run Locally

Requires Python 3.10 or newer, Ollama, and the
`qwen3:4b-instruct` model.

From the project folder on macOS, create and activate a virtual
environment, then install the dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If `.venv` already exists, skip the creation command.

Ensure Ollama is running and confirm the model is installed:

```bash
ollama list
```

Start the web app:

```bash
python -m streamlit run app.py
```

Open the Local URL shown in the terminal.

## Conversation Context

The interface displays the conversation from the current session.

For each request, the backend sends:

1. The system instruction
2. Up to 20 recent history messages
3. The user's new question

In the current app, 20 history messages represent 10 complete
user-assistant exchanges. Older messages remain visible but are
excluded from subsequent model requests.

The New chat button clears the session's conversation history.

## Manual Checks Completed

- Backend returns a model response.
- Web interface displays questions and answers.
- Follow-up questions use conversation history.
- New chat clears the conversation context.
- A test with 22 history messages produced a response consistent
  with excluding the oldest exchange.
- Response time appears below the newest answer.

## Initial Performance Observations

Tested locally on a MacBook Air M5 using `qwen3:4b-instruct`.

Two consecutive requests for a one-sentence explanation of
machine learning took 1.73 and 1.32 seconds.

Timing measures the complete Python backend call, including
communication with Ollama and answer generation.

These are preliminary observations, not a controlled benchmark.
Conversation history and generated answers differed between requests.

## Current Limitations

- Conversations are not saved permanently.
- Answers may contain factual errors.
- No web search or external knowledge retrieval.
- History is limited to 20 messages, but individual message length
  and total token count are not yet capped.
- Answers appear only after generation finishes.
- Response timing is not stored in conversation history.
- Errors display a general message rather than a specific diagnosis.

## Planned Development

Integrate a Discord bot using the same Python backend.

Deploy the Discord bot and Ollama on an ASUS ROG server so the
bot can operate independently of the MacBook.

Verify operating system, Python version, hardware, and dependency
compatibility during server setup.