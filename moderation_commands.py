import asyncio

import discord
from discord import app_commands

from moderation_store import (
    initialize_warning_database,
    record_warning,
)


def register_moderation_commands(tree, guild):
    initialize_warning_database()

    @tree.command(
        name="warn",
        description="Record a moderation warning for a server member.",
        guild=guild,
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(
        member="The member receiving the warning.",
        reason="Why this warning is being recorded (up to 500 characters).",
    )
    async def warn(
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
    ):
        await interaction.response.defer(ephemeral=True, thinking=True)

        server = interaction.guild
        if server is None:
            await interaction.edit_original_response(
                content="This command must be used in a server."
            )
            return

        reason = reason.strip()
        if not 1 <= len(reason) <= 500:
            await interaction.edit_original_response(
                content="Please enter a reason between 1 and 500 characters."
            )
            return

        # Fetch current membership, permissions, and roles.
        try:
            moderator = await server.fetch_member(interaction.user.id)
            target = await server.fetch_member(member.id)
        except discord.HTTPException:
            await interaction.edit_original_response(
                content="I couldn't verify the members. Please try again."
            )
            return

        if not moderator.guild_permissions.moderate_members:
            await interaction.edit_original_response(
                content="You need the Moderate Members permission."
            )
            return

        if target.id == moderator.id:
            await interaction.edit_original_response(
                content="You cannot warn yourself."
            )
            return

        if target.bot:
            await interaction.edit_original_response(
                content="This command records warnings for human members."
            )
            return

        if target.id == server.owner_id:
            await interaction.edit_original_response(
                content="You cannot warn the server owner."
            )
            return

        # The server owner can moderate members regardless of role position.
        if (
            moderator.id != server.owner_id
            and target.top_role >= moderator.top_role
        ):
            await interaction.edit_original_response(
                content="You can only warn members below your highest role."
            )
            return

        try:
            warning_id = await asyncio.to_thread(
                record_warning,
                server.id,
                target.id,
                moderator.id,
                reason,
            )
        except Exception as error:
            print(
                f"Warning database error: {type(error).__name__}: {error}",
                flush=True,
            )
            await interaction.edit_original_response(
                content="The warning could not be saved. Please try again."
            )
            return

        safe_reason = discord.utils.escape_markdown(reason)

        await interaction.edit_original_response(
            content=(
                f"Warning #{warning_id} recorded for member {target.id}.\n"
                f"Reason: {safe_reason}\n\n"
                "The member has not been automatically notified."
            ),
            allowed_mentions=discord.AllowedMentions.none(),
        )
