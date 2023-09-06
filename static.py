CHAR_TYPES = ['player', 'npc', 'trader', 'mutant', 'dead']
ITEM_TYPES = ['item',
              'weapon', 'ammo', 'ammo_types',
              'detector', 'artefact',
              'medicine', 'provision', 'profession', 'plate_carrier', 'armor_plate', 'armor']
ITEM_TYPES_NOT_GM = ['item',
                     'weapon', 'ammo',
                     'detector', 'artefact',
                     'medicine', 'provision', 'plate_carrier', 'armor_plate', 'armor']
CAN_BE_MODIFIED = ['helmet', 'armor', 'full_armor', 'hazmat_suit', 'exoskeleton', 'weapon']
ITEM_LOCALIZED_FIELDS = ['name', 'description', 'use_effect_name', 'on_use_text']
USE_ACTION_TYPES = ['instant', 'continuous']
CAN_BE_CHANGED_IN_ITEM = [
    'name', 'description', 'use_effect_name', 'use_effect_description', 'on_use_text', 'type',
    'head',
    'thorax',
    'stomach', 'plate_class',
    'right_arm', 'left_arm',
    'right_leg', 'left_leg',
    'weight', 'price',
    'actions_when_used', 'actions_when_equipped',
    'can_be_used', 'can_be_equipped',
    'modification_slots', 'image_url', 'stat', 'damage', 'armor_penetration'
]
PLATE_CARRIER_ZONES = {
    'thorax': 'thorax_protection',
    'stomach': 'stomach_protection',
    'right_arm': 'arms_protection',
    'left_arm': 'arms_protection',
    'right_leg': 'legs_protection',
    'left_leg': 'legs_protection',

}
ZONES = [
    'thorax_protection',
    'arms_protection',
    'stomach_protection',
    'legs_protection',

]
PLATE_TYPES = [
    'plate', 'kevlar'
]
CAN_BE_BOOL_IN_ITEM = ['can_be_used', 'can_be_equipped',
                       ]
CAN_BE_NUM_IN_ITEM = ['weight', 'price', 'modification_slots', 'head',
                      'thorax', 'plate_class',
                      'stomach',
                      'right_arm', 'left_arm',
                      'right_leg', 'left_leg',
                      ]
CAN_BE_CHANGED_IN_CHAR = [
    'background_url', 'img_url',
    'location',
    'name',
    'type',
    'owner_id', 'meters', 'money', 'radiation', 'food', 'chill', 'water', 'morale',
    'faction',
    'coordinates', 'counter_f', 'counter_w', 'meters'
]
CAN_BE_INT_IN_CHAR = ['meters', 'money', 'radiation', 'food', 'chill', 'water', 'morale']
CAN_BE_STR_IN_CHAR = ['background_url', 'name', 'img_url']
SKILLS = {
    'weapons': 0,
    'heavy_weapons': 0,
    'military_education': 0,
    'recon': 0,
    'command': 0,
    'fitness': 0,
}
HEALTH_COORDS = {
    'head': (613, 75),
    'thorax': (365, 271),
    'stomach': (365, 431),
    'right_arm': (25, 431),
    'left_arm': (705, 431),
    'right_leg': (123, 751),
    'left_leg': (603, 751),
}
HEALTH_DEBUFFS = {
    'head': (30, 50, 100),
    'thorax': (10, 20, 30),
    'stomach': (10, 20, 30),
    'left_arm': (5, 10, 20),
    'right_arm': (5, 10, 20),
    'left_leg': (5, 10, 20),
    'right_leg': (5, 10, 20),
}
SHOOT_OPTIONS = [
    (
        True,
        [
            ('blinded', -999),
            ('darkness', -3),
            ('smoke_or_fog', -2),
            ('sun_front', -2),
            ('dusk', -2),
            ('dim_light', -1),
            ('daylight', 1),
            ('sun_behind', 2),
        ],
    ),
    (
        True,
        [
            ('target_suppressed', -3),
            ('target_behind_cover', -3),
            ('target_running', -2),
            ('target_prone', -2),
            ('target_kneeling', -1),
            ('target_stunned', 2),
            ('target_off_guard', 3),
        ]
    ),
    (
        False,
        [
            ('hand_to_hand_distance', -2),
            ('point_blank_distance', 3),
            ('short_distance', 2),
            ('combat_distance', 1),
            ('long_distance', -1),
            ('extreme_distance', -3),
        ]
    ),
    (
        False,
        [
            ('ambush_shot', 3, 1),
            ('single_shot', 2, 1),
            ('duplet_shot', 1, 2),
            ('suppressive_fire', 0, 30),
            ('short_burst', -1, 3),
            ('burst', -2, (4, 10)),
            ('long_burst', -3, (11, 20)),
        ]
    )
]
STATS = {
    # WEAPONS
    'pistols': {'skill': 'weapons', 'value': 0, 'multiplier': 1},
    'smgs': {'skill': 'weapons', 'value': 0, 'multiplier': 1},
    'rifles': {'skill': 'weapons', 'value': 0, 'multiplier': 1},
    'assault_rifles': {'skill': 'weapons', 'value': 0, 'multiplier': 1},
    'dmrs': {'skill': 'weapons', 'value': 0, 'multiplier': 1},
    'bolt_action_rifles': {'skill': 'weapons', 'value': 0, 'multiplier': 1},
    # HEAVY_WEAPONS
    'amrs': {'skill': 'heavy_weapons', 'value': 0, 'multiplier': 1},
    'machine_guns': {'skill': 'heavy_weapons', 'value': 0, 'multiplier': 1},
    'grenade_launchers': {'skill': 'heavy_weapons', 'value': 0, 'multiplier': 1},
    'manpads': {'skill': 'heavy_weapons', 'value': 0, 'multiplier': 1},
    'atgms': {'skill': 'heavy_weapons', 'value': 0, 'multiplier': 1},
    # MILITARY_EDUCATION
    'sappers': {'skill': 'military_education', 'value': 0, 'multiplier': 1},
    'electronics': {'skill': 'military_education', 'value': 0, 'multiplier': 1},
    'medicine': {'skill': 'military_education', 'value': 0, 'multiplier': 1},
    # RECON
    'uavs': {'skill': 'recon', 'value': 0, 'multiplier': 1},
    'nvgs': {'skill': 'recon', 'value': 0, 'multiplier': 1},
    'camouflage': {'skill': 'recon', 'value': 0, 'multiplier': 1},
    # COMMAND
    'leadership': {'skill': 'command', 'value': 0, 'multiplier': 1},
    'tactics': {'skill': 'command', 'value': 0, 'multiplier': 1},
    # FITNESS
    'mobility': {'skill': 'fitness', 'value': 0, 'multiplier': 1},
    'grenadier': {'skill': 'fitness', 'value': 0, 'multiplier': 1},
}

FACTIONS = [
    'loner',
]
AVAILABLE_FACTIONS = [
    'loner',
]
FACTION_EMOJIS = {
    'loner': '<:Z_Loner:659426661833637929>',
}
RESIST_LIST = [
    'body_armor_points',
    'head_armor_points',
    'heat_resistance',
    'electric_resistance',
    'chemical_resistance',
    'radiation_resistance',
    'psi_resistance'
]
HEAD_RESIST_LIST = [
    'chemical_resistance',
    'radiation_resistance',
    'psi_resistance'
]
BODY_RESIST_LIST = [
    'heat_resistance',
    'electric_resistance',
    'chemical_resistance',
    'radiation_resistance'
]
RESIST_EMOJIS = {
    'body_armor_points': '<:armor_res:1098957736961646612>',
    'head_armor_points': '<:helmet_res:1098960124397240392>',
    'heat_resistance': '<:fire_res:1098957710965362788>',
    'electric_resistance': '<:electicity_res:1098957740577136732>',
    'chemical_resistance': '<:chemical_res:1098957744121327666>',
    'radiation_resistance': '<:radiation_res:1098957742552658021>',
    'psi_resistance': '<:psl_res:1098957735627870309>',
}
EMOJIS = {
    'hp': '<:hp:1099433070198788176>',
    'psi_hp': '<:psihp:1099438702469591100>',
    'radiation': '<:radhp:1099435800111878297>',
    'money': '<:karbovanets:1099027246842400888>',
    'broken_armor': '<:brokenarmor:1099427325713592472>',
    'broken_helmet': '<:brokenhelmet:1099427323192807575>',
    'weight': '<:weight:1099698824739557416>',
    'modification_slots': '<:modification_slots:1101518584439636159>',
}
admin_ids = [
    311105854223024128,
    746744738044182588,
    459754079154077716
]
col = {
    'Голова': (613, 75),
    'Грудна клітина': (365, 271),
    'Тулуб': (365, 431),
    'Права рука': (25, 431),
    'Ліва рука': (705, 431),
    'Права нога': (123, 751),
    'Ліва нога': (603, 751),
}
armor_zones = ['Грудна клітина', 'Тулуб', 'Голова', 'Спина', 'Плечи']
debufs = {
    'Голова': (30, 50, 100),
    'Грудна клітина': (10, 20, 30),
    'Тулуб': (10, 20, 30),
    'Права рука': (5, 10, 20),
    'Ліва рука': (5, 10, 20),
    'Права нога': (5, 10, 20),
    'Ліва нога': (5, 10, 20),
}

fight_vision = {
    'Осліплений -ПРОВАЛ': -1000,  # temp
    'Темрява -30': -30,
    'Дим, туман -20': -20,
    'Сонце на фронті -20': -20,
    'Дим, туман -15': -15,
    'Слабке світло -10': -10,
    'Денне світло +10': 10,
    'Сонце за спиною +20': 20,
}
fight_conditions = {
    'Пригнічений вогнем -30': -30,
    'Ціль за укриттям -25': -25,
    'Ціль біжить -20': -20,
    'Ціль лежить -20': -20,
    'Ціль сидить -15': -15,
    'Ціль оглушена +20': 20,
    'Зненацька +30': 30
}
fight_distance = {
    'Стрілянина в рукопашну (1м) -20': -20,
    'Дистанція в упор (1-10м) +30': 30,
    'Коротка дистанція (10-50м) +20': 20,
    'Бойова дистанція (50-150м) +10': 10,
    'Дальня дистанція (150-500) -10': -10,
    'Екстремальна дистанція (500+) -30': -30
}
fight_shooting = {
    'Постріл із засідки +30': 30,
    'Поодинокий постріл +15': 15,
    'Здвоєний одиночний постріл +10': 10,
    'Стрілянина на придушення (фулавто весь магазин)': 0,
    'Коротка черга (3 патрони) -10': -10,
    'Довга черга (3-10 патронів) -20': -20,
    'Широка черга (10+ набоїв) -30': -30
}
fight_shooting_nums = {
    'Постріл із засідки +30': '1',
    'Поодинокий постріл +15': '1',
    'Здвоєний одиночний постріл +10': '2',
    'Стрілянина на придушення (фулавто весь магазин)': 'mag',
    'Коротка черга (3 патрони) -10': '3',
    'Довга черга (3-10 патронів) -20': '4-10',
    'Широка черга (10+ набоїв) -30': '11-20'
}

profs = {
    'Піхотинець': {'Штурмова гвинтівка': 20},
    'Штурмовик': {'Штурмова гвинтівка': 20, 'Пістолет': 10},
    'Єгер': {'Рушниця ': 15, 'Гвинтівки з поздовжньо-ковзним затвором': 10},
    'Коп': {'Пістолет-кулемет': 15, 'Пістолет': 10},
    'Марксман': {'DMR': 15, 'Штурмова гвинтівка': 10},
    'Снайпер': {'Гвинтівки з поздовжньо-ковзним затвором': 15, 'DMR': 10},
    'Високоточник': {'Гвинтівки з поздовжньо-ковзним затвором': 15, 'Крупнокаліберні гвинтівки': 10},
    'Кулеметник': {'Кулемет': 15, 'Штурмова гвинтівка': 10},
    'Гранатометник': {'Гранатомет': 15, 'Штурмова гвинтівка': 10},
    'Денний розвідник': {'Маскування': 15, 'Штурмова гвинтівка': 10},
    'Нічний розвідник': {'Маскування': 15, 'Робота з ПНБ': 10},
    'Оператор ПЗРК': {'ПЗРК': 30},
    'Оператор ПТКР': {'ПТКР': 30},
    'Сапер': {'Саперна справа': 30},
    'Зв\'язківець': {'Радіотехніка': 30},
    'Оператор БПЛА': {'БПЛА': 30, 'Робота з ПНБ': 10},
    'Командир відділення': {'Тактика': 15, 'Штурмова гвинтівка': 10, 'Лідерство': 5},
    'Старший': {'Лідерство': 20, 'Тактика': 5},
    'Збирач': {'Радіотехніка': 20, 'Тактика': 10, 'Маскування': 10},

}
fight_list = [
    'Пістолет',
    'Пістолет-кулемет',
    'Рушниця ',
    'Штурмова гвинтівка',
    'DMR',
    'Гвинтівки з поздовжньо-ковзним затвором',
    'Крупнокаліберні гвинтівки',
    'Кулемет',
    'Гранатомет',
    'ПЗРК',
    'ПТРК',
    'БПЛА',
]
weapon_list = [
    'Пістолет',
    'Пістолет-кулемет',
    'Рушниця ',
    'Штурмова гвинтівка',
    'DMR',
    'Гвинтівки з поздовжньо-ковзним затвором',
    'Крупнокаліберні гвинтівки',
    'Кулемет',
]
currencies = ['usd', 'eur', 'uah']
ammo_types = ['12/70', '20/70', '23x75 мм', '.357', '9x18 мм', '7.62x25мм', '9x19 мм', '.45', '9x21 мм', '5.7x28 мм',
              '4.6x30 мм', '9x39 мм', '.366', '5.45x39 мм', '5.56x45 мм', '7.62x39 мм', '7.62x51 мм', '7.62x54R',
              '.300', '.338 Lapua Magnum', '12.7x55 мм']
item_types = ['ammo', 'helmet', 'armor', 'weapon', 'item']

zoom_lst = [0.6, 1, 2, 6, 10, 16]
speed_lst = [1, 5, 10, 50, 100]
dic = {
    (-1, 0): '<:l_:1067167436069142589>',
    (1, 0): '<:r_:1067167440590614540>',
    (0, 1): '<:up:1067165279244787735>',
    (0, -1): '<:d_:1067167438535401503>',
    (1, 1): '<:rt:1067167434030723224>',
    (-1, 1): '<:lt:1067167431396700300>',
    (-1, -1): '<:ld:1067167429425365062>',
    (1, -1): '<:rd:1067167426376106136>'
}
modes = [
    'Оптимальний маршрут до точки зі списку',
    'Оптимальний маршрут до точки',
]
fails = {
    # Моб,   Так,   Мас
    (True, False, False): (["Ви рухались швидко, але це не допомогло. "
                            "Тактика ваша не була задовільною, а з тим і шум який ви створювали. "],
                           "Провал тактики і маскування."),
    (False, True, False): (["Ви підійшли до діла з розумом, але одного розуму мало."
                            "Занадто повільно, занадто помітно... "], "Провал мобільності і маскування."),
    (False, False, True): (["Ви зливались з тінню. Проте процес цей не є швидким. "
                            "Схоже обдуманим він теж не був..."], "Провал мобільності і тактики."),
    (False, False, False): (["Все пішло шкереберть!"], "Провал всіх перевірок."),
}
succes = {
    # Моб,   Так,   Мас
    (True, True, False): (["Швидко та хитро, дарма що шумно."], "Успіх мобільності і тактики. (Провал маскування)"),
    (False, True, True): (
        ["Повільно, але з розумом. І це головне."], "Успіх тактики і маскування. (Провал мобільності)"),
    (True, False, True): (["Швидкі як вітер, тихі як земля. Розумом теж зрівнянні з обома."],
                          "Успіх мобільності і маскування. (Провал тактики)"),
    (True, True, True): (["Ідеальна подорож!"], "Успіх всіх перевірок."),
}
lvlup_roles = [
    (1, 1136236798759145502),
    (2, 1136236797555380235),
    (3, 1136236796154478632),
    (4, 1136236795055575050),
    (5, 1136236793277190215),
    (6, 1136236792027304047),
    (7, 1136236790534123681),
    (8, 1136236789309390899),
    (9, 1136236787677798421),
    (10, 1136236786444677200),
]
wounds = [
    1054659696671342662,
    1054659802346836028,
    1054659985746968598,
]
zoned_wounds = {
    'Голова': 1054662029606146069,
    'Грудна клітина': 1057019676078637056,
    'Тулуб': 1054661393074364426,
    'Права рука': 1054661487274242161,
    'Ліва рука': 1054661487274242161,
    'Права нога': 1054661595789266966,
    'Ліва нога': 1054661595789266966,
}
mutants = {
    'Кабан': {
        'hp': 600,
        'prg': 30,
        'moves': {
            'Знайти по сліду': {
                'dice': (1, 100, 30),
                'desc': 'Кабан витрачає хід на пошук сліду жертви.',
            },
            'Відступ': {
                'dice': None,
                'desc': 'Кабан безперешкодно тікає, пробиваючи собі хід тараном.',
            }
        },
        'atacks': {
            'Таран (Шкода 1d80)': {
                'dice': (1, 80, 0),
                'desc': 'Кабан націлюється на противника, і у разі попадання збиває його з ніг, завдаючи шкоди кісткою (1d80). Противник втрачає один хід, щоб повернутися до бойової готовності.',

            },
            'Якірний удар (5d10)': {
                'dice': (5, 10, 0),
                'desc': 'Кабан мчить на жертву і зачіпає своїм гострим іклом її кінцівку, тим самим тягнучи її п\'ять метрів за собою по траєкторії свого удару. ',
            },
        }
    },
    'Сліпий пес': {
        'hp': 100,
        'prg': 40,
        'moves': {
            'Знайти по сліду': {
                'dice': (1, 100, 30),
                'desc': 'Псина витрачає хід на пошук сліду жертви.',
            },
            'Насторожений слух': {
                'dice': (1, 100, 20),
                'desc': 'Псина витрачає хід на пошук жертви за звуком.',
            }
        },
        'atacks': {
            'Рвати (Шкода 3d10)': {
                'dice': (3, 10, 0),
                'desc': 'Тварюка вчепляється в кінцівку жертві і завдає триразової шкоди, зчепившись із противником. Кожен хід, жертва кидає спаски володіння зброєю в його руках, щоб скинути тварюку з себе і перервати серію атак. Поки собака тримається за кінцівку, їй не потрібно кидати кістку влучення по меті, тільки кістку шкоди. Жертва кидає спаски на володіння зброєю в руках по порозі 40, щоб не втратити його з рук, у разі провалу - зброя в руках відлітає убік. ',
            },
        }
    },

}
