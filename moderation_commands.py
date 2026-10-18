import asyncio
from datetime import timedelta

import discord
from discord import app_commands

from moderation_store import (
    initialize_warning_database,
    record_warning,
)

PERMISSIONS = {
    "warn": ("moderate_members", "Moderate Members"),
    "mute": ("moderate_members", "Moderate Members"),
    "kick": ("kick_members", "Kick Members"),
    "ban": ("ban_members", "Ban Members"),
}


async def respond(interaction, text):
    await interaction.edit_original_response(
        content=text,
        allowed_mentions=discord.AllowedMentions.none(),
    )


async def check_target(interaction, member, action):
    server = interaction.guild

    if server is None:
        await respond(interaction, "This command must be used in a server.")
        return None

    permission, permission_name = PERMISSIONS[action]

    try:
        moderator = await server.fetch_member(interaction.user.id)
        target = await server.fetch_member(member.id)
    except discord.HTTPException:
        await respond(
            interaction,
            "I couldn't verify the members. Please try again.",
        )
        return None

    if not getattr(moderator.guild_permissions, permission):
        await respond(
            interaction,
            f"You need the {permission_name} permission.",
        )
        return None

    if target.id == moderator.id:
        await respond(interaction, f"You cannot {action} yourself.")
        return None

    if target.bot:
        await respond(interaction, "This command is for human members.")
        return None

    if target.id == server.owner_id:
        await respond(
            interaction,
            f"You cannot {action} the server owner.",
        )
        return None

    if (
        moderator.id != server.owner_id
        and target.top_role >= moderator.top_role
    ):
        await respond(
            interaction,
            f"You can only {action} members below your highest role.",
        )
        return None

    return moderator, target


async def check_bot_permissions(interaction, target, action):
    permission, permission_name = PERMISSIONS[action]

    try:
        bot_member = await interaction.guild.fetch_member(
            interaction.client.user.id
        )
    except discord.HTTPException:
        await respond(
            interaction,
            "I couldn't verify my permissions. Please try again.",
        )
        return False

    if not getattr(bot_member.guild_permissions, permission):
        await respond(
            interaction,
            f"I need the {permission_name} permission.",
        )
        return False

    if target.top_role >= bot_member.top_role:
        await respond(
            interaction,
            "My highest role must be above this member's role.",
        )
        return False

    return True


async def handle_moderation(
    interaction, member, reason, action, minutes=None
):
    await interaction.response.defer(ephemeral=True, thinking=True)

    reason = reason.strip()
    maximum = 500 if action == "warn" else 400

    if not 1 <= len(reason) <= maximum:
        await respond(
            interaction,
            f"Please enter a reason between 1 and {maximum} characters.",
        )
        return

    checked = await check_target(interaction, member, action)
    if checked is None:
        return

    moderator, target = checked
    safe_reason = discord.utils.escape_markdown(reason)

    if action == "warn":
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
            await respond(
                interaction,
                "The warning could not be saved. Please try again.",
            )
            return

        await respond(
            interaction,
            f"Warning #{warning_id} recorded for member {target.id}.\n"
            f"Reason: {safe_reason}\n\n"
            "The member has not been automatically notified.",
        )
        return

    if action == "mute":
        if target.guild_permissions.administrator:
            await respond(
                interaction,
                "Discord does not allow timeouts on administrators.",
            )
            return

        if target.is_timed_out():
            await respond(
                interaction,
                "This member already has an active timeout.",
            )
            return

    if not await check_bot_permissions(interaction, target, action):
        return

    audit_reason = f"Moderator {moderator.id}: {reason}"

    try:
        if action == "mute":
            await target.timeout(
                timedelta(minutes=minutes),
                reason=audit_reason,
            )
            result = (
                f"Member {target.id} timed out for {minutes} minute(s)."
            )

        elif action == "kick":
            await target.kick(reason=audit_reason)
            result = f"Member {target.id} was kicked from the server."

        elif action == "ban":
            await target.ban(
                reason=audit_reason,
                delete_message_seconds=0,
            )
            result = (
                f"Member {target.id} was banned from the server.\n"
                "Existing message history was preserved."
            )

        else:
            raise ValueError(f"Unsupported moderation action: {action}")

    except discord.NotFound:
        await respond(
            interaction,
            "Discord could not find the target. Check the member's status.",
        )
        return

    except discord.Forbidden:
        await respond(
            interaction,
            f"Discord denied the {action}. Check my permissions "
            "and role position.",
        )
        return

    except discord.HTTPException as error:
        print(f"{action} request error: {error}", flush=True)
        await respond(
            interaction,
            f"I couldn't confirm the {action}. Check the member's status "
            "and server audit log before trying again.",
        )
        return

    await respond(
        interaction,
        f"{result}\nReason: {safe_reason}",
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
        reason="Reason for the warning (up to 500 characters).",
    )
    async def warn(
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
    ):
        await handle_moderation(interaction, member, reason, "warn")

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
        await handle_moderation(
            interaction, member, reason, "mute", minutes=minutes
        )

    @tree.command(
        name="kick",
        description="Remove a member from the server without banning them.",
        guild=guild,
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(kick_members=True)
    @app_commands.describe(
        member="The member to remove from the server.",
        reason="Reason for the kick (up to 400 characters).",
    )
    async def kick(
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
    ):
        await handle_moderation(interaction, member, reason, "kick")

    @tree.command(
        name="ban",
        description="Ban a server member while preserving message history.",
        guild=guild,
    )
    @app_commands.guild_only()
    @app_commands.default_permissions(ban_members=True)
    @app_commands.describe(
        member="The member to ban from the server.",
        reason="Reason for the ban (up to 400 characters).",
    )
    async def ban(
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
    ):
        await handle_moderation(interaction, member, reason, "ban")
