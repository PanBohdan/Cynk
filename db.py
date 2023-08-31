
try:
    from secret import *
except ImportError:
    pass
import os

from pymongo import MongoClient

m_client = MongoClient(os.environ.get('DB'))
db = m_client['cynk_db']
users = db['users']
characters = db['chars']
servers = db['servers']
locations = db['locations']
events = db['events']
items = db['items']
map_collection = db['map']
roles = db['roles']
localized_data = db['localized_data']
localized_text = db['localized_text']

languages = db['languages']
localized_commands = db['localized_commands']


def get_localized_answer(request, locale):
    localized = localized_text.find_one({'request': request})
    if localized:
        return localized['local'].get(locale, localized['local']['default'])


def get_item_from_translation_dict(translation_dict, localization, data_to_get):
    return translation_dict.get(localization, translation_dict['default']) \
        .get(data_to_get, translation_dict['default']
             .get(data_to_get, data_to_get))
