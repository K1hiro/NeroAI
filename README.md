# NeroAI

A local AI chatbot built with Python, Ollama, and Qwen3 4B Instruct.

I built NeroAI to learn how to integrate a language model into an application, manage conversation history, and retrieve information from reference documents. The project started as a Streamlit app and now includes a Discord bot running independently on a separate laptop.

## Features

- Streamlit chat interface with session history and response timing
- Discord slash commands for chat, memory reset, and document lookup
- SQLite conversation persistence, isolated by user and channel
- Local document retrieval with source references
- Request queuing and per-user cooldowns
- Permission-checked Discord moderation commands
- Local model inference using an NVIDIA GPU on the Discord host

## Tools and Technologies

| Technology | Purpose |
|---|---|
| Python | Application logic and backend integration |
| Ollama | Local model serving |
| Qwen3 4B Instruct | Response generation |
| Streamlit | Web chat interface |
| discord.py | Discord integration and slash commands |
| SQLite | Conversation history and warning records |
| scikit-learn | TF-IDF vectorization and cosine similarity |
| asyncio | Asynchronous request coordination |
| python-dotenv | Local configuration and credentials |
| Ubuntu / WSL 2 | Linux environment on the Windows host |
| systemd | Background service management |
| Git, GitHub, and GitHub CLI | Version control, remote storage, and authentication |

Development tools include VS Code, Windows Terminal, and GNU nano. Python dependencies are managed using `venv`, pip, and a pinned `requirements.txt`.

## Architecture

```text
Streamlit → Shared Python backend → Ollama → Qwen3

Discord /ask → Conversation history → Shared backend → Ollama
                    ↕
                  SQLite

Discord /lookup → Document retrieval → Reference passages → Ollama
                                                              ↓
                                                     Answer with sources
```

The Streamlit interface manages its own session history. The Discord bot stores conversation history in SQLite.

AI requests from Discord share a processing lock, allowing one request at a time. Up to five requests can be pending, including the active request. A ten-second cooldown applies per user across `/ask` and `/lookup`.

Blocking model and database operations run in worker threads to keep the Discord connection responsive.

## Conversation Memory

For each general chat request, the backend sends:

1. A system instruction
2. Up to 20 recent history messages
3. The user's new question

In Streamlit, older messages remain visible in the session but are excluded from later model requests. The New chat button clears the session history.

In Discord, the latest 20 messages are retained for each user and channel. This history survives bot restarts. `/reset` clears only the requesting user's conversation in the current channel.

Memory isolation does not make responses private: replies remain visible to people who can read the channel.

## Document Retrieval

The `/lookup` command uses a basic retrieval-augmented generation pipeline:

1. Read text files from `knowledge/`.
2. Split documents into sections at `##` headings.
3. Represent passages using TF-IDF.
4. Rank them using cosine similarity against the question.
5. Supply up to three passages above the similarity threshold to Qwen3.
6. Return an answer with citations and source labels.

The reference collection currently covers machine learning notes, an artist profile, and Indonesian furry conventions.

Each lookup is independent and does not use conversation history. The model is instructed to acknowledge when the references do not contain an answer.

## Discord Commands

| Command | Purpose |
|---|---|
| `/ask question` | Chat with persistent conversation memory |
| `/reset` | Clear your saved history in the current channel |
| `/lookup question` | Answer using local reference documents |
| `/warn member reason` | Record a warning in SQLite |
| `/mute member minutes reason` | Apply a timed Discord timeout |
| `/kick member reason` | Remove a member from the server |
| `/ban member reason` | Ban a member while preserving message history |

Moderation commands check the caller's permissions and role hierarchy. Timeout, kick, and ban actions also check the bot's permissions and role position.

Moderation actions are explicitly requested by a moderator; they are not decided by the language model. Warning records are separate from chat history and are not removed by `/reset`.

## Project Structure

```text
NeroAI/
├── app.py                    # Streamlit interface
├── llm_backend.py            # Shared Ollama backend
├── discord_bot.py            # Slash commands and request management
├── memory_store.py           # SQLite conversation storage
├── rag_retriever.py           # Document loading and ranking
├── rag_backend.py             # Reference-grounded response generation
├── moderation_commands.py    # Moderation actions and permission checks
├── moderation_store.py       # Warning storage
├── knowledge/                # Reference documents
├── requirements.txt          # Python dependencies
├── .gitignore
└── README.md
```

The local `.env`, `.venv/`, and `data/` directory are excluded from Git.

## Run Locally

### Prerequisites

- Python; the Discord deployment was tested with Python 3.14.4
- [Ollama](https://ollama.com/download)
- The `qwen3:4b-instruct` model
- A Discord application and test server if using the bot

Compatibility with other Python versions has not been comprehensively tested.

### Set up Python

From the project folder on macOS or Ubuntu:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If `.venv` already exists, skip the creation command.

### Prepare Ollama

Ensure Ollama is running, then download the model:

```bash
ollama pull qwen3:4b-instruct
```

The backend connects to:

```text
http://localhost:11434
```

### Start Streamlit

```bash
python -m streamlit run app.py
```

Open the Local URL shown in the terminal.

### Start the Discord bot

Create an application in the [Discord Developer Portal](https://discord.com/developers/applications) and install it in a test server with the `bot` and `applications.commands` scopes.

Create a `.env` file in the project folder:

```dotenv
DISCORD_TOKEN=your_bot_token
DISCORD_GUILD_ID=your_test_server_id
```

Give the bot access to the intended channels and enable the moderation permissions needed for your deployment. Its highest role must be above members it times out, kicks, or bans.

Run:

```bash
python discord_bot.py
```

Slash commands are registered in the server specified by `DISCORD_GUILD_ID`. The current slash-command implementation does not require Message Content Intent.

Keep the bot token private and never commit `.env`.

## Adding Reference Documents

Place UTF-8 `.txt` files inside `knowledge/`:

```text
Title: Example Reference

## Topic Name
Write a self-contained passage about the topic.

Source:
https://example.com/reference
```

Documents are read on each lookup, so no separate indexing command is required.

Text before the first `##` heading is not retrieved. Include relevant dates, context, and source URLs within the individual sections.

## Development and Deployment

The original Streamlit application was developed and tested on a **MacBook Air M5**.

The Discord bot and Ollama run on an **ASUS ROG G531GU**:

- Windows 11 with Ubuntu through WSL 2
- Intel Core i7-9750H
- NVIDIA GTX 1660 Ti with 6 GB VRAM
- 16 GB RAM

The bot is configured as a systemd service on this host. Windows sign-in startup through Task Scheduler remains unfinished.

## Manual Checks Completed

### Chat and memory

- Backend returns model responses.
- Streamlit displays questions, answers, and response timing.
- Follow-up questions use conversation history.
- New chat and `/reset` clear the intended history.
- SQLite conversations survive bot restarts.
- Different users and channels have separate histories.
- History truncation excludes older exchanges.

### Retrieval and request handling

- Relevant passages are retrieved from all three reference files.
- Answers include the expected facts and source citations.
- Missing-information questions receive an appropriate response.
- Cooldowns reject requests sent too quickly.
- Waiting requests receive answers after the active request finishes.

### Moderation

- Warnings are saved in SQLite.
- Timeouts prevent messaging and expire automatically.
- Kicked members can rejoin through an invite.
- Ordinary members do not see restricted moderation commands.
- Self-warning, self-mute, self-kick, and self-ban attempts are rejected.

A successful ban has not been verified. The test attempt was rejected because the bot lacked Ban Members permission, which was intentionally left disabled.

These checks are manual development tests, not comprehensive automated or security testing.

## Initial Performance Observations

On the MacBook Air M5, two consecutive requests for a one-sentence explanation of machine learning took **1.73 and 1.32 seconds**. These measurements covered the complete Python backend call.

On the ROG, Ollama reported **100% GPU** model loading. One warm-model test took approximately **1.47 seconds**, generating **54.34 tokens per second** with a mostly cached prompt.

These are preliminary observations, not a controlled comparison between the machines.

## Current Limitations

- Model answers can contain factual errors.
- Citations are generated by the model and are not automatically verified.
- TF-IDF depends on word overlap and can miss differently phrased questions.
- The retrieved-source list includes all supplied passages, not only those cited.
- `/lookup` does not use conversation history or live web search.
- History is limited by message count rather than total tokens.
- Replies are sent after generation finishes.
- Queued requests and cooldowns do not survive restarts.
- Long-running requests may exceed Discord's interaction response window.
- Warning management, `/unmute`, and `/unban` are not implemented.
- Broader permission, failure-recovery, and load testing remains pending.

## Next Steps

- Add automated tests for storage, retrieval, and moderation checks.
- Build an evaluation dataset for retrieval accuracy and answer grounding.
- Measure response latency and resource usage under different workloads.
- Compare TF-IDF with embedding-based retrieval.
- Improve context limits, queue handling, and deployment reliability.

## What I Learned

Building NeroAI gave me practical experience connecting a local language model to user-facing applications, managing persistent state, and coordinating asynchronous requests.

The retrieval work also highlighted an important distinction: finding a relevant passage does not guarantee the model will use it correctly. Evaluating retrieval and generated answers separately is a priority for the next stage of the project.
