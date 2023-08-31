import io
from typing import List, Optional

import bson
import discord.app_commands
from discord.components import SelectOption
from discord.utils import MISSING
import gspread
import gspread.utils
import numpy
import requests
from PIL import Image, ImageDraw
from discord import SelectOption, Interaction
from discord.ui import View, Button, Select, Modal, TextInput
from bson.json_util import dumps

from db import localized_data, characters, get_item_from_translation_dict, map_collection
from db_clases import Character, User
from static import SKILLS, CAN_BE_STR_IN_CHAR, CAN_BE_INT_IN_CHAR, FACTION_EMOJIS, \
    AVAILABLE_FACTIONS, RESIST_LIST, RESIST_EMOJIS, EMOJIS, FACTIONS, CAN_BE_MODIFIED, ARMOR_TYPES, HEALTH_DEBUFFS, \
    SHOOT_OPTIONS, PLATE_CARRIER_ZONES
from misc import chunker, get_localized_answer, log, \
    set_stat_or_skill, lvl_up, get_stat, get_char, roll_stat, gm_check, check_for_none, universal_updater, Server, \
    get_loc_image, get_hp_image
from placeholders import char_image_placeholder
from db import items
from copy import deepcopy
import random
from io import BytesIO
import pyastar2d
import datetime
from discord import ButtonStyle
from static import dic, fails, succes, zoom_lst, modes, speed_lst  # todo replace this

client = gspread.service_account('credentials.json')

# preloading images
background_image = Image.open('images/info_back.png')
bars = Image.open('images/bars.png')
hp_bar = Image.open('images/hp_bar.png')
rad_bar = Image.open('images/rad_bar.png')
psi_bar = Image.open('images/psi_bar.png')
COLORS = {
    'very_bad': '#ff2020',
    'bad': '#f8801c',
    'neutral': '#fcff00',
    'good': '#88ea3a',
    'very_good': '#00d303'
}
top = Image.open('images/rep_background_top.png')
middle = Image.open('images/rep_background_middle.png')
bottom = Image.open('images/rep_background_bottom.png')
background = Image.open('images/frac_rep_background.png')
rep_bars = Image.open('images/rep_bars.png')
faction_images = {}
for fact in FACTIONS:
    try:
        fac_img = Image.open(f'images/{fact}.webp')
    except FileNotFoundError:
        fac_img = Image.open('notfound.webp')
    fac_img.thumbnail((39, 39), resample=Image.LANCZOS)
    faction_images[fact] = fac_img


async def followup_images(interaction, images, title=''):
    if images:
        for image in images:
            temp_emb = discord.Embed(title=title)
            temp_emb.set_image(url=image)
            await interaction.followup.send(embed=temp_emb, ephemeral=True)


class ManualSelect(Select):
    def __init__(self, initial_data):
        options = [SelectOption(label=name) for name, _ in initial_data]
        super().__init__(options=options)

    async def callback(self, interaction: Interaction):
        emb = discord.Embed()
        for key, value in self.view.data:
            emb.add_field(name=key, value=value[:100], inline=False)
        v = PaginatedBackView(self.view, emb, self.values[0], dict(self.view.data).get(self.values[0]))
        new_emb, images = v.get_embed()

        await interaction.response.edit_message(content=v.get_content(), view=v, embed=new_emb)
        await followup_images(interaction, images, v.key)

    def update_options(self):
        self.view.data = self.view.get_localized_paginated_list()
        self.options = [SelectOption(label=name) for name, _ in self.view.data]


class ManualView(View):
    def __init__(self, localization, spreadsheet_url, max_options=5, ):
        super().__init__()
        spreadsheet = client.open_by_url(spreadsheet_url)
        self.sheet = spreadsheet.worksheet('manual')
        self.locale = localization

        self.page = 0

        values = self.sheet.get_values(f'A2:C')
        self.max_options = max_options
        self.max_range = int(values[0][2])
        values = [[x, y] for x, y, _ in values]
        self.cell_coords = dict(values)
        self.data = self.get_localized_paginated_list()
        self.select = ManualSelect(self.data)
        self.add_item(self.select)
        self.opts = int(numpy.ceil(self.max_range / self.max_options))
        if self.opts > 1:
            self.add_item(PageChangeBTN(-1, self.opts, '<'))
            self.add_item(PageChangeBTN(1, self.opts, '>'))

    def get_localized_paginated_list(self):
        r, c = gspread.utils.a1_to_rowcol(self.cell_coords['default'])
        r_l, c_l = gspread.utils.a1_to_rowcol(self.cell_coords.get(self.locale, self.cell_coords['default']))
        r, r_l = r + self.page * self.max_options, r_l + self.page * self.max_options

        data, localized_data = self.sheet.batch_get([f'{gspread.utils.rowcol_to_a1(r, c)}:'
                                                     f'{gspread.utils.rowcol_to_a1(r + self.max_options - 1, c + 1)}',
                                                     f'{gspread.utils.rowcol_to_a1(r_l, c_l)}:'
                                                     f'{gspread.utils.rowcol_to_a1(r_l + self.max_options - 1, c_l + 1)}'])
        if self.locale != 'default' and self.locale in self.cell_coords.keys():
            localized_data = gspread.utils.fill_gaps(localized_data, len(data), 2)
            for n, (loc_dat, dat) in enumerate(zip(localized_data, data)):
                if not loc_dat[0] or not loc_dat[1]:
                    localized_data[n] = dat
            data = localized_data
        return data

    def get_embed(self):
        emb = discord.Embed()
        for key, _ in self.data:
            if len(key) > 256:
                key = key[:250] + '...'
            emb.add_field(name=key, inline=False, value='')
        return emb

    def get_content(self):
        if self.opts > 1:
            return f'{self.page + 1}/{self.opts}'
        return ''

    async def change_page(self, i: Interaction):
        await i.response.defer(ephemeral=True)
        sel = self.select
        self.remove_item(sel)
        self.select.update_options()
        self.add_item(sel)
        msg = await i.original_response()
        await msg.edit(content=self.get_content(), embed=self.get_embed(), view=self)


class PaginatedBackView(View):
    def __init__(self, original_view, emb, key, value):
        super().__init__()
        self.original_view = original_view
        if len(key) > 256:
            key = key[:250] + '...'

        self.key = key
        self.emb = emb
        self.page = 0
        self.chunked = chunker(value, '\n', 4096)
        self.add_item(BackBTN(get_localized_answer('back_btn_label', original_view.locale)))
        if len(self.chunked) > 1:
            self.add_item(PageChangeBTN(-1, len(self.chunked) - 1, '<'))
            self.add_item(PageChangeBTN(1, len(self.chunked) - 1, '>'))

    def get_embed(self):
        new_emb = discord.Embed(title=self.key, description='')
        images = []
        key_for_image = '{image_url='
        for x in range(0, self.chunked[self.page].count(key_for_image)):
            if self.chunked[self.page].count(key_for_image) >= 1 and self.chunked[self.page].count('}') >= 1:
                first_keyword = self.chunked[self.page].index(key_for_image)
                second_keyword = self.chunked[self.page].index('}')
                url = self.chunked[self.page][first_keyword + len(key_for_image):second_keyword]
                self.chunked[self.page] = self.chunked[self.page][:first_keyword] + self.chunked[self.page][
                                                                                    second_keyword + 1:]
                images.append(url)
        if images:
            new_emb.set_image(url=images.pop(0))

        if self.chunked[self.page]:
            new_emb.description = self.chunked[self.page]
        return new_emb, images

    def get_content(self):
        if len(self.chunked) > 1:
            return f'{self.page + 1}/{len(self.chunked)}'
        return ''

    async def change_page(self, interaction: Interaction):
        embed, images = self.get_embed()
        await interaction.response.edit_message(content=self.get_content(), embed=embed)
        await followup_images(interaction, images, self.key)


class BackBTN(Button):
    def __init__(self, label):
        super().__init__(label=label)

    async def callback(self, i: Interaction):
        await i.response.defer(ephemeral=True)
        msg = await i.original_response()
        await msg.edit(content=self.view.original_view.get_content(),
                       embed=self.view.original_view.get_embed(),
                       view=self.view.original_view)


class PageChangeBTN(Button):
    def __init__(self, move_dir, max_idx, emoji):
        super().__init__(label=emoji)
        self.move_dir = move_dir
        self.max_idx = max_idx

    async def callback(self, interaction: Interaction):
        self.view.page += self.move_dir
        self.view.page = int(numpy.clip(self.view.page, 0, self.max_idx))
        await self.view.change_page(interaction)


class GenericView(View):
    def __init__(self, i, row=4):
        super().__init__(timeout=3599)
        self.user_id = i.user.id
        self.page = 0
        self.pages = []
        self.page_minus_all = ChangePageBTN('min', '<<', row)
        self.page_plus_all = ChangePageBTN('max', '>>', row)
        self.page_minus = ChangePageBTN(-1, '<', row)
        self.page_plus = ChangePageBTN(1, '>', row)

    def change_page(self):
        pass

    def get_str(self):
        return ''

    def get_image(self):
        return []

    def get_embeds(self):
        return []

    async def interaction_check(self, interaction):
        if res := interaction.user.id == self.user_id:
            return res
        else:
            raise Exception

    # async def on_error(self, i: Interaction, error: Exception, item) -> None:
    #     user_localization = User(i.user.id, i.guild.id).get_localization()
    #     await i.response.send_message(content=get_localized_answer('not_yours_view', user_localization), ephemeral=True)
    #     print(error)

    def regenerate_pages(self):
        self.page_minus.disabled = False
        self.page_plus.disabled = False
        self.page_minus_all.disabled = False
        self.page_plus_all.disabled = False

        if self.page == 0:
            self.page_minus.disabled = True
            self.page_minus_all.disabled = True
        if self.page == len(self.pages) - 1:
            self.page_plus.disabled = True
            self.page_plus_all.disabled = True
        self.add_item(self.page_minus_all)
        self.add_item(self.page_minus)
        self.add_item(self.page_plus)
        self.add_item(self.page_plus_all)


class ChangePageBTN(Button):
    def __init__(self, direction, label, row=2):
        super().__init__(label=label, row=row)
        self.direction = direction

    async def callback(self, i: discord.Interaction):
        mes = i.message
        await i.response.defer()
        if type(self.direction) == str:
            if self.direction == 'min':
                self.view.page = 0
            elif self.direction == 'max':
                self.view.page = len(self.view.pages) - 1
        elif len(self.view.pages) > self.view.page + self.direction >= 0:
            self.view.page += self.direction
        await mes.edit(content=self.view.change_page(), view=self.view, embeds=self.view.get_embeds())
        await mes.edit(attachments=self.view.get_image())


class InputNumModal(Modal):
    def __init__(self, title, input_title, function, stat, u_id, message, view, default='1'):
        super().__init__(title=title)
        self.function, self.stat, self.u_id = function, stat, u_id
        self.message = message
        self.view = view

        self.text_input = TextInput(label=input_title, default=default)
        self.add_item(self.text_input)

    async def on_submit(self, i: discord.Interaction):
        await self.function(i, self.stat, int(self.text_input.value), self.u_id, self.view.gm)
        self.view.character.update_char()
        await self.message.edit(content=self.view.get_str())


class UniUpdateModal(Modal):
    def __init__(self, title, input_title, placeholder, u_id, what_to_update, mode, faction, rep, message, view,
                 value_type):
        super().__init__(title=title)
        self.what_to_update, self.mode, self.u_id, self.faction, self.rep = what_to_update, mode, u_id, faction, rep
        self.value_type = value_type
        self.message = message
        self.view = view

        self.text_input = TextInput(label=input_title, default=placeholder)
        self.add_item(self.text_input)

    async def on_submit(self, i: discord.Interaction):
        await universal_updater(i, self.u_id, self.what_to_update, self.value_type(self.text_input.value), self.mode,
                                self.faction)
        self.view.character.update_char()
        await self.message.edit(content=self.view.get_str(), attachments=self.view.get_image())


class StatSelect(Select):
    def __init__(self, pages, page, row=0):
        self.pages = pages
        self.page = page
        cur_page = pages[page]
        super().__init__(options=[
                                     SelectOption(label=cur_page[0][1])
                                 ] + [SelectOption(label=stat[1]) for stat in cur_page[1]], row=row)

    async def callback(self, i: discord.Interaction):
        self.view.replace_select_placeholder(self.values[0])
        await i.response.edit_message(view=self.view)

    def replace_placeholder(self, placeholder):
        self.placeholder = placeholder

    def replace_options(self):
        self.replace_placeholder(None)
        self.page = self.view.page
        cur_page = self.pages[self.page]
        self.options = [SelectOption(label=cur_page[0][1])] + \
                       [SelectOption(label=stat[1]) for stat in cur_page[1]]


class RollBTN(Button):
    def __init__(self, label, row=1, emoji=None, style=discord.ButtonStyle.gray, disabled=False):
        super().__init__(label=label, row=row, emoji=emoji, style=style, disabled=disabled)

    async def callback(self, i: discord.Interaction):
        message = i.message
        await i.response.send_modal(InputNumModal(get_localized_answer('number_input_modal', self.view.localization),
                                                  get_localized_answer('number_input_modal_textbox_roll',
                                                                       self.view.localization),
                                                  roll_stat,
                                                  self.view.select.values[0],
                                                  self.view.character.u_id,
                                                  message,
                                                  self.view,
                                                  '0'))


class LVLupBTN(Button):
    def __init__(self, label, row=1, emoji=None, style=discord.ButtonStyle.gray, disabled=False):
        super().__init__(label=label, row=row, emoji=emoji, style=style, disabled=disabled)

    async def callback(self, i: discord.Interaction):
        message = i.message
        await i.response.send_modal(InputNumModal(get_localized_answer('number_input_modal', self.view.localization),
                                                  get_localized_answer('number_input_modal_textbox',
                                                                       self.view.localization),
                                                  lvl_up,
                                                  self.view.select.values[0],
                                                  self.view.character.u_id,
                                                  message,
                                                  self.view))


class UniUpdateBTN(Button):
    def __init__(self, label, localization, row=1, emoji=None, style=discord.ButtonStyle.gray, disabled=False,
                 mode=None):
        super().__init__(label=label, row=row, emoji=emoji, style=style, disabled=disabled)
        if not mode:
            mode = [0, False, False, int]
        self.mode = mode
        self.localization = localization
        self.localized_dict = localized_data.find_one({'request': 'uni_modal_data'})['local']

    async def callback(self, i: discord.Interaction):
        message = i.message
        if self.mode[3] == int:
            mode = 'int'
        elif self.mode[3] == float:
            mode = 'float'
        elif self.mode[3] == str:
            mode = 'str'

        else:
            mode = ''
        text_label = get_item_from_translation_dict(self.localized_dict, self.localization, f'input_{mode}')
        placeholder = get_item_from_translation_dict(self.localized_dict, self.localization,
                                                     f'input_{mode}_placeholder')
        await i.response.send_modal(
            UniUpdateModal(get_item_from_translation_dict(self.localized_dict, self.localization, 'modal_name'),
                           text_label,
                           placeholder,
                           self.view.character.u_id,
                           self.view.select.values[0],
                           self.mode[0],
                           self.mode[1],
                           self.mode[2],
                           message,
                           self.view,
                           self.mode[3]))


class ChangeCharNameBTN(Button):
    def __init__(self, label, row=1, emoji=None, style=discord.ButtonStyle.gray, disabled=False):
        super().__init__(label=label, row=row, emoji=emoji, style=style, disabled=disabled)

    async def callback(self, i: discord.Interaction):
        message = i.message
        await i.response.send_modal(CharChangeNameCreationModal(
            get_localized_answer('char_creation_modal_title', self.view.localization),
            message,
            self.view
        ))


class SETstatBTN(Button):
    def __init__(self, label, row=1, emoji=None, style=discord.ButtonStyle.gray, disabled=False):
        super().__init__(label=label, row=row, emoji=emoji, style=style, disabled=disabled)

    async def callback(self, i: discord.Interaction):
        message = i.message
        await i.response.send_modal(InputNumModal(get_localized_answer('number_input_modal', self.view.localization),
                                                  get_localized_answer('number_input_modal_textbox',
                                                                       self.view.localization),
                                                  set_stat_or_skill,
                                                  self.view.select.values[0],
                                                  self.view.character.u_id,
                                                  message,
                                                  self.view))


class FactionSelectView(GenericView):
    def __init__(self, i, localization, s_list, extras, gm):
        translation_dict = localized_data.find_one({'request': 'factions'})['local']
        super().__init__(i)
        self.localization = localization
        self.extras = extras
        self.list = s_list
        self.select = FactionSelect(translation_dict, localization, gm)
        self.add_item(self.select)
        self.create_char_btn = CreateCharBTN(self.extras,
                                             get_localized_answer('finish_char_creation_btn', localization), True,
                                             discord.ButtonStyle.green)
        self.back_btn = GenericToViewBTN(SkillGenerationView, get_localized_answer('back_btn', localization), False,
                                         discord.ButtonStyle.blurple, (i, localization, self.extras, gm, False))
        self.add_item(self.create_char_btn)
        self.add_item(self.back_btn)

    def replace_select_placeholder(self, placeholder):
        self.clear_items()
        self.remove_item(self.create_char_btn)
        self.remove_item(self.select)
        self.select.replace_placeholder(placeholder)
        self.create_char_btn.disabled = False
        self.add_item(self.select)
        self.add_item(self.create_char_btn)
        self.add_item(self.back_btn)

    def get_str(self):
        ret_str = f'{self.extras.get("name", "nonameerror")}\n```'
        for item in self.list:
            ret_str += f'{item[1]}: {self.extras["skills"].get(item[0], 2)}\n'
        ret_str += '```'
        return ret_str


class FactionSelect(Select):
    def __init__(self, translation_dict, localization, gm, rebuild=False):
        self.localization = localization
        self.translation_dict = translation_dict
        self.rebuild = rebuild
        if gm:
            options = [
                SelectOption(
                    label=get_item_from_translation_dict(translation_dict, localization, x),
                    value=x,
                    emoji=FACTION_EMOJIS[x]
                ) for x in FACTIONS
            ]
        else:
            options = [
                SelectOption(
                    label=get_item_from_translation_dict(translation_dict, localization, x),
                    value=x,
                    emoji=FACTION_EMOJIS[x]
                ) for x in AVAILABLE_FACTIONS
            ]

        super().__init__(options=options)

    async def callback(self, i: discord.Interaction):
        if self.rebuild:
            self.replace_placeholder(
                get_item_from_translation_dict(self.translation_dict, self.localization, self.values[0]))
            self.view.rebuild()
        else:
            self.view.extras['faction'] = self.values[0]
            self.view.replace_select_placeholder(
                get_item_from_translation_dict(self.translation_dict, self.localization, self.values[0]))
        await i.response.edit_message(view=self.view)

    def replace_placeholder(self, placeholder):
        self.placeholder = placeholder


class StatsView(GenericView):
    def __init__(self, i, character, localization, gm=False, back_data=None):
        super().__init__(i)
        self.gm = gm
        if not character or type(character) == bson.ObjectId:
            character = get_char(i, character)
        self.localization_dict = localized_data.find_one({'request': 'stats_view_data'})['local']
        self.character = character
        self.character.update_char()
        self.stats_data = localized_data.find_one({'request': 'stats_and_skills'})['local']
        self.pages = self.character.get_stat_and_skill_lst(localization, self.stats_data)
        self.page = 0
        self.select = StatSelect(self.pages, self.page)
        self.select_profs_to_remove = ProfSelectRemove(self.character, self.character.get_profession_list(), localization, 3, self.localization_dict)
        self.lvl_up_btn = LVLupBTN(get_item_from_translation_dict(self.localization_dict, localization, 'lvlup_btn'),
                                   style=discord.ButtonStyle.green)
        self.set_stat_btn = SETstatBTN(
            get_item_from_translation_dict(self.localization_dict, localization, 'set_lvl_btn'),
            style=discord.ButtonStyle.blurple)
        self.localization = localization
        self.back_data = back_data
        self.roll_btn = RollBTN(get_localized_answer('dice_btn', localization), emoji='🎲')
        self.add_prof_btn = GenericToViewBTN(ProfessionsView,
                                             get_item_from_translation_dict(self.localization_dict, localization,
                                                                            'add_prof_btn'), False,
                                             discord.ButtonStyle.green, [i, character, localization,
                                                                         [i, self.character, self.localization, self.gm,
                                                                          self.back_data]], row=2)
        if self.back_data:
            self.back_btn = GenericToViewBTN(MainMenuView, get_localized_answer('back_btn', localization), False,
                                             discord.ButtonStyle.blurple, [*back_data], row=4)

        self.replace_select_placeholder(None)

    def get_str(self):
        return self.character.get_str_from_lst(self.pages, self.page, self.localization, self.localization_dict,
                                               self.stats_data)

    def change_page(self):
        self.replace_select_options()
        self.replace_select_placeholder(None)
        return self.get_str()

    def replace_select_placeholder(self, placeholder):
        self.clear_items()
        self.select.replace_placeholder(placeholder)
        self.add_item(self.select)
        if self.select.values and placeholder:
            self.add_item(self.roll_btn)
            if get_stat(self.select.values[0], self.localization) not in SKILLS:
                self.add_item(self.lvl_up_btn)
            if self.gm:
                self.add_item(self.set_stat_btn)
        if self.character.get_number_of_available_professions() >= 1:
            self.add_item(self.add_prof_btn)
        if self.gm:
            if self.character.get_profession_list():
                self.add_item(self.select_profs_to_remove)
        self.regenerate_pages()
        if self.back_data:
            self.add_item(self.back_btn)

    def replace_select_options(self):
        self.remove_item(self.select)
        for child in [self.lvl_up_btn, self.roll_btn, self.set_stat_btn]:
            self.remove_item(child)
        self.select.replace_options()
        self.add_item(self.select)


class CharCreationModal(Modal):
    def __init__(self, title, localization, gm=False, extras=None, owner_id=None, char_type='npc'):
        super().__init__(title=title)
        if not extras:
            extras = {}
        extras['owner_id'] = owner_id
        extras['type'] = char_type
        self.extras = extras
        self.inp_name = TextInput(label=get_localized_answer('char_creation_modal_input_name', localization),
                                  min_length=1, max_length=124)
        self.add_item(self.inp_name)
        self.localization = localization
        self.gm = gm

    async def on_submit(self, i):
        self.extras['name'] = str(self.inp_name)
        view = SkillGenerationView(i, self.localization, self.extras, self.gm)
        await i.response.send_message(content=view.get_str(), view=view)


class CharChangeNameCreationModal(Modal):
    def __init__(self, title, message, view):
        super().__init__(title=title)
        self.message = message
        self.view = view
        self.inp_name = TextInput(label=get_localized_answer('char_creation_modal_input_name', view.localization))
        self.add_item(self.inp_name)

    async def on_submit(self, i):
        self.view.extras['name'] = str(self.inp_name)
        await self.message.edit(content=self.view.get_str(), view=self.view)
        await i.response.send_message(content=get_localized_answer('name_changed', self.view.localization),
                                      ephemeral=True)


class SelectSkillNum(Select):
    def __init__(self, skill_name, skill_localized_name, placeholder, max_num=3):
        self.skill_name = skill_name
        super().__init__(
            options=[SelectOption(label=f'{x} {skill_localized_name}', value=str(x)) for x in range(0, max_num)],
            placeholder=placeholder)

    async def callback(self, i: discord.Interaction):
        self.view.extras["skills"][self.skill_name] = int(self.values[0])
        self.view.rebuild()
        await i.response.edit_message(content=self.view.get_str(), view=self.view)


def split_to_ns(lst, n):
    return [lst[x:x + n] for x in range(0, len(lst), n)]


class GenericToViewBTN(Button):
    def __init__(self, new_view, label='', disabled=False, style=discord.ButtonStyle.gray, n_args=(), row=None):
        super().__init__(label=label, style=style, disabled=disabled, row=row)
        self.new_view = new_view
        self.n_args = n_args

    async def callback(self, i: discord.Interaction):
        self.new_view = self.new_view(*self.n_args)
        await i.response.edit_message(content=self.new_view.get_str(), view=self.new_view,
                                      attachments=self.new_view.get_image(), embeds=self.new_view.get_embeds())


class GenericFuncBTN(Button):
    def __init__(self, func, label='', disabled=False, style=discord.ButtonStyle.gray, n_args=()):
        super().__init__(label=label, style=style, disabled=disabled)
        self.func = func
        self.n_args = n_args

    async def callback(self, i: discord.Interaction):
        await self.func(*self.n_args)


class CreateCharBTN(Button):
    def __init__(self, extras, label='', disabled=False, style=discord.ButtonStyle.gray):
        super().__init__(label=label, style=style, disabled=disabled)
        self.extras = extras

    async def callback(self, i: discord.Interaction):
        extras = self.extras
        char = Character(i.guild_id, extras['owner_id'], faction=extras['faction'])
        char.create(extras['name'], extras['type'], skills=extras['skills'])

        await i.response.edit_message(content=char_creation_str(extras['name'], self.view.localization), view=None)


def char_creation_str(name, localization):
    return get_localized_answer("char_created", localization).format(name=name)


class SkillGenerationView(GenericView):
    def __init__(self, i, localization, extras: dict, gm, reset_skills=True):
        super().__init__(i, 4)
        self.localization = localization
        self.not_selected_points_str = get_localized_answer('not_selected_points_str', localization)
        self.list = Character.get_skill_lst(localization)
        self.pages = split_to_ns(self.list, 3)
        self.skills_limit = 5
        self.page = 0
        self.extras = extras
        if reset_skills:
            self.extras['skills'] = {}
        self.continue_btn = GenericToViewBTN(FactionSelectView, get_localized_answer('continue_btn', localization),
                                             True, discord.ButtonStyle.green,
                                             (i, localization, self.list, self.extras, gm))
        self.reset_btn = GenericToViewBTN(SkillGenerationView, get_localized_answer('reset_btn', localization),
                                          False, discord.ButtonStyle.danger, (i, localization, self.extras, gm))
        self.back_btn = ChangeCharNameBTN(get_localized_answer('back_btn', localization),
                                          style=discord.ButtonStyle.blurple, row=3)
        self.rebuild()

    def change_page(self):
        self.rebuild()
        return self.get_str()

    def rebuild(self):
        self.clear_items()
        dif = self.skills_limit - self.get_sum()
        if not dif:
            self.continue_btn.disabled = False
        else:
            self.continue_btn.disabled = True

        for skill in self.pages[self.page]:
            self.add_item(SelectSkillNum(skill[0], skill[1], f'{self.extras["skills"].get(skill[0], 0)}: {skill[1]}',
                                         numpy.clip(self.extras["skills"].get(skill[0],
                                                                              0) + dif,
                                                    0, 2) + 1))
        self.add_item(self.continue_btn)
        self.add_item(self.back_btn)

        self.add_item(self.reset_btn)
        self.regenerate_pages()

    def get_str(self):
        ret_str = f'{self.extras.get("name", "nonameerror")}\n```'
        for item in self.list:
            ret_str += f'{item[1]}: {self.extras["skills"].get(item[0], 0)}\n'
        ret_str += f'```{self.not_selected_points_str} {self.skills_limit - self.get_sum()}\n{self.page + 1}/{len(self.pages)}\n'
        return ret_str

    def get_sum(self):
        ret_int = 0
        for item in self.list:
            ret_int += self.extras["skills"].get(item[0], 0)
        return ret_int


async def get_stats(i, name, gm=False):
    can_pass, char, user_locale = await checks(i, name, gm)
    if can_pass:
        reply = char.get_stat_str(user_locale)
        await i.response.send_message(reply)


async def checks(i, name, gm):
    user_locale = User(i.user.id, i.guild_id).get_localization()
    if gm:
        char = get_char(i, name, False, True)
    else:
        char = get_char(i, name)
    if char:
        if char.char:
            if await gm_check(i, char.char, user_locale, gm):
                return False, char, user_locale
    return await check(i, char, name, user_locale)


async def check(i, char, name, user_locale):
    if char:  # todo fix this
        if not char.char:
            if not name:
                await create_char(i, False, i.user.id, 'player')
                return False, char, user_locale
            else:
                raise Exception
    return True, char, user_locale


async def get_stat_view(i, name, gm=False):
    can_pass, char, user_locale = await checks(i, name, gm)
    if can_pass:
        view = StatsView(i, char, user_locale, gm)
        await i.response.send_message(content=view.get_str(), view=view)


async def get_info(i, name, gm=False):
    await checks(i, name, gm)
    view = InfoView(i, name, User(i.user.id, i.guild_id).get_localization(), gm)
    if await gm_check(i, view.character.char, view.localization, gm):
        return
    await i.response.send_message(content=view.get_str(), view=view, files=view.get_image())


async def create_char(i: discord.Interaction, gm, owner_id, char_type):
    localization = User(i.user.id, i.guild.id).get_localization()
    modal = CharCreationModal(get_localized_answer('char_creation_modal_title', localization),
                              localization, gm, owner_id=owner_id, char_type=char_type)
    await i.response.send_modal(modal)


class CharSelect(Select):
    def __init__(self, i, pages, page, row=0):
        pages = pages
        page = page
        cur_page = pages[page]
        super().__init__(options=[SelectOption(label=check_for_none(i, char),
                                               value=str(char['_id']),
                                               emoji=FACTION_EMOJIS[char['faction']]) for char in cur_page], row=row)

    async def callback(self, i: discord.Interaction):
        cur_page = self.view.pages[self.view.page]
        tmp_dict = {str(char['_id']): char['name'] for char in cur_page}
        self.replace_placeholder(tmp_dict[self.values[0]])
        self.view.rebuild()
        await i.response.edit_message(view=self.view)

    def replace_placeholder(self, placeholder):
        self.placeholder = placeholder

    def replace_options(self, i):
        self.replace_placeholder(None)
        if self.view.pages:
            cur_page = self.view.pages[self.view.page]
            self.options = [SelectOption(label=check_for_none(i, char),
                                         value=str(char['_id']),
                                         emoji=FACTION_EMOJIS[char['faction']]) for char in cur_page]


class DeleteCharBTN(Button):
    def __init__(self, label, row=1, emoji=None, style=discord.ButtonStyle.gray, disabled=False):
        super().__init__(label=label, row=row, emoji=emoji, style=style, disabled=disabled)

    async def callback(self, i: discord.Interaction):
        await delete_char(i, self.view.select.values[0], self.view)


class CharsView(GenericView):
    def __init__(self, i: discord.Interaction, owner_id: int, gm: bool, all_chars: bool):
        super().__init__(i)
        self.interaction = i
        self.localization = User(i.user.id, i.guild_id).get_localization()
        self.owner_id = owner_id
        self.gm = gm
        self.page = 0
        self.per_page = 25
        if all_chars:
            self.character_filter = {}
        else:
            self.character_filter = {'owner_id': owner_id}

        self.characters = [x for x in
                           characters.find(self.character_filter, {'name': 1, '_id': 1, 'faction': 1, 'owner_id': 1})]
        self.pages = split_to_ns(self.characters, self.per_page)
        if not self.pages:
            return
        self.select = CharSelect(i, self.pages, self.page)
        self.continue_btn = GenericToViewBTN(MainMenuView, get_localized_answer('continue_btn', self.localization),
                                             False,
                                             discord.ButtonStyle.green,
                                             [i, owner_id, gm, all_chars, '', self.localization], row=1, )
        self.delete_char_btn = DeleteCharBTN(label=get_localized_answer('delete_btn', self.localization),
                                             style=discord.ButtonStyle.danger)
        self.rebuild()

    def change_page(self):
        self.rebuild(False)
        self.select.replace_options(self.interaction)
        return self.get_str()

    def get_str(self):
        if self.pages:
            return f'{self.page + 1}/{len(self.pages)}'
        else:
            return get_localized_answer('no_chars_error', self.localization)

    def rebuild(self, add_buttons=True):
        self.clear_items()
        if self.pages:
            if self.select.values and add_buttons:
                self.continue_btn.n_args[4] = bson.ObjectId(self.select.values[0])
                self.add_item(self.continue_btn)
                if self.gm:
                    self.add_item(self.delete_char_btn)
            self.add_item(self.select)
            self.regenerate_pages()


class FieldSelect(Select):
    def __init__(self, translation_dict, localization):
        self.translation_dict = translation_dict
        self.localization = localization
        super().__init__(options=[
            SelectOption(
                label=get_item_from_translation_dict(translation_dict, localization, x),
                value=x) for x in CAN_BE_STR_IN_CHAR + CAN_BE_INT_IN_CHAR])

    async def callback(self, i: discord.Interaction):
        self.replace_placeholder(
            get_item_from_translation_dict(self.translation_dict, self.localization, self.values[0]))
        self.view.rebuild()
        await i.response.edit_message(content=self.view.get_str(), view=self.view, attachments=self.view.get_image())

    def replace_placeholder(self, placeholder):
        self.placeholder = placeholder


class ArmorSelect(Select):
    def __init__(self, character, localization):
        items, _ = character.read_equipped()
        super().__init__(options=[
            SelectOption(
                label=get_item_from_translation_dict(x['localization'], localization, 'name'),
                value=f'{n}|{x["_id"]}') for n, x in enumerate(items['equipped']) if x['type'] in ARMOR_TYPES])
        self.items = items['equipped']
        self.localization = localization

    async def callback(self, i: discord.Interaction):
        self.replace_placeholder(
            get_item_from_translation_dict(self.items[int(self.values[0].split('|')[0])]['localization'],
                                           self.localization, 'name'))
        self.view.rebuild()
        await i.response.edit_message(content=self.view.get_str(), view=self.view, attachments=self.view.get_image())

    def replace_placeholder(self, placeholder):
        self.placeholder = placeholder


class BuffAndDebuffSelect(Select):
    def __init__(self, character, localization, page):
        super().__init__(
            options=[
                SelectOption(
                    label=get_item_from_translation_dict(x['localization'], localization,
                                                         'use_effect_name') + f' {n + 1}',
                    value=n) for n, x in enumerate(character.char['buffs_and_debuffs'][page * 24:page * 24 + 24])
            ]
        )

    async def callback(self, i: discord.Interaction):
        self.replace_placeholder(get_item_from_translation_dict(
            self.view.character.char['buffs_and_debuffs'][
                int(self.values[0]) * int(self.view.pages[self.view.page].split('_')[-1])]['localization'],
            self.view.localization, 'use_effect_name'))
        self.view.rebuild()
        await i.response.edit_message(content=self.view.get_str(), view=self.view, attachments=self.view.get_image())

    def replace_placeholder(self, placeholder):
        self.placeholder = placeholder


class ModeSelect(Select):
    def __init__(self, localization):
        super().__init__(
            options=[
                SelectOption(
                    label=x,  # get_localized_answer(x, localization)
                    value=x) for x in ['counters', 'armor']])

    async def callback(self, i: discord.Interaction):
        self.view.mode = self.values[0]
        self.replace_placeholder(self.view.mode)
        self.view.mode_select = self
        self.view.rebuild()
        await i.response.edit_message(content=self.view.get_str(), view=self.view, attachments=self.view.get_image())

    def replace_placeholder(self, placeholder):
        self.placeholder = placeholder


class RepairOrDamageBTN(Button):
    def __init__(self, label, style, row=0, disabled=False):
        super().__init__(label=label, style=style, row=row, disabled=disabled)

    async def callback(self, i: discord.Interaction):
        idx, u_id = self.view.armor_select.values[0].split('|')
        idx, u_id = int(idx), bson.ObjectId(u_id)
        await i.response.send_modal(
            RepairOrDamageModal(i.message, self.view, self.view.character, self.view.localization, idx, u_id))


class RemoveBuffOrDebuffBTN(Button):
    def __init__(self, label, style, row=0, disabled=False):
        super().__init__(label=label, style=style, row=row, disabled=disabled)

    async def callback(self, i: discord.Interaction):
        idx = int(self.view.buff_and_debuff_select.values[0]) * int(self.view.pages[self.view.page].split('_')[-1])
        self.view.character.remove_buff_or_debuff_at_idx(idx)
        self.view.pages = self.view.character.get_buffs_and_debuffs_pages()
        self.view.rebuild()
        await i.response.edit_message(content=self.view.get_str(), view=self.view, attachments=self.view.get_image())


class RepairOrDamageModal(Modal):
    def __init__(self, message, view, character, localization, idx, u_id):
        super().__init__(title='todo')
        self.character = character
        self.localization = localization
        self.idx = idx
        self.u_id = u_id
        self.message = message
        self.view = view
        self.head_damage = TextInput(label='head', placeholder='0', min_length=1, max_length=3, default='0')
        self.body_damage = TextInput(label='body', placeholder='0', min_length=1, max_length=3, default='0')
        self.add_item(self.head_damage)
        self.add_item(self.body_damage)

    async def on_submit(self, i: discord.Interaction):
        head_damage, body_damage = int(str(self.head_damage)), int(str(self.body_damage))
        if head_damage:
            self.character.damage_or_repair_item_at_idx(self.idx, self.u_id, 'head', head_damage)
        if body_damage:
            self.character.damage_or_repair_item_at_idx(self.idx, self.u_id, 'body', body_damage)
        await i.response.send_message('todo', ephemeral=True)
        await self.message.edit(content=self.view.get_str(), attachments=self.view.get_image())


class InfoView(GenericView):
    def __init__(self, i, name, localization, gm=False, back_data=None):
        super().__init__(i)
        self.character = get_char(i, name)
        self.gm = gm
        self.localization = localization
        self.back_data = back_data
        self.page = 0
        self.pages = ['main', 'frac_rep', *[f'buffs_and_debuffs_{x}' for x in
                                            range(len(split_to_ns(self.character.char['buffs_and_debuffs'], 25)))]]
        self.mode = 'counters'
        self.mode_select = ModeSelect(self.localization)
        self.localization_dict = localized_data.find_one({'request': 'info_view_data'})['local']
        self.faction_dict = localized_data.find_one({'request': 'factions'})['local']
        self.fields_dict = localized_data.find_one({'request': 'char_fields'})['local']
        self.armor_dict = localized_data.find_one({'request': 'armor_data'})['local']
        self.stats_and_skills_data = localized_data.find_one({'request': 'stats_and_skills'})['local']
        self.field_select = FieldSelect(self.fields_dict, self.localization)
        self.armor_select = ArmorSelect(self.character, self.localization)
        self.buff_and_debuff_select = BuffAndDebuffSelect(self.character, self.localization, self.page)
        self.damage_or_repair_btn = RepairOrDamageBTN(label='todo', style=discord.ButtonStyle.gray, row=2)
        self.remove_buff_or_debuff_btn = RemoveBuffOrDebuffBTN(label='todo', style=discord.ButtonStyle.red, row=2)
        self.background_btn = None
        self.back_btn = None
        self.uni_set_btn = UniUpdateBTN(
            label=get_item_from_translation_dict(self.localization_dict, localization, 'set_btn'),
            localization=self.localization,
            row=2
        )
        self.uni_change_btn = UniUpdateBTN(
            label=get_item_from_translation_dict(self.localization_dict, localization, 'change_btn'),
            mode=[0, False, False, float],
            localization=self.localization,
            row=2
        )

        self.faction_select = FactionSelect(self.faction_dict, self.localization, True, True)
        self.select = None
        if url := self.character.char['background_url']:
            self.background_btn = Button(
                label=get_item_from_translation_dict(self.localization_dict, localization, 'background_btn_label'),
                url=url,
                row=4
            )
        if self.back_data:
            self.back_btn = GenericToViewBTN(MainMenuView, get_localized_answer('back_btn', localization), False,
                                             discord.ButtonStyle.blurple, [*back_data], row=3)
        self.rebuild()

    def change_page(self):
        self.rebuild()
        return self.get_str()

    def rebuild(self):
        self.clear_items()
        if self.gm:
            current_page = self.pages[self.page]
            match self.pages[self.page]:
                case 'main':
                    self.add_item(self.mode_select)
                    match self.mode:
                        case 'counters':
                            self.select = self.field_select
                            self.add_item(self.select)
                            if self.select.values:
                                if self.select.values[0] in CAN_BE_INT_IN_CHAR:
                                    self.uni_change_btn.mode = [1, False, False, int]
                                    self.uni_set_btn.mode = [0, False, False, int]
                                    self.add_item(self.uni_set_btn)
                                    self.add_item(self.uni_change_btn)
                                else:
                                    self.uni_set_btn.mode = [0, False, False, str]
                                    self.add_item(self.uni_set_btn)
                        case 'armor':
                            self.select = self.armor_select
                            self.add_item(self.select)
                            if self.select.values:
                                self.add_item(self.damage_or_repair_btn)
                case 'frac_rep':
                    self.select = self.faction_select
                    self.add_item(self.select)
                    self.uni_change_btn.mode = [1, True, False, float]
                    self.uni_set_btn.mode = [0, True, False, float]
                    if self.select.values:
                        self.add_item(self.uni_set_btn)
                        self.add_item(self.uni_change_btn)
                case _:
                    if current_page.startswith('buffs_and_debuffs_'):
                        self.add_item(self.buff_and_debuff_select)
                        if self.buff_and_debuff_select.values:
                            self.add_item(self.remove_buff_or_debuff_btn)
        self.regenerate_pages()
        if self.background_btn:
            self.add_item(self.background_btn)
        if self.back_btn:
            self.add_item(self.back_btn)

    def get_str(self):
        current_page = self.pages[self.page]
        match current_page:
            case 'main':
                hp = self.character.char['hp']
                hp_limit = self.character.get_hp_limit()
                hp_status = ''
                if hp <= numpy.floor(hp_limit / 4):
                    hp_status = f"[{get_item_from_translation_dict(self.localization_dict, self.localization, 'very_serious_wound')} (-5)]"
                elif hp <= numpy.floor(hp_limit / 2):
                    hp_status = f"[{get_item_from_translation_dict(self.localization_dict, self.localization, 'serious_wound')} (-3)]"
                elif hp <= numpy.floor(hp_limit * 3 / 4):
                    hp_status = f"[{get_item_from_translation_dict(self.localization_dict, self.localization, 'wound')} (-1)]"
                main_str = f"{self.character.char['name']}\n" \
                           f"|{EMOJIS['hp']}{hp}/{hp_limit} {hp_status:}" \
                           f"|{EMOJIS['psi_hp']}{self.character.char['psi_hp']}/{self.character.get_psi_hp_limit()}" \
                           f"|{EMOJIS['radiation']}{self.character.char['radiation']}/{hp}|\n" \
                           f"{self.character.count_points() - self.character.count_used_points()} {get_item_from_translation_dict(self.localization_dict, self.localization, 'pts_remain')}\n" \
                           f"{self.character.char['mastery']} {get_item_from_translation_dict(self.localization_dict, self.localization, 'mastery')}\n" \
                           f"{self.character.char['money']}{EMOJIS['money']}\n"
                items_str = ''
                items, mods = self.character.read_equipped()
                for item in items['equipped']:
                    if item['type'] in ['full_armor', 'hazmat_suit', 'exoskeleton']:
                        items_str += '|'
                        for resist in RESIST_LIST:
                            items_str += f'{RESIST_EMOJIS[resist]}{item.get(resist, 0):>2}|'
                        items_str += f'\n|{EMOJIS["broken_armor"]}{item.get("body_damage", 0):>2}|{EMOJIS["broken_helmet"]}{item.get("head_damage", 0):>2}|'
                    elif item['type'] == 'helmet':
                        items_str += '|'
                        for resist in RESIST_LIST[1:]:
                            items_str += f'{RESIST_EMOJIS[resist]}{item.get(resist, 0)}|'
                        items_str += f'\n|{EMOJIS["broken_helmet"]}{item.get("head_damage", 0):>2}|'
                    elif item['type'] == 'armor':
                        items_str += '|'
                        items_str += f'{RESIST_EMOJIS["body_armor_points"]}{item.get("body_armor_points", 0):>2}|'
                        for resist in RESIST_LIST[2:]:
                            items_str += f'{RESIST_EMOJIS[resist]}{item.get(resist, 0)} |'
                        items_str += f'\n|{EMOJIS["broken_armor"]}{item.get("body_damage", 0):>2}|'
                    items_str += '\n'
                    items_str += f" {get_item_from_translation_dict(item['localization'], self.localization, 'name')} ({item['weight']}кг)\n"
                    for modification in item['modifications']:
                        current_mod = mods[modification]
                        effects = ''
                        if current_mod['weight']:
                            effects += f"({int(mods[modification]['weight'] * 100)}%) "
                        for buff_debuff in current_mod['actions_when_equipped']:
                            sign = '+' if buff_debuff["num"] > 0 else '-'
                            effects += f'({get_item_from_translation_dict(self.armor_dict, self.localization, buff_debuff["what_to_buff"])} ' \
                                       f'{sign}{buff_debuff["num"]})'
                        items_str += f"     •{get_item_from_translation_dict(current_mod['localization'], self.localization, 'name')} {effects}\n"
                main_str += items_str
                main_str += f"{get_item_from_translation_dict(self.localization_dict, self.localization, 'page')}{self.page + 1}/{len(self.pages)}"
                return main_str
            case 'frac_rep':
                fac_rep = ''
                rep_strings = [(-numpy.inf, -1, 'rep_very_bad'),
                               (-1, -0.5, 'rep_bad'),
                               (0.5, 1, 'rep_good'),
                               (1, numpy.inf, 'rep_very_good')]
                for faction, rep in self.character.char['frac_rep'].items():
                    cur_str = ''
                    for mn, mx, st in rep_strings:
                        if rep >= 0:
                            if mn <= rep < mx:
                                cur_str = st
                                break
                        else:
                            if mn < rep <= mx:
                                cur_str = st
                                break
                    if not cur_str:
                        cur_str = 'rep_neutral'

                    fac_rep += \
                        f'{get_item_from_translation_dict(self.faction_dict, self.localization, faction)}: ' \
                        f'{get_item_from_translation_dict(self.localization_dict, self.localization, cur_str)} ({rep})\n'
                if not fac_rep:
                    fac_rep = '. . .'
                return f"{self.character.char['name']}\n```{fac_rep}```" \
                       f"{get_item_from_translation_dict(self.localization_dict, self.localization, 'page')}{self.page + 1}/{len(self.pages)}"
            case _:
                ret_str = f'{self.character.char["name"]}\n'
                if current_page.startswith('buffs_and_debuffs_'):
                    use_effect_str = get_item_from_translation_dict(self.localization_dict, self.localization,
                                                                    'use_effect_str')
                    page_num = int(current_page.split('_')[-1])
                    for buff_or_debuff in self.character.char['buffs_and_debuffs'][page_num * 24:page_num * 24 + 24]:
                        buffs_str = ''
                        for buff in buff_or_debuff['buffs']:
                            buffs_str += f'{get_item_from_translation_dict(self.stats_and_skills_data, self.localization, buff["name"])} +{buff["value"]}, '
                        for debuff in buff_or_debuff['debuffs']:
                            buffs_str += f'{get_item_from_translation_dict(self.stats_and_skills_data, self.localization, debuff["name"])} -{abs(debuff["value"])}, '
                        if buffs_str:
                            buffs_str = buffs_str[:-2]
                            buffs_str += '\n'

                        ret_str += use_effect_str.format(
                            use_effect_name=get_item_from_translation_dict(buff_or_debuff["localization"],
                                                                           self.localization, "use_effect_name"),
                            name=get_item_from_translation_dict(buff_or_debuff["localization"], self.localization,
                                                                "name"),
                            effects=buffs_str)
                    return ret_str

    def get_image(self):
        image = []
        match self.pages[self.page]:
            case 'main':
                profile_pic = self.character.char['img_url']
                if not profile_pic:
                    profile_pic = char_image_placeholder
                response = requests.get(profile_pic)
                profile_pic_img = Image.open(io.BytesIO(response.content))
                if profile_pic_img.size != (128, 128):
                    profile_pic_img = profile_pic_img.resize((128, 128))
                hp_limit = self.character.get_hp_limit()
                psi_hp_limit = self.character.get_psi_hp_limit()
                hp_bar_cropped, show_hp_bar = crop_bars(hp_bar, self.character.char['hp'], hp_limit)
                rad_bar_cropped, show_rad_bar = crop_bars(rad_bar, self.character.char['radiation'], hp_limit)
                psi_bar_cropped, show_psi_bar = crop_bars(psi_bar, self.character.char['psi_hp'], psi_hp_limit)
                image = background_image.copy()
                image.paste(profile_pic_img, (48, 51))
                if show_hp_bar:
                    image.paste(hp_bar_cropped, (52, 204))
                if show_psi_bar:
                    image.paste(psi_bar_cropped, (52, 222))
                if show_rad_bar:
                    image.paste(rad_bar_cropped, (52, 239))
                image.paste(bars, (20, 183), bars)
            case 'frac_rep':
                factions = self.character.char['frac_rep']
                images = [top, *[middle] * (len(factions) - 1), bottom]
                widths, heights = zip(*(i.size for i in images))
                total_width = max(widths)
                max_height = sum(heights)
                image = Image.new('RGBA', (total_width, max_height))
                y_offset = 0
                for im in images:
                    image.paste(im, (0, y_offset))
                    y_offset += im.size[1]
                current_y = 14
                for faction, rep_num in factions.items():
                    draw = ImageDraw.Draw(image)
                    image.paste(background, (1, current_y), background)
                    rectangle_y = current_y + 39
                    faction_image = faction_images.get(faction)
                    image.paste(faction_image, (33 + 21 - int(numpy.floor(faction_image.size[0] / 2)), current_y + 5),
                                faction_image.convert("RGBA"))
                    if -0.51 < rep_num < 0:
                        draw.rectangle((104, rectangle_y, 117, rectangle_y - int(28 * (-rep_num * 2))),
                                       fill=COLORS['bad'])
                    elif rep_num < -0.5:
                        draw.rectangle((104, rectangle_y, 117, current_y + 9), fill=COLORS['bad'])
                        draw.rectangle(
                            (85, rectangle_y, 98, rectangle_y - numpy.clip(int(28 * ((-rep_num - 0.5) * 2)), 0, 28)),
                            fill=COLORS['very_bad'])
                    if 0 < rep_num < 0.51:
                        draw.rectangle((142, rectangle_y, 155, rectangle_y - int(28 * (rep_num * 2))),
                                       fill=COLORS['good'])
                    elif 0.5 < rep_num:
                        draw.rectangle((142, rectangle_y, 155, current_y + 9), fill=COLORS['good'])
                        draw.rectangle(
                            (161, rectangle_y, 174, rectangle_y - numpy.clip(int(28 * ((rep_num - 0.5) * 2)), 0, 28)),
                            fill=COLORS['very_good'])

                    image.paste(rep_bars, (63, current_y - 11), rep_bars)
                    current_y += 69

        if not image:
            return image
        with io.BytesIO() as buffer:
            image.save(buffer, 'PNG')
            buffer.seek(0)
            return [discord.File(buffer, filename='info.png')]


class SelectViews(Select):
    def __init__(self, opts, data, localization):
        super().__init__(options=[
            SelectOption(
                label=get_item_from_translation_dict(data, localization, x), value=x)
            for x in opts
        ])

    async def callback(self, interaction: Interaction):
        mes = interaction.message
        view = self.view.menu_options[self.values[0]](interaction, self.view.selected_char, self.view.localization,
                                                      self.view.gm,
                                                      (interaction, self.view.owner_id, self.view.gm,
                                                       self.view.all_chars, self.view.selected_char,
                                                       self.view.localization))
        await interaction.response.edit_message(content=view.get_str(), view=view, embeds=view.get_embeds())
        await mes.edit(attachments=view.get_image())


class MainMenuView(GenericView):
    def __init__(self, i: discord.Interaction, owner_id: int, gm: bool, all_chars: bool, selected_char, localization):
        super().__init__(i)
        self.menu_options = {
            # 'get_info': InfoView,
            'get_stats': StatsView,
            'get_inventory': InventoryView,
            'get_health': HealthView,
            'get_pda': PDA
        }
        self.all_chars = all_chars
        self.selected_char = selected_char
        self.gm = gm
        self.localization = localization
        self.owner_id = owner_id
        self.localized_data = localized_data.find_one({'request': 'menu_view_data'})['local']
        self.select = SelectViews(self.menu_options.keys(), self.localized_data, self.localization)
        self.back_btn = GenericToViewBTN(CharsView, get_localized_answer('back_btn', localization), False,
                                         discord.ButtonStyle.blurple, [i, owner_id, gm, all_chars], 1)
        self.rebuild()

    def rebuild(self):
        self.clear_items()
        if self.select.values:
            self.select.placeholder = get_item_from_translation_dict(self.localized_data, self.localization,
                                                                     self.select.values[0])
        self.add_item(self.select)
        self.add_item(self.back_btn)


def crop_bars(image, number, limit):
    if number <= 0:
        return image, False
    elif number >= limit:
        return image, True
    else:
        return image.crop((0, 0, int(image.size[0] * number / limit), image.size[1])), True


async def chars(i: discord.Interaction, owner_id, gm, all_chars=False, skip_checks=False):
    if not skip_checks:
        await checks(i, None, gm)
    view = CharsView(i, owner_id, gm, all_chars)
    await i.response.send_message(content=view.get_str(), view=view)


async def get_inventory_view(i: discord.Interaction, name, gm=False):
    can_pass, char, user_locale = await checks(i, name, gm)
    if can_pass:
        view = InventoryView(i, char, user_locale, gm)
        await i.response.send_message(content=view.get_str(), view=view, embeds=view.get_embeds())


class SelectItem(Select):
    def __init__(self, opts, localization, gm):
        opts = deepcopy(opts)
        if not opts[-1]:
            opts.pop()

        super().__init__(options=[
            SelectOption(
                label=get_item_from_translation_dict(x['localization'], localization, 'name'), value=n)
            for n, x in enumerate(opts)
        ])
        self.gm = gm
        self.localization = localization
        self.opts = opts

    async def callback(self, interaction: Interaction):
        self.placeholder = get_item_from_translation_dict(
            self.view.pages[self.view.page][int(self.values[0])]['localization'],
            self.view.localization, 'name')
        self.view.rebuild()
        await interaction.response.edit_message(view=self.view)

    def replace_options(self):
        self.placeholder = None
        opts = deepcopy(self.view.pages[self.view.page])
        if not opts[-1]:
            opts.pop()

        self.options = [
            SelectOption(
                label=get_item_from_translation_dict(x['localization'], self.localization, 'name'), value=n)
            for n, x in enumerate(opts)
        ]


class EquipButton(discord.ui.Button):
    def __init__(self, localization):
        super().__init__(label=get_localized_answer('equip_btn', localization), style=discord.ButtonStyle.green)

    async def callback(self, interaction: Interaction):
        selected = int(self.view.select.values[0])
        page = self.view.page - self.view.equipped_length
        if page < 0:
            page = 0
        result = self.view.character.equip_item_at_idx(selected + page * self.view.max_on_page,
                                                       self.view.pages[self.view.page][selected]['_id'],
                                                       self.view.pages[self.view.page][selected]['type'])
        item = self.view.pages[self.view.page][selected]
        self.view.replace_pages()
        self.view.change_page()
        await interaction.response.edit_message(content=self.view.get_str(), view=self.view, embeds=self.view.get_embeds())
        if result:
            await interaction.followup.send(
                f'{get_item_from_translation_dict(self.view.translation_data, self.view.localization, "equipped")} '
                f'{get_item_from_translation_dict(item["localization"], self.view.localization, "name")}',
                ephemeral=True)  # TODO: add localization
        else:
            await interaction.followup.send('can\'t', ephemeral=True)  # TODO: add localization


class UseButton(discord.ui.Button):
    def __init__(self, localization):
        # get_localized_answer('use_btn', localization) todo
        super().__init__(label='use', style=discord.ButtonStyle.green)

    async def callback(self, interaction: Interaction):
        selected = int(self.view.select.values[0])
        selected_item = self.view.pages[self.view.page][selected]
        result, ret_str = self.view.character.use_item_with_uid(selected_item['_id'], self.view.localization)
        self.view.replace_pages()
        self.view.change_page()
        await interaction.response.edit_message(content=self.view.get_str(), view=self.view, embeds=self.view.get_embeds())
        if result:
            await interaction.followup.send(
                f'used {get_item_from_translation_dict(selected_item["localization"], self.view.localization, "name")}\n' + ret_str)  # TODO: add localization
        else:
            await interaction.followup.send('can\'t')  # TODO: add localization


class UnEquipButton(discord.ui.Button):
    def __init__(self, localization):
        super().__init__(label=get_localized_answer('unequip_btn', localization), style=discord.ButtonStyle.red)

    async def callback(self, interaction: Interaction):
        selected = int(self.view.select.values[0])
        self.view.character.unequip_item_at_idx(selected + self.view.page * self.view.max_on_page,
                                                self.view.pages[self.view.page][selected]['_id'])
        self.view.replace_pages()
        self.view.change_page()
        await interaction.response.edit_message(content=self.view.get_str(), view=self.view, embeds=self.view.get_embeds())


class DropButton(discord.ui.Button):
    def __init__(self, localization):
        super().__init__(label=get_localized_answer('drop_btn', localization), style=discord.ButtonStyle.red)

    async def callback(self, interaction: Interaction):
        await interaction.response.send_modal(DropModal(self.view))


class CycleInventoryModeBTN(Button):
    def __init__(self, translation_data, localization):
        super().__init__(label=get_item_from_translation_dict(translation_data, localization, 'cycle_btn'), row=3)

    async def callback(self, interaction: Interaction):
        self.view.mode += 1
        if self.view.mode > 2:
            self.view.mode = 0
        self.view.rebuild()
        await interaction.response.edit_message(content=self.view.get_str(), embeds=self.view.get_embeds())


class InventoryView(GenericView):
    def __init__(self, i, character, localization, gm=False, back_data=None):
        super().__init__(i, row=4)
        self.localization = localization
        self.gm = gm
        self.i = i
        self.back_data = back_data
        self.translation_data = localized_data.find_one({'request': 'inventory_view_data'})['local']
        self.body_part_translation_data = localized_data.find_one({'request': 'body_parts'})['local']
        self.embed_data = localized_data.find_one({'request': 'item_embed_data'})['local']
        if not character or type(character) == bson.ObjectId:
            character = get_char(i, character)
        self.character = character
        self.inventory, _, self.dict_of_inv_mods, self.dict_of_eq_mods = character.read_inv()
        self.max_on_page = 5
        self.use_btn = UseButton(self.localization)
        self.equip_btn = EquipButton(self.localization)
        self.unequip_btn = UnEquipButton(self.localization)
        self.drop_btn = DropButton(self.localization)
        self.cycle_btn = CycleInventoryModeBTN(self.translation_data, self.localization)
        self.modify_btn = GenericToViewBTN(ModifyItemView,
                                           get_item_from_translation_dict(self.translation_data, self.localization,
                                                                          'modify'), row=1)
        self.unmodify_btn = GenericToViewBTN(ModifyItemView,
                                             get_item_from_translation_dict(self.translation_data, self.localization,
                                                                            'unmodify'), row=1)
        self.shoot_btn = GenericToViewBTN(ShootView,
                                          get_item_from_translation_dict(self.translation_data, self.localization,
                                                                         'shoot'), row=1)
        self.plate_carrier_btn = GenericToViewBTN(PlateCarrierView,
                                                  get_item_from_translation_dict(self.translation_data,
                                                                                 self.localization, 'plates'), row=1)
        self.mode = 1
        equipped = split_to_ns(self.inventory['equipped'], self.max_on_page)
        if equipped:
            equipped = list(map(lambda x: x + [False], equipped))
            self.equipped_length = len(equipped)
            self.pages = equipped + split_to_ns(self.inventory['inventory'], self.max_on_page)
        else:
            self.pages = split_to_ns(self.inventory['inventory'], self.max_on_page)
            self.equipped_length = 0
        if self.pages:
            self.select = SelectItem(self.pages[self.page], self.localization, self.gm)

        if back_data:
            self.back_btn = GenericToViewBTN(MainMenuView, get_localized_answer('back_btn', localization), False,
                                             discord.ButtonStyle.blurple, back_data, 4)
        self.rebuild(False)

    def change_page(self):
        if self.page >= len(self.pages):
            self.page -= 1
        self.select.replace_options()
        self.rebuild(False)
        return self.get_str()

    def rebuild(self, add_buttons=True):
        self.clear_items()
        self.add_item(self.cycle_btn)
        if self.pages:
            self.add_item(self.select)
            if add_buttons:
                if self.pages[self.page][-1]:
                    if self.select.values:
                        item = self.pages[self.page][int(self.select.values[0])]
                        if item['can_be_equipped']:
                            self.add_item(self.equip_btn)
                        if item['can_be_used']:
                            self.add_item(self.use_btn)
                        self.add_item(self.drop_btn)
                else:
                    self.add_item(self.unequip_btn)
                    if self.select.values:
                        item = self.pages[self.page][int(self.select.values[0])]
                        idx = int(self.select.values[0])
                        # if item['type'] in CAN_BE_MODIFIED:
                        #     self.modify_btn.n_args = (
                        #         self.i, self.character, item, idx, self.inventory['inventory'],
                        #         self.dict_of_eq_mods, self.localization, 0,
                        #         (self.i, self.character, self.localization, self.gm, self.back_data))
                        #     self.add_item(self.modify_btn)
                        #     if self.gm:
                        #         self.unmodify_btn.n_args = (
                        #             self.i, self.character, item, idx,
                        #             self.inventory['inventory'],
                        #             self.dict_of_eq_mods, self.localization, 1,
                        #             (self.i, self.character, self.localization, self.gm, self.back_data))
                        #         self.add_item(self.unmodify_btn)
                        if item['type'] == 'weapon':
                            self.shoot_btn.n_args = (self.i, self.character, item,
                                                     [self.i, self.character, self.localization, self.gm,
                                                      self.back_data])
                            self.add_item(self.shoot_btn)
                        elif item['type'] == 'plate_carrier':
                            self.plate_carrier_btn.n_args = (
                                self.i, self.character, item, idx, self.localization, self.gm,
                                [self.i, self.character, self.localization, self.gm, self.back_data])
                            self.add_item(self.plate_carrier_btn)

        self.regenerate_pages()
        if self.back_data:
            self.add_item(self.back_btn)

    def replace_pages(self):
        self.inventory, _, _, _ = self.character.read_inv()
        equipped = split_to_ns(self.inventory['equipped'], self.max_on_page)
        if equipped:
            equipped = list(map(lambda x: x + [False], equipped))
            self.equipped_length = len(equipped)
            self.pages = equipped + split_to_ns(self.inventory['inventory'], self.max_on_page)
        else:
            self.pages = split_to_ns(self.inventory['inventory'], self.max_on_page)
            self.equipped_length = 0

    def get_str(self):
        if self.pages:
            our_items = deepcopy(self.pages[self.page])
            if not our_items[-1]:
                equipped_item_str = get_item_from_translation_dict(self.translation_data, self.localization, 'equipped')
                our_items.pop()
            else:
                equipped_item_str = get_item_from_translation_dict(self.translation_data, self.localization,
                                                                   'inventory')
            return (f'{equipped_item_str} {self.character.char["name"]}  {self.page + 1}/{len(self.pages)} '
                    f'{get_item_from_translation_dict(self.translation_data, self.localization, str(self.mode))}')
        else:
            return 'empty'  # TODO: add localization

    def get_embeds(self):
        embed_list = []
        if self.pages:
            our_items = deepcopy(self.pages[self.page])
            if not our_items[-1]:
                our_items.pop()

            for item in our_items:
                embed_list.append(
                    get_item_embed(item, self.body_part_translation_data, self.translation_data, self.embed_data,
                                   self.localization, self.mode))
        return embed_list


class ShopView(GenericView):
    def __init__(self, i, character, typ, per_page, localization, gm=False, back_data=None):
        super().__init__(i, row=4)
        self.localization = localization
        self.gm = gm
        self.i = i
        self.back_data = back_data
        self.translation_data = localized_data.find_one({'request': 'inventory_view_data'})['local']
        self.body_part_translation_data = localized_data.find_one({'request': 'body_parts'})['local']
        self.embed_data = localized_data.find_one({'request': 'item_embed_data'})['local']
        if not character or type(character) == bson.ObjectId:
            character = get_char(i, character)
        self.max_on_page = per_page
        self.cycle_btn = CycleInventoryModeBTN(self.translation_data, self.localization)
        self.mode = 1
        self.pages = split_to_ns(list(items.find({'guild_id': i.guild_id, 'type': typ})), self.max_on_page)
     #   if self.pages:
     #       self.select = SelectItem(self.pages[self.page], self.localization, self.gm)

        if back_data:
            self.back_btn = GenericToViewBTN(MainMenuView, get_localized_answer('back_btn', localization), False,
                                             discord.ButtonStyle.blurple, back_data, 4)
        self.rebuild(False)

    def change_page(self):
        if self.page >= len(self.pages):
            self.page -= 1
#        self.select.replace_options()
        self.rebuild(False)
        return self.get_str()

    def rebuild(self, add_buttons=True):
        self.clear_items()
        self.add_item(self.cycle_btn)
        #if self.pages:
        #    self.add_item(self.select)
        self.regenerate_pages()
        if self.back_data:
            self.add_item(self.back_btn)

    def get_str(self):
        if self.pages:
            return f'{self.page + 1}/{len(self.pages)}'
        else:
            return 'empty'  # TODO: add localization

    def get_embeds(self):
        embed_list = []
        for item in self.pages[self.page]:
            embed_list.append(
                get_item_embed(item, self.body_part_translation_data, self.translation_data, self.embed_data,
                               self.localization, self.mode))
        return embed_list

class DropModal(Modal):
    def __init__(self, view: InventoryView):
        self.view = view
        self.quantity = TextInput(
            label=get_item_from_translation_dict(view.translation_data, view.localization, 'input_num'),
            placeholder='1')
        super().__init__(
            title=get_item_from_translation_dict(view.translation_data, view.localization, 'drop_modal_title'))
        self.add_item(self.quantity)

    async def on_submit(self, interaction: Interaction):
        selected = int(self.view.select.values[0])
        page = self.view.page - self.view.equipped_length
        self.view.character.remove_item_by_idx(self.view.pages[self.view.page][selected],
                                               selected + page * self.view.max_on_page, abs(int(str(self.quantity))))
        self.view.replace_pages()
        self.view.change_page()
        await interaction.response.edit_message(content=self.view.get_str(), view=self.view,
                                                embeds=self.view.get_embeds())


def get_item_embed(item, body_part_translation_data, translation_data, embed_data, localization, mode: int):
    embed = discord.Embed(title=get_item_from_translation_dict(item["localization"], localization, "name").strip())
    single_weight = ''
    misc_text = ''
    image_set = False
    inline = False
    if mode == 0:
        inline = True
    if mode >= 1:
        match item['type']:
            case 'weapon':
                if url := item.get('image_url'):
                    embed.set_image(url=url)
                    image_set = True
                ammo = items.find_one({'_id': item.get('ammo_type')})
                misc_text += f' {get_item_from_translation_dict(ammo["localization"], localization, "name")}\n'

            case 'plate_carrier':
                misc_text += get_item_from_translation_dict(translation_data, localization, 'protects') + '\n'
                plates = item.get('plates', {})
                for body_part in PLATE_CARRIER_ZONES.keys():
                    if plate := plates.get(body_part):
                        misc_text += f' {get_item_from_translation_dict(body_part_translation_data, localization, body_part)} - {get_item_from_translation_dict(plate["localization"], localization, "name")}\n'
            case 'armor':
                misc_text += get_item_from_translation_dict(translation_data, localization, 'protects') + '\n'
                for body_part in list(PLATE_CARRIER_ZONES.keys())+['head']:
                    if plate := item.get(body_part, 0):
                        misc_text += f' {get_item_from_translation_dict(body_part_translation_data, localization, body_part)} - {plate}'
            case 'medicine':
                misc_text += f" ({item['max_healing_potential'] - item.get('healing', 0)}/{item['max_healing_potential']}) "
        if misc_text:
            embed.add_field(name=get_item_from_translation_dict(embed_data, localization, "other"), value=misc_text,
                            inline=inline)

    if mode >= 2:
        embed.add_field(name=get_item_from_translation_dict(embed_data, localization, 'description'),
                        value=get_item_from_translation_dict(item['localization'], localization, 'description'))

    if url := item.get('image_url'):
        if not image_set:
            embed.set_thumbnail(url=url)

    if item.get('quantity', 1) > 1:
        single_weight = f'[{item["weight"]}]'
    embed.add_field(name=get_item_from_translation_dict(embed_data, localization, 'quantity'),
                    value=f'{item.get("quantity", 1)} {get_item_from_translation_dict(embed_data, localization, "quantity_sub_str")}',
                    inline=inline)
    weight_str = f'{round(item["weight"] * item.get("quantity", 1), 3)}{single_weight} {get_item_from_translation_dict(embed_data, localization, "weight_sub_str")}'
    embed.add_field(name=get_item_from_translation_dict(embed_data, localization, 'weight'), value=weight_str,
                    inline=inline)
    if not image_set and not inline:
        embed.set_image(url='https://cdn.discordapp.com/attachments/937328189859057674/944647455109156884/1.png')
    return embed


class ModifyItemView(GenericView):
    def __init__(self, i, character, item, idx, inventory, dict_of_eq_mods, localization, mode, back_data=None):
        super().__init__(i, row=4)
        self.item = item
        self.idx = idx
        self.inventory = inventory
        self.character = character
        self.back_data = back_data
        self.mode = mode
        if self.back_data:
            self.back_btn = GenericToViewBTN(InventoryView, get_localized_answer('back_btn', localization), False,
                                             discord.ButtonStyle.blurple, back_data, 4)
        self.dict_of_eq_mods = dict_of_eq_mods
        available_mods = []
        match mode:
            case 0:  # modify
                available_mods = []
                accepted_types = []
                max_mods = item['modification_slots']
                for mod in item['modifications']:
                    max_mods -= dict_of_eq_mods[mod]['modification_slots']
                if self.item['type'] in ARMOR_TYPES:
                    accepted_types.append(1)
                if self.item['type'] == 'exoskeleton':
                    accepted_types.append(2)
                for mod in self.inventory:
                    if mod.get('modification_type', -1) in accepted_types and mod.get('modification_slots',
                                                                                      0) <= max_mods:
                        available_mods.append(mod)
                self.available_mods = available_mods
            case 1:  # remove
                available_mods = []
                mods = set(item['modifications'])
                for mod in mods:
                    available_mods.append(dict_of_eq_mods[mod])
                self.available_mods = available_mods

        self.select = SelectModification(localization, available_mods)
        self.rebuild()

    def get_str(self):
        return f'{self.idx}'

    def rebuild(self):
        self.clear_items()
        self.add_item(self.select)
        if self.back_data:
            self.add_item(self.back_btn)

    def update_view(self):
        items, _, _, self.dict_of_eq_mods = self.character.read_inv()
        self.inventory = items['inventory']
        self.item = items['equipped'][self.idx]
        item = self.item
        match self.mode:
            case 0:  # modify
                available_mods = []
                accepted_types = []
                max_mods = item['modification_slots']
                for mod in item['modifications']:
                    max_mods -= self.dict_of_eq_mods[mod]['modification_slots']
                if self.item['type'] in ARMOR_TYPES:
                    accepted_types.append(1)
                if self.item['type'] == 'exoskeleton':
                    accepted_types.append(2)
                for mod in self.inventory:
                    if mod.get('modification_type', -1) in accepted_types and mod.get('modification_slots',
                                                                                      0) <= max_mods:
                        available_mods.append(mod)
                self.available_mods = available_mods
            case 1:  # remove
                available_mods = []
                mods = set(item['modifications'])
                for mod in mods:
                    available_mods.append(self.dict_of_eq_mods[mod])
                self.available_mods = available_mods

        self.select.replace_options()
        self.rebuild()
        return self


class SelectModification(Select):
    def __init__(self, localization, available_mods):
        options = [SelectOption(label=get_item_from_translation_dict(mod['localization'], localization, 'name'),
                                value=str(mod['_id'])) for mod in available_mods]

        if not options:
            options = [SelectOption(label='empty', value=0)]

        super().__init__(options=options)
        self.localization = localization

    async def callback(self, interaction: Interaction):
        if self.values[0] == '0':
            await interaction.response.edit_message(content=self.view.get_str())
            await interaction.followup.send('todo_no_mods')
            return
        match self.view.mode:
            case 0:  # modify
                self.view.character.add_modification(self.view.item, self.view.idx, bson.ObjectId(self.values[0]))
            case 1:  # remove
                self.view.character.remove_modification(self.view.idx, bson.ObjectId(self.values[0]))
        view = self.view.update_view()
        await interaction.response.edit_message(content=self.view.get_str(), view=view)
        match self.view.mode:
            case 0:  # modify
                await interaction.followup.send('todo_mod_added')
            case 1:  # remove
                await interaction.followup.send('todo_mod_removed')

    def replace_options(self):
        self.options = [
            SelectOption(label=get_item_from_translation_dict(mod['localization'], self.localization, 'name'),
                         value=str(mod['_id'])) for mod in self.view.available_mods]
        if not self.options:
            self.options = [SelectOption(label='empty', value=0)]


class ConfirmDeletionView(GenericView):
    def __init__(self, i: discord.Interaction, user, char, server, edited_view):
        super().__init__(i)
        self.i = i
        self.char = char
        self.char = char
        self.server = server
        self.edited_view = edited_view

    @discord.ui.button(emoji='✔', style=discord.ButtonStyle.danger)
    async def yes(self, i: discord.Interaction, _: discord.ui.Button):
        char_name = self.char.char['name']
        bson_str = dumps(self.char.char, indent=4)
        self.char.delete()
        await i.response.edit_message(
            content=get_localized_answer('char_deleted', self.user.get_localization()).format(name=char_name),
            view=None)
        if self.edited_view:
            self.edited_view.chars = [x for x in
                                      characters.find(self.edited_view.character_filter,
                                                      {'name': 1, '_id': 1, 'faction': 1, 'owner_id': 1})]
            self.edited_view.pages = split_to_ns(self.edited_view.chars, self.edited_view.per_page)
            if self.edited_view.page >= len(self.edited_view.pages):
                self.edited_view.page = len(self.edited_view.pages) - 1
            if self.edited_view.page <= 0:
                self.edited_view.page = 0
            self.edited_view.change_page()
            await self.i.message.edit(content=self.edited_view.get_str(), view=self.edited_view)

        with io.StringIO(bson_str) as string_buffer:
            await log(f'```{char_name}```', i, self.server.server['char_deletion_log'],
                      discord.File(string_buffer, filename=f'char.json'))

    @discord.ui.button(emoji='❌', style=discord.ButtonStyle.gray)
    async def no(self, i: discord.Interaction, _: discord.ui.Button):
        await i.message.delete()

    def get_str(self):
        return get_localized_answer('confirm_deletion', self.user.get_localization()).format(
            name=self.char.char['name'])


async def delete_char(i: discord.Interaction, u_id, edited_view=None):
    user = User(i.user.id, i.guild.id)
    char = Character(i.guild_id, u_id=bson.ObjectId(u_id))
    server = Server(i.guild_id)
    view = ConfirmDeletionView(i, user, char, server, edited_view)
    await i.response.send_message(content=view.get_str(), view=view)


class PDAMoveBTN(Button):
    def __init__(self, char: Character, direction: tuple, emoji='', row=0, label=''):
        super().__init__(style=ButtonStyle.grey, label=label, emoji=emoji, row=row)
        self.char = char
        self.direction = direction

    async def callback(self, interaction: Interaction):
        assert self.view is not None
        view: PDA = self.view
        match view.mode:
            case _:
                view.set_view_coord(view.x + int(round(self.direction[0] * 10 / view.zoom) * view.speed),
                                    view.y + int(round(self.direction[1] * 10 / view.zoom) * view.speed))
        coords = (view.x, view.y)
        usr_coords = self.char.char['coordinates']
        match view.mode:
            case 0:
                view.update_select()

        # self.user.change_coordinates(self.direction[0], self.direction[1])
        if self.direction == (0, 0):
            await interaction.response.defer()

            match view.mode:
                case _:
                    with BytesIO() as output:
                        mapp = Image.open('map.jpg')
                        draw = ImageDraw.Draw(mapp)
                        with open('arr.npy', 'rb') as f:
                            arr = numpy.load(f)  # NOQA
                        x, y = self.char.char['coordinates']
                        match view.mode:
                            case 0:
                                if self.view.selector.values:
                                    mx, my = read_map_value(bson.ObjectId(self.view.selector.values[0]), 'coordinates')
                                else:
                                    return
                            case 1:
                                mx, my = view.x, view.y
                        path = pyastar2d.astar_path(arr, (y, x), (my, mx))
                        draw.rectangle(((path[0][1] + 5, path[0][0] + 5), (path[0][1] - 5, path[0][0] - 5)),
                                       fill='red')
                        price = 0
                        for n, point in enumerate(path):
                            price += arr[point[0]][point[1]]
                            if not n + 1 >= len(path):
                                draw.line((point[1], point[0], path[n + 1][1], path[n + 1][0]), fill='red', width=3)
                        price = round(price)
                        max_x, max_y, min_x, min_y = 0, 0, mapp.size[1] + 1, mapp.size[1] + 1
                        for coord in path:
                            if max_x < coord[1]:
                                max_x = coord[1]
                            if min_x > coord[1]:
                                min_x = coord[1]
                            if max_y < coord[0]:
                                max_y = coord[0]
                            if min_y > coord[0]:
                                min_y = coord[0]

                        mapp = mapp.crop((min_x - 100, min_y - 100, max_x + 100, max_y + 100))
                        mapp.save(output, format="JPEG")
                        output.seek(0)
                        out_str = f'{str(datetime.timedelta(seconds=price))}\n{len(path)}м'
                        await interaction.followup.send(content=out_str,
                                                        file=discord.File(fp=output, filename='map.jpg'),
                                                        view=PathView(self.char, self.view, (int(mx), int(my)), price,
                                                                      len(path),
                                                                      interaction.message, interaction.user,
                                                                      out_str, path))

        else:
            with BytesIO() as output:
                get_loc_image(usr_coords, view.zoom, coords).save(output, format="JPEG")
                output.seek(0)
                await interaction.response.edit_message(attachments=[discord.File(fp=output, filename='map.jpg')],
                                                        view=view)


class ZoomBTN(Button):
    def __init__(self, char: Character, zoom=1, emoji='', row=0, label=''):
        super().__init__(style=ButtonStyle.secondary, emoji=emoji, row=row, label=label)
        self.char = char
        self.zoom = zoom

    async def callback(self, interaction: Interaction):
        assert self.view is not None
        view: PDA = self.view
        try:
            view.zoom = zoom_lst[zoom_lst.index(view.zoom) + self.zoom]
        except IndexError:
            pass

        with BytesIO() as output:
            get_loc_image(self.char.char['coordinates'], view.zoom, (view.x, view.y)).save(output, format="JPEG")
            output.seek(0)
            await interaction.response.edit_message(content=view.get_str(),
                                                    attachments=[discord.File(fp=output, filename='map.jpg')],
                                                    view=view)


class SpeedBTN(Button):
    def __init__(self, char: Character, speed=1, emoji='', row=0, label=''):
        super().__init__(style=ButtonStyle.secondary, emoji=emoji, row=row, label=label)
        self.char = char
        self.speed = speed

    async def callback(self, interaction: Interaction):
        assert self.view is not None
        view: PDA = self.view
        try:
            view.speed = speed_lst[speed_lst.index(view.speed) + self.speed]
        except IndexError:
            pass

        await interaction.response.edit_message(content=view.get_str(), view=view)


class LocationMoveSLC(Select):
    def __init__(self, char: Character, x, y):
        self.char = char
        opts = [SelectOption(label=x['name'], value=str(x['_id'])) for x in char.get_closest_coords(x, y)]
        super().__init__(options=opts, max_values=1)

    async def callback(self, interaction: Interaction):
        assert self.view is not None
        await interaction.response.edit_message(content=self.view.get_str())

    def update_options(self):
        self.options = [SelectOption(label=x['name'], value=str(x['_id'])) for x in self.char.get_closest_coords(
            self.view.x,
            self.view.y
        )]


class PDA(GenericView):
    def __init__(self, i, character, localization, gm=False, back_data=None):
        super().__init__(i)

        if not character or type(character) == bson.ObjectId:
            character = get_char(i, character)

        char = character
        self.zoom = 10
        self.x, self.y = char.char['coordinates']
        self.mode = 0
        self.speed = 10
        self.char = character
        self.add_item(ZoomBTN(char, 1, '<:zoomin:1067103004702023760>'))
        for x in range(-1, 2):
            self.add_item(PDAMoveBTN(char, (x, -1), dic.get((x, 1), '<:ok:1067084630899048509>')))
        self.add_item(ZoomBTN(char, -1, '<:zoomout:1067103001703100529>'))
        self.add_item(SpeedBTN(char, 1, '<:sp:1067169342829109318>', 1))
        for x in range(-1, 2):
            self.add_item(PDAMoveBTN(char, (x, 0), dic.get((x, 0), '<:ok:1067084630899048509>'), 1))
        self.add_item(SpeedBTN(char, -1, '<:sp:1067169339603697805>', 1))
        for x in range(-1, 2):
            self.add_item(PDAMoveBTN(char, (x, 1), dic.get((x, -1), '<:ok:1067084630899048509>'), 2))
        if back_data:
            self.add_item(GenericToViewBTN(MainMenuView, get_localized_answer('back_btn', localization), False,
                                           discord.ButtonStyle.blurple, back_data, 2))
        else:
            self.add_item(Button(label='‎', disabled=True, row=2))

        # @Rozvidka ✙#4439 я тут візуал підтягую і хтів спитати чи не замінити
        self.selector = LocationMoveSLC(char, self.x, self.y)
        self.add_item(self.selector)

    def set_view_coord(self, x, y):
        self.x, self.y = numpy.clip(x, 0, 5411), numpy.clip(y, 0, 4498)

    def get_str(self):
        st = f'Кратність: {self.zoom}x; Швидкість камери: {self.speed}; \nРежим: {modes[self.mode]}'
        if not self.mode:
            if self.selector.values:
                st += f"\nОбрано {read_map_value(bson.ObjectId(self.selector.values[0]), 'name')}"
        return st

    @discord.ui.select(options=[SelectOption(label='Оптимальний маршрут до точки зі списку', value=str(0)),
                                SelectOption(label='Оптимальний маршрут до точки', value=str(1))], row=4,
                       placeholder='Обрати режим КПК')
    async def mode_selector(self, i: Interaction, select):
        match int(select.values[0]):
            case 0:
                self.update_select()
                self.mode = 0
            case 1:
                self.remove_item(self.selector)
                self.mode = 1
        await i.response.edit_message(content=self.get_str(), view=self)

    @discord.ui.button(emoji='<:center:1067101518316175400>', row=2)
    async def center_btn(self, i: Interaction, button):
        self.x, self.y = self.char.char['coordinates']
        self.zoom = 10
        with BytesIO() as output:
            get_loc_image((self.x, self.y), self.zoom).save(output, format="JPEG")
            output.seek(0)
            await i.response.edit_message(content=self.get_str(), view=self,
                                          attachments=[discord.File(fp=output, filename='map.jpg')])

    def update_select(self):
        self.remove_item(self.selector)
        self.selector.update_options()
        self.add_item(self.selector)

    def get_image(self):
        with BytesIO() as output:
            get_loc_image((self.x, self.y), self.zoom).save(output, format="JPEG")
            output.seek(0)
            return [discord.File(fp=output, filename='map.jpg')]


class PathView(View):
    def __init__(self, char: Character, view: PDA, new_coords: tuple, price: int, distance: int,
                 orig_message: discord.Message,
                 author: discord.User, st: str, all_coords: numpy.ndarray):
        super().__init__()
        self.char = char
        self.view = view
        self.new_coords = new_coords
        self.price = price
        self.message = orig_message
        self.author = author
        self.distance = distance
        self.st = st
        self.all_coords = all_coords

    async def interaction_check(self, interaction: Interaction, /) -> bool:
        resp = interaction.user.id == self.author.id
        if not resp:
            await interaction.response.send_message(content='Це не ваше меню!', ephemeral=True)
        return resp

    @discord.ui.button(label='Піти по шляху', row=1)
    async def move(self, i: Interaction, button):
        self.char.update_char()
        x, y = self.new_coords
        food, water = self.char.road_prov(self.price)
        response = ''
        if water <= -24:
            response += 'Спрага занадто сильна, якщо нічого не вдіяти то життя покине вас.\n'
        if food <= -12:
            response += "Голод невимовний. Вбити, звісно, не вб'є але варто щось з'їсти бо так і загнутись можна.\n"
        event = ''
        ch_mob = self.char.roll_dice('mobility')[1] >= 4
        ch_tac = self.char.roll_dice('tactics')[1] >= 4
        ch_ste = self.char.roll_dice('camouflage')[1] >= 4

        if sum((ch_mob, ch_tac, ch_ste)) <= 1:
            ev = fails.get((ch_mob, ch_tac, ch_ste))
            event += f'{random.choice(ev[0])}\n**{ev[1]}**'
            x, y = self.all_coords[int(len(self.all_coords) / 2)]
            x, y = int(y), int(x)
        else:
            ev = succes.get((ch_mob, ch_tac, ch_ste))
            event += f'{random.choice(ev[0])}\n**{ev[1]}**'

        self.char.update('coordinates', (x, y))
        self.char.update('meters', self.distance + self.char.char['meters'])
        self.view.set_view_coord(x, y)
        match self.view.mode:
            case 0:
                self.view.update_select()

        await i.response.edit_message(content=f'{self.st}\n{response}Баланс їжі/води {food}/{water}\n\n{event}',
                                      view=None)
        with BytesIO() as output:
            get_loc_image(self.char.read()['coordinates'], self.view.zoom,
                          (self.view.x, self.view.y)).save(output,
                                                           format="JPEG")
            output.seek(0)
            await self.message.edit(attachments=[discord.File(fp=output, filename='map.jpg')], view=self.view)

    @discord.ui.button(emoji='❌', row=1)
    async def close(self, i: Interaction, button):
        await i.message.delete()


async def pda(i: discord.Interaction, name: str, gm=False):
    user_locale = User(i.user.id, i.guild_id).get_localization()
    if gm:
        char = get_char(i, name, False, True)
    else:
        char = get_char(i, name)
    with BytesIO() as output:
        get_loc_image(char.char['coordinates'], 10).save(output, format="JPEG")
        output.seek(0)
        pd = PDA(i, char, user_locale)
        await i.response.send_message(content=pd.get_str(), files=pd.get_image(),
                                      view=pd)


async def health(i: discord.Interaction, name: str, gm=False):
    user_locale = User(i.user.id, i.guild_id).get_localization()
    if gm:
        char = get_char(i, name, False, True)
    else:
        char = get_char(i, name)
    with BytesIO() as output:
        get_hp_image(char.char['hp']).save(output, format='JPEG')
        output.seek(0)

        await i.response.send_message(content='todo',
                                      file=discord.File(output, filename='health.jpg'),
                                      view=HealthView(i, char, user_locale, gm))


class ChangeHpBTN(Button):
    def __init__(self, localization, mode: int):
        self.mode = mode
        label = get_localized_answer('change', localization) if mode == 0 else get_localized_answer('set', localization)
        super().__init__(label=label)

    async def callback(self, interaction: Interaction):
        await interaction.response.send_modal(ChangeHpModal(interaction.message, self.view, self.mode))


class HealthView(GenericView):
    def __init__(self, i, character, localization, gm=False, back_data=None):
        super().__init__(i)
        self.select = HealthSelect(localization)
        self.back_btn = None
        self.localization = localization
        self.heal_select = None
        self.translation_data = localized_data.find_one({'request': 'body_parts'})['local']
        if not character or type(character) == bson.ObjectId:
            character = get_char(i, character)
        self.gm = gm
        self.change_hp_btn = ChangeHpBTN(localization, 0)
        self.set_hp_btn = ChangeHpBTN(localization, 1)
        self.character = character
        self.back_data = back_data
        if self.back_data:
            self.back_btn = GenericToViewBTN(MainMenuView, get_localized_answer('back_btn', localization), False,
                                             discord.ButtonStyle.blurple, [*back_data], row=3)
        self.rebuild()

    def replace_select_placeholder(self, placeholder):
        self.select.replace_placeholder(placeholder)
        self.rebuild()

    def rebuild(self):
        self.clear_items()
        self.add_item(self.select)
        if self.select.values:
            self.heal_select = HealSelect(self.localization, self.character, self.select.values[0])
            self.add_item(self.heal_select)
            if self.gm:
                self.add_item(self.change_hp_btn)
                self.add_item(self.set_hp_btn)
        if self.back_btn:
            self.add_item(self.back_btn)

    def get_image(self):
        with io.BytesIO() as buffer:
            get_hp_image(self.character.char['hp']).save(buffer, format='JPEG')
            buffer.seek(0)
            return [discord.File(buffer, filename='health.jpeg')]

    def get_str(self):
        ret_str = ''
        for body_part in HEALTH_DEBUFFS.keys():
            hp = self.character.char['hp'][body_part]
            ret_str += f"{get_item_from_translation_dict(self.translation_data, self.localization, body_part)}: [{hp[0]}/{hp[1]}]\n"
        return ret_str


class ChangeHpModal(Modal):
    def __init__(self, message: discord.Message, view: HealthView, mode):
        super().__init__(title='Меню')
        self.message = message
        self.view = view
        self.mode = mode
        self.text_input = TextInput(label='Введіть число', default='1')  # todo localize
        self.add_item(self.text_input)

    async def on_submit(self, i: discord.Interaction):
        num = int(str(self.text_input))
        match self.mode:
            case 0:
                self.view.character.change_hp(self.view.select.values[0], num)
            case _:
                self.view.character.set_hp(self.view.select.values[0], num)
        self.view.rebuild()
        await i.response.edit_message(content=self.view.get_str(), view=self.view, attachments=self.view.get_image())


class PlateCarrierView(GenericView):
    def __init__(self, i, character, item, idx, localization, gm=False, back_data=None):
        super().__init__(i)
        self.back_btn = None
        self.select = HealthSelect(localization)
        self.localization = localization
        self.item = item
        self.body_part_data = localized_data.find_one({'request': 'body_parts'})['local']
        self.translation_data = localized_data.find_one({'request': 'plate_carrier'})['local']
        if not character or type(character) == bson.ObjectId:
            character = get_char(i, character)
        self.gm = gm
        self.idx = idx
        self.character = character
        self.back_data = back_data
        if self.back_data:
            self.back_btn = GenericToViewBTN(InventoryView, get_localized_answer('back_btn', localization), False,
                                             discord.ButtonStyle.blurple, [*back_data], row=4)
        self.rebuild()

    def rebuild(self):
        self.clear_items()
        self.add_item(self.select)
        if self.select.values:
            self.add_item(SelectPlate(self.character, self.item, self.idx, self.select.values[0], self.localization,
                                      self.translation_data))
        # self.regenerate_pages() # todo add this
        if self.back_btn:
            self.add_item(self.back_btn)

    def get_str(self):
        equipped, _ = self.character.read_equipped()
        equipped = equipped['equipped']
        if equipped[self.idx]['_id'] == self.item['_id']:
            item = equipped[self.idx]
            plates = item.get('plates', {})
            ret_str = f'{get_item_from_translation_dict(item["localization"], self.localization, "name")}\n'
            for body_part in PLATE_CARRIER_ZONES.keys():
                ret_str += f'{get_item_from_translation_dict(self.body_part_data, self.localization, body_part)}: {plates.get(body_part, {}).get("plate_class", 0)}\n'
            return ret_str
        else:
            return 'error'

    def replace_select_placeholder(self, placeholder):
        self.select.replace_placeholder(placeholder)
        self.rebuild()


class ProfessionsView(GenericView):
    def __init__(self, i, character: Character, localization, back_data=None):
        super().__init__(i)
        self.back_btn = None
        self.select = HealthSelect(localization)
        self.localization = localization
        self.character = character
        self.back_data = back_data
        self.max_on_page = 10
        self.pages = split_to_ns(character.get_available_professions(), self.max_on_page)
        self.select = ProfSelectAdd(self.character, self.pages[self.page], self.localization)
        self.stats_data = localized_data.find_one({'request': 'stats_and_skills'})['local']
        self.localization_dict = localized_data.find_one({'request': 'stats_view_data'})['local']
        if self.back_data:
            self.back_btn = GenericToViewBTN(StatsView, get_localized_answer('back_btn', localization), False,
                                             discord.ButtonStyle.blurple, [*back_data], row=4)
        self.rebuild()

    def rebuild(self):
        self.clear_items()
        self.add_item(self.select)
        self.regenerate_pages()
        if self.back_btn:
            self.add_item(self.back_btn)

    def get_str(self):
        prof_str = ''
        for prof in self.pages[self.page]:
            prof_dict = prof['localization']
            prof_str += f'{get_item_from_translation_dict(prof_dict, self.localization, "name")}: '
            for buff in prof.get('actions_when_equipped', []):
                if buff['action'] == 'buff_or_debuff':
                    prof_str += f'{get_item_from_translation_dict(self.stats_data, self.localization, buff["what_to_buff"])}'
                    prof_str += f' +{abs(buff["num"])}, ' if buff["num"] >= 0 else f' -{abs(buff["num"])}, '
            prof_str = prof_str[:-2] + '\n'
        return prof_str

    def change_page(self):
        self.select.options = self.select.get_options(self.pages[self.page], self.localization)
        self.rebuild()
        return self.get_str()


class ProfSelectRemove(Select):
    def __init__(self, character: Character, prof_list, localization, row, localization_dict):
        self.character = character
        super().__init__(options=ProfSelectAdd.get_options(prof_list, localization), row=row, placeholder=get_item_from_translation_dict(localization_dict, localization, 'remove_prof'))

    async def callback(self, interaction: Interaction):
        self.view.character.rem_prof(bson.ObjectId(self.values[0]))
        self.view.replace_select_placeholder(None)
        await interaction.response.edit_message(content=self.view.get_str(), view=self.view)


class ProfSelectAdd(Select):
    def __init__(self, character: Character, prof_list, localization):
        self.character = character
        super().__init__(options=ProfSelectAdd.get_options(prof_list, localization))

    async def callback(self, interaction: Interaction):
        self.character.add_prof(bson.ObjectId(self.values[0]))
        view = StatsView(*self.view.back_data)
        await interaction.response.edit_message(content=view.get_str(), view=view)

    @staticmethod
    def get_options(prof_list, localization):
        return [SelectOption(label=get_item_from_translation_dict(prof['localization'], localization, 'name'),
                             value=str(prof['_id'])) for prof in prof_list]


class SelectPlate(Select):
    def __init__(self, character, item, idx, body_part, localization, translation_data):
        self.character, self.item, self.idx, self.body_part, self.localization, self.translation_data = character, item, idx, body_part, localization, translation_data
        super().__init__(options=SelectPlate.get_options(character, item, body_part, localization, translation_data),
                         placeholder=get_item_from_translation_dict(translation_data, localization,
                                                                    'plate_placeholder'))

    async def callback(self, interaction: Interaction):
        if self.values[0] == 'none':
            await interaction.response.edit_message(content=self.view.get_str(), view=self.view)
            self.view.character.update_char()
            self.view.rebuild()
            return
        if self.values[0] == 'remove':
            self.view.character.add_item(self.item['plates'][self.body_part]['_id'])
            characters.update_one({'_id': self.view.character.char['_id']},
                                  {'$unset': {f'equipped.{self.idx}.plates.{self.body_part}': 1}})
            self.view.character.update_char()
            equipped, _ = self.view.character.read_equipped()
            equipped = equipped['equipped']
            self.view.item = equipped[self.idx]
            self.view.rebuild()
            await interaction.response.edit_message(content=self.view.get_str(), view=self.view)
            return

        self.view.character.insert_plate_at_idx(self.idx, self.item['_id'], self.body_part,
                                                bson.ObjectId(self.values[0]))
        self.view.character.update_char()
        equipped, _ = self.view.character.read_equipped()
        equipped = equipped['equipped']
        self.view.item = equipped[self.idx]
        self.view.rebuild()
        await interaction.response.edit_message(content=self.view.get_str(), view=self.view)

    @staticmethod
    def get_options(character: Character, selected_item, body_part, localization, translation_data):
        options = []
        inventory, _, _, _ = character.read_inv()
        inventory = inventory['inventory']
        for item in inventory:
            if item['type'] == 'armor_plate' and selected_item.get(PLATE_CARRIER_ZONES.get(body_part)) == item.get(
                    'plate_type'):
                options.append(
                    SelectOption(label=get_item_from_translation_dict(item['localization'], localization, 'name'),
                                 value=str(item['_id'])))
        if not options:
            options.append(
                SelectOption(label=get_item_from_translation_dict(translation_data, localization, 'none_plate'),
                             value='none'))
        if selected_item.get('plates', {}).get(body_part):
            options.append(
                SelectOption(label=get_item_from_translation_dict(translation_data, localization, 'remove_plate'),
                             value='remove'))
        return options


def get_available_medicine(character, body_part):
    list_of_medicine = []
    for n, item in enumerate(character.read_inv()[0]['inventory']):
        if item['type'] == 'medicine':
            if floor := item.get('health_floor'):
                match floor:
                    case 'red':
                        if character.char['hp'][body_part][0] / character.char['hp'][body_part][1] <= 0.2:
                            continue
                    case 'yellow':
                        if character.char['hp'][body_part][0] / character.char['hp'][body_part][1] <= 0.4:
                            continue
                    case 'green':
                        if character.char['hp'][body_part][0] / character.char['hp'][body_part][1] <= 0.7:
                            continue

            list_of_medicine.append((item, n))
    return list_of_medicine


class HealSelect(Select):
    def __init__(self, localization, character, body_part):
        super().__init__(options=self.get_options(localization, character, body_part))
        # Якщо ліків буде > 25 воно поламається # todo пофіксь це бо інакше забудеш, мде.

    async def callback(self, interaction: Interaction):
        if self.values[0] == 'none':
            await interaction.response.edit_message(view=self.view)
        else:
            await interaction.response.send_modal(HealModal(interaction.message, self.view))

    @staticmethod
    def get_options(localization, character, body_part):
        opts = [SelectOption(
            label=f"{item['quantity']}шт. {get_item_from_translation_dict(item['localization'], localization, 'name')} ({item['max_healing_potential'] - item.get('healing', 0)}/{item['max_healing_potential']})",
            value=f"{item['_id']}|{idx}") for item, idx in get_available_medicine(character, body_part)][:25]
        if not opts:
            opts.append(SelectOption(label='...', value='none'))
        return opts


class HealModal(Modal):
    def __init__(self, message, view: HealthView):
        super().__init__(title='Меню лікування')
        self.message = message
        self.view = view
        self.text_input = TextInput(label='Скільки очків аптечки ви хочете витратити?', default='1')
        self.add_item(self.text_input)

    async def on_submit(self, i: discord.Interaction):
        current_hp, max_hp = self.view.character.char['hp'][self.view.select.values[0]]
        u_id, idx = self.view.heal_select.values[0].split('|')
        idx = int(idx)
        u_id = bson.ObjectId(u_id)
        inventory, _, _, _ = self.view.character.read_inv()
        item = inventory['inventory'][idx]
        if item['_id'] != u_id:
            return  # todo add error
        cap = item['max_healing_potential'] - item.get('healing', 0)
        to_heal = int(str(self.text_input))
        to_heal = int(numpy.clip(to_heal, 1, cap))
        remove_heal = False
        if to_heal + item.get('healing', 0) == item['max_healing_potential']:
            remove_heal = True

        self.view.character.remove_item_by_idx(item, idx)
        if not remove_heal:
            self.view.character.add_item(u_id, 1, to_heal + item.get('healing', 0))
        roll_str, bonus = self.view.character.roll_dice('medicine')
        self.view.character.update(self.view.select.values[0],
                                   (int(numpy.clip(current_hp + bonus + to_heal, 0, max_hp)), max_hp))
        await i.response.send_message(
            content=f"{bonus + to_heal} = "
                    f"{roll_str.split('=')[1]}+{to_heal} "
                    f"[{get_item_from_translation_dict(item['localization'], self.view.localization, 'name')}]")
        self.view.character.update_char()
        self.view.rebuild()
        await self.message.edit(content=self.view.get_str(), attachments=self.view.get_image(), view=self.view)


class HealthSelect(Select):
    def __init__(self, localization):
        data = localized_data.find_one({'request': 'body_parts'})['local']
        self.data = data
        self.localization = localization
        super().__init__(
            options=[SelectOption(label=get_item_from_translation_dict(data, localization, x), value=x) for x in
                     HEALTH_DEBUFFS.keys()],
            placeholder=get_item_from_translation_dict(data, localization, 'body_part_placeholder'))

    async def callback(self, i: discord.Interaction):
        self.view.replace_select_placeholder(
            get_item_from_translation_dict(self.data, self.localization, self.values[0]))
        await i.response.edit_message(content=self.view.get_str(), view=self.view)

    def replace_placeholder(self, placeholder):
        self.placeholder = placeholder


class ShootView(GenericView):
    def __init__(self, i, character, gun, back_data=None):
        super().__init__(i)
        self.localization = User(i.user.id, i.guild_id).get_localization()
        self.character = character
        self.gun = gun
        self.pages = SHOOT_OPTIONS
        self.translation_data = localized_data.find_one({'request': "shooting_view_data"})['local']
        self.select = ShootSelect(*self.pages[self.page], self.translation_data, self.localization)
        self.shoot_dict = {}
        self.shoot_btn = ShootBTN(self.translation_data, self.localization)
        self.shooting = False
        self.back_data = back_data
        if self.back_data:
            self.back_btn = GenericToViewBTN(InventoryView, get_localized_answer('back_btn', self.localization), False,
                                             discord.ButtonStyle.blurple, [*back_data], row=4)

        self.rebuild()

    def reset(self):
        self.page = 0
        self.shooting = False
        self.character.update_char()
        self.select = ShootSelect(*self.pages[self.page], self.translation_data, self.localization)
        self.shoot_dict = {}
        self.shoot_btn = ShootBTN(self.translation_data, self.localization)
        self.rebuild()

    def rebuild(self):
        self.clear_items()
        self.add_item(self.select)
        shoot_dict = self.shoot_dict
        if len(shoot_dict.keys()) == 4 and not self.shooting:
            self.add_item(self.shoot_btn)
        self.regenerate_pages()
        if self.back_data:
            self.add_item(self.back_btn)

    def get_str(self):
        ret_str = ''
        for x in range(0, 4):
            ret_str += f"**{get_item_from_translation_dict(self.translation_data, self.localization, str(x))}**\n"
            for selected in self.shoot_dict.get(x, []):
                ret_str += f"{get_item_from_translation_dict(self.translation_data, self.localization, selected.split('|')[0])} \n"

        ret_str += f"\n{self.page + 1}/{len(self.pages)}"
        return ret_str

    def change_page(self):
        self.select.placeholder = get_item_from_translation_dict(self.translation_data, self.localization,
                                                                 str(self.page))
        self.select.replace_options()
        self.rebuild()
        return self.get_str()


class ShootBTN(Button):
    def __init__(self, translation_data, localization):
        self.translation_data = translation_data
        self.localization = localization
        super().__init__(label=get_item_from_translation_dict(translation_data, localization, 'shoot'))

    async def callback(self, interaction: Interaction):
        ammo_to_parse = self.view.shoot_dict[3][0]
        ammo_to_parse = ammo_to_parse.split('|')[-1]
        if ammo_to_parse.count(','):
            ammo_to_parse = ammo_to_parse.replace('(', '')
            ammo_to_parse = ammo_to_parse.replace(')', '')
            ammo_to_parse = ammo_to_parse.split(',')
            ammo_to_parse = random.randint(int(ammo_to_parse[0]), int(ammo_to_parse[1]))
        else:
            ammo_to_parse = int(ammo_to_parse)
        self.view.select = AmmoSelect(self.view.character, self.translation_data, self.view.localization, self.view.gun,
                                      ammo_to_parse)
        self.view.shooting = True
        self.view.rebuild()
        await interaction.response.edit_message(view=self.view)


class AmmoSelect(Select):
    def __init__(self, character: Character, translation_data, localization, gun, used_ammo: int):
        self.gun = gun
        self.used_ammo = used_ammo
        self.localization = localization
        self.character = character
        super().__init__(options=self.get_options(character, localization, gun, used_ammo), max_values=1,
                         placeholder=get_item_from_translation_dict(translation_data, self.localization, 'select_ammo'))

    @staticmethod
    def get_options(character, localization, gun, used_ammo):
        options = []
        inventory, _, _, _ = character.read_inv()
        inventory = inventory['inventory']
        for item in inventory:
            if item['quantity'] >= used_ammo and item.get('ammo_type') == gun['ammo_type']:
                options.append(
                    SelectOption(label=get_item_from_translation_dict(item['localization'], localization, 'name'),
                                 value=str(item['_id'])))
        return options

    async def callback(self, interaction: Interaction):
        await interaction.response.send_modal(
            ShootModal(
                self.character,
                self.gun,
                items.find_one({'_id': bson.ObjectId(self.values[0])}),
                self.used_ammo,
                interaction.message,
                self.view,
            )
        )


class ShootModal(Modal):
    def __init__(self, character: Character, gun, ammo, used_ammo: int, message, view: ShootView):
        self.character = character
        self.gun = gun
        self.ammo = ammo
        self.used_ammo = used_ammo
        self.message = message
        self.view = view
        super().__init__(
            title=get_item_from_translation_dict(view.translation_data, view.localization, 'modal_title')
        )
        self.num = TextInput(
            label=get_item_from_translation_dict(view.translation_data, view.localization, 'modal_input')
        )
        self.add_item(self.num)

    async def on_submit(self, interaction: Interaction) -> None:
        str_roll = ''
        missed_shots = 0
        buff_and_debuff_number = 0
        for buff_or_debuff_lst in self.view.shoot_dict.values():
            for buff_or_debuff in buff_or_debuff_lst:
                buff_and_debuff_number += int(buff_or_debuff.split('|')[1])
        for x in range(0, self.used_ammo):
            temp_roll = ''
            dice_str, roll = self.character.roll_dice(self.gun['stat'])
            roll += buff_and_debuff_number
            temp_roll += f'{roll} = {buff_and_debuff_number}+[{dice_str}]'
            if roll >= int(str(self.num)):
                temp_roll += f' > {self.num} '
                damage_num = 0
                for a in range(self.ammo['damage'][0]):
                    damage_num += random.randint(1, self.ammo['damage'][0] + 1) + self.ammo['damage'][2]
                pen_str = ''
                pen = self.ammo['armor_penetration']
                pened_last = True
                if pen[0]:
                    pen_str += f'Гарантовано пробиває {pen[0]} клас. '
                if pen[1]:
                    chosen = random.choice([(f'Не пробиває {pen[1]} клас. ', 0), (f'Пробиває {pen[1]} клас. ', 1)])
                    pen_str += chosen[0]
                    pened_last = chosen[1]
                if pen[2]:
                    if pened_last:
                        pen_str += random.choice([f'Не пробиває {pen[2]} клас. ',
                                                  f'Не пробиває {pen[2]} клас. ',
                                                  f'Не пробиває {pen[2]} клас. ',
                                                  f'Пробиває {pen[2]} клас. '])
                if not pen_str:
                    'Нічого не пробиває.'
                temp_roll += f'Попали! Пошкодження {damage_num}, {pen_str}'
                str_roll += temp_roll
                str_roll += '\n'
            else:
                missed_shots += 1

        str_roll += f"Мимо цілі полетіло {missed_shots} пострілів"
        chunks = chunker(str_roll)
        self.character.remove_item_by_id(self.ammo['_id'], self.used_ammo)

        sent = False
        for chunk in chunks:
            if not sent:
                await interaction.response.send_message(content=chunk)
                sent = True
            else:
                await interaction.followup.send(content=chunk)
        self.view.reset()
        await self.message.edit(content=self.view.get_str(), view=self.view)


class ShootSelect(Select):
    def __init__(self, multi_choice: bool, choices: list, translation_data, localization):
        if multi_choice:
            max_choices = len(choices)
        else:
            max_choices = 1
        super().__init__(options=self.get_options(choices, translation_data, localization), max_values=max_choices,
                         placeholder=get_item_from_translation_dict(translation_data, localization, '0'))

    @staticmethod
    def get_options(choices, translation_data, localization):
        list_of_options = []
        for choice in choices:
            value_str = ''
            for value in choice:
                value_str += f'{value}|'
            value_str = value_str[:-1]
            list_of_options.append(
                SelectOption(label=get_item_from_translation_dict(translation_data, localization, choice[0]),
                             value=value_str))
        return list_of_options

    def replace_options(self):
        choices = self.view.pages[self.view.page]
        self.options = self.get_options(choices[1], self.view.translation_data, self.view.localization)
        if choices[0]:
            self.max_values = len(choices[1])
        else:
            self.max_values = 1

    async def callback(self, interaction: Interaction):
        self.view.shoot_dict[self.view.page] = self.values
        self.view.rebuild()
        await interaction.response.edit_message(content=self.view.get_str(), view=self.view)


def read_map_value(m_id: bson.ObjectId, value: str):
    return map_collection.find_one({'_id': m_id})[value]


class ItemDescriptionView(GenericView):
    def __init__(self):
        super().__init__()
