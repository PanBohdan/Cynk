import os

from discord import Interaction
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands

from db import languages
from db_clases import User, Character
from misc import set_locale_autocomplete, get_localized_answer, player_chars_autocomplete, stats_autocomplete, \
    stat_and_skill_autocomplete, roll_stat, lvl_up, \
    say
from views import chars, trade


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

    @roll.error
    @lvl_up.error
    @chars.error
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

    @app_commands.command(description='roll_dice_description')
    async def roll_dice(self, i: Interaction, num: int, sides: int, buff_or_debuff: int = 0, crits: bool = False):
        if sides < 2 or num < 1:
            await i.response.send_message(content=get_localized_answer('roll_dice_bad_sides', User(i.user.id, i.guild.id).get_localization()), ephemeral=True)
            return

        ret_str = ''
        final_sum = 0
        if buff_or_debuff > 0:
            ret_str += f' + {buff_or_debuff}'
        elif buff_or_debuff < 0:
            ret_str += f' - {abs(buff_or_debuff)}'

        final_sum += buff_or_debuff

        for _ in range(num):
            dice_sum = 0
            dice_str = '['
            for sign, rolled_number in Character.roll(1, sides, crits):
                dice_str += f'{sign}{abs(rolled_number)}'
                dice_sum += rolled_number
            dice_str += ']'
            if dice_sum >= 0:
                ret_str += f' + {dice_sum}' + dice_str
            else:
                ret_str += f' - {abs(dice_sum)}' + dice_str
            final_sum += dice_sum
        # remove ret_str first two symbols
        ret_str = ret_str[2:]
        ret_str = f'Результат: {final_sum} = {ret_str}'
        await i.response.send_message(content=ret_str)


async def setup(client):
    await client.add_cog(Cynk(client))
