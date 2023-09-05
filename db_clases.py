import random

import bson
import numpy

from db import servers, locations, characters, events, items, localized_data, users, roles, \
    get_localized_answer, get_item_from_translation_dict, map_collection
from static import RESIST_LIST, HEAD_RESIST_LIST, BODY_RESIST_LIST, SKILLS, STATS, FACTIONS, \
    CAN_BE_CHANGED_IN_CHAR, CAN_BE_CHANGED_IN_ITEM, ITEM_LOCALIZED_FIELDS, CHAR_TYPES, HEALTH_DEBUFFS, \
    PLATE_CARRIER_ZONES

from typing import Union
from copy import deepcopy
import math


class Server:
    def __init__(self, server_id):
        self.server_id = server_id
        self.server = self.roc_server()

    def roc_server(self):  # Read or create
        if server := servers.find_one({'id': self.server_id}):
            return server
        else:
            servers.insert_one({
                'id': self.server_id,
                'local': 'ukr',
                'manual_url': None,
                'webhook': None,
                'char_say_log': None,
                'char_deletion_log': None
            })
            return servers.find_one({'id': self.server_id})

    def set_manual_url(self, url: str):
        servers.find_one_and_update({'id': self.server_id}, {'$set': {'manual_url': url}})

    def set_webhook_url(self, url: str):
        servers.find_one_and_update({'id': self.server_id}, {'$set': {'webhook': url}})

    def set_char_say_log(self, channel_id: int):
        servers.find_one_and_update({'id': self.server_id}, {'$set': {'char_say_log': channel_id}})

    def set_char_change_log(self, channel_id: int):
        servers.find_one_and_update({'id': self.server_id}, {'$set': {'char_change_log': channel_id}})

    def set_char_deletion_log(self, channel_id: int):
        servers.find_one_and_update({'id': self.server_id}, {'$set': {'char_deletion_log': channel_id}})


class User:
    def __init__(self, user_id, server_id):
        self.user_id = user_id
        self.server_id = server_id
        self.user = self.roc_user()

    def roc_user(self):  # Read or create
        if user := users.find_one({'id': self.user_id}):
            return user
        else:
            loc = Server(self.server_id).server['local']
            users.insert_one({
                'id': self.user_id,
                'local': loc
            })
            return users.find_one({'id': self.user_id})

    def upd_user(self, new_user):
        pass

    def get_localization(self):
        return self.user['local']

    def set_localization(self, locale):
        users.update_one({'id': self.user_id}, {"$set": {'local': locale}})
        self.user = self.roc_user()


class Location:
    def __init__(self, role_id, guild_id):
        self.role_id = role_id
        self.guild_id = guild_id

    def roc_location(self):
        if location := locations.find_one({'id': self.role_id, 'guild_id': self.guild_id}):
            return location
        else:
            locations.insert_one({
                'id': self.role_id,
                'guild_id': self.guild_id,
                'attached_locations': []
            })
            return locations.find_one({'id': self.role_id, 'guild_id': self.guild_id})

    def remove_location(self, role_id, guild_id):
        for loc in locations.find({'guild_id': guild_id}):
            try:
                loc['attached_locations'].remove(role_id)
            except ValueError:
                pass
            self.update_attachments(loc['id'], guild_id, loc['attached_locations'])
        locations.delete_one({'id': role_id, 'guild_id': guild_id})

    @staticmethod
    def update_attachments(l_id, guild_id, new):
        locations.update_one({'id': l_id, 'guild_id': guild_id}, {"$set": {'attached_locations': new}})

    def update_image(self, image_url):
        self.roc_location()
        locations.update_one({'id': self.role_id, 'guild_id': self.guild_id}, {"$set": {'url': image_url}})

    def update_description(self, description, locale):
        loc = self.roc_location()
        if desc := loc.get('description', None):
            desc[locale] = description
        else:
            desc = {locale: description}

        locations.update_one({'id': self.role_id, 'guild_id': self.guild_id}, {"$set": {'description': desc}})

    def attach_or_detach(self, attach_id, guild_id):
        if attachment := locations.find_one({'id': attach_id, 'guild_id': guild_id}):
            pass
        else:
            attachment = Location(attach_id, guild_id).roc_location()

        if self.role_id in attachment['attached_locations']:  # detach
            attachment['attached_locations'].remove(self.role_id)
            locs = self.roc_location()['attached_locations']
            locs.remove(attach_id)
        else:  # attach
            attachment['attached_locations'].append(self.role_id)
            locs = self.roc_location()['attached_locations']
            locs.append(attach_id)
        self.update_attachments(attach_id, guild_id, attachment['attached_locations'])
        self.update_attachments(self.role_id, guild_id, locs)


class Event:
    def __init__(self, guild_id, weight=1., location_id=None, url=None):
        self.location_id = location_id
        self.guild_id = guild_id
        self.weight = weight
        self.url = url

    def roc_event(self, e_id=None):
        if event := events.find_one({'_id': e_id, 'guild_id': self.guild_id}):
            return event
        else:
            doc = events.insert_one({
                'location_id': self.location_id,
                'guild_id': self.guild_id,
                'localized_events': {},
                'statistical_weight': self.weight,
                'url': self.url
            })
            return events.find_one({'_id': doc.inserted_id, 'guild_id': self.guild_id})

    def remove_event(self, e_id):
        events.delete_one({'_id': e_id, 'guild_id': self.guild_id})

    def edit_event(self, e_id, new_event, locale):
        event = events.find_one({'_id': e_id, 'guild_id': self.guild_id})
        event['localized_events'][locale] = new_event
        events.update_one({'_id': e_id, 'guild_id': self.guild_id},
                          {"$set": {'localized_events': event['localized_events']}})

    def change_event_location(self, e_id, location=None):
        events.update_one({'_id': e_id, 'guild_id': self.guild_id}, {"$set": {'location_id': location}})

    def change_event_weight(self, e_id):
        events.update_one({'_id': e_id, 'guild_id': self.guild_id}, {"$set": {'statistical_weight': self.weight}})

    def change_event_url(self, e_id, url):
        events.update_one({'_id': e_id, 'guild_id': self.guild_id}, {"$set": {'url': url}})


def take_dist(elem):
    return elem['dist']


class Character:
    def __init__(self, guild_id: int, owner_id: Union[int, bson.ObjectId] = None, u_id: bson.ObjectId = None,
                 faction: str = None):
        self.guild_id = guild_id
        self.u_id = u_id
        self.owner_id = owner_id
        self.faction = faction
        self.char = self.read()

    def road_prov(self, price):
        src = self.read()
        food, water, counter_f, counter_w = src['food'], src['water'], src['counter_f'], src['counter_w']
        counter_f += price
        counter_w += price
        if counter_f >= 14400:
            fm = int(numpy.floor(counter_f / 60 / 60 / 4))
            counter_f -= fm * 14400
            food -= fm
        if counter_w >= 7200:
            fm = int(numpy.floor(counter_w / 60 / 60 / 2))
            counter_w -= fm * 7200
            water -= fm
        self.update('counter_f', counter_f)
        self.update('counter_w', counter_w)
        self.update('food', food)
        self.update('water', water)
        return food, water

    def change_hp(self, body_part, num):
        current_hp, max_hp = self.char['hp'][body_part]
        self.update(body_part, (int(numpy.clip(num + current_hp, 0, max_hp)), max_hp))
        self.update_char()

    def set_hp(self, body_part, num):
        current_hp, max_hp = self.char['hp'][body_part]
        self.update(body_part, (num, max_hp))
        self.update_char()

    def read(self):
        if self.u_id:
            if char := characters.find_one({'_id': self.u_id}):
                self.owner_id = char['owner_id']
                return char
        else:
            if char := characters.find_one({'owner_id': self.owner_id, 'guild_id': self.guild_id, 'type': 'player'}):
                self.u_id = char['_id']
                return char
        return False

    def get_closest_coords(self, x=None, y=None):
        char = self.read()
        lst = [x for x in map_collection.find({'map_uid': char['location']})]
        if not x and not y:
            ux, uy = char['coordinates']
        else:
            ux, uy = x, y
        for itm in lst:
            itm['dist'] = numpy.sqrt(
                numpy.square(ux - itm['coordinates'][0]) + numpy.square(uy - itm['coordinates'][1]))
        lst.sort(key=take_dist)
        return lst[:24]

    def get_profession_list(self):
        ret_lst = []
        for profession in self.char['professions']:
            ret_lst.append(items.find_one({'_id': profession}))
        return ret_lst

    def get_available_professions(self):
        ne_list = []
        for profession in self.char['professions']:
            ne_list.append({'_id': {'$ne': profession}})
        return list(items.find(
            {
                '$and': ne_list + [{'type': 'profession'}]
            }
        ))

    def add_prof(self, prof_id: bson.ObjectId):
        self.update_char()
        if self.get_number_of_available_professions() and prof_id not in self.char['professions']:
            characters.update_one({'_id': self.u_id}, {'$push': {'professions': prof_id}})

    def rem_prof(self, prof_id: bson.ObjectId):
        self.update_char()
        for n, prof in enumerate(self.char['professions']):
            if prof == prof_id:
                characters.update_one({'_id': self.u_id}, {"$unset": {f'professions.{n}': None}})
                characters.update_one({'_id': self.u_id}, {"$pull": {f'professions': None}})
                return

    def read_inv(self):
        char = characters.aggregate([
            {'$match': {'_id': self.u_id}},
            {
                '$lookup': {
                    'from': 'items',
                    'localField': 'inventory._id',
                    'foreignField': '_id',
                    'as': 'inventory_unfolded'
                }
            }, {
                '$lookup': {
                    'from': 'items',
                    'localField': 'equipped._id',
                    'foreignField': '_id',
                    'as': 'equipped_unfolded'
                }
            }, {
                '$project': {
                    'inventory': {
                        '$map': {
                            'input': '$inventory',
                            'as': 'f',
                            'in': {
                                '$mergeObjects': [
                                    '$$f', {
                                        '$arrayElemAt': [
                                            {
                                                '$filter': {
                                                    'input': '$inventory_unfolded',
                                                    'cond': {
                                                        '$eq': [
                                                            '$$this._id', '$$f._id'
                                                        ]
                                                    }
                                                }
                                            }, 0
                                        ]
                                    }
                                ]
                            }
                        }
                    },
                    'equipped': {
                        '$map': {
                            'input': '$equipped',
                            'as': 'f',
                            'in': {
                                '$mergeObjects': [
                                    '$$f', {
                                        '$arrayElemAt': [
                                            {
                                                '$filter': {
                                                    'input': '$equipped_unfolded',
                                                    'cond': {
                                                        '$eq': [
                                                            '$$this._id', '$$f._id'
                                                        ]
                                                    }
                                                }
                                            }, 0
                                        ]
                                    }
                                ]
                            }
                        }
                    }
                }
            }, {
                '$lookup': {
                    'from': 'items',
                    'localField': 'equipped.modifications',
                    'foreignField': '_id',
                    'as': 'equipped_modifications'
                }
            }, {
                '$lookup': {
                    'from': 'items',
                    'localField': 'inventory.modifications',
                    'foreignField': '_id',
                    'as': 'inventory_modifications'
                }
            }
        ]).next()
        dict_of_inv_mods = {mod['_id']: mod for mod in char['inventory_modifications']}
        dict_of_eq_mods = {mod['_id']: mod for mod in char['equipped_modifications']}
        weight = 0
        for n, itm in enumerate(char['inventory']):
            if not itm.get('localization'):
                removed = char['inventory'].pop(n)
                if self.char['inventory'][n]['_id'] == removed['_id']:
                    self.char['inventory'].pop(n)
                    characters.update_one({'_id': self.u_id}, {'$pull': {f'inventory': removed}})

                continue
            if itm['type'] == 'plate_carrier':
                plates = itm.get('plates', {})
                for body_part_name in PLATE_CARRIER_ZONES.keys():
                    if plate := plates.get(body_part_name):
                        if not items.find_one({'_id': plate.get('_id')}):
                            characters.update_one({'_id': self.u_id},
                                                  {'$unset': {f'inventory.{n}.plates.{body_part_name}': ''}})
                        else:
                            itm['plates'][body_part_name] = items.find_one({'_id': plate.get('_id')})
                            char['inventory'][n]['weight'] = char['inventory'][n]['weight'] + itm['plates'][body_part_name][
                                'weight']

            item_weight = round(Item.get_item_weight(itm, dict_of_inv_mods), 3)
            char['inventory'][n]['weight'] = item_weight
            weight += item_weight * itm['quantity']

        for n, itm in enumerate(char['equipped']):
            if not itm.get('localization'):
                removed = char['equipped'].pop(n)
                if self.char['equipped'][n]['_id'] == removed['_id']:
                    self.char['equipped'].pop(n)
                    characters.update_one({'_id': self.u_id}, {'$pull': {f'equipped': removed}})

                continue

            item_weight = round(Item.get_item_weight(itm, dict_of_eq_mods), 3)
            char['equipped'][n]['weight'] = item_weight
            if itm['type'] == 'plate_carrier':
                plates = itm.get('plates', {})
                for body_part_name in PLATE_CARRIER_ZONES.keys():
                    if plate := plates.get(body_part_name):
                        if not items.find_one({'_id': plate.get('_id')}):
                            characters.update_one({'_id': self.u_id}, {'$unset': {f'equipped.{n}.plates.{body_part_name}': ''}})
                        else:
                            itm['plates'][body_part_name] = items.find_one({'_id': plate.get('_id')})
                            char['equipped'][n]['weight'] = char['equipped'][n]['weight'] + itm['plates'][body_part_name][
                                'weight']

            weight += item_weight * itm['quantity']

        return char, weight, dict_of_inv_mods, dict_of_eq_mods

    def read_equipped(self, ignore_damage: bool = False):
        char = characters.aggregate([
            {'$match': {'_id': self.u_id}},
            {
                '$lookup': {
                    'from': 'items',
                    'localField': 'equipped._id',
                    'foreignField': '_id',
                    'as': 'equipped_unfolded'
                }
            }, {
                '$project': {
                    'equipped': {
                        '$map': {
                            'input': '$equipped',
                            'as': 'f',
                            'in': {
                                '$mergeObjects': [
                                    '$$f', {
                                        '$arrayElemAt': [
                                            {
                                                '$filter': {
                                                    'input': '$equipped_unfolded',
                                                    'cond': {
                                                        '$eq': [
                                                            '$$this._id', '$$f._id'
                                                        ]
                                                    }
                                                }
                                            }, 0
                                        ]
                                    }
                                ]
                            }
                        }
                    }
                }
            }, {
                '$lookup': {
                    'from': 'items',
                    'localField': 'equipped.modifications',
                    'foreignField': '_id',
                    'as': 'equipped_modifications'
                }
            },
        ]).next()
        dict_of_eq_mods = {mod['_id']: mod for mod in char['equipped_modifications']}
        for n, itm in enumerate(char['equipped']):
            if not itm.get('localization'):
                removed = char['equipped'].pop(n)
                if self.char['equipped'][n]['_id'] == removed['_id']:
                    self.char['equipped'].pop(n)
                    characters.update_one({'_id': self.u_id}, {'$pull': {f'equipped': removed}})

                continue

            char['equipped'][n]['weight'] = round(Item.get_item_weight(itm, dict_of_eq_mods), 3)
            for modification in itm['modifications']:
                for buff_debuff in dict_of_eq_mods[modification]['actions_when_equipped']:
                    if buff_debuff['action'] == 'buff_or_debuff' and buff_debuff['what_to_buff'] in RESIST_LIST:
                        char['equipped'][n][buff_debuff['what_to_buff']] += buff_debuff['num']
            if itm['type'] == 'plate_carrier':
                plates = itm.get('plates', {})
                for body_part_name in PLATE_CARRIER_ZONES.keys():
                    if plate := plates.get(body_part_name):
                        if not items.find_one({'_id': plate.get('_id')}):
                            characters.update_one({'_id': self.u_id}, {'$unset': {f'equipped.{n}.plates.{body_part_name}': ''}})
                        else:
                            itm['plates'][body_part_name] = items.find_one({'_id': plate.get('_id')})

        return char, dict_of_eq_mods

    def add_item(self, item_id: bson.ObjectId, quantity: int = 1, healing=0):
        for n, item in enumerate(self.char['inventory']):
            if item['_id'] == item_id:
                if not item['modifications'] and item.get('healing') == healing:
                    item['quantity'] += quantity
                    characters.update_one({'_id': self.u_id}, {"$set": {f'inventory.{n}': item}})
                    return
        item = {'_id': item_id, 'quantity': quantity, 'modifications': [], 'healing': healing}
        self.char['inventory'].append(item)
        characters.update_one({'_id': self.u_id}, {"$push": {'inventory': item}})

    def add_item_dict(self, new_item, quantity: int = 1):
        new_item.pop('quantity')
        for n, item in enumerate(self.char['inventory']):
            item_clone = deepcopy(item)
            item_clone.pop('quantity')
            if item_clone == new_item:
                item['quantity'] += quantity
                characters.update_one({'_id': self.u_id}, {"$set": {f'inventory.{n}': item}})
                return
        new_item['quantity'] = quantity
        self.char['inventory'].append(new_item)
        characters.update_one({'_id': self.u_id}, {"$push": {'inventory': new_item}})

    def add_modification(self, item, idx, modification_id):
        if self.char['equipped'][idx]['_id'] == item['_id']:
            self.char['equipped'][idx]['modifications'].append({modification_id})
            characters.update_one({'_id': self.u_id}, {"$push": {f'equipped.{idx}.modifications': modification_id}})
        self.remove_item_by_id(modification_id)

    def remove_modification(self, idx, modification_id):
        for n, mod in enumerate(self.char['equipped'][idx]['modifications']):
            if mod == modification_id:
                self.char['equipped'][idx]['modifications'].pop(n)
                characters.update_one({'_id': self.u_id}, {"$unset": {f'equipped.{idx}.modifications.{n}': None}})
                characters.update_one({'_id': self.u_id}, {"$pull": {f'equipped.{idx}.modifications': None}})
                self.add_item(modification_id)
                return

    def remove_item_by_id(self, item_id: bson.ObjectId, quantity: int = 1):
        for n, item in enumerate(self.char['inventory']):
            if item['_id'] == item_id:
                item['quantity'] -= quantity
                if item['quantity'] <= 0:
                    self.char['inventory'].pop(n)
                    characters.update_one({'_id': self.u_id}, {"$unset": {f'inventory.{n}': None}})
                    characters.update_one({'_id': self.u_id}, {"$pull": {'inventory': None}})
                    return
                characters.update_one({'_id': self.u_id}, {"$set": {f'inventory.{n}': item}})
                return

    def remove_item_by_idx(self, item, idx, quantity: int = 1):
        if item['_id'] == self.char['inventory'][idx]['_id']:
            self.char['inventory'][idx]['quantity'] -= quantity
            if self.char['inventory'][idx]['quantity'] <= 0:
                self.char['inventory'].pop(idx)
                characters.update_one({'_id': self.u_id}, {"$unset": {f'inventory.{idx}': None}})
                characters.update_one({'_id': self.u_id}, {"$pull": {'inventory': None}})
                return
            characters.update_one({'_id': self.u_id},
                                  {"$set": {f'inventory.{idx}.quantity': self.char['inventory'][idx]['quantity']}})
            return

    def update_char(self):
        self.char = characters.find_one({'_id': self.u_id})

    def get_stat_str(self, localization):
        localized_dict = localized_data.find_one({'request': 'stats_and_skills'})['local']
        ret_str = f'{self.char["name"]}\n'
        for skill in self.char['skills'].keys():
            ret_str += f'```{get_item_from_translation_dict(localized_dict, localization, skill)}: {self.char["skills"][skill]}``````'
            for stat, value in self.char['stats'].items():
                if self.char['stats'][stat]['skill'] == skill:
                    x_str = ''
                    if value['multiplier'] != 1:
                        x_str += f' (x{value["multiplier"]})'
                    ret_str += f'{get_item_from_translation_dict(localized_dict, localization, stat)}{x_str}: {self.char["stats"][stat]["value"]}\n'
            ret_str += '```\n'
        ret_str += f"{self.count_used_points()}/{self.count_points()}"
        return ret_str

    def get_stat_and_skill_lst(self, localization, localized_dict):
        ret_lst = []
        for n, skill in enumerate(self.char['skills'].keys()):
            stats = []
            for stat, value in self.char['stats'].items():
                if self.char['stats'][stat]['skill'] == skill:
                    stats.append(
                        (
                            (stat,
                             localized_dict.get(localization, localized_dict["default"]).get(stat, localized_dict[
                                 "default"].get(stat, stat)), value['multiplier'])
                        )
                    )
            ret_lst.append(
                ((skill, localized_dict.get(localization, localized_dict["default"]).get(skill,
                                                                                         localized_dict["default"].get(
                                                                                             skill, skill))),
                 stats)
            )
        return ret_lst

    @staticmethod
    def get_skill_lst(localization):
        localized_dict = localized_data.find_one({'request': 'stats_and_skills'})['local']
        ret_lst = []
        for n, skill in enumerate(SKILLS):
            ret_lst.append(
                (skill, localized_dict.get(localization, localized_dict["default"]).get(skill,
                                                                                        localized_dict["default"].get(
                                                                                            skill, skill))))
        return ret_lst

    def get_str_from_lst(self, lst, page, localization, localization_dict, stats_dict):
        ret_str = f'{self.char["name"]}\n'
        data_on_page = lst[page]
        ret_str += f'```{data_on_page[0][1]}: {self.char["skills"].get(data_on_page[0][0])}``````'
        for stat in data_on_page[1]:
            x_str = ''
            if stat[2] != 1:
                x_str += f' (x{stat[2]})'

            ret_str += f'{stat[1]}{x_str}: {self.char["stats"].get(stat[0])["value"]}\n'
        prof_str = ''
        for prof in self.get_profession_list():
            prof_str += get_item_from_translation_dict(localization_dict, localization, 'professions') + '\n'
            prof_dict = prof['localization']
            prof_str += f'{get_item_from_translation_dict(prof_dict, localization, "name")}: '
            for buff in prof.get('actions_when_equipped', []):
                if buff['action'] == 'buff_or_debuff':
                    prof_str += f'{get_item_from_translation_dict(stats_dict, localization, buff["what_to_buff"])}'
                    prof_str += f' +{abs(buff["num"])}, ' if buff["num"] >= 0 else f' -{abs(buff["num"])}, '
            prof_str = prof_str[:-2]
        ret_str += f"```\n" \
                   f"| {self.count_points() - self.count_used_points()} " \
                   f"{get_item_from_translation_dict(localization_dict, localization, 'pts_remain')} | " \
                   f"{get_item_from_translation_dict(localization_dict, localization, 'meters').format(self.char['meters'])} | " \
                   f"{get_item_from_translation_dict(localization_dict, localization, 'level').format(self.get_level())} |\n" \
                   f"{prof_str}\n" \
                   f"{get_item_from_translation_dict(localization_dict, localization, 'page')} {page + 1}/{len(lst)}"

        return ret_str

    @staticmethod
    def roll(min_num: int, max_num: int):
        crit_fail = False
        crit_success = False
        sign = ''
        while True:
            rolled_num = random.randint(min_num, max_num)
            yield sign, rolled_num
            if rolled_num == min_num:
                if not crit_success:
                    crit_fail = True
                    sign = ' - '
                break
            elif rolled_num == max_num:
                crit_success = True
                sign = ' + '
            else:
                break

        if crit_fail:
            while True:
                rolled_num = random.randint(min_num, max_num)
                yield sign, -rolled_num
                if rolled_num != max_num:
                    break

    def get_stat_or_skill(self, stat_or_skill, dont_ignore_hp_debuff=True):
        ret_str = ''
        final_sum = 0
        items_to_check = []

        if stat_or_skill in SKILLS.keys():
            skill_bonus = self.char['skills'][stat_or_skill]
            final_sum += skill_bonus
            ret_str += str(skill_bonus)
            items_to_check.append(stat_or_skill)
        else:
            skill_str, stat_bonus = self.char['stats'][stat_or_skill]['skill'], self.char['stats'][stat_or_skill][
                'value']
            skill_bonus = self.char['skills'][skill_str]
            items_to_check.append(skill_str)
            items_to_check.append(stat_or_skill)
            final_sum += skill_bonus + stat_bonus
            ret_str += f'{skill_bonus} + {stat_bonus}'

        bonus_str = '('
        bonus_num = 0
        # ADD BUFFS AND DEBUFFS
        for entry in self.char['achievements'] + self.char['buffs_and_debuffs']:
            if buffs := entry.get('buffs'):
                for buff in buffs:
                    if buff['name'] in items_to_check:
                        bonus_num += buff['value']
                        bonus_str += f' + {buff["value"]}'
            elif debuffs := entry.get('debuffs'):
                for debuff in debuffs:
                    if debuff['name'] in items_to_check:
                        bonus_num -= debuff['value']
                        bonus_str += f' - {debuff["value"]}'

        # ADD ITEM BUFFS AND DEBUFFS
        inv, weight, inventory_modifications, equipped_modifications = self.read_inv()
        for item in inv['equipped'] + self.get_profession_list():
            for buff in item.get('actions_when_equipped', []):
                if buff['what_to_buff'] in items_to_check:
                    bonus_num += buff['num']
                    if buff['num'] >= 0:
                        bonus_str += f' + {buff["num"]}'
                    else:
                        bonus_str += f' - {buff["num"]}'

            for modification in item.get('modifications', []):
                for buff in equipped_modifications[modification]['actions_when_equipped']:
                    if buff['what_to_buff'] in items_to_check:
                        bonus_num += buff['num']
                        if buff['num'] >= 0:
                            bonus_str += f' + {buff["num"]}'
                        else:
                            bonus_str += f' - {buff["num"]}'
        if int(numpy.floor(weight/20)) > 0 and stat_or_skill == 'mobility':
            bonus_num -= int(numpy.floor(weight/20))
            bonus_str += f' - {int(numpy.floor(weight/20))}'

        final_sum += bonus_num
        if bonus_num:
            if len(bonus_str) > 1:
                temp_char = ''
                if bonus_str[2] == '-':
                    temp_char = '-'
                bonus_str = bonus_str[0] + temp_char + bonus_str[4:] + ')'
                if bonus_num > 0:
                    ret_str += f' + {bonus_num}' + bonus_str
                else:
                    ret_str += f' - {abs(bonus_num)}' + bonus_str
        return final_sum, ret_str

    def get_hp_limit(self):
        return self.get_stat_or_skill('body', False)[0] * 5 + 15

    def get_psi_hp_limit(self):
        return self.get_stat_or_skill('intellect', False)[0] * 5 + 15

    def roll_dice(self, stat_or_skill, buff_or_debuff=0):
        final_sum = 0
        ret_str = ''
        stat_or_skill_bonus, stat_or_skill_str = self.get_stat_or_skill(stat_or_skill)
        final_sum += stat_or_skill_bonus
        ret_str += stat_or_skill_str
        if buff_or_debuff > 0:
            ret_str += f' + {buff_or_debuff}'
        elif buff_or_debuff < 0:
            ret_str += f' - {abs(buff_or_debuff)}'

        final_sum += buff_or_debuff

        dice_sum = 0
        dice_str = '['
        for sign, rolled_number in Character.roll(1, 10):
            dice_str += f'{sign}{abs(rolled_number)}'
            dice_sum += rolled_number
        dice_str += ']'
        if dice_sum >= 0:
            ret_str += f' + {dice_sum}' + dice_str
        else:
            ret_str += f' - {abs(dice_sum)}' + dice_str

        final_sum += dice_sum

        # Health check:
        hp_dict = self.char['hp']
        debuff = 0
        for key, value in hp_dict.items():
            hp_now, hp_max = value
            ratio = hp_now / hp_max
            if ratio <= 0.2:
                debuff += HEALTH_DEBUFFS[key][2]
            elif ratio <= 0.4:
                debuff += HEALTH_DEBUFFS[key][1]
            elif ratio <= 0.7:
                debuff += HEALTH_DEBUFFS[key][0]
        if debuff:
            final_sum -= (final_sum / 100) * debuff
            final_sum = int(numpy.floor(final_sum))
            ret_str = f'Результат: {final_sum} = ({ret_str})-{debuff}%'
            if debuff >= 100:
                ret_str += '\nПровалено в зв\'язку зі станом здоров\'я'
        else:
            ret_str = f'Результат: {final_sum} = {ret_str}'
        return ret_str, final_sum

    def count_points(self):
        def_cap = 0
        lvls = [1, 2, 3, 4, 6, 7, 8, 9, 10]
        cur_lvl = self.get_level()
        for lvl in lvls:
            if cur_lvl >= lvl:
                def_cap += 1
        return def_cap

    def get_level(self):
        self.update_char()
        usr = self.char
        if 5_000 <= usr['meters'] < 10_000:
            lvl = 1
        elif 10_000 <= usr['meters'] < 20_000:
            lvl = 2
        elif 250_000 <= usr['meters']:
            lvl = 10
        elif usr['meters'] < 5_000:
            lvl = 0
        else:
            lvl = int(math.floor(usr['meters'] / 20_000)) + 2
        return lvl

    def damage_or_repair_item_at_idx(self, idx, u_id, body_part, damage=1):
        self.update_char()
        inv, _ = self.read_equipped(ignore_damage=True)
        if self.char['equipped'][idx]['_id'] == u_id:
            self.char['equipped'][idx][f'{body_part}_damage'] = damage + self.char['equipped'][idx].get(
                f'{body_part}_damage', 0)
            if self.char['equipped'][idx][f'{body_part}_damage'] < 0:
                self.char['equipped'][idx][f'{body_part}_damage'] = 0
            characters.update_one({'_id': self.char['_id']},
                                  {'$set': {f'equipped.{idx}.{body_part}_damage': self.char['equipped'][idx][
                                      f'{body_part}_damage']}})

    def insert_plate_at_idx(self, idx, u_id, body_part, plate_id: bson.ObjectId):
        self.update_char()
        self.remove_item_by_id(plate_id)
        inv, _ = self.read_equipped()

        if self.char['equipped'][idx]['_id'] == u_id:
            if plate := self.char['equipped'][idx].get('plates', {}).get(body_part):
                self.add_item(plate)
            characters.update_one({'_id': self.char['_id']},
                                  {'$set': {f'equipped.{idx}.plates.{body_part}._id': plate_id}})

    def use_item_with_uid(self, u_id, localization):
        fields_data = localized_data.find_one({'request': 'char_fields'})['local']
        stats_and_skills_data = localized_data.find_one({'request': 'stats_and_skills'})['local']

        ret_str = ''
        self.update_char()
        inv, _, _, _ = self.read_inv()
        for item in inv['inventory']:
            if item['_id'] == u_id:
                request = {}
                buffs, debuffs = [], []
                for action in item['actions_when_used']:
                    match action['action']:
                        case 'one_time_buff_or_debuff':
                            if not request.get('$inc', False):
                                request['$inc'] = {}
                            number = 0
                            sign, x, y, z = action['num']
                            st_sign = '+' if sign == 1 else '-'
                            other_sign = '-' if z < 0 else '+'
                            ret_str += f'{get_item_from_translation_dict(fields_data, localization, action["what_to_buff"])}, {st_sign}({x}d{y}{other_sign}{abs(z)})\n'
                            if x:
                                for _ in range(x):
                                    addition = random.randint(1, y)
                                    number += addition
                                    ret_str += f'{addition} + '
                                ret_str = ret_str[:-3]
                            number += z
                            number *= sign
                            ret_str += f' = {number}\n'
                            request['$inc'][f'{action["what_to_buff"]}'] = number
                        case 'buff_or_debuff':
                            if action['num'] > 0:
                                buffs.append({'name': action['what_to_buff'], 'value': action['num']})
                                sign = '+'
                            else:
                                debuffs.append({'name': action['what_to_buff'], 'value': abs(action['num'])})
                                sign = '-'
                            ret_str += f'{get_item_from_translation_dict(stats_and_skills_data, localization, action["what_to_buff"])} {sign}{abs(action["num"])}\n'

                if buffs or debuffs:
                    request['$push'] = {
                        'buffs_and_debuffs': {'buffs': buffs, 'debuffs': debuffs, 'localization': item['localization']}}

                if request:
                    characters.update_one({'_id': self.char['_id']}, request)
                    # cleanup
                    self.update_char()
                self.remove_item_by_id(u_id)
                return True, ret_str

    def equip_item_at_idx(self, idx, u_id, type_of_item):
        self.update_char()
        equipped, _ = self.read_equipped()
        if self.char['inventory'][idx]['_id'] == u_id:
            self.char['inventory'][idx]['quantity'] -= 1
            item = deepcopy(self.char['inventory'][idx])
            item['quantity'] = 1
            self.char['equipped'].append(item)
            characters.update_one({'_id': self.char['_id']}, {'$push': {'equipped': item}})
            if self.char['inventory'][idx]['quantity'] <= 0:
                self.char['inventory'].pop(idx)
                characters.update_one({'_id': self.char['_id']}, {'$unset': {f'inventory.{idx}': ''}})
                characters.update_one({'_id': self.char['_id']}, {'$pull': {'inventory': None}})
                return True
        return True

    def unequip_item_at_idx(self, idx, u_id):
        self.update_char()
        if self.char['equipped'][idx]['_id'] == u_id:
            item = self.char['equipped'].pop(idx)
            self.add_item_dict(item)
            characters.update_one({'_id': self.char['_id']}, {'$unset': {f'equipped.{idx}': ''}})
            characters.update_one({'_id': self.char['_id']}, {'$pull': {'equipped': None}})

    def count_achievements(self):
        counted = 0
        for achievement in self.char['achievements']:
            if achievement.get('counted_for_legend', False):
                counted += 1
        return counted

    def lvl_up(self, upped_stat, stat_name, num=1, user_locale='default'):
        if num <= 0:
            raise Exception  # TODO
        limit = 10
        all_points = self.count_points()
        stat = self.char['stats'][upped_stat]
        new_value = stat['value'] + num
        if new_value > limit - stat['value']:
            return get_localized_answer('lvl_up_limit_fail', user_locale).format(
                stat_name=stat_name,
                old_lvl=stat['value'],
                new_lvl=new_value,
                limit=limit
            )
        sum_used = 0
        points_str = ''
        if stat['multiplier'] != 1:
            points_str = f'({num})*{stat["multiplier"]}={sum_used}'
        else:
            points_str += f'={num * stat["multiplier"]}'
        used_points = self.count_used_points() + sum_used
        if used_points > all_points:
            return get_localized_answer('lvl_up_fail', user_locale).format(
                stat_name=stat_name,
                old_lvl=stat['value'],
                new_lvl=new_value,
                points_str=points_str,
                points_dif=abs(all_points - used_points)
            )

        else:
            characters.update_one({'_id': self.char['_id']}, {'$inc': {f'stats.{upped_stat}.value': num}})
            return get_localized_answer('lvl_up_success', user_locale).format(
                stat_name=stat_name,
                old_lvl=stat['value'],
                new_lvl=new_value,
                points_str=points_str
            )

    def count_used_points(self):
        points_used = 0
        for _, stat in self.char['stats'].items():
            points_used += stat['value'] * stat['multiplier']
        return points_used

    def check_for_death(self, localization):
        return '', False  # todo implement
        hp = self.char['hp']
        death = ''
        dead = False
        localized_dict = localized_data.find_one({'request': 'death_strings'})['local']
        if self.char['radiation'] >= hp and self.char['radiation'] != 0:
            death += get_item_from_translation_dict(localized_dict, localization, 'rad_death') + '\n'
            dead = True
        if self.char['psi_hp'] <= 0:
            death += get_item_from_translation_dict(localized_dict, localization, 'psi_hp_death') + '\n'
            dead = True
        if hp < 0:
            death += get_item_from_translation_dict(localized_dict, localization, 'hp_death_near').format(
                treshold=abs(hp * 2)) + '\n'
            dead = True

        return dead, death

    def update(self, what_to_update: str, with_what):
        if what_to_update in CAN_BE_CHANGED_IN_CHAR:
            if what_to_update == 'faction' and with_what not in FACTIONS:
                raise TypeError
            characters.update_one({'_id': self.char['_id']}, {'$set': {what_to_update: with_what}})
        elif what_to_update in SKILLS:
            characters.update_one({'_id': self.char['_id']}, {'$set': {f'skills.{what_to_update}': with_what}})
        elif what_to_update in STATS:
            characters.update_one({'_id': self.char['_id']}, {'$set': {f'stats.{what_to_update}.value': with_what}})
        elif what_to_update in FACTIONS:
            characters.update_one({'_id': self.char['_id']}, {'$set': {f'frac_rep.{what_to_update}': with_what}})
        elif what_to_update in HEALTH_DEBUFFS.keys():
            characters.update_one({'_id': self.char['_id']}, {'$set': {f'hp.{what_to_update}': with_what}})

        else:
            try:
                characters.update_one({'_id': self.char['_id']},
                                      {'$set': {f'npc_rep.{bson.ObjectId(what_to_update)}': with_what}})
            except TypeError:
                return False
        self.update_char()
        return True

    def delete(self):
        return characters.delete_one(self.char)

    def get_number_of_available_professions(self):
        profs = 1
        if self.get_level() >= 5:
            profs += 1
        return profs - len(self.char['professions'])

    def clone(self, new_name: str = None, new_owner=None, new_type: str = None):
        if new_name:
            self.char['name'] = new_name
        if new_owner:
            self.char['owner_id'] = new_owner
        if new_type:
            self.char['type'] = new_type
        self.char.pop('_id')
        characters.insert_one(self.char)

    def create(self, name: str, char_type: str, skills: dict = None, img_url: str = '', background_url: str = ''):
        copied_skills = SKILLS.copy()
        if not skills:
            skills = {}
        for key, value in skills.items():
            copied_skills[key] = value
        if char_type not in CHAR_TYPES:
            return False
        if self.faction not in FACTIONS:
            self.faction = 'loner'
        return characters.insert_one(
            {
                'guild_id': self.guild_id,
                'owner_id': self.owner_id,  # discord id or uid
                'type': char_type,  # player, npc, trader, mutant (?)
                'name': name,
                'meters': 0,
                'hp': {
                    'head': (35, 35),
                    'thorax': (85, 85),
                    'left_arm': (60, 60),
                    'right_arm': (60, 60),
                    'stomach': (70, 70),
                    'left_leg': (65, 65),
                    'right_leg': (65, 65),
                },
                'morale': 0,
                'radiation': 0,
                'water': 0,
                'food': 0,
                'counter_f': 0,
                'counter_w': 0,
                'chill': 0,
                'frac_rep': {},  # frac name: float
                'npc_rep': {},  # chars uid: float
                'inventory': [  # todo
                    # 'item_uid': {
                    #    'quantity': 1,
                    #    'modifications': [],'
                    # }
                ],
                'money': 2000,
                'stashes': {  # todo
                    # 'stash_uid',
                    # 'stash2_uid'
                },
                'skills': copied_skills,
                'stats': STATS,

                'achievements': [],  # todo
                'location': bson.ObjectId('64d21f30f5e681a0db294bd4'),
                'coordinates': (2201, 2735),
                'equipped': [],  # todo
                'buffs_and_debuffs': [],
                'professions': [],
                'img_url': img_url,
                'background_url': background_url,
                'faction': self.faction,
            })


class Item:
    def __init__(self, guild_id: int, u_id: bson.ObjectId = None):
        self.guild_id = guild_id
        self.u_id = u_id
        self.item = self.read()
        return

    def read(self):
        if self.u_id:
            if item := items.find_one({'_id': self.u_id}):
                return item
        return False

    def update_item(self):
        self.item = items.find_one({'_id': self.u_id})

    def update(self, what_to_update: str, with_what, localization: str = 'default'):
        if what_to_update.lower() in CAN_BE_CHANGED_IN_ITEM + RESIST_LIST + ['containers']:
            if what_to_update in ITEM_LOCALIZED_FIELDS:
                items.update_one({'_id': self.u_id},
                                 {'$set': {f'localization.{localization}.{what_to_update}': with_what}})
            else:
                items.update_one({'_id': self.u_id}, {'$set': {what_to_update: with_what}})
            self.update_item()
            return True
        else:
            return False

    def add_buff_action(self, when, what, num):
        items.update_one(
            {'_id': self.u_id},
            {'$push': {
                f'actions_when_{when}': {
                    'action': 'buff_or_debuff',
                    'what_to_buff': what,
                    'num': num}
            }
            }
        )

    def add_one_time_buff_action(self, when, what, num: tuple[int, int, int, int]):
        # what = (sign, x, y, z) sign = 1 or -1 (XdY+Z)*sign
        items.update_one(
            {'_id': self.u_id},
            {'$push': {
                f'actions_when_{when}': {
                    'action': 'one_time_buff_or_debuff',
                    'what_to_buff': what,
                    'num': num}
            }
            }
        )

    def clear_buff_actions(self):
        items.update_one(
            {'_id': self.u_id},
            {'$set': {
                'actions_when_equipped': [],
                'actions_when_used': [],
            }
            }
        )

    def delete(self):
        return items.delete_one(self.item)

    def clone(self, new_name: str = None):
        if new_name:
            self.item['name'] = new_name
        self.item.pop('_id')
        items.insert_one(self.item)

    def create(self, name: str, description: str, item_type: str, weight: float, price: int, can_be_used: bool,
               can_be_equipped: bool):
        return items.insert_one(
            {
                'guild_id': self.guild_id,
                'type': item_type,
                'localization': {
                    "default": {
                        'name': name,
                        'description': description
                    }
                },
                'weight': weight,
                'price': price,
                'actions_when_used': [],  # instant, continuous
                'actions_when_equipped': [],  # buffs, debuffs
                'can_be_used': can_be_used,
                'can_be_equipped': can_be_equipped,
                'modification_slots': 0,
            })

    def create_ammo(self, name: str, description: str, weight: float, price: int, damage: tuple[int, int, int],
                    armor_penetration: tuple[int, int, int], ammo_type: bson.ObjectId):
        return items.insert_one(
            {
                'guild_id': self.guild_id,
                'type': 'ammo',
                'localization': {
                    "default": {
                        'name': name,
                        'description': description
                    }
                },
                'weight': weight,
                'price': price,
                'actions_when_used': [],  # instant, continuous
                'actions_when_equipped': [],  # buffs, debuffs
                'can_be_used': False,
                'can_be_equipped': False,
                'modification_slots': 0,
                'damage': damage,
                'armor_penetration': armor_penetration,
                'ammo_type': ammo_type
            })

    def create_weapon(self, name: str, description: str, weight: float, price: int, stat: str,
                      ammo_type: bson.ObjectId):
        return items.insert_one(
            {
                'guild_id': self.guild_id,
                'type': 'weapon',
                'localization': {
                    "default": {
                        'name': name,
                        'description': description
                    }
                },
                'weight': weight,
                'price': price,
                'actions_when_used': [],  # instant, continuous
                'actions_when_equipped': [],  # buffs, debuffs
                'can_be_used': False,
                'can_be_equipped': True,
                'modification_slots': 0,
                'stat': stat,
                'ammo_type': ammo_type
            })

    def create_modification(self, name: str, description: str, mod_type: int, weight: float, price: int,
                            modification_slots: int):
        return items.insert_one(
            {
                'guild_id': self.guild_id,
                'type': 'modification',  # item, helmet, full_armor, armor, weapon, detector, artefact
                'localization': {
                    "default": {
                        'name': name,
                        'description': description
                    }
                },
                'weight': weight,
                'price': price,
                'actions_when_used': [],  # instant, continuous
                'actions_when_equipped': [],  # buffs, debuffs
                'can_be_used': False,
                'can_be_equipped': False,
                'modification_slots': modification_slots,
                'modification_type': mod_type,  # 0 - weapon, 1 - armor, 2 - exoskeleton
            })

    def create_plate_carrier(self, name, description, weight, price, modification_slots,
                             stomach_protection, thorax_protection, arms_protection, legs_protection):
        return items.insert_one(
            {
                'guild_id': self.guild_id,
                'type': 'plate_carrier',
                'localization': {
                    "default": {
                        'name': name,
                        'description': description
                    }
                },
                'weight': weight,
                'price': price,
                'actions_when_used': [],
                'actions_when_equipped': [],
                'can_be_used': False,
                'can_be_equipped': True,
                'modification_slots': modification_slots,
                'stomach_protection': stomach_protection,  # None, plate, kevlar
                'thorax_protection': thorax_protection,
                'arms_protection': arms_protection,
                'legs_protection': legs_protection
            })

    def create_armor(self, name, description, weight, price, modification_slots,
                     head: int, thorax: int, stomach: int,
                     right_arm: int, left_arm: int, right_leg: int, left_leg: int):
        return items.insert_one(
            {
                'guild_id': self.guild_id,
                'type': 'armor',
                'localization': {
                    "default": {
                        'name': name,
                        'description': description
                    }
                },
                'weight': weight,
                'price': price,
                'actions_when_used': [],
                'actions_when_equipped': [],
                'can_be_used': False,
                'can_be_equipped': True,
                'modification_slots': modification_slots,
                'head': head,
                'thorax': thorax,
                'stomach': stomach,
                'right_arm': right_arm,
                'left_arm': left_arm,
                'right_leg': right_leg,
                'left_leg': left_leg,
            })

    def create_plate(self, name, description, weight, price, plate_class: int, plate_type):
        return items.insert_one(
            {
                'guild_id': self.guild_id,
                'type': 'armor_plate',
                'localization': {
                    "default": {
                        'name': name,
                        'description': description
                    }
                },
                'weight': weight,
                'price': price,
                'actions_when_used': [],
                'actions_when_equipped': [],
                'can_be_used': False,
                'can_be_equipped': False,
                'modification_slots': 0,
                'plate_class': plate_class,
                'plate_type': plate_type  # plate, kevlar
            })

    @staticmethod
    def get_item_weight(item, modifications):
        weight = item['weight']
        modificators = 1
        for mod in item['modifications']:
            modificators += modifications[mod]['weight']
        return weight * modificators
