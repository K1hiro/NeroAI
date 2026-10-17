import asyncio
import os

import discord
from dotenv import load_dotenv

from llm_backend import MAX_HISTORY_MESSAGES, generate_reply
from memory_store import (
    clear_history,
    initialize_database,
    load_history,
    save_turn,
)

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from .env")

initialize_database()

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(
    intents=intents,
    allowed_mentions=discord.AllowedMentions.none(),
)

# Keep requests from the same user in the same channel in order.
conversation_locks: dict[tuple[int, int], asyncio.Lock] = {}


@client.event
async def on_ready():
    print(f"Connected to Discord as {client.user}", flush=True)


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    parts = message.content.strip().split(maxsplit=1)
    if not parts:
        return

    command = parts[0].lower()
    if command not in ("!ask", "!reset"):
        return

    channel_id = message.channel.id
    user_id = message.author.id
    key = (channel_id, user_id)
    lock = conversation_locks.setdefault(key, asyncio.Lock())

    if command == "!reset":
        async with lock:
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
        await message.channel.send(
            "Try: !ask Explain overfitting in simple terms."
        )
        return

    question = parts[1]

    async with lock:
        try:
            async with message.channel.typing():
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


client.run(TOKEN)
