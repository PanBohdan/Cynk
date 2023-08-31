import asyncio
import datetime
import io
import random
import math

import bson
import discord.ext.commands
from discord import app_commands, Interaction
from discord.ext import commands
from discord.ui import View, Button

import db
from db import get_localized_answer, characters, map_collection
from db_clases import User, Server
from misc import chunker


class Admin(commands.GroupCog, name="admin"):
    def __init__(self, client):
        self.client: discord.Client = client
        super().__init__()

    @app_commands.command(description='set_manual_url_description')
    async def set_manual_url(self, i: Interaction, url: str):
        user = User(i.user.id, i.guild.id)
        Server(i.guild.id).set_manual_url(url)
        await i.response.send_message(content=get_localized_answer('set_manual_url', user.get_localization()))

    @app_commands.command(description='votum_description')
    async def votum(self, i: Interaction, text: str, ping: bool, seconds: int, excluded_user: discord.User = None, minutes: int = 0, hours: int = 0, days: int = 0):
        await i.response.defer()
        if excluded_user:
            excluded_user = excluded_user.id
        v = VotumView(text,
                      datetime.timedelta(seconds=seconds, minutes=minutes, hours=hours, days=days).total_seconds(),
                      i.user.id, i.guild.id, self.client, ping, excluded_user)
        await i.followup.send(content=v.get_str(), view=v)

    @app_commands.command(description='set_webhook_url_description')
    async def set_webhook_url(self, i: Interaction, url: str):
        user = User(i.user.id, i.guild.id)
        Server(i.guild.id).set_webhook_url(url)
        await i.response.send_message(content=get_localized_answer('generic_good_answer', user.get_localization()))

    @app_commands.command(description='set_char_say_log_description')
    async def set_char_say_log(self, i: Interaction, channel: discord.TextChannel):
        user = User(i.user.id, i.guild.id)
        Server(i.guild.id).set_char_say_log(channel.id)
        await i.response.send_message(content=get_localized_answer('generic_good_answer', user.get_localization()))

    @app_commands.command(description='set_char_change_log_description')
    async def set_char_change_log(self, i: Interaction, channel: discord.TextChannel):
        user = User(i.user.id, i.guild.id)
        Server(i.guild.id).set_char_change_log(channel.id)
        await i.response.send_message(content=get_localized_answer('generic_good_answer', user.get_localization()))

    @app_commands.command(description='set_char_deletion_log_description')
    async def set_char_deletion_log(self, i: Interaction, channel: discord.TextChannel):
        user = User(i.user.id, i.guild.id)
        Server(i.guild.id).set_char_deletion_log(channel.id)
        await i.response.send_message(content=get_localized_answer('generic_good_answer', user.get_localization()))

    @app_commands.command(description='top10_description')
    async def top10(self, i: Interaction):
        ret_str = ''
        for n, char in enumerate(characters.aggregate(
                [{'$sort': {'mastery': -1}}, {'$limit': 10}])):
            ret_str += f"{n + 1}) {char['name']} {char['mastery']}\n"
        await i.response.send_message(content=ret_str)

    @app_commands.command()
    async def fixer(self, i: Interaction):
        map_collection.update_many({}, {'$set': {'map_uid': bson.ObjectId('64d21f30f5e681a0db294bd4')}})

class VoteButton(Button):
    def __init__(self, label, style, vote_yes, emoji=''):
        super().__init__(style=style, label=label, emoji=emoji)
        self.vote_yes = vote_yes

    async def callback(self, interaction: Interaction):
        user = User(interaction.user.id, interaction.guild.id)
        localization = user.get_localization()
        if interaction.user.id == self.view.excluded_user_id:
            await interaction.response.send_message(content=get_localized_answer('voting_for_yourself_error', localization),
                                                    ephemeral=True)
        elif interaction.user.id in self.view.voters:
            await interaction.response.send_message(content=get_localized_answer('vote_error', localization),
                                                    ephemeral=True)
        else:
            if self.vote_yes:
                self.view.votes_yes += 1
            else:
                self.view.votes_no += 1
            self.view.voters.append(interaction.user.id)
            await interaction.response.edit_message(content=self.view.get_str())
            await interaction.followup.send(content=get_localized_answer('vote_counted', localization),
                                            ephemeral=True)


class StartTimeButton(Button):
    def __init__(self, label, style):
        super().__init__(style=style, label=label)

    async def callback(self, interaction: Interaction):
        self.view.remove_item(self)
        await interaction.response.edit_message(view=self.view)
        await self.view.closer(interaction.channel_id, interaction.message.id)


class VotumView(View):
    def __init__(self, text, timer, user_id, server_id, client: discord.Client, ping, excluded_user_id=None):
        super().__init__(timeout=None)
        self.user = User(user_id, server_id)
        self.excluded_user_id = excluded_user_id
        self.localization = self.user.get_localization()
        self.text = text
        self.ping = ping
        self.votes_yes, self.votes_no = 0, 0
        self.voters = []
        self.add_item(VoteButton('', discord.ButtonStyle.green, True, '✔'))
        self.add_item(VoteButton('', discord.ButtonStyle.red, False, '✖'))
        self.timer = timer
        self.add_item(StartTimeButton(get_localized_answer('start_timer', self.user.get_localization()), discord.ButtonStyle.blurple))
        self.yay = get_localized_answer('yay', self.localization)
        self.nay = get_localized_answer('nay', self.localization)
        self.client = client

    def get_str(self):
        return f"{self.text}\n\n{self.yay} - {self.votes_yes} | {self.nay} - {self.votes_no}"

    async def closer(self, channel_id, message_id):
        await asyncio.sleep(self.timer)
        msg: discord.Message = await self.client.get_channel(channel_id).fetch_message(message_id)
        await msg.edit(view=None)
        if self.ping:
            voters = ''
            for voter in self.voters:
                try:
                    voters += msg.guild.get_member(voter).mention + '\n'
                except AttributeError:
                    voters += f'<@{voter}>\n'
            chunks = chunker(
                f'{get_localized_answer("votum_closed", self.localization).format(num_of_users=len(self.voters))}\n {voters}')
            for chunk in chunks:
                await msg.reply(content=chunk)

        else:
            voters = ''
            for voter in self.voters:
                try:
                    voters += str(msg.guild.get_member(voter)) + '\n'
                except AttributeError:
                    voters += f'<@{voter}>\n'

            with io.StringIO(voters) as string_buffer:
                await msg.reply(content=f'{get_localized_answer("votum_closed", self.localization).format(num_of_users=len(self.voters))}',
                                file=discord.File(string_buffer, filename='votes.txt'))


async def setup(client):
    await client.add_cog(Admin(client))
