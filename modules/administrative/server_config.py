import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select, Modal, TextInput
import aiosqlite

class WelcomeMessageModal(Modal, title="Edit welcome message"):
    def __init__(self, db_path: str, current_message: str=""):
        super().__init__()
        self.db_path = db_path
        self.message_input = TextInput(
            label = "Welcome message",
            style=discord.TextStyle.paragraph,
            placeholder="Input your message. Use {user} to mention an user.",
            default=current_message,
            max_length=1000,
            required=False
        )
        self.add_item(self.message_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        new_message = self.message_input.value
        guild_id = interaction.guild.id
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE guild_settings SET welcome_message =? WHERE guild_id = ?",
                (new_message, guild_id)
            )
            await db.commit()
        await interaction.response.send_message("Welcome message has been updated!", ephemeral=True)

# --- Main view with buttons ---
class ConfigView(View):
    def __init__(self, bot: commands.Bot, author: discord.User):
        super().__init__(timeout=300)
        self.bot = bot
        self.author = author
        self.db_path = self.bot.config["database_path"]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Only autor of command can use this panel.", ephemeral=True)
            return False
        return True
    
    @discord.ui.button(label="Welcome message", style=discord.ButtonStyle.primary, emoji="👋")
    async def welcome_message_button(self, interaction: discord.Interaction, button: Button):
        # Download current message to show it in view
        current_message = ""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT welcome_message FROM guild_settings WHERE guild_id = ?", (interaction.guild.id))
            result = await cursor.fetchone()
            if result and result[0]:
                current_message = result[0]
        modal = WelcomeMessageModal(self.db_path, current_message)
        await interaction.response.send_modal(modal)


# --- Main Cog ---
class ServerConfig(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="configuration", description="Opens up a panel to configure bot for this server")
    @app_commands.checks.has_permissions(administrator=True)
    async def configure(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title = "Bot configuration panel",
            description="Choose option which you want to configure",
            color=discord.Color.blurple()
        )
        view=ConfigView(self.bot, interaction.user)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerConfig(bot))