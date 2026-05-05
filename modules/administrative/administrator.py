import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import json
import os
from typing import Optional, List

_ = app_commands.locale_str


class Administrator(commands.Cog):
    """
    Administrative module for managing bot settings per guild.

    Features:
    - Enable / disable modules per guild (guild_modules table).
    - Add / remove jokes.
    - Add / remove auto-responder triggers.
    - Configure cooldown limits for features.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = self.bot.config["database_path"]

    # ------------------------------------------------------------------
    # Module management commands  (/admin module ...)
    # ------------------------------------------------------------------

    admin_group = app_commands.Group(
        name=_("admin", key="administrator:group_name"),
        description=_("Bot administration commands.", key="administrator:group_description"),
    )

    module_group = app_commands.Group(
        name=_("module", key="administrator:module_group_name"),
        description=_("Enable or disable bot modules for this server.", key="administrator:module_group_description"),
        parent=admin_group,
    )

    @module_group.command(
        name=_("enable", key="administrator:module_enable_name"),
        description=_("Enable a module for this server.", key="administrator:module_enable_description"),
    )
    @app_commands.describe(
        module_name=_("Name of the module to enable.", key="administrator:module_name_description"),
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def module_enable(self, interaction: discord.Interaction, module_name: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO guild_modules (guild_id, module_name, is_enabled, allow_in_dm)
                VALUES (?, ?, 1, 1)
                ON CONFLICT(guild_id, module_name) DO UPDATE SET is_enabled = 1
                """,
                (guild_id, module_name),
            )
            await db.commit()

        await interaction.followup.send(
            f"Module **{module_name}** has been **enabled** for this server.", ephemeral=True
        )

    @module_group.command(
        name=_("disable", key="administrator:module_disable_name"),
        description=_("Disable a module for this server.", key="administrator:module_disable_description"),
    )
    @app_commands.describe(
        module_name=_("Name of the module to disable.", key="administrator:module_name_description"),
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def module_disable(self, interaction: discord.Interaction, module_name: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO guild_modules (guild_id, module_name, is_enabled, allow_in_dm)
                VALUES (?, ?, 0, 0)
                ON CONFLICT(guild_id, module_name) DO UPDATE SET is_enabled = 0
                """,
                (guild_id, module_name),
            )
            await db.commit()

        await interaction.followup.send(
            f"Module **{module_name}** has been **disabled** for this server.", ephemeral=True
        )

    @module_group.command(
        name=_("list", key="administrator:module_list_name"),
        description=_("List all configured modules for this server.", key="administrator:module_list_description"),
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def module_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT module_name, is_enabled, allow_in_dm FROM guild_modules WHERE guild_id = ? ORDER BY module_name",
                (guild_id,),
            )
            rows = await cursor.fetchall()

        if not rows:
            await interaction.followup.send(
                "No modules have been configured for this server yet.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Module configuration for this server",
            color=discord.Color.blurple(),
        )
        for row in rows:
            status = "✅ Enabled" if row["is_enabled"] else "❌ Disabled"
            dm_status = "DM: ✅" if row["allow_in_dm"] else "DM: ❌"
            embed.add_field(
                name=row["module_name"],
                value=f"{status} | {dm_status}",
                inline=True,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # Joke management commands  (/admin joke ...)
    # ------------------------------------------------------------------

    joke_admin_group = app_commands.Group(
        name=_("joke", key="administrator:joke_group_name"),
        description=_("Manage jokes for this server.", key="administrator:joke_group_description"),
        parent=admin_group,
    )

    @joke_admin_group.command(
        name=_("add", key="administrator:joke_add_name"),
        description=_("Add a joke to the database for this server.", key="administrator:joke_add_description"),
    )
    @app_commands.describe(
        category=_("Category of the joke.", key="administrator:joke_category_description"),
        text=_("The joke text.", key="administrator:joke_text_description"),
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def joke_add(self, interaction: discord.Interaction, category: str, text: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO jokes (guild_id, category, text) VALUES (?, ?, ?)",
                    (guild_id, category, text),
                )
                await db.commit()
            await interaction.followup.send(
                f"Joke added to category **{category}**.", ephemeral=True
            )
        except aiosqlite.IntegrityError:
            await interaction.followup.send(
                "This exact joke text already exists in the database for this server.",
                ephemeral=True,
            )

    @joke_admin_group.command(
        name=_("remove", key="administrator:joke_remove_name"),
        description=_("Remove a joke from the database by its ID.", key="administrator:joke_remove_description"),
    )
    @app_commands.describe(
        joke_id=_("ID of the joke to remove.", key="administrator:joke_id_description"),
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def joke_remove(self, interaction: discord.Interaction, joke_id: int):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM jokes WHERE joke_id = ? AND guild_id = ?",
                (joke_id, guild_id),
            )
            await db.commit()

        if cursor.rowcount > 0:
            await interaction.followup.send(
                f"Joke **#{joke_id}** has been removed.", ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"Joke **#{joke_id}** was not found on this server.", ephemeral=True
            )

    @joke_admin_group.command(
        name=_("list", key="administrator:joke_list_name"),
        description=_("List jokes for this server (optionally filtered by category).", key="administrator:joke_list_description"),
    )
    @app_commands.describe(
        category=_("Filter by category (optional).", key="administrator:joke_list_category_description"),
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def joke_list(self, interaction: discord.Interaction, category: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if category:
                cursor = await db.execute(
                    "SELECT joke_id, category, text FROM jokes WHERE guild_id = ? AND category = ? ORDER BY joke_id LIMIT 20",
                    (guild_id, category),
                )
            else:
                cursor = await db.execute(
                    "SELECT joke_id, category, text FROM jokes WHERE guild_id = ? ORDER BY joke_id LIMIT 20",
                    (guild_id,),
                )
            rows = await cursor.fetchall()

        if not rows:
            await interaction.followup.send("No jokes found.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Jokes" + (f" – {category}" if category else ""),
            color=discord.Color.yellow(),
        )
        for row in rows:
            preview = row["text"][:80] + "…" if len(row["text"]) > 80 else row["text"]
            embed.add_field(
                name=f"#{row['joke_id']} [{row['category']}]",
                value=preview,
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # Auto-responder management  (/admin response ...)
    # ------------------------------------------------------------------

    response_admin_group = app_commands.Group(
        name=_("response", key="administrator:response_group_name"),
        description=_("Manage auto-responder triggers for this server.", key="administrator:response_group_description"),
        parent=admin_group,
    )

    @response_admin_group.command(
        name=_("add", key="administrator:response_add_name"),
        description=_("Add an auto-responder trigger.", key="administrator:response_add_description"),
    )
    @app_commands.describe(
        trigger=_("The trigger phrase (message content to match).", key="administrator:response_trigger_description"),
        response=_("The response text the bot will send.", key="administrator:response_text_description"),
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def response_add(self, interaction: discord.Interaction, trigger: str, response: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO guild_responses (guild_id, trigger_text, response_text) VALUES (?, ?, ?)",
                    (guild_id, trigger.lower(), response),
                )
                await db.commit()
            await interaction.followup.send(
                f"Response trigger **{trigger}** has been added.", ephemeral=True
            )
        except aiosqlite.IntegrityError:
            await interaction.followup.send(
                f"A trigger for **{trigger}** already exists on this server.",
                ephemeral=True,
            )

    @response_admin_group.command(
        name=_("remove", key="administrator:response_remove_name"),
        description=_("Remove an auto-responder trigger.", key="administrator:response_remove_description"),
    )
    @app_commands.describe(
        trigger=_("The trigger phrase to remove.", key="administrator:response_remove_trigger_description"),
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def response_remove(self, interaction: discord.Interaction, trigger: str):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "DELETE FROM guild_responses WHERE guild_id = ? AND trigger_text = ?",
                (guild_id, trigger.lower()),
            )
            await db.commit()

        if cursor.rowcount > 0:
            await interaction.followup.send(
                f"Trigger **{trigger}** has been removed.", ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"No trigger found for **{trigger}** on this server.", ephemeral=True
            )

    @response_admin_group.command(
        name=_("list", key="administrator:response_list_name"),
        description=_("List all auto-responder triggers for this server.", key="administrator:response_list_description"),
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def response_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT trigger_text, response_text FROM guild_responses WHERE guild_id = ? ORDER BY trigger_text",
                (guild_id,),
            )
            rows = await cursor.fetchall()

        if not rows:
            await interaction.followup.send(
                "No auto-responder triggers configured for this server.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title="Auto-responder triggers",
            color=discord.Color.green(),
        )
        for row in rows:
            preview = row["response_text"][:80] + "…" if len(row["response_text"]) > 80 else row["response_text"]
            embed.add_field(
                name=f'Trigger: "{row["trigger_text"]}"',
                value=preview,
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # Cooldown management  (/admin cooldown ...)
    # ------------------------------------------------------------------

    cooldown_admin_group = app_commands.Group(
        name=_("cooldown", key="administrator:cooldown_group_name"),
        description=_("Configure cooldown limits for features on this server.", key="administrator:cooldown_group_description"),
        parent=admin_group,
    )

    @cooldown_admin_group.command(
        name=_("set", key="administrator:cooldown_set_name"),
        description=_("Set a cooldown limit for a feature.", key="administrator:cooldown_set_description"),
    )
    @app_commands.describe(
        feature=_("Feature/command name (e.g. sra_command).", key="administrator:cooldown_feature_description"),
        limit_name=_("Descriptive name for this limit (e.g. '15 minute limit').", key="administrator:cooldown_limit_name_description"),
        limit_count=_("Maximum uses allowed within the period.", key="administrator:cooldown_limit_count_description"),
        period_seconds=_("Time period in seconds.", key="administrator:cooldown_period_description"),
        dm_threshold=_("Warning level at which a DM is sent (optional).", key="administrator:cooldown_dm_threshold_description"),
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def cooldown_set(
        self,
        interaction: discord.Interaction,
        feature: str,
        limit_name: str,
        limit_count: int,
        period_seconds: int,
        dm_threshold: Optional[int] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO guild_cooldowns
                    (guild_id, feature_name, limit_name, limit_count, period_seconds, dm_warning_threshold)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(guild_id, feature_name, period_seconds)
                DO UPDATE SET
                    limit_name = excluded.limit_name,
                    limit_count = excluded.limit_count,
                    dm_warning_threshold = excluded.dm_warning_threshold
                """,
                (guild_id, feature, limit_name, limit_count, period_seconds, dm_threshold),
            )
            await db.commit()

        await interaction.followup.send(
            f"Cooldown for **{feature}** set: max **{limit_count}** uses per **{period_seconds}s** ({limit_name}).",
            ephemeral=True,
        )

    @cooldown_admin_group.command(
        name=_("list", key="administrator:cooldown_list_name"),
        description=_("List cooldown rules configured for this server.", key="administrator:cooldown_list_description"),
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def cooldown_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT feature_name, limit_name, limit_count, period_seconds, dm_warning_threshold FROM guild_cooldowns WHERE guild_id = ? ORDER BY feature_name",
                (guild_id,),
            )
            rows = await cursor.fetchall()

        if not rows:
            await interaction.followup.send(
                "No cooldown rules configured for this server.", ephemeral=True
            )
            return

        embed = discord.Embed(title="Cooldown rules", color=discord.Color.red())
        for row in rows:
            dm_info = f" | DM at lvl {row['dm_warning_threshold']}" if row["dm_warning_threshold"] else ""
            embed.add_field(
                name=f"{row['feature_name']} – {row['limit_name'] or 'Unnamed'}",
                value=f"Max **{row['limit_count']}** / **{row['period_seconds']}s**{dm_info}",
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Administrator(bot))
