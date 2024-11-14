import discord
from discord import app_commands, Interaction
from discord.ext import commands

from misc import get_char, chars_autocomplete_for_npc
from views import chars


class GM(commands.GroupCog, name="gm"):
    @app_commands.command(description='mutants_description')
    async def mutants(self, i: Interaction):
        await chars(i, 1164511378955055136, True, False, True)

    @app_commands.command(description='mutants_description')
    async def npc(self, i: Interaction):
        await chars(i, 1137324730765037609, True, False, True)

    @app_commands.command(description='all_description')
    @app_commands.autocomplete(npc_owner=chars_autocomplete_for_npc)
    async def all(self, i: discord.Interaction, user: discord.User = None, npc_owner: str = None,
                    all_chars: bool = False):
        if user:
            user = user.id
        elif npc_owner:
            user = get_char(i, npc_owner, False, False).char['_id']
        else:
            user = i.user.id
        await chars(i, user, True, all_chars)


async def setup(client):
    await client.add_cog(GM(client))
