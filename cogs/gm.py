import os
from typing import List

import discord
from discord import app_commands, Interaction
from discord.app_commands import Choice
from discord.ext import commands

from cheks import check_for_stat_or_skill
from db import characters, get_localized_answer
from db_clases import User, Character
from static import CAN_BE_STR_IN_CHAR, CAN_BE_INT_IN_CHAR, CHAR_TYPES, FACTIONS, RESIST_LIST, ITEM_TYPES
from misc import chars_autocomplete, stat_and_skill_autocomplete, set_stat_or_skill, roll_stat, stats_autocomplete, \
    lvl_up, get_char, universal_updater, clone_char, say, set_image, chars_autocomplete_for_npc, items_autocomplete, \
    inventory_swaper
from views import char_creation_str, create_char, get_stats, chars, get_info, get_stat_view, delete_char, \
    get_inventory_view, ShopView, checks, MainMenuView
from bson import json_util, ObjectId


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
