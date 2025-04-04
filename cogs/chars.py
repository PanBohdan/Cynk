import os
from typing import List

import discord
from bson import json_util, ObjectId
from discord import app_commands, Interaction
from discord.app_commands import Choice
from discord.ext import commands

from cheks import check_for_stat_or_skill
from db import characters, get_localized_answer
from db_clases import User, Character
from misc import chars_autocomplete, stat_and_skill_autocomplete, set_stat_or_skill, roll_stat, stats_autocomplete, \
    lvl_up, get_char, universal_updater, clone_char, say, set_image, chars_autocomplete_for_npc, items_autocomplete, \
    inventory_swaper
from static import CAN_BE_STR_IN_CHAR, CAN_BE_INT_IN_CHAR, CHAR_TYPES, FACTIONS, ITEM_TYPES
from views import char_creation_str, create_char, get_stats, chars, get_info, get_stat_view, delete_char, \
    get_inventory_view, ShopView, checks, shoot


async def get_character_autocomplete(interaction: discord.Interaction, current: str) -> List[Choice[str]]:
    choices = [str(x['_id']) for x in characters.find({'guild_id': interaction.guild_id})]
    return [
               Choice(name=choice, value=choice)
               for choice in choices if current in choice
           ][:25]


class Chars(commands.GroupCog, name="chars"):
    def __init__(self, client):
        self.client: discord.Client = client
        super().__init__()

    @app_commands.command(description='create_char_description')
    @app_commands.autocomplete(npc_owner=chars_autocomplete)
    @app_commands.choices(char_type=[Choice(name=typ, value=typ) for typ in CHAR_TYPES],
                          faction=[Choice(name=typ, value=typ) for typ in FACTIONS])
    async def create(self, i: Interaction, name: str, char_type: str, player_owner: discord.User = None,
                     npc_owner: str = None, faction: str = None):
        owner = None
        if player_owner:
            owner = player_owner.id
        elif npc_owner:
            owner = get_char(i, npc_owner, False, False).char['_id']
        user = User(i.user.id, i.guild.id)
        char = Character(i.guild_id, owner, faction=faction)
        char.create(name, char_type)
        await i.response.send_message(content=char_creation_str(name, user.get_localization()))

    @app_commands.command(description='change_owner_description')
    @app_commands.autocomplete(name=chars_autocomplete, npc_owner=chars_autocomplete)
    async def change_owner(self, i: Interaction, name: str, player_owner: discord.User = None, npc_owner: str = None):
        owner = None
        if player_owner:
            owner = player_owner.id
        elif npc_owner:
            owner = get_char(i, npc_owner, False, False).char['_id']
        user = User(i.user.id, i.guild.id)
        char = get_char(i, name, False, False)
        char.update('owner_id', owner)
        await i.response.send_message(content=get_localized_answer('owner_changed', user.get_localization()))

    @app_commands.command(description='creation_menu_description')
    @app_commands.choices(char_type=[Choice(name=typ, value=typ) for typ in CHAR_TYPES])
    async def creation_menu(self, i: discord.Interaction, char_type: str, owner: discord.User = None):
        if owner:
            owner = owner.id
        await create_char(i, True, owner, char_type)

    @app_commands.command(description='delete_char_description')
    @app_commands.autocomplete(name=chars_autocomplete)
    async def delete(self, i: Interaction, name: str):
        await delete_char(i, name)

    @app_commands.command(description='load_char_description')
    async def load(self, i: discord.Interaction, file: discord.Attachment):
        if file.filename.endswith('.json'):
            char_bson = json_util.loads(await file.read())
            char_bson.pop('_id')
            characters.insert_one(char_bson)
            await i.response.send_message(content='loaded')  # TODO: localization
        else:
            await i.response.send_message(content='not json')  # TODO: localization

    @app_commands.command(description='clone_char_description')
    @app_commands.autocomplete(name=chars_autocomplete)
    @app_commands.choices(new_type=[Choice(name=typ, value=typ) for typ in CHAR_TYPES])
    async def clone(self, i: Interaction, name: str, new_name: str = None, new_owner: discord.User = None,
                    new_type: str = None):
        if new_owner:
            new_owner = new_owner.id
        await clone_char(i, name, new_name, new_owner, new_type)

    @app_commands.command(description='edit_int_char_description')
    @app_commands.autocomplete(name=chars_autocomplete)
    @app_commands.choices(what_to_set=[Choice(name=typ, value=typ) for typ in CAN_BE_INT_IN_CHAR],
                          mode=[Choice(name='set', value=0), Choice(name='change', value=1)])
    async def edit_int(self, i: Interaction, mode: int, name: str, what_to_set: str, value: int):
        await universal_updater(i, name, what_to_set, value, mode)

    @app_commands.command(description='set_str_char_description')
    @app_commands.autocomplete(name=chars_autocomplete)
    @app_commands.choices(what_to_set=[Choice(name=typ, value=typ) for typ in CAN_BE_STR_IN_CHAR])
    async def set_str(self, i: Interaction, name: str, what_to_set: str, value: str):
        await universal_updater(i, name, what_to_set, value, 0)

    @app_commands.command(description='set_stat_or_skill_char_description')
    @app_commands.autocomplete(name=chars_autocomplete, what_to_set=stat_and_skill_autocomplete)
    @app_commands.check(check_for_stat_or_skill)
    async def set_stat_or_skill(self, i: Interaction, name: str, what_to_set: str, value: int):
        await set_stat_or_skill(i, what_to_set, value, name, True)

    @app_commands.command(description='faction_rep_char_description')
    @app_commands.autocomplete(name=chars_autocomplete)
    @app_commands.choices(what_to_set=[Choice(name=typ, value=typ) for typ in FACTIONS],
                          mode=[Choice(name='set', value=0), Choice(name='change', value=1)])
    async def faction_rep(self, i: Interaction, mode: int, name: str, what_to_set: str, value: float):
        await universal_updater(i, name, what_to_set, value, mode, True)

    @app_commands.command(description='change_faction_description')
    @app_commands.autocomplete(name=chars_autocomplete)
    @app_commands.choices(value=[Choice(name=typ, value=typ) for typ in FACTIONS])
    async def change_faction(self, i: Interaction, name: str, value: str):
        await universal_updater(i, name, 'faction', value, 0)

    @app_commands.command(description='character_rep_char_description')
    @app_commands.autocomplete(name=chars_autocomplete, rep_name=chars_autocomplete)
    @app_commands.choices(mode=[Choice(name='set', value=0), Choice(name='change', value=1)])
    async def character_rep(self, i: Interaction, mode: int, name: str, rep_name: str, value: float):
        await universal_updater(i, name, rep_name, value, mode, False, True)

    @app_commands.command(description='roll_description')
    @app_commands.autocomplete(name=chars_autocomplete, stat=stat_and_skill_autocomplete)
    async def roll(self, i: discord.Interaction, name: str, stat: str, buff_or_debuff: int = 0):
        await roll_stat(i, stat, buff_or_debuff, name, True)

    @app_commands.command(description='lvl_up_description')
    @app_commands.autocomplete(name=chars_autocomplete, stat=stats_autocomplete)
    async def lvl_up(self, i: discord.Interaction, name: str, stat: str, num: int = 1):
        await lvl_up(i, stat, num, name, True)

    @app_commands.command(description='char_get_description')
    @app_commands.autocomplete(name=chars_autocomplete)
    @app_commands.choices(
        mode=[Choice(name='stats', value=0), Choice(name='info_menu', value=1), Choice(name='stats_menu', value=2),
              Choice(name='inventory_menu', value=3),
              ])
    async def get(self, i: discord.Interaction, mode: int, name: str = None):
        match mode:
            case 0:
                await get_stats(i, name, True)
            case 1:
                await get_info(i, name, True)
            case 2:
                await get_stat_view(i, name, True)
            case 3:
                await get_inventory_view(i, name, True)

    @app_commands.command(description='set_char_image_description')
    @app_commands.autocomplete(name=chars_autocomplete)
    async def set_image(self, i: discord.Interaction, name: str, image: discord.Attachment = None):
        await set_image(i, name, image, True)

    @app_commands.command(description='say_char_description')
    @app_commands.autocomplete(name=chars_autocomplete)
    async def say(self, i: discord.Interaction, name: str, what_to_say: str):
        await say(i, name, what_to_say, True, self.client, os.environ.get('TOKEN'))

    @app_commands.command(description='panel_description')
    async def admin_panel(self, i: Interaction):
        await chars(i, 1164511378955055136, True, False, True)

    @app_commands.command(description='shoot_char_description')
    @app_commands.autocomplete(who_is_shooting=chars_autocomplete, who_is_shot=chars_autocomplete)
    async def shoot(self, i: discord.Interaction, who_is_shooting: str, who_is_shot: str):
        await shoot(i, who_is_shooting, who_is_shot)
    #
    # @app_commands.command(description='test_autofight')
    # async def test_autofight(self, i: discord.Interaction):
    #     localizations = User(i.user.id, i.guild.id).get_localization()
    #     body_part_data = localized_data.find_one({'request': 'body_parts'})['local']
    #     await i.response.send_message('test_autofight')
    #     char1 = get_char(i, '66bdede72e088008748e1b46')
    #     char2 = get_char(i, '66bdedc92e088008748e1b45')
    #     char3 = get_char(i, '66bdeda22e088008748e1b44')
    #     char4 = get_char(i, '66bded872e088008748e1b43')
    #     for char in [char1, char2, char3, char4]:
    #         for body_part in char.char['hp'].keys():
    #             current = char.char['hp'][body_part]
    #             current = (current[1], current[1])
    #             char.update(body_part, current)
    #     team_1 = [char1, char2]
    #     team_2 = [char3, char4]
    #     await i.followup.send(f'{team_1[0].char["name"]} and {team_1[1].char["name"]} vs {team_2[0].char["name"]} and {team_2[1].char["name"]}')
    #     initiative_pool = []
    #     dead_chars = []
    #     for char in team_1 + team_2:
    #         initiative_pool.append((char.roll_dice('mobility')[1], char))
    #     initiative_pool.sort(key=lambda x: x[0], reverse=True)
    #     await i.followup.send(f'Initiative pool: {[(x[1].char["name"], x[0]) for x in initiative_pool]}')
    #     while len(dead_chars) < 3:
    #         for _, char in initiative_pool:
    #             if char in dead_chars:
    #                 continue
    #             if char in team_1:
    #                 target = team_2
    #             else:
    #                 target = team_1
    #             target = [x for x in target if x not in dead_chars]
    #             if len(target) == 0:
    #                 break
    #             target = random.choice(target)
    #             await i.followup.send(f'{char.char["name"]} attacks {target.char["name"]}')
    #             log, ammo, body_part_damage = char.shoot(target)
    #             await i.followup.send(interpreted_logs(log, localizations, body_part_data))
    #             for entry in log:
    #                 if entry.get('penetrated', False):
    #                     target.damage(entry['damage'], entry['body_part'])
    #                     await i.followup.send(f'{target.char["name"]} takes {entry["damage"]} damage to {entry["body_part"]}')
    #                     if target.is_dead():
    #                         dead_chars.append(target)
    #                         await i.followup.send(f'{target.char["name"]} is dead')
    #                         break
    #                 else:
    #                     if entry.get('missed', True):
    #                         pass
    #                     else:
    #                         await i.followup.send(f'{char.char["name"]} hit {target.char["name"]} but did not penetrate')
    #         await i.followup.send(f'End of round\n'
    #                               f'current hp:\n'
    #                               'Team 1:\n'
    #                               f'{team_1[0].char["name"]}: {team_1[0].char["hp"]}\n'
    #                               f'{team_1[1].char["name"]}: {team_1[1].char["hp"]}\n'
    #                               'Team 2:\n'
    #                               f'{team_2[0].char["name"]}: {team_2[0].char["hp"]}\n'
    #                               f'{team_2[1].char["name"]}: {team_2[1].char["hp"]}')
    #         await i.followup.send('Round')
    @app_commands.command(description='chars_description')
    @app_commands.autocomplete(npc_owner=chars_autocomplete_for_npc)
    async def chars(self, i: discord.Interaction, user: discord.User = None, npc_owner: str = None,
                    all_chars: bool = False):
        if user:
            user = user.id
        elif npc_owner:
            user = get_char(i, npc_owner, False, False).char['_id']
        else:
            user = i.user.id
        await chars(i, user, True, all_chars)

    @app_commands.command(description='add_char_item_description')
    @app_commands.autocomplete(name=chars_autocomplete, item=items_autocomplete)
    @app_commands.choices(mode=[Choice(name='add', value=0), Choice(name='remove', value=1)])
    async def items(self, i: discord.Interaction, mode: int, name: str, item: str, quantity: int = 1):
        char = get_char(i, name)
        match mode:
            case 0:
                char.add_item(ObjectId(item), quantity)
                await i.response.send_message('item_added')  # TODO add localization
            case 1:
                char.remove_item_by_id(ObjectId(item), quantity)
                await i.response.send_message('item_removed')  # TODO add localization

    @app_commands.command(description='shop')
    @app_commands.choices(item_type=[Choice(name=typ, value=typ) for typ in ITEM_TYPES],
                          per_page=[Choice(name=str(typ), value=typ) for typ in [3, 5, 10]])
    @app_commands.autocomplete(name=chars_autocomplete)
    async def shop(self, i, name: str, item_type: str, per_page: int = 5):
        await i.response.defer()
        can_pass, char, user_locale = await checks(i, name, True)
        view = ShopView(i, char, item_type, per_page, user_locale, True)
        await i.edit_original_response(content=view.get_str(), view=view, embeds=view.get_embeds())

    @app_commands.command(description='character_inventory_swap_description')
    @app_commands.autocomplete(name=chars_autocomplete, receiver_name=chars_autocomplete)
    @app_commands.choices(
        mode=[Choice(name='replace', value=0), Choice(name='add', value=1), Choice(name='add_to_limit', value=2), ])
    async def inventory_swap(self, i: Interaction, mode: int, name: str, receiver_name: str):
        await inventory_swaper(i, name, receiver_name, mode)

    # async def cog_app_command_error(self, i: discord.Interaction, error: app_commands.AppCommandError):
    #    user_localization = User(i.user.id, i.guild.id).get_localization()
    #    await i.response.send_message(get_localized_answer('char_error', user_localization), ephemeral=True)
    #    print(error)


async def setup(client):
    await client.add_cog(Chars(client))
