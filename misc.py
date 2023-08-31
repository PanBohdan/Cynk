import random
from typing import List, Union

import bson
import discord
from discord.app_commands import Choice
import io
from io import BytesIO
from db import get_localized_answer, characters, languages, localized_data, events, get_item_from_translation_dict, \
    items
from db_clases import User, Character, Server
from static import SKILLS, STATS, FACTIONS, CAN_BE_CHANGED_IN_CHAR, ARMOR_TYPES, HEALTH_COORDS
from PIL import Image, ImageDraw, ImageFont
from placeholders import char_image_placeholder


async def gm_check(i, char, user_locale, gm):
    if check := not gm:
        if check := char['owner_id'] != i.user.id:
            await i.response.send_message(get_localized_answer('not_yours', user_locale))
    return check


def get_hp_image(hp_dict):
    img = Image.open('HUD.jpg')
    img_dr = ImageDraw.Draw(img)
    font = ImageFont.truetype('bender_bolf.otf', 20)
    for x in HEALTH_COORDS.keys():
        if hp_dict[x][0] <= 0:
            color = 'black'
        elif 0.4 < hp_dict[x][0] / hp_dict[x][1] <= 0.7:
            color = '#cccc00'
        elif 0.2 < hp_dict[x][0] / hp_dict[x][1] <= 0.4:
            color = '#f65b00'
        elif hp_dict[x][0] / hp_dict[x][1] <= 0.2:
            color = "#770500"
        else:
            color = '#069104'
        if hp_dict[x][0] > 0:
            img_dr.rectangle((HEALTH_COORDS[x],
                              (HEALTH_COORDS[x][0] + 233 * hp_dict[x][0] / hp_dict[x][1], HEALTH_COORDS[x][1] + 17)),
                             fill=color)
        img_dr.text(((HEALTH_COORDS[x][0] + 233 / 2 - 30), (HEALTH_COORDS[x][1] + 17) - 20),
                    f"{hp_dict[x][0]}/{hp_dict[x][1]}",
                    fill='white',
                    align='right', font=font, stroke_fill='black', stroke_width=2)
    return img


def get_loc_image(coords, zoom, cam_coords=None):
    if not cam_coords:
        cam_coords = coords
    view = (int(770 / zoom), int(1152 / zoom))
    resize_factor = (int(77 / zoom), int(246 / zoom))
    img = Image.open('map.jpg')
    pinpoint = Image.open('pinpoint.png').resize((resize_factor[0], resize_factor[1]))
    img.paste(pinpoint, (coords[0] - int(pinpoint.size[0] / 2), int(coords[1] - pinpoint.size[1])), pinpoint)
    img = img.crop((cam_coords[0] - view[0], cam_coords[1] - view[1], cam_coords[0] + view[0], cam_coords[1] + view[1]))
    pda = Image.open('pda.png')
    img = img.resize(pda.size, resample=Image.LANCZOS)
    img.paste(pda, mask=pda)
    cross = Image.open('crosshair.png')
    img.paste(cross,
              (int(img.size[0] * 0.5) - int(cross.size[0] / 2) + 1, int(img.size[1] * 0.5) - int(cross.size[1] / 2)),
              cross)
    return img


async def universal_updater(i: discord.Interaction, name: str, what_to_update: str,
                            value: Union[str, int, float], mode: int, faction=False, rep=False, feedback=True):
    """
    mode 0 - set \n
    mode 1 - increment, only for ints and floats
    """
    what_to_update = what_to_update.lower()
    localization = User(i.user.id, i.guild_id).get_localization()
    char = get_char(i, name, False, False)
    locale_name = what_to_update
    bsonified = 0
    if what_to_update not in CAN_BE_CHANGED_IN_CHAR:
        if faction:
            what_to_update = what_to_update.capitalize()
            what_to_update = get_field(what_to_update, localization, 'factions')
            what_to_update = what_to_update.lower()
            if what_to_update in FACTIONS:
                locale_name = get_item_from_translation_dict(localized_data.find_one({'request': 'factions'})['local'],
                                                             localization,
                                                             what_to_update)
        elif rep:
            bsonified = bson.ObjectId(what_to_update)
        else:
            what_to_update = get_field(what_to_update, localization)
    else:
        if what_to_update == 'faction':
            locale_name = get_item_from_translation_dict(localized_data.find_one({'request': 'char_fields'})['local'],
                                                         localization, what_to_update)
            value = get_field(value, localization, 'factions')
        else:
            locale_name = get_item_from_translation_dict(localized_data.find_one({'request': 'char_fields'})['local'],
                                                         localization, what_to_update)

    match mode:
        case 0:  # set
            char.update(what_to_update, value)
        case 1:  # change
            if type(value) == str:
                raise TypeError
            if what_to_update in FACTIONS:
                value = value + char.char['frac_rep'].get(what_to_update, 0)
            elif rep:
                value = value + char.char['npc_rep'].get(bsonified, 0)
            else:
                value = value + char.char[what_to_update]
            char.update(what_to_update, value)

    char.update_char()
    dead, data = char.check_for_death(localization)
    if value in FACTIONS:
        value = get_item_from_translation_dict(localized_data.find_one({'request': 'factions'})['local'], localization,
                                               value)
    if feedback:
        await i.response.send_message(content=f'{char.char["name"]}\n{locale_name.capitalize()} = {value}\n{data}',
                                      ephemeral=True)
    await log(f'{char.char["name"]}\n{locale_name.capitalize()} = {value}\n{data}', i,
              Server(i.guild_id).server['char_change_log'])
    return f'{char.char["name"]}\n{locale_name.capitalize()} = {value}\n{data}'


async def damage(i: discord.Interaction, name: str, damage_type: str, num: int, damage_armor: int):
    localization = User(i.user.id, i.guild_id).get_localization()
    char = get_char(i, name, False, False)
    equipped = char.read_equipped()[0]['equipped']
    if damage_type == 'body_armor_points' or damage_type == 'head_armor_points':
        armor_or_helmet = None
        if damage_type == 'body_armor_points':
            excluded = 'head'
            damaged = 'body_armor_points'
        else:
            excluded = 'armor'
            damaged = 'head_armor_points'
        n = 0
        for n, item in enumerate(equipped):
            if item['type'] in ARMOR_TYPES and not item['type'] == excluded:
                armor_or_helmet = item
                break
        if not armor_or_helmet:
            if damaged == 'head_armor_points':
                await universal_updater(i, name, 'hp', -num * 3, 1)
            else:
                await universal_updater(i, name, 'hp', -num, 1)
            return
        if -num + armor_or_helmet[damaged] < 0:
            if damaged == 'head_armor_points':
                await universal_updater(i, name, 'hp', (-num + armor_or_helmet[damaged]) * 3, 1)
            else:
                await universal_updater(i, name, 'hp', -num + armor_or_helmet[damaged], 1)
        char.damage_or_repair_item_at_idx(n, armor_or_helmet['_id'], damaged.split('_')[0], damage_armor)
    else:
        resistance = 0
        helmet = None
        helmet_idx = None
        armor = None
        armor_idx = None
        for n, item in enumerate(equipped):
            resistance += item.get(damage_type, 0)
            if item['type'] == item['type'] in ARMOR_TYPES and not item['type'] == 'armor':
                helmet = item
                helmet_idx = n
            if item['type'] in ARMOR_TYPES and not item['type'] == 'helmet':
                armor = item
                armor_idx = n
        if damage_type == 'psi_resistance':
            if -num + resistance < 0:
                await universal_updater(i, name, 'psi_hp', -num + resistance, 1)
        else:
            if -num + resistance < 0:
                await universal_updater(i, name, 'hp', -num + resistance, 1)
            if helmet:
                char.damage_or_repair_item_at_idx(helmet_idx, helmet['_id'], "head", damage_armor)
            if armor:
                char.damage_or_repair_item_at_idx(armor_idx, armor['_id'], "body", damage_armor)

    char.update_char()
    dead, data = char.check_for_death(localization)
    # await i.response.send_message(content=f'{char.char["name"]}\n{data}')


def get_char(i, name, belongs_to_player=True, fuzzy_search_allowed=True):
    char = None
    if not name:
        char = Character(i.guild_id, i.user.id)
    else:
        try:
            char = Character(i.guild_id, i.user.id, bson.ObjectId(name))
        except bson.errors.InvalidId:
            if fuzzy_search_allowed:
                if belongs_to_player:
                    document = characters.aggregate(get_search_player_npc_char_pipeline(name, i.guild_id, i.user.id))
                else:
                    document = characters.aggregate(get_search_char_pipeline(name, i.guild_id))
                try:
                    char = Character(i.guild_id, i.user.id, document.next()['_id'])
                except StopIteration:
                    pass
    if not char:
        return False
    return char


def unwrap_data(data, user_locale):
    if x := data.get(user_locale):
        combined_dict = {
            v: k for k, v in x.items()
        }
    else:
        combined_dict = {}
    combined_dict.update({
        v: k for k, v in data['default'].items()
    })
    return combined_dict


def get_stat(stat, user_locale):
    localized_dict = unwrap_data(localized_data.find_one({'request': 'stats_and_skills'})['local'], user_locale)
    return localized_dict.get(stat, stat)


def get_field(to_set, user_locale, what_to_get='char_fields'):
    localized_dict = unwrap_data(localized_data.find_one({'request': what_to_get})['local'], user_locale)
    return localized_dict.get(to_set, to_set)


async def roll_stat(i: discord.Interaction, stat: str, buff_or_debuff: int, name: str, gm=False):
    reply = ''
    reply += stat + ' '
    user_locale = User(i.user.id, i.guild_id).get_localization()
    stat = get_stat(stat, user_locale)

    if gm:
        char = get_char(i, name, False, True)
    else:
        char = get_char(i, name)

    if await gm_check(i, char.char, gm, user_locale):
        return

    reply += char.char['name'] + ':\n'
    reply += char.roll_dice(stat, buff_or_debuff)[0]
    await i.response.send_message(reply)


available_formats = ['jpeg', 'jpg', 'png', 'webp']


async def set_image(i: discord.Interaction, name: str, image: discord.Attachment = None, gm=False):
    user_locale = User(i.user.id, i.guild_id).get_localization()
    if gm:
        char = get_char(i, name, False, True)
    else:
        char = get_char(i, name)

    if await gm_check(i, char.char, gm, user_locale):
        return

    await i.response.defer()
    if image:
        img = await image.to_file()
        save_format = img.filename.split('.')[-1]
        if save_format.lower() not in available_formats:
            await i.followup.send(
                content=get_localized_answer('wrong_format_error', user_locale).format(types=available_formats))
            return
        if save_format.lower() == 'jpg':
            save_format = 'jpeg'
        with Image.open(img.fp) as img:
            if img.size != (128, 128):
                img = img.resize(size=(128, 128), resample=Image.LANCZOS)
            with io.BytesIO() as buffer:
                img.save(buffer, save_format)
                buffer.seek(0)
                mes = await i.followup.send(content='', file=discord.File(buffer, filename=f'avatar.{save_format}'))
        image = mes.attachments[0].url
    char.update('img_url', image)


async def say(i: discord.Interaction, name: str, what_to_say: str, gm, client, token):
    user_locale = User(i.user.id, i.guild_id).get_localization()
    if gm:
        char = get_char(i, name, False, True)
    else:
        char = get_char(i, name)

    if await gm_check(i, char.char, gm, user_locale):
        return

    server = Server(i.guild_id)
    await i.response.defer(ephemeral=True)
    hook = discord.Webhook.from_url(
        url=server.server['webhook'],
        client=client, bot_token=token)
    if hook.channel != i.channel:
        await hook.edit(channel=i.channel)
    img = char.char['img_url']
    if not img:
        img = char_image_placeholder
    await hook.send(content=what_to_say, username=char.char['name'], avatar_url=img)
    await i.followup.send(content=get_localized_answer('message_sent', user_locale))
    await log(what_to_say, i, server.server['char_say_log'])


async def lvl_up(i: discord.Interaction, stat_name: str, num: int, name: str, gm=False):
    user_locale = User(i.user.id, i.guild_id).get_localization()
    stat = get_stat(stat_name, user_locale)

    if gm:
        char = get_char(i, name, False, True)
    else:
        char = get_char(i, name)

    if await gm_check(i, char.char, gm, user_locale):
        return

    reply = char.lvl_up(stat, stat_name, num, user_locale)
    await i.response.send_message(reply, ephemeral=True)
    await log(reply, i, Server(i.guild_id).server['char_change_log'])


async def clone_char(i: discord.Interaction, u_id, new_name: str = None, new_owner=None, new_type: str = None):
    user = User(i.user.id, i.guild.id)
    char = Character(i.guild_id, u_id=bson.ObjectId(u_id))
    char.clone(new_name, new_owner, new_type)
    await i.response.send_message(
        content=get_localized_answer('char_cloned', user.get_localization()).format(name=char.char['name'])
    )


async def set_stat_or_skill(i: discord.Interaction, not_translated_stat: str, num: int, name: str, gm=True):
    user_locale = User(i.user.id, i.guild_id).get_localization()
    stat = get_stat(not_translated_stat, user_locale)
    char = get_char(i, name)

    if await gm_check(i, char.char, gm, user_locale):
        return

    reply = char.update(stat, num)
    if reply:
        reply = get_localized_answer('char_set_stat_or_skill_success', user_locale).format(name=char.char['name'],
                                                                                           num=num,
                                                                                           stat=not_translated_stat)
    else:
        raise Exception
    await i.response.send_message(reply)


def check_for_server_default(localization, i):
    server = Server(i.guild_id)
    if localization == server.roc_server()['local']:
        localization = 'default'
    return localization


async def set_locale_autocomplete(interaction: discord.Interaction, current: str, ) -> List[Choice[str]]:
    choices = [x['language'] for x in languages.find()]
    return [
               Choice(name=choice, value=choice)
               for choice in choices if current.lower() in choice.lower()
           ][:25]


async def get_location_autocomplete(interaction: discord.Interaction, current: str) -> List[Choice[str]]:
    choices = [str(x['_id']) for x in events.find({'guild_id': interaction.guild_id})]
    return [
               Choice(name=choice, value=choice)
               for choice in choices if current in choice
           ][:25]


def get_local_and_data_for_field(interaction):
    return User(interaction.user.id, interaction.guild_id).get_localization(), \
        localized_data.find_one({'request': 'char_fields'})['local']


def get_search_char_pipeline(name, guild_id):
    return [
        {
            '$search': {
                "compound": {
                    'must': [{
                        'autocomplete': {
                            'query': name,
                            'path': 'name',
                            'fuzzy': {
                                'maxEdits': 1
                            }}}
                    ],
                    "filter": [{
                        "equals": {
                            "value": guild_id,
                            "path": "guild_id"
                        }}]
                }
            }},
        {"$limit": 25},
    ]


def get_search_item_pipeline(name, guild_id, mode='item'):
    if mode == 'mod':
        query = [
            {
                '$search': {
                    "compound": {
                        'must': [{
                            'text': {
                                'query': name,
                                'path': {
                                    'wildcard': "localization.*.name"
                                },
                                'fuzzy': {
                                    'maxEdits': 1
                                }}}
                        ],
                        "filter": [{
                            "equals": {
                                "value": guild_id,
                                "path": "guild_id"}
                        },
                            {'text': {
                                'query': "modification",
                                'path': 'type',
                            }}]
                    },
                }},
            {"$limit": 25},
        ]
    else:
        query = [
            {
                '$search': {
                    "compound": {
                        'must': [{
                            'text': {
                                'query': name,
                                'path': {
                                    'wildcard': "localization.*.name"
                                },
                                'fuzzy': {
                                    'maxEdits': 1
                                }}}
                        ],
                        "filter": [{
                            "equals": {
                                "value": guild_id,
                                "path": "guild_id"
                            },
                        }]
                    },
                }},
            {"$limit": 25},
        ]

    if mode != 'ammo_types':
        query[0]['$search']['compound']['mustNot'] = [{
            'text': {
                'query': '/^ammo_types/i',
                'path': 'type'}},
        ]
    else:
        query[0]['$search']['compound']['filter'].append(
            {'text': {
                'query': "ammo_types",
                'path': 'type',
            }}
        )
    if mode != 'profession':
        if not query[0]['$search']['compound'].get('mustNot'):
            query[0]['$search']['compound']['mustNot'] = []

        query[0]['$search']['compound']['mustNot'].append(
            {
                'text': {
                    'query': '/^profession/i',
                    'path': 'type'}},

        )
    return query


def get_search_charnpc_pipeline(name, guild_id):
    return [
        {
            '$search': {
                "compound": {
                    'must': [{
                        'autocomplete': {
                            'query': name,
                            'path': 'name',
                            'fuzzy': {
                                'maxEdits': 1
                            }}}
                    ],
                    "filter": [{
                        "equals": {
                            "value": guild_id,
                            "path": "guild_id"
                        }},
                        {'text': {
                            'query': "\"npc\" \"mutant\" \"trader\"",
                            'path': 'type',
                        }}
                    ]
                }
            }},
        {"$limit": 25},
    ]


def get_search_player_npc_char_pipeline(name, guild_id, p_id):
    return [
        {
            '$search': {
                "compound": {
                    'must': [{
                        'autocomplete': {
                            'query': name,
                            'path': 'name',
                            'fuzzy': {
                                'maxEdits': 1
                            }}}
                    ],
                    "filter": [{
                        "equals": {
                            "value": guild_id,
                            "path": "guild_id"
                        }},
                        {"equals": {
                            "value": p_id,
                            "path": "owner_id"
                        }},
                        {'text': {
                            'query': 'npc',
                            'path': 'type',

                        }}

                    ]
                }
            }},
        {"$limit": 25},
    ]


async def player_chars_autocomplete(interaction: discord.Interaction, current: str, ) -> List[Choice[str]]:
    if current:
        pipeline = get_search_player_npc_char_pipeline(current, interaction.guild_id, interaction.user.id)
    else:
        pipeline = [
            {'$match': {'guild_id': interaction.guild_id,
                        'owner_id': interaction.user.id,
                        'type': 'npc'}},
            {"$limit": 25}]

    choices = characters.aggregate(pipeline)
    return [Choice(name=choice['name'][:100], value=str(choice['_id'])) for choice in choices]


def check_for_none(interaction, choice):
    member_name = ''
    if owner_id := choice['owner_id']:
        if member := interaction.guild.get_member(owner_id):
            member_name = f' ({member.display_name[:29]})'
    return choice['name'][:100 - len(member_name)] + member_name


async def chars_autocomplete(interaction: discord.Interaction, current: str, ) -> List[Choice[str]]:
    if current:
        pipeline = get_search_char_pipeline(current, interaction.guild_id)
    else:
        pipeline = [
            {'$match': {'guild_id': interaction.guild_id}},
            {"$limit": 25}]

    choices = characters.aggregate(pipeline)
    return [Choice(name=check_for_none(interaction, choice), value=str(choice['_id'])) for choice in choices]


async def items_autocomplete(interaction: discord.Interaction, current: str, ) -> List[Choice[str]]:
    user = User(interaction.user.id, interaction.guild_id)
    localization = user.get_localization()
    if current:
        pipeline = get_search_item_pipeline(current, interaction.guild_id)
    else:
        pipeline = [
            {'$match': {'guild_id': interaction.guild_id}},
            {'$match': {'type': {'$ne': 'ammo_types'}}},
            {'$match': {'type': {'$ne': 'profession'}}},
            {"$limit": 25}
        ]

    choices = items.aggregate(pipeline)
    return [Choice(name=get_item_from_translation_dict(choice['localization'], localization, 'name')[:100],
                   value=str(choice['_id'])) for choice in
            choices]


async def items_buff_autocomplete(interaction: discord.Interaction, current: str, ) -> List[Choice[str]]:
    user = User(interaction.user.id, interaction.guild_id)
    localization = user.get_localization()
    if current:
        pipeline = get_search_item_pipeline(current, interaction.guild_id, 'profession')
    else:
        pipeline = [
            {'$match': {'guild_id': interaction.guild_id}},
            {'$match': {'type': {'$ne': 'ammo_types'}}},
            {"$limit": 25}
        ]

    choices = items.aggregate(pipeline)
    return [Choice(name=get_item_from_translation_dict(choice['localization'], localization, 'name')[:100],
                   value=str(choice['_id'])) for choice in
            choices]


async def profs_autocomplete(interaction: discord.Interaction, current: str, ) -> List[Choice[str]]:
    user = User(interaction.user.id, interaction.guild_id)
    localization = user.get_localization()
    if current:
        pipeline = get_search_item_pipeline(current, interaction.guild_id)
    else:
        pipeline = [
            {'$match': {'guild_id': interaction.guild_id}},
            {'$match': {'type': 'profession'}},
            {"$limit": 25}
        ]

    choices = items.aggregate(pipeline)
    return [Choice(name=get_item_from_translation_dict(choice['localization'], localization, 'name')[:100],
                   value=str(choice['_id'])) for choice in
            choices]


async def ammo_types_autocomplete(interaction: discord.Interaction, current: str, ) -> List[Choice[str]]:
    user = User(interaction.user.id, interaction.guild_id)
    localization = user.get_localization()
    if current:
        pipeline = get_search_item_pipeline(current, interaction.guild_id, 'ammo_types')
    else:
        pipeline = [
            {'$match': {'guild_id': interaction.guild_id, 'type': 'ammo_types'}},
            {"$limit": 25}
        ]

    choices = items.aggregate(pipeline)
    return [Choice(name=get_item_from_translation_dict(choice['localization'], localization, 'name')[:100],
                   value=str(choice['_id'])) for choice in
            choices]


async def modifications_autocomplete(interaction: discord.Interaction, current: str, ) -> List[Choice[str]]:
    user = User(interaction.user.id, interaction.guild_id)
    localization = user.get_localization()
    if current:
        pipeline = get_search_item_pipeline(current, interaction.guild_id, 'mod')
    else:
        pipeline = [
            {'$match': {'guild_id': interaction.guild_id, 'type': 'modification'}},
            {'$match': {'type': {'$ne': 'ammo_types'}}},
            {"$limit": 25}
        ]

    choices = items.aggregate(pipeline)
    return [Choice(name=get_item_from_translation_dict(choice['localization'], localization, 'name')[:100],
                   value=str(choice['_id'])) for choice in
            choices]


async def chars_autocomplete_for_npc(interaction: discord.Interaction, current: str, ) -> List[Choice[str]]:
    if current:
        pipeline = get_search_charnpc_pipeline(current, interaction.guild_id)
    else:
        pipeline = [
            {'$match': {'guild_id': interaction.guild_id}},
            {'$match': {'type': {'$ne': 'player'}}},
            {"$limit": 25}]

    choices = characters.aggregate(pipeline)
    return [Choice(name=check_for_none(interaction, choice), value=str(choice['_id'])) for choice in choices]


async def stat_and_skill_autocomplete(interaction: discord.Interaction, current: str, ) -> List[Choice[str]]:
    user_locale = User(interaction.user.id, interaction.guild_id).get_localization()
    localized_dict = localized_data.find_one({'request': 'stats_and_skills'})
    choices = [
        localized_dict['local'].get(
            user_locale, localized_dict['local']['default']
        ).get(
            x, localized_dict['local']['default'].get(x, x)
        ) for x in list(SKILLS.keys()) + list(STATS.keys())
    ]
    return [
               Choice(name=choice, value=choice)
               for choice in choices if current.lower() in choice.lower()
           ][:25]


async def stats_autocomplete(interaction: discord.Interaction, current: str, ) -> List[Choice[str]]:
    user_locale = User(interaction.user.id, interaction.guild_id).get_localization()
    localized_dict = localized_data.find_one({'request': 'stats_and_skills'})
    choices = [
        localized_dict['local'].get(
            user_locale, localized_dict['local']['default']
        ).get(
            x, localized_dict['local']['default'].get(x, x)
        ) for x in list(STATS.keys())
    ]

    return [
               Choice(name=choice, value=choice)
               for choice in choices if current.lower() in choice.lower()
           ][:25]


def update_events_and_weights(event_list, localization, fin_eve_list, weight_list):
    for x in event_list:
        fin_eve_list.append((x['localized_events'].get(localization, x['localized_events']['default']),
                             x.get('url', None), x.get('location_id', None)))
        weight_list.append(x['statistical_weight'])


def process_event(inp_str: str) -> object:
    try:
        if inp_str.count('{') >= 1 and inp_str.count('}') >= 1:
            sub_str = inp_str[inp_str.rindex("{") + 1:inp_str.rindex("}")]
            split_str = sub_str.split('=')
            var = split_str[0].lower().replace(' ', '').lstrip().rstrip()
            if var == 'rand_num':
                x, y = split_str[1].split('|')
                x, y = int(x.replace(' ', '')), int(y.replace(' ', ''))
                inp_str = inp_str[:inp_str.rindex("{")] + str(random.randint(x, y)) + inp_str[inp_str.rindex("}") + 1:]

            elif var == 'rand_list':
                list_of_values = split_str[1].split(',')
                for n, value in enumerate(list_of_values):
                    list_of_values[n] = value.lstrip().rstrip()
                inp_str = inp_str[:inp_str.rindex("{")] + random.choice(list_of_values) + inp_str[
                                                                                          inp_str.rindex("}") + 1:]
            elif var == 'rand_w_list':
                list_of_values = split_str[1].split(',')
                values = []
                weights = []
                for val in list_of_values:
                    val = val.split('|')
                    val[0] = val[0].lstrip().rstrip()
                    values.append(val[0])
                    weights.append(float(val[1]))
                ch = random.choices(values, weights=weights)
                inp_str = inp_str[:inp_str.rindex("{")] + ch[0] + inp_str[inp_str.rindex("}") + 1:]
            return process_event(inp_str)
        return inp_str
    except ValueError as exc:
        return exc


def chunker(inp_str, chunk_str='\n', limit=2000):
    chunks = []
    not_chunked_text = inp_str

    while not_chunked_text:
        if len(not_chunked_text) <= limit:
            chunks.append(not_chunked_text)
            break
        split_index = not_chunked_text.rfind(chunk_str, 0, limit)
        if split_index == -1:
            # The chunk is too big, so everything until the next newline is deleted
            try:
                not_chunked_text = not_chunked_text.split(chunk_str, 1)[1]
            except IndexError:
                # No "\n" in not_chunked_text, i.e. the end of the input text was reached
                break
        else:
            chunks.append(not_chunked_text[:split_index + 1])
            not_chunked_text = not_chunked_text[split_index + 1:]
    return chunks


async def log(content, i, log_channel, file=None):
    channel = i.client.get_channel(log_channel)
    emb = discord.Embed(description=content + '\n\n' + f'{i.user.mention}      <#{i.channel_id}>')
    discord.Message = await channel.send(embed=emb, file=file)
