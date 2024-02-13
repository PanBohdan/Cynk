try:
    from secret_files import *
except ImportError:
    pass
import os
import discord
from discord.app_commands import Translator
from discord.ext.commands import Bot
from cogs.admin import Admin
from cogs.chars import Chars, chars
from cogs.gm import GM
from cogs.items import Item
from cogs.cynk import Cynk
from db import localized_commands

#from re import match
intent = discord.Intents.all()

# Main settings
TOKEN = os.environ.get('TOKEN')
prefix = '.'

# Cogs setup
cogs_dir = 'cogs'
dict_of_cog_names_and_classes = {'cynk': Cynk,
                                 'gm': GM,
                                 'admin': Admin,
                                 'chars': Chars,
                                 'items': Item
                                 }
list_of_full_cog_path = [f"{cogs_dir}.{cog}" for cog in dict_of_cog_names_and_classes.keys()]

# Bot setup
client = Bot(prefix, intents=intent, application_id=int(os.environ.get('APP_ID')))
client.synced = False


class Translation(Translator):
    def __init__(self):
        super().__init__()
        self.command = {}
        for locale in localized_commands.find():
            self.command[locale['command']] = locale['local']

    async def translate(self, locale_str, locale, context):
        if localized := self.command.get(str(locale_str), None):
            if localized_fin := localized.get(str(locale), None):
                return localized_fin
            elif localized_fin := localized.get('default', None):
                return localized_fin
        return None


@client.event
async def on_ready():
    await client.tree.set_translator(Translation())
    for cog in list_of_full_cog_path:
        try:
            await client.load_extension(cog)
        except discord.ext.commands.ExtensionAlreadyLoaded:
            await client.reload_extension(cog)
    if not client.synced:
        await client.tree.sync()
        client.synced = True
    await client.change_presence(status=discord.Status.online, activity=discord.Game('/цинк'))

    await client.wait_until_ready()
    print(f'Logged in as: {client.user.name}')
    print(f'With ID: {client.user.id}')
    print(f'Loaded cogs: {list(dict_of_cog_names_and_classes.keys())}')


@client.tree.context_menu(name='Get Chars')
async def get_user_chars(i: discord.Interaction, message: discord.Message):
    await chars(i, message.author.id, True, False, True)


@client.tree.context_menu(name='Get Chars')
async def get_message_chars(i: discord.Interaction, user: discord.User):
    await chars(i, user.id, True, False, True)

if __name__ == '__main__':
    client.run(TOKEN)
