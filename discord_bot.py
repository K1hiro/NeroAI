import asyncio
import os
import time
from pathlib import Path
from moderation_commands import register_moderation_commands
import discord
from discord import app_commands
from dotenv import load_dotenv

from llm_backend import MAX_HISTORY_MESSAGES, generate_reply
from memory_store import (
    clear_history,
    initialize_database,
    load_history,
    save_turn,
)
from rag_backend import generate_grounded_reply

load_dotenv(Path(__file__).resolve().parent / ".env")

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("DISCORD_GUILD_ID")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing from .env")

if not GUILD_ID or not GUILD_ID.isdigit():
    raise RuntimeError("DISCORD_GUILD_ID must be a numeric server ID")

TEST_GUILD = discord.Object(id=int(GUILD_ID))

COOLDOWN_SECONDS = 10
MAX_PENDING_REQUESTS = 5

initialize_database()

conversation_locks: dict[tuple[int, int], asyncio.Lock] = {}
last_request_times: dict[int, float] = {}
processing_lock = asyncio.Lock()
pending_requests = 0


class NeroBot(discord.Client):
    def __init__(self):
        super().__init__(
            intents=discord.Intents.default(),
            allowed_mentions=discord.AllowedMentions.none(),
        )
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        commands = await self.tree.sync(guild=TEST_GUILD)
        print(
            f"Synced {len(commands)} slash commands "
            f"to server {TEST_GUILD.id}",
            flush=True,
        )

    async def on_ready(self):
        print(f"Connected to Discord as {self.user}", flush=True)


client = NeroBot()


def build_answer(channel_id, user_id, question, lookup):
    """Run blocking model and database work in a worker thread."""
    if lookup:
        return generate_grounded_reply(question)

    history = load_history(
        channel_id,
        user_id,
        limit=MAX_HISTORY_MESSAGES,
    )

    reply = generate_reply(question, history=history)
    reply = (reply or "").strip()

    if reply:
        save_turn(
            channel_id,
            user_id,
            question,
            reply,
            limit=MAX_HISTORY_MESSAGES,
        )

    return reply


async def send_answer(interaction, answer):
    chunks = [
        answer[start:start + 1900]
        for start in range(0, len(answer), 1900)
    ]

    await interaction.edit_original_response(
        content=chunks[0],
        allowed_mentions=discord.AllowedMentions.none(),
    )

    for chunk in chunks[1:]:
        await interaction.followup.send(
            chunk,
            allowed_mentions=discord.AllowedMentions.none(),
        )


async def handle_question(interaction, question, lookup=False):
    global pending_requests

    question = question.strip()

    if not question:
        await interaction.response.send_message(
            "Please enter a question.",
            ephemeral=True,
        )
        return

    if interaction.channel_id is None:
        await interaction.response.send_message(
            "Please use this command in a server channel.",
            ephemeral=True,
        )
        return

    user_id = interaction.user.id
    channel_id = interaction.channel_id
    now = time.monotonic()
    last_request = last_request_times.get(user_id)

    if last_request is not None:
        remaining = COOLDOWN_SECONDS - (now - last_request)
        if remaining > 0:
            await interaction.response.send_message(
                f"Please wait {remaining:.1f} seconds "
                "before asking another question.",
                ephemeral=True,
            )
            return

    if pending_requests >= MAX_PENDING_REQUESTS:
        await interaction.response.send_message(
            "I'm handling several requests right now. "
            "Please try again shortly.",
            ephemeral=True,
        )
        return

    key = (channel_id, user_id)
    lock = conversation_locks.setdefault(key, asyncio.Lock())

    # Reserve capacity before yielding to another command handler.
    requests_ahead = pending_requests
    pending_requests += 1
    last_request_times[user_id] = now

    try:
        # Acknowledge immediately, before waiting or generating.
        await interaction.response.defer(thinking=True)

        if requests_ahead > 0:
            await interaction.edit_original_response(
                content="Your question is waiting for current requests."
            )

        async with lock:
            async with processing_lock:
                # Skip a request that waited beyond Discord's reply window.
                if interaction.is_expired():
                    return

                reply = await asyncio.to_thread(
                    build_answer,
                    channel_id,
                    user_id,
                    question,
                    lookup,
                )

                reply = (reply or "").strip()
                if not reply:
                    reply = "The model returned an empty response."

                await send_answer(interaction, reply)

    except Exception as error:
        print(
            f"Request error: {type(error).__name__}: {error}",
            flush=True,
        )
        try:
            if interaction.response.is_done():
                await interaction.edit_original_response(
                    content="Sorry, I couldn't complete your request."
                )
            else:
                await interaction.response.send_message(
                    "Sorry, I couldn't complete your request.",
                    ephemeral=True,
                )
        except discord.HTTPException:
            pass

    finally:
        pending_requests -= 1


@client.tree.command(
    name="ask",
    description="Chat with NeroAI using your saved conversation memory.",
    guild=TEST_GUILD,
)
@app_commands.describe(question="What would you like to ask?")
async def ask(interaction: discord.Interaction, question: str):
    await handle_question(interaction, question)


@client.tree.command(
    name="lookup",
    description="Search NeroAI's knowledge files and answer with sources.",
    guild=TEST_GUILD,
)
@app_commands.describe(question="Include the topic you want to look up.")
async def lookup(interaction: discord.Interaction, question: str):
    await handle_question(interaction, question, lookup=True)


@client.tree.command(
    name="reset",
    description="Clear your saved conversation memory in this channel.",
    guild=TEST_GUILD,
)
async def reset(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True, thinking=True)

    if interaction.channel_id is None:
        await interaction.edit_original_response(
            content="Please use this command in a server channel."
        )
        return

    key = (interaction.channel_id, interaction.user.id)
    lock = conversation_locks.setdefault(key, asyncio.Lock())

    try:
        async with lock:
            await asyncio.to_thread(clear_history, *key)

        await interaction.edit_original_response(
            content="Your saved conversation memory "
            "in this channel has been cleared."
        )

    except Exception as error:
        print(
            f"Reset error: {type(error).__name__}: {error}",
            flush=True,
        )
        await interaction.edit_original_response(
            content="Sorry, I couldn't clear your memory. Please try again."
        )


if __name__ == "__main__":
    register_moderation_commands(client.tree, TEST_GUILD)
    client.run(TOKEN)
