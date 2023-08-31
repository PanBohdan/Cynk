import discord
from db import localized_data
from db_clases import User
from static import SKILLS, STATS


def check_for_stat_or_skill(interaction: discord.Interaction) -> bool:
    user_locale = User(interaction.user.id, interaction.guild_id).get_localization()
    localized_dict = localized_data.find_one({'request': 'stats_and_skills'})
    list_of_values = [
        localized_dict['local'].get(
            user_locale, localized_dict['local']['default']
        ).get(
            x, localized_dict['local']['default'].get(x, x)
        ) for x in list(SKILLS.keys()) + list(STATS.keys())
    ]
    option_dict = {
        data['name']: data['value'] for data in interaction.data['options'][0]['options']
    }
    return option_dict.get('stat', option_dict['what_to_set']) in list_of_values
