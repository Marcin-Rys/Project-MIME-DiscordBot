import discord
from discord.ext import commands
import aiosqlite

## for future private messages to select roles on server
class RoleAssignmentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) #timeout=None makes that message will not disappear

        """
        === Placeholder for future buttons ===
        self.add_item(discord.ui.Button)(label="I want role A!"), custom_id="role_a_button")) #TODO language pack
        self.add_item(discord.ui.Button)(label="I want role B!"), custom_id="role_b_button"))
        ======================================
        """

class WelcomeHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _get_guild_settings(self, guild_id: int) -> dict:
        """Fetches welcome message and notification channel from database."""
        db_path = self.bot.config["database_path"]
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT notification_channel_id, welcome_message FROM guild_settings WHERE guild_id = ?",
                (guild_id,)
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "notification_channel_id": row["notification_channel_id"],
                    "welcome_message": row["welcome_message"]
                }
        return {}

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        ### This maintains new member join events

        settings = await self._get_guild_settings(member.guild.id)

        #1. Sending private message with panel
        try:
            dm_channel = await member.create_dm()

            view = RoleAssignmentView() #we creating instance for our panel

            # Use welcome message from DB if set, otherwise use default
            welcome_message = settings.get("welcome_message")
            if welcome_message:
                welcome_text = welcome_message.replace("{user}", member.mention)
            else:
                welcome_text = f"Hej {member.name}, witaj na serwerze! Honk! \n Below you can select your roles." #TODO language pack

            await dm_channel.send(welcome_text, view=view) #we are sending welcome with role changing panel

        except discord.errors.Forbidden:
            print(f"#on_member_join.py | Info | Cannot send DM to {member.name} (ID: {member.id}).") #TODO language pack
        except Exception as e:
            print(f"#on_member_join.py | ERROR | Unexpected error while sending DM to {member.name}: {e}") #TODO language pack

        #2. Sending notification to public channel
        notification_channel_id = settings.get("notification_channel_id")

        if not notification_channel_id:
            print(f"#on_member_join.py | Warning | No notification_channel_id set for guild {member.guild.id}.") #TODO language pack
            return

        channel = self.bot.get_channel(notification_channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            try:
                await channel.send(f"Nowy użytkownik dołączył do serwera: {member.mention}! Witamy! Honk!") #TODO language pack
            except discord.errors.Forbidden:
                print(f"#on_member_join.py | ERROR | No privileges to send in notification channel (ID: {notification_channel_id})") #TODO language pack
        else:
            print(f"#on_member_join.py | ERROR | Notification channel not found, ID: {notification_channel_id}")


async def setup(bot: commands.Bot): #standard initialization function
    await bot.add_cog(WelcomeHandler(bot))
