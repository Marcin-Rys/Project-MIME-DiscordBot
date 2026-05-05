import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import random
from typing import Optional

_ = app_commands.locale_str

MODULE_NAME = "warner"


class Warner(commands.Cog):
    """
    Centralised warning module.
    Provides a shared warn_user() helper used by other modules as well as
    admin slash-commands to view and reset user warning counts.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = self.bot.config["database_path"]

    # ------------------------------------------------------------------
    # Public helper – other cogs can call this directly
    # ------------------------------------------------------------------
    async def warn_user(
        self,
        user: discord.User,
        guild: discord.Guild,
        feature_name: str,
        locale: discord.Locale = discord.Locale.american_english,
    ) -> int:
        """
        Issues a warning for *user* in *guild* for *feature_name*.
        Increments the warning counter in the DB and sends a DM when the
        configured threshold is reached.

        Returns the new warning level.
        """
        translator = self.bot.translator

        # 1. Increment warning level in database
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO cooldown_warnings (user_id, guild_id, feature_name, warning_level)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(user_id, guild_id, feature_name)
                DO UPDATE SET warning_level = warning_level + 1
                """,
                (user.id, guild.id, feature_name),
            )
            cursor = await db.execute(
                "SELECT warning_level FROM cooldown_warnings WHERE user_id = ? AND guild_id = ? AND feature_name = ?",
                (user.id, guild.id, feature_name),
            )
            result = await cursor.fetchone()
            await db.commit()
            warning_level = result[0] if result else 1

        # 2. Check DM threshold from guild_cooldowns table
        dm_threshold = 999
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT dm_warning_threshold FROM guild_cooldowns WHERE guild_id = ? AND feature_name = ?",
                (guild.id, feature_name),
            )
            row = await cursor.fetchone()
            if row and row["dm_warning_threshold"] is not None:
                dm_threshold = row["dm_warning_threshold"]

        # 3. Send DM if threshold reached
        if warning_level >= dm_threshold:
            try:
                dm_text_variants = translator.get_translation(
                    "orphans:cooldown_dm_warning", locale
                )
                if isinstance(dm_text_variants, list) and dm_text_variants:
                    dm_text = random.choice(dm_text_variants)
                else:
                    dm_text = dm_text_variants or "You have been warned."
                await user.send(dm_text)
                # Reset warning counter after DM has been sent
                await self._reset_warnings(user.id, guild.id, feature_name)
            except discord.Forbidden:
                print(
                    f"#warner.py | Info | Cannot send DM to {user} – DMs are blocked."
                )

        return warning_level

    async def _reset_warnings(
        self, user_id: int, guild_id: int, feature_name: str
    ) -> None:
        """Resets warning counter for a user/guild/feature combination."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM cooldown_warnings WHERE user_id = ? AND guild_id = ? AND feature_name = ?",
                (user_id, guild_id, feature_name),
            )
            await db.commit()

    # ------------------------------------------------------------------
    # Admin slash commands
    # ------------------------------------------------------------------

    warn_admin_group = app_commands.Group(
        name=_("warnings", key="warner:group_name"),
        description=_("Manage user warnings.", key="warner:group_description"),
    )

    @warn_admin_group.command(
        name=_("check", key="warner:command_check_name"),
        description=_("Check warning count for a user.", key="warner:command_check_description"),
    )
    @app_commands.describe(
        user=_("User to check warnings for.", key="warner:option_user_description"),
        feature=_("Feature/module name (leave blank for all).", key="warner:option_feature_description"),
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def check_warnings(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        feature: Optional[str] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if feature:
                cursor = await db.execute(
                    "SELECT feature_name, warning_level FROM cooldown_warnings WHERE user_id = ? AND guild_id = ? AND feature_name = ?",
                    (user.id, guild_id, feature),
                )
            else:
                cursor = await db.execute(
                    "SELECT feature_name, warning_level FROM cooldown_warnings WHERE user_id = ? AND guild_id = ?",
                    (user.id, guild_id),
                )
            rows = await cursor.fetchall()

        if not rows:
            await interaction.followup.send(
                f"No warnings found for {user.mention}.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"Warnings for {user.display_name}",
            color=discord.Color.orange(),
        )
        for row in rows:
            embed.add_field(
                name=row["feature_name"],
                value=f"Level: **{row['warning_level']}**",
                inline=True,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @warn_admin_group.command(
        name=_("reset", key="warner:command_reset_name"),
        description=_("Reset warnings for a user.", key="warner:command_reset_description"),
    )
    @app_commands.describe(
        user=_("User whose warnings to reset.", key="warner:option_user_reset_description"),
        feature=_("Feature/module name (leave blank to reset all).", key="warner:option_feature_reset_description"),
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def reset_warnings(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        feature: Optional[str] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        async with aiosqlite.connect(self.db_path) as db:
            if feature:
                await db.execute(
                    "DELETE FROM cooldown_warnings WHERE user_id = ? AND guild_id = ? AND feature_name = ?",
                    (user.id, guild_id, feature),
                )
            else:
                await db.execute(
                    "DELETE FROM cooldown_warnings WHERE user_id = ? AND guild_id = ?",
                    (user.id, guild_id),
                )
            await db.commit()

        scope = f"for **{feature}**" if feature else "for all features"
        await interaction.followup.send(
            f"Warnings {scope} for {user.mention} have been reset.", ephemeral=True
        )

    @warn_admin_group.command(
        name=_("warn", key="warner:command_warn_name"),
        description=_("Manually warn a user via DM.", key="warner:command_warn_description"),
    )
    @app_commands.describe(
        user=_("User to warn.", key="warner:option_warn_user_description"),
        reason=_("Reason for the warning.", key="warner:option_warn_reason_description"),
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def manual_warn(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        reason: str,
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            await user.send(
                f"⚠️ You have received a warning on **{interaction.guild.name}**:\n{reason}"
            )
            await interaction.followup.send(
                f"Warning sent to {user.mention} via DM.", ephemeral=True
            )
        except discord.Forbidden:
            await interaction.followup.send(
                f"Could not send DM to {user.mention} – their DMs are disabled.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Warner(bot))
