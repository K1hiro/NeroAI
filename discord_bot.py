import asyncio
import os
import time

import discord
from dotenv import load_dotenv

from llm_backend import MAX_HISTORY_MESSAGES, generate_reply
from memory_store import (
    clear_history,
    initialize_database,
    load_history,
    save_turn,
)
from rag_backend import generate_grounded_reply

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from .env")

initialize_database()

COOLDOWN_SECONDS = 10
MAX_PENDING_REQUESTS = 5

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(
    intents=intents,
    allowed_mentions=discord.AllowedMentions.none(),
)

conversation_locks: dict[tuple[int, int], asyncio.Lock] = {}
last_request_times: dict[int, float] = {}

processing_lock = asyncio.Lock()
pending_requests = 0


@client.event
async def on_ready():
    print(f"Connected to Discord as {client.user}", flush=True)


async def answer_question(message, question, command):
    channel_id = message.channel.id
    user_id = message.author.id

    try:
        async with message.channel.typing():
            if command == "!lookup":
                reply = await asyncio.to_thread(
                    generate_grounded_reply,
                    question,
                )
            else:
                history = await asyncio.to_thread(
                    load_history,
                    channel_id,
                    user_id,
                    limit=MAX_HISTORY_MESSAGES,
                )

                reply = await asyncio.to_thread(
                    generate_reply,
                    question,
                    history=history,
                )

            reply = (reply or "").strip()
            if not reply:
                await message.channel.send(
                    "The model returned an empty response."
                )
                return

            # Only general chat is stored in conversation memory.
            if command == "!ask":
                await asyncio.to_thread(
                    save_turn,
                    channel_id,
                    user_id,
                    question,
                    reply,
                    limit=MAX_HISTORY_MESSAGES,
                )

    except Exception as error:
        print(
            f"Request error: {type(error).__name__}: {error}",
            flush=True,
        )
        await message.channel.send(
            "Sorry, I couldn't complete your request. Please try again."
        )
        return

    for start in range(0, len(reply), 1900):
        await message.channel.send(reply[start:start + 1900])


@client.event
async def on_message(message: discord.Message):
    global pending_requests

    if message.author.bot:
        return

    parts = message.content.strip().split(maxsplit=1)
    if not parts:
        return

    command = parts[0].lower()
    if command not in ("!ask", "!lookup", "!reset"):
        return

    channel_id = message.channel.id
    user_id = message.author.id
    key = (channel_id, user_id)
    conversation_lock = conversation_locks.setdefault(
        key, asyncio.Lock()
    )

    if command == "!reset":
        async with conversation_lock:
            try:
                await asyncio.to_thread(
                    clear_history,
                    channel_id,
                    user_id,
                )
            except Exception as error:
                print(
                    f"Reset error: {type(error).__name__}: {error}",
                    flush=True,
                )
                await message.channel.send(
                    "Sorry, I couldn't clear your memory. Please try again."
                )
                return

            await message.channel.send(
                "Your saved conversation memory in this channel "
                "has been cleared."
            )
        return

    if len(parts) < 2:
        if command == "!lookup":
            example = "!lookup What does IWAG stand for?"
        else:
            example = "!ask Explain overfitting in simple terms."

        await message.channel.send(f"Try: {example}")
        return

    question = parts[1]
    now = time.monotonic()
    last_request = last_request_times.get(user_id)

    if last_request is not None:
        remaining = COOLDOWN_SECONDS - (now - last_request)
        if remaining > 0:
            await message.channel.send(
                f"Please wait {remaining:.1f} seconds "
                "before asking another question."
            )
            return

    if pending_requests >= MAX_PENDING_REQUESTS:
        await message.channel.send(
            "I'm handling several requests right now. "
            "Please try again shortly."
        )
        return

    requests_ahead = pending_requests
    pending_requests += 1
    last_request_times[user_id] = now

    try:
        async with conversation_lock:
            if requests_ahead > 0:
                await message.channel.send(
                    "Your question has been accepted and is waiting "
                    "for the current requests to finish."
                )

            async with processing_lock:
                await answer_question(message, question, command)

    except Exception as error:
        print(
            f"Discord handler error: {type(error).__name__}: {error}",
            flush=True,
        )

    finally:
        pending_requests -= 1


client.run(TOKEN)
