import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
from typing import List

class RolePanelAdmin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db_path = self.bot.config["database_path"]
        
    # --- Helper function to autocomplete ---
    async def group_autocomplete(self,interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    # Returns an list of group roles from server to be autocompleted
        choices = []
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT group_name FROM role_groups WHERE guild_id = ?", (interaction.guild.id,))
            groups = await cursor.fetchall()
            for group in groups:
                if current.lower() in group[0].lower():
                    choices.append(app_commands.Choice(name=group[0], value=group[0]))
        return choices[:25]
    
    # --- Command group ---
    admin_role_group = app_commands.Group(name="manage_roles", description="Commands to modify panels to edit roles.") # TODO language pack

    # --- Commands to change role groups ---
    
    #Create group
    @admin_role_group.command(name="create_group", description="Creates new role to be selected.") # TODO language pack
    @app_commands.describe(name="Group name (ex. Notifications)", description="Short group description") #TODO language pack
    @app_commands.checks.has_permissions(manage_roles=True)
    async def create_group(self, interaction: discord.Interaction, name:str, description:str):
        await interaction.response.defer(ephemeral=True)
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    "INSERT INTO role_groups (guild_id, group_name, group_description) VALUES (?, ?, ?)",
                    (interaction.guild.id, name, description)
                )
                await db.commit()
            await interaction.followup.send(f"Succesfully created roles group: **{name}**.", ephemeral=True) #TODO language pack
        except aiosqlite.IntegrityError:
            await interaction.followup.send(f"Error: Group with name **{name}** already exists on this server.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Unexpected error occured: {e}", ephemeral=True)


    #Delete group
    @admin_role_group.command(name="delete_group", description="Deletes role group.") # TODO language pack
    @app_commands.describe(name="Group name to be deleted") #TODO language pack
    @app_commands.autocomplete(group=group_autocomplete)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def delete_group(self, interaction: discord.Interaction, group:str):
        await interaction.response.defer(ephemeral=True)
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "DELETE FROM role_groups WHERE guild_id = ? AND group_name = ?",
                    (interaction.guild.id, group)
                )
                await db.commit()
                if cursor.rowcount > 0:
                    await interaction.followup.send(f"Succesfully role group **{group}**.", ephemeral=True)
                else: 
                    await interaction.followup.send(f"Error: Couldnt find group of name **{group}**.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"ERROR: Unexpected error ocurred: {e}", ephemeral=True)

    # --- Commands to change roles in groups ---
    # Adding role to groups
    @admin_role_group.command(name="add_role", description="Adds role to be selected in group.")
    @app_commands.describe(group="Group name", role="Role, which can be selected in group", description="Short role description.")
    @app_commands.autocomplete(group=group_autocomplete)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def add_role_to_group(self, interaction: discord.Interaction, group: str, role: discord.Role, description: str):
        await interaction.response.defer(ephemeral=True)
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # First check group_id on base of group name
                cursor = await db.execute("SELECT group_id FROM role_groups WHERE guild_id = ? AND group_name = ?", (interaction.guild.id, group))
                group_row = await cursor.fetchone()
                if not group_row:
                    await interaction.followup.send(f"ERROR: No found group with name **{group}**.", ephemeral=True)
                    return
                group_id = group_row[0]
                
                await db.execute(
                    "INSERT INTO selectable_roles (guild_id, group_id, role_id, role_description) VALUES (?, ?, ?, ?)",
                    (interaction.guild.id, group_id, role.id, description)
                )
                await db.commit
            await interaction.followup.send(f"Added role **{role.name}** to group **{group}**", ephemeral=True)
        except aiosqlite.IntegrityError:
            await interaction.followup.send(f"Error: Role **{role.name} is already in group **{group}**", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Unexpected error occured: {e}", ephemeral=True)
    
    # Removing role from groups
    @admin_role_group.command(name="remove_role", description="Removes role from group selection.")
    @app_commands.describe(group="Group name", role="Role to be removed from selection")
    @app_commands.autocomplete(group=group_autocomplete)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def remove_role_to_group(self, interaction: discord.Interaction, group: str, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                        """
                        DELETE FROM selectable_roles
                        WHERE role_id = ? AND group_id = (
                            SELECT group_id FROM role_groups WHERE guild_id = ? AND group_name = ?
                            )
                        """, (role.id, interaction.guild.id, group)
                )
                await db.commit()
                if cursor.rowcount > 0:
                    await interaction.followup.send(f"Succesfully removed role **{role.name} from group **{group}**.", ephemeral=True)
                else:
                    await interaction.followup.send(f"ERROR: Not found such role in that group", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Occured unexpected error: {e}", ephemeral=True)

    # --- Commands to change privileges ---
    @admin_role_group.command(name="add_access", description="Adds an access for role to group roles")
    @app_commands.describe(group="Group name", role_needed="Role, which gives permission to use this group")
    @app_commands.autocomplete(group=group_autocomplete)
    @app_commands.checks.has_permissions(manage_roles = True)
    async def grant_access(self, interaction: discord.Interaction, group: str, role_needed= discord.Role):
        await interaction.response.defer(ephemeral=True)
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("SELECT group_id FROM role_groups WHERE guild_id = ? AND group_name = ?",
                                          (interaction.guild.id, group))
                group_row = await cursor.fetchone()
                if not group_row:
                    await interaction.followup.send(f"ERROR:Couldn't find group with name **{group}**.", ephemeral=True)
                    return
                group_id = group_row[0]

                await db.execute(
                    "INSERT INTO role_group_permissions (guild_id, required_role_id, group_id) VALUES (?, ?, ?)",
                    (interaction.guild.id, role_needed.id, group_id)
                )
                await db.commit()
            await interaction.followup.send(f"Role **{role_needed} has now acces to this group: {group}.", ephemeral=True)
        except aiosqlite.IntegrityError:
            await interaction.followup.send(f"ERROR: This role already has access to this group.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"ERROR: Unexpected error: {e}.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(RolePanelAdmin(bot))