import re
SHOOT_OPTIONS = [
    (
        True,
        [
            ('blinded', 'fail'),
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
words_str = """Осліплений -провал
Темрява -30
Дим, туман -20
Сонце на фронті -20
Сутінки -15
Слабке світло -10
Денне світло +10
Сонце за спиною +20
Пригнічений вогнем -30
Ціль за укриттям -25
Ціль біжить -20
Ціль лежить -20
Ціль сидить -15
Ціль оглушена +20
Зненацька +30
Стрілянина в рукопашну (1м) -20
Дистанція в упор (1-10м) +30
Коротка дистанція (10-50м) +20
Бойова дистанція (50-150м) +10
Дальня дистанція (150-500) -10
Екстремальна дистанція (500+) –30
Постріл із засідки +30
Поодинокий постріл +15
Здвоєний одиночний постріл +10
Стрілянина на придушення (фулавто весь магазин) -0
Коротка черга (3 патрони) -10
Довга черга (3-10 патронів) -20
Широка черга (10+ набоїв) -30
"""
words_str = words_str.split('\n')
ctr = 0
for x in SHOOT_OPTIONS:
    for y in x[1]:
        word = words_str[ctr]
        word = word[:word.rfind('-')][:word.rfind('+')]
        print(f'"{y[0]}": "{word}",')
        ctr += 1