import asyncio
from datetime import timedelta

import discord
from discord import app_commands

from moderation_store import (
    initialize_warning_database,
    record_warning,
)


async def check_target(interaction, member, action):
    """Check moderator permissions and member hierarchy."""
    server = interaction.guild

    if server is None:
        await interaction.edit_original_response(
            content="This command must be used in a server."
        )
        return None

    try:
        moderator = await server.fetch_member(interaction.user.id)
        target = await server.fetch_member(member.id)
    except discord.HTTPException:
        await interaction.edit_original_response(
            content="I couldn't verify the members. Please try again."
        )
        return None

    if not moderator.guild_permissions.moderate_members:
        await interaction.edit_original_response(
            content="You need the Moderate Members permission."
        )
        return None

    if target.id == moderator.id:
        await interaction.edit_original_response(
            content=f"You cannot {action} yourself."
        )
        return None

    if target.bot:
        await interaction.edit_original_response(
            content="This command is for human members."
        )
        return None

    if target.id == server.owner_id:
        await interaction.edit_original_response(
            content=f"You cannot {action} the server owner."
        )
        return None

    if (
        moderator.id != server.owner_id
        and target.top_role >= moderator.top_role
    ):
        await interaction.edit_original_response(
            content=f"You can only {action} members below your highest role."
        )
        return None

    return moderator, target


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

        reason = reason.strip()
        if not 1 <= len(reason) <= 500:
            await interaction.edit_original_response(
                content="Please enter a reason between 1 and 500 characters."
            )
            return

        checked = await check_target(interaction, member, "warn")
        if checked is None:
            return

        moderator, target = checked

        try:
            warning_id = await asyncio.to_thread(
                record_warning,
                interaction.guild.id,
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

    @tree.command(
        name="mute",
        description="Apply a timed Discord timeout to a server member.",
        guild=guild,
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(
        member="The member to time out.",
        minutes="Timeout duration in minutes, from 1 to 40320.",
        reason="Reason for the timeout (up to 400 characters).",
    )
    async def mute(
        interaction: discord.Interaction,
        member: discord.Member,
        minutes: app_commands.Range[int, 1, 40320],
        reason: str,
    ):
        await interaction.response.defer(ephemeral=True, thinking=True)

        reason = reason.strip()
        if not 1 <= len(reason) <= 400:
            await interaction.edit_original_response(
                content="Please enter a reason between 1 and 400 characters."
            )
            return

        checked = await check_target(interaction, member, "mute")
        if checked is None:
            return

        moderator, target = checked
        server = interaction.guild

        if target.guild_permissions.administrator:
            await interaction.edit_original_response(
                content="Discord does not allow timeouts on administrators."
            )
            return

        try:
            bot_member = await server.fetch_member(interaction.client.user.id)
        except discord.HTTPException:
            await interaction.edit_original_response(
                content="I couldn't verify my permissions. Please try again."
            )
            return

        if not bot_member.guild_permissions.moderate_members:
            await interaction.edit_original_response(
                content="I need the Moderate Members permission."
            )
            return

        if target.top_role >= bot_member.top_role:
            await interaction.edit_original_response(
                content="My highest role must be above this member's role."
            )
            return

        # Avoid accidentally replacing an existing timeout.
        if target.is_timed_out():
            await interaction.edit_original_response(
                content="This member already has an active timeout."
            )
            return

        audit_reason = f"Moderator {moderator.id}: {reason}"

        try:
            await target.timeout(
                timedelta(minutes=minutes),
                reason=audit_reason,
            )
        except discord.Forbidden:
            await interaction.edit_original_response(
                content="Discord denied the timeout. Check my permissions "
                "and role position."
            )
            return
        except discord.HTTPException as error:
            print(
                f"Timeout request error: {type(error).__name__}: {error}",
                flush=True,
            )
            await interaction.edit_original_response(
                content="I couldn't confirm the timeout. Check the member's "
                "status before trying again."
            )
            return

        safe_reason = discord.utils.escape_markdown(reason)

        await interaction.edit_original_response(
            content=(
                f"Member {target.id} timed out for {minutes} minute(s).\n"
                f"Reason: {safe_reason}"
            ),
            allowed_mentions=discord.AllowedMentions.none(),
        )
