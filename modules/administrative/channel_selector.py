import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Select, View
import aiosqlite

class ChannelSelectorDropdown(Select):
    def __init__(self, bot: commands.Bot, channels: list[discord.TextChannel]):
        self.bot = bot
        options = [
            discord.SelectOption(label=channel.name, value=str(channel.id), description=f"ID: {channel.id}")
            for channel in channels[:25] # Discord allows only 25 options
        ]

        super().__init__(placeholder="Wybierz kanal dla powiadomień", options=options) #TODO language pack

    async def callback(self, interaction: discord.Interaction):
        # Loading database path from central bot config
        db_path = self.bot.config["database_path"]
        selected_channel_id = int(self.values[0])
        guild_id = interaction.guild.id

        try:
            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    """
                    INSERT INTO guild_settings (guild_id, notification_channel_id) VALUES (?,?)
                    ON CONFLICT(guild_id) DO UPDATE SET notification_channel_id = excluded.notification_channel_id
                    """,
                    (guild_id, selected_channel_id)
                )
                await db.commit()
            
            channel = self.bot.get_channel(selected_channel_id)
            await interaction.response.send_message(f"Kanał powiadomień został pomyślnie ustawiony na {channel.mention}!", ephemeral=True) #TODO language pack

        except Exception as e:
            print(f"Error during saving to database in channel_selector {e}")
            await interaction.response.send_message("Wystąpił błąd podczas zapisywania ustawień.", ephemeral=True)

#Class for menu view
class ChannelSelectView(View):
    def __init__(self, bot: commands.Bot, author: discord.User, channels: list[discord.TextChannel]):
        super().__init__(timeout=180) # dissapears after 3 minutes
        self.author = author
        self.add_item(ChannelSelectorDropdown(bot, channels))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Checking if interaction is by same person which invoked an command
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("Co, chcialo się użyć czyjegoś menu? Nie ma tak łatwo!", ephemeral=True) #TODO language pack
            return False
        return True
    
# Main Cog/Module class
class ChannelSelector(commands.Cog):
    def __init__(self,bot: commands.Bot):
        self.bot = bot
    
    @app_commands.command(name="ustaw_powitania", description="Ustawia kanał powiadomień dla tego serwera.")
    @app_commands.checks.has_permissions(administrator=True) # Checking privileges
    async def select_greetings(self, interaction: discord.Interaction):
        text_channels = interaction.guild.text_channels
        
        if not text_channels:
            await interaction.response.send_message("Na tym serwerze nie ma żadnych kanałów tekstowych", ephemeral=True) #TODO language pack
            return
        
        view = ChannelSelectView(bot=self.bot, author=interaction.user, channels=text_channels)
        await interaction.response.send_message("Wybierz kanał, na ktory mają przychodzić powiadomienia:", view=view, ephemeral=True) #TODO language pack

    @select_greetings.error
    async def select_greetings_error(self,interaction: discord.Interaction, error: app_commands.AppCommandError):
        # Dedicated for non-privileged error
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("Nie masz uprawnien administratora, aby użyć tej komendy.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Wystąpił nieoczekiwany błąd: {error}", ephemeral=True)
            raise error

async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelSelector(bot))
