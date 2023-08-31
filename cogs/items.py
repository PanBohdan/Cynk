import re

import bson
import discord
from PIL import Image
from discord import app_commands, Interaction
from discord.app_commands import Choice
from discord.ext import commands

from db_clases import Item, User

from misc import items_autocomplete, set_locale_autocomplete, check_for_server_default, \
    stat_and_skill_autocomplete, get_stat, ammo_types_autocomplete, available_formats, get_localized_answer, localized_data, items_buff_autocomplete
from views import get_item_embed
from static import ITEM_TYPES, CAN_BE_NUM_IN_ITEM, ITEM_LOCALIZED_FIELDS, CAN_BE_BOOL_IN_ITEM, \
    CAN_BE_INT_IN_CHAR, PLATE_TYPES
import io

class Items(commands.GroupCog, name="items"):
    def __init__(self, client):
        self.client: discord.Client = client
        super().__init__()

    @app_commands.command(description='create_item')
    @app_commands.choices(item_type=[Choice(name=typ, value=typ) for typ in ITEM_TYPES])
    async def create(self, i: Interaction, name: str, description: str, item_type: str, price: int,
                     weight: float, can_be_used: bool, can_be_equipped: bool):
        item = Item(i.guild_id)
        item.create(name, description, item_type, weight, price, can_be_used, can_be_equipped)
        await i.response.send_message(content='todo  OK')  # todo  OK

    @app_commands.command(description='create_plate_carrier')
    @app_commands.choices(stomach_protection=[Choice(name=typ, value=typ) for typ in PLATE_TYPES + ['none']],
                          thorax_protection=[Choice(name=typ, value=typ) for typ in PLATE_TYPES + ['none']],
                          arms_protection=[Choice(name=typ, value=typ) for typ in PLATE_TYPES + ['none']],
                          legs_protection=[Choice(name=typ, value=typ) for typ in PLATE_TYPES + ['none']])
    async def create_plate_carrier(self, i: Interaction, name: str, description: str, price: int,
                                   weight: float, modification_slots: int, stomach_protection: str,
                                   thorax_protection: str, arms_protection: str, legs_protection: str):
        if stomach_protection == 'none':
            torso_protection = None
        if thorax_protection == 'none':
            thorax_protection = None
        if arms_protection == 'none':
            arms_protection = None
        if legs_protection == 'none':
            legs_protection = None
        item = Item(i.guild_id)
        item.create_plate_carrier(name, description, weight, price, modification_slots, torso_protection,
                                  thorax_protection, arms_protection, legs_protection)
        await i.response.send_message(content='todo  OK')  # todo  OK

    @app_commands.command(description='create_armor')
    async def create_armor(self, i: Interaction, name: str, description: str, price: int,
                           weight: float, modification_slots: int,
                           head: int, thorax: int, stomach: int,
                           right_arm: int, left_arm: int, right_leg: int, left_leg: int):
        item = Item(i.guild_id)
        item.create_armor(name, description, weight, price, modification_slots, head, thorax,
                          stomach, right_arm, left_arm, right_leg, left_leg)
        await i.response.send_message(content='todo  OK')  # todo  OK

    @app_commands.command(description='create_plate')
    @app_commands.choices(plate_type=[Choice(name=typ, value=typ) for typ in PLATE_TYPES])
    async def create_plate(self, i: Interaction, name: str, description: str, price: int,
                           weight: float, plate_class: int, plate_type: str):
        item = Item(i.guild_id)
        item.create_plate(name, description, weight, price, plate_class, plate_type)
        await i.response.send_message(content='todo  OK')  # todo  OK

    @app_commands.command(description='create_ammo')
    @app_commands.autocomplete(ammo_type=ammo_types_autocomplete)
    async def create_ammo(self, i: Interaction, name: str, description: str, ammo_type: str,
                          price: int, weight: float,
                          dice_count: int, dice_sides: int, dice_bonus: int,
                          penetration_green: int, penetration_yellow: int, penetration_red: int):
        item = Item(i.guild_id)
        ammo_type = bson.ObjectId(ammo_type)
        damage_dice = (dice_count, dice_sides, dice_bonus)
        armor_penetration = (penetration_green, penetration_yellow, penetration_red)
        item.create_ammo(name, description, weight, price, damage_dice, armor_penetration, ammo_type)
        await i.response.send_message(content='todo  OK')

    @app_commands.command(description='create_weapon')
    @app_commands.autocomplete(used_stat=stat_and_skill_autocomplete, ammo_type=ammo_types_autocomplete)
    async def create_weapon(self, i: Interaction, name: str, description: str, price: int,
                            weight: float, used_stat: str, ammo_type: str):
        item = Item(i.guild_id)
        user = User(i.user.id, i.guild_id)
        ammo_type = bson.ObjectId(ammo_type)
        item.create_weapon(name, description, weight, price, get_stat(used_stat, user.get_localization()), ammo_type)
        await i.response.send_message(content='todo  OK')

    @app_commands.command(description='create_modification')
    @app_commands.choices(mod_type=[Choice(name=typ, value=n) for n, typ in enumerate(['weapon', 'armor'])])
    async def create_modification(self, i: Interaction, name: str, description: str, mod_type: int, price: int,
                                  weight: float, modification_slots: int):
        item = Item(i.guild_id)
        item.create_modification(name, description, mod_type, weight, price, modification_slots)
        await i.response.send_message(content='todo  OK')  # todo  OK

    @app_commands.command(description='delete_item')
    @app_commands.autocomplete(name=items_autocomplete)
    async def delete(self, i: Interaction, name: str):
        item = Item(i.guild_id, bson.ObjectId(name))
        item.delete()
        await i.response.send_message(content='todo  OK')  # todo  OK

    @app_commands.command(description='set_item_type')
    @app_commands.autocomplete(name=items_autocomplete)
    @app_commands.choices(what_to_set=[Choice(name=typ, value=typ) for typ in ITEM_TYPES])
    async def set_type(self, i: Interaction, name: str, what_to_set: str):
        item = Item(i.guild_id, bson.ObjectId(name))
        item.update('type', what_to_set)
        await i.response.send_message(content='todo  OK')  # todo  OK

    @app_commands.command(description='set_item_number')
    @app_commands.autocomplete(name=items_autocomplete)
    @app_commands.choices(what_to_update=[Choice(name=typ, value=typ) for typ in CAN_BE_NUM_IN_ITEM])
    async def set_number(self, i: Interaction, name: str, what_to_update: str, number: float):
        item = Item(i.guild_id, bson.ObjectId(name))
        if what_to_update != 'weight':
            number = int(number)
        item.update(what_to_update, number)
        await i.response.send_message(content='todo  OK')

    @app_commands.command(description='set_item_bool')
    @app_commands.autocomplete(name=items_autocomplete)
    @app_commands.choices(what_to_update=[Choice(name=typ, value=typ) for typ in CAN_BE_BOOL_IN_ITEM])
    async def set_bool(self, i: Interaction, name: str, what_to_update: str, boolean: bool):
        item = Item(i.guild_id, bson.ObjectId(name))
        item.update(what_to_update, boolean)
        await i.response.send_message(content='todo  OK')

    @app_commands.command(description='set_item_string')
    @app_commands.autocomplete(name=items_autocomplete, localization=set_locale_autocomplete)
    @app_commands.choices(what_to_update=[Choice(name=typ, value=typ) for typ in ITEM_LOCALIZED_FIELDS])
    async def set_string(self, i: Interaction, name: str, what_to_update: str, string: str,
                         localization: str = 'default'):
        localization = check_for_server_default(localization, i)
        item = Item(i.guild_id, bson.ObjectId(name))
        item.update(what_to_update, string, localization)
        await i.response.send_message(content='todo  OK')

    @app_commands.command(description='set_item_image')
    @app_commands.autocomplete(name=items_autocomplete)
    async def set_image(self, i: Interaction, name: str, url: str = None, image: discord.Attachment = None):
        image_url = ''
        user_locale = User(i.user.id, i.guild_id).get_localization()
        item = Item(i.guild_id, bson.ObjectId(name))

        await i.response.defer()
        if url:
            pattern = "^https:\/\/[0-9A-z.]+.[0-9A-z.]+.[a-z]+$"
            result = re.match(pattern, url)
            if result:
                image_url = url
        elif Image:
            img = await image.to_file()
            save_format = img.filename.split('.')[-1]
            if save_format.lower() not in available_formats:
                await i.followup.send(
                    content=get_localized_answer('wrong_format_error', user_locale).format(types=available_formats))
                return
            if save_format.lower() == 'jpg':
                save_format = 'jpeg'
            with Image.open(img.fp) as img:
                with io.BytesIO() as buffer:
                    img.save(buffer, save_format)
                    buffer.seek(0)
                    mes = await i.followup.send(content='', file=discord.File(buffer, filename=f'avatar.{save_format}'))
            image_url = mes.attachments[0].url
        if not image_url:
            await i.followup.send(content='error todo  OK')
        else:
            item.update('image_url', image_url)
            await i.followup.send(content='Done')

    @app_commands.command(description='info')
    @app_commands.autocomplete(name=items_autocomplete)
    async def info(self, i: Interaction, name: str):
        item = Item(i.guild_id, bson.ObjectId(name))
        user = User(i.user.id, i.guild_id)
        translation_data = localized_data.find_one({'request': 'inventory_view_data'})['local']
        body_part_translation_data = localized_data.find_one({'request': 'body_parts'})['local']
        embed_data = localized_data.find_one({'request': 'item_embed_data'})['local']

        await i.response.send_message(embeds=[get_item_embed(item.item, body_part_translation_data, translation_data, embed_data, user.get_localization(), 2)])

    @app_commands.command(description='add_buff_action_to_item')
    @app_commands.autocomplete(name=items_buff_autocomplete, what_to_buff=stat_and_skill_autocomplete)
    @app_commands.choices(when=[Choice(name='used', value='used'), Choice(name='equipped', value='equipped')])
    async def add_buff_action(self, i: Interaction, name: str, when: str, what_to_buff: str, value: int):
        item = Item(i.guild_id, bson.ObjectId(name))
        user = User(i.user.id, i.guild_id)
        item.add_buff_action(when, get_stat(what_to_buff, user.get_localization()), value)
        await i.response.send_message(content='todo  OK')

    @app_commands.command(description='add_one_time_buff_action_to_item')
    @app_commands.autocomplete(name=items_autocomplete)
    @app_commands.choices(what_to_buff=[Choice(name=x, value=x) for x in CAN_BE_INT_IN_CHAR])
    async def add_one_time_buff_action(self, i: Interaction, name: str, what_to_buff: str, positive: bool, x: int,
                                       y: int, z: int):
        item = Item(i.guild_id, bson.ObjectId(name))
        user = User(i.user.id, i.guild_id)
        positive = 1 if positive else -1
        item.add_one_time_buff_action('used', what_to_buff, (positive, x, y, z))
        await i.response.send_message(content='todo  OK')

    @app_commands.command(description='clear_buff_actions')
    @app_commands.autocomplete(name=items_buff_autocomplete)
    async def clear_buff_actions(self, i: Interaction, name: str):
        item = Item(i.guild_id, bson.ObjectId(name))
        user = User(i.user.id, i.guild_id)
        item.clear_buff_actions()
        await i.response.send_message(content='todo  OK')



async def setup(client):
    await client.add_cog(Items(client))
