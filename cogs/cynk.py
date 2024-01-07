import os
import pprint
import random

import discord.ext.commands
import numpy
from discord import SelectOption
from discord import app_commands
from discord.ext import commands
from discord.ui import Select, View
from discord.app_commands import Choice
from discord import Interaction, Button, ButtonStyle
from PIL import Image, ImageDraw
from io import BytesIO
from db import languages, events, locations, roles
from db_clases import User, Location, Server
from misc import set_locale_autocomplete, chunker, process_event, get_localized_answer, update_events_and_weights, \
    player_chars_autocomplete, stats_autocomplete, stat_and_skill_autocomplete, localized_data, roll_stat, lvl_up, \
    get_item_from_translation_dict, say, set_image
from placeholders import move_url_placeholder
from views import ManualView, chars, get_stats, get_info, get_stat_view, checks, get_inventory_view, pda, health, \
    ShopView, TradersView, trade
from static import ITEM_TYPES_NOT_GM


class Cynk(commands.GroupCog, name="cynk"):
    def __init__(self, client):
        self.client = client
        super().__init__()

    @app_commands.command(description='set_localization_description')
    @app_commands.autocomplete(choices=set_locale_autocomplete)
    async def set_localization(self, i: Interaction, choices: str):
        user = User(i.user.id, i.guild.id)
        if languages.find_one({'language': choices}):
            user.set_localization(choices)
            await i.response.send_message(content=get_localized_answer('set_localization_good_answer',
                                                                       user.get_localization()), ephemeral=True)
        else:
            await i.response.send_message(content=get_localized_answer('set_localization_bad_answer',
                                                                       user.get_localization()), ephemeral=True)

    @app_commands.command(description='lvl_up_description')
    @app_commands.autocomplete(name=player_chars_autocomplete, stat=stats_autocomplete)
    async def lvl_up(self, i: Interaction, stat: str, name: str = None, num: int = 1):
        await lvl_up(i, stat, num, name)

    @app_commands.command(description='roll_description')
    @app_commands.autocomplete(name=player_chars_autocomplete, stat=stat_and_skill_autocomplete)
    async def roll(self, i: Interaction, stat: str, buff_or_debuff: int = 0, name: str = None):
        await roll_stat(i, stat, buff_or_debuff, name)

    @app_commands.command(description='chars_description')
    async def chars(self, i: Interaction):
        await chars(i, i.user.id, False)

    @app_commands.command(description='say_char_description')
    @app_commands.autocomplete(name=player_chars_autocomplete)
    async def say(self, i: Interaction, what_to_say: str, name: str = None):
        await say(i, name, what_to_say, False, self.client, os.environ.get('TOKEN'))

    @app_commands.command(description='set_char_image_description')
    @app_commands.autocomplete(name=player_chars_autocomplete)
    async def set_image(self, i: Interaction, image: discord.Attachment, name: str = None):
        await set_image(i, name, image, False)

    @roll.error
    @lvl_up.error
    @chars.error
    @set_image.error
    async def char_error(self, i: Interaction, error: app_commands.AppCommandError):
        user_localization = User(i.user.id, i.guild.id).get_localization()
        await i.response.send_message(get_localized_answer('char_error', user_localization), ephemeral=True)
        print(error)

   # @app_commands.command(description='shop')
   # @app_commands.choices(item_type=[Choice(name=typ, value=typ) for typ in ITEM_TYPES_NOT_GM],
    #                      per_page=[Choice(name=str(typ), value=typ) for typ in [3, 5, 10]])
   # @app_commands.autocomplete(name=player_chars_autocomplete)
   # async def shop(self, i, item_type: str, name: str = None, per_page: int = 5):
    #    can_pass, char, user_locale = await checks(i, name, False)
     #   view = ShopView(i, char, item_type, per_page, user_locale, False)
      #  await i.response.send_message(content=view.get_str(), view=view, embeds=view.get_embeds())

    @app_commands.command(description='trade')
    @app_commands.autocomplete(name=player_chars_autocomplete)
    @app_commands.choices(trade_select=[Choice(name=typ, value=typ) for typ in ['traders', 'npcs', 'players']])
    async def trade(self, i, trade_select: str, name: str = None):
        await trade(i, name, trade_select)


async def setup(client):
    await client.add_cog(Cynk(client))
