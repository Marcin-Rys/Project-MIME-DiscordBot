import discord
from discord import app_commands
from discord.ext import commands
import aiosqlite
import os

class CounterCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = self.bot.config["database_path"] 
    counter_group = app_commands.Group(name="licznik", description="Zarządzanie licznikami rang")

    @counter_group.command(name="add_role_counter", description="Adds a channel for selecter role")
    @app_commands.describe(role="role which you want to add to counter")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def add_counter(self, interaction: discord.Interaction, role: discord.Role):
        guild = interaction.guild
        
        ### Checking if this role is not counted already ###
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT 1 FROM role_counters WHERE guild_id = ? AND role_id =?", (guild.id, role.id)) as cursor:
                if await cursor.fetchone():
                    await interaction.response.send_message(f"Already counting role **{role.name}**!", ephemeral=True)
                    return
        
        ### creating voice channel ###
        try:
            #setting up so no-one can conect
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(connect=False),
                guild.me: discord.PermissionOverwrite(connect=True) #bot has an access
            }
            channel_name = f"{role.name}: {len(role.members)}"
            channel = await guild.create_voice_channel(name=channel_name, overwrites=overwrites, reason=f"Counter for role {role.name}")
        except discord.errors.Forbidden:
            await interaction.response.send_message("Error, no privileges to set up channels", ephemeral=True)
            return

        ### Saving to database ###
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO role_counters (guild_id, role_id, channel_id) VALUES (?, ?, ?)",
                (guild.id, role.id, channel.id)
            )
            await db.commit()

        await interaction.response.send_message(f"Succesfully created role counter for role **{role.name} n channel {channel.mention}.", ephemeral=True)

    @counter_group.command(name="delete_role_counter", description="Removing role counter for selected role")
    @app_commands.describe(role="Role which counter you want to remove")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def remove_counter(self, interaction: discord.Interaction, role: discord.Role):
        guild = interaction.guild

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT channel_id FROM role_counters WHERE guild_id = ? AND role_id = ?", (guild.id, role.id)) as cursor:
                result = await cursor.fetchone()
                if not result:
                    await interaction.response.send_message(f"Not counting role **{role.name}**", ephemeral=True)
                    return
                channel_id = result[0]

            ### removing from database ###
            await db.execute("DELETE FROM role_counters WHERE guild_id = ? AND role_id = ?", (guild.id, role.id))
            await db.commit()

        channel = guild.get_channel(channel_id)
        if channel:
            try:
                await channel.delete(reason=f"Deleting counter for role {role.name}")
            except discord.errors.Forbidden:
                await interaction.response.send_message("Cleared from database, but cannot remove channel(no privileges).", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(CounterCommands(bot))