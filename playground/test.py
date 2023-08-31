
    @app_commands.command(description='arena')
    async def arena(self, i: discord.Interaction, team1: int, team2: int):
        client = gspread.service_account('credentials.json')

        spreadsheet = client.open_by_url('https://docs.google.com/spreadsheets/d/1e_ddEVXHCxGBHXT5U8PGAW5nxGdusDs5PrGWv7eIi7E/edit?usp=sharing')
        sheet = spreadsheet.worksheet('Sheet1')
        team1_data, team1_name = [], ''
        team1_name = sheet.cell(2 + (team1 - 1) * 3, 1).value
        raw_data = sheet.get_values(f'B{2 + (team1 - 1) * 3}:G{4 + (team1 - 1) * 3}')
        for x in raw_data:
            team1_data.append(
                {'name': x[0], 'health': int(x[1]), 'shooting': int(x[2]), 'damage': int(x[3]), 'evasion': int(x[4]), 'initiative': int(x[5]),
                 'team': 1})
        team2_data, team2_name = [], ''
        raw_data2 = sheet.get_values(f'B{2 + (team2 - 1) * 3}:G{4 + (team2 - 1) * 3}')
        team2_name = sheet.cell(2 + (team2 - 1) * 3, 1).value
        for x in raw_data2:
            team2_data.append(
                {'name': x[0], 'health': int(x[1]), 'shooting': int(x[2]), 'damage': int(x[3]), 'evasion': int(x[4]), 'initiative': int(x[5]),
                 'team': 2})
        await i.response.send_message(content='arena', view=ArenaView(i.user.id, team1_name, team1_data, team2_name, team2_data))
        await i.followup.send(content='Подождите, идёт подготовка арены')
        # await asyncio.sleep(1)


class ArenaView(View):
    async def interaction_check(self, interaction: discord.Interaction, /):
        return interaction.user.id == self.uid

    def __init__(self, uid, team1_name, team1, team2_name, team2):
        super().__init__(timeout=None)
        self.uid = uid
        self.team1_name = team1_name
        self.team1 = team1
        # team1 = [{'name': 'name1', 'health': 1, 'shooting': 1, 'damage': 1, 'evasion': 0, 'initiative': 0, 'team': 1},
        #         {'name': 'name2', 'health': 1, 'shooting': 1, 'damage': 1, 'evasion': 0, 'initiative': 0, 'team': 1},
        #         {'name': 'name3', 'health': 1, 'shooting': 1, 'damage': 1, 'evasion': 0, 'initiative': 0, 'team': 1}]

        self.team2_name = team2_name
        self.team2 = team2
        self.round_number = 1
        self.stage = 0
        self.chosen_char = None
        self.target = None

    @discord.ui.button(label='Далее', style=discord.ButtonStyle.green)
    async def next(self, i: discord.Interaction, button: discord.ui.Button):
        if self.stage:
            # (1) Броски инициативы - стреляет этот тип
            # (2) Бросок на выбор цели - этот тип стреляет по этой цели
            # (3) Бросок на выстрел vs уклонение - этот тип попал/не попал
            # (4) Бросок на урон - этот тип нанес столько-то урона (и убил)
            # (5) Вернись на пункт 1
            # (1) Каждый боец бросает дайс [1d10] к которому прибавляется его бонус инициативы, полученный до начала боя.
            # Боец с наиболее высоким итоговым значением стреляет в этом раунде боя.
            st = ''
            match self.stage:
                case 1:
                    initiative_list = []
                    max_initiative = 0
                    for char in self.team1 + self.team2:
                        initiative = random.randint(1, 10) + char['initiative_bonus']
                        initiative_list.append({'name': char['name'], 'initiative': initiative, 'team': char['team']})
                        if initiative > max_initiative:
                            max_initiative = initiative
                        st += f"{char['name']} получил {initiative}[({initiative - char['initiative_bonus']})1d10 + {char['initiative_bonus']}] инициативы\n"
                    new = []
                    for n, char in enumerate(initiative_list):
                        if char['initiative'] == max_initiative:
                            new.append(char)
                    initiative_list = new
                    chosen_char = random.choice(initiative_list)
                    if chosen_char['team'] == 1:
                        for char in self.team1:
                            if char['name'] == chosen_char['name']:
                                chosen_char = char
                                break
                    else:
                        for char in self.team2:
                            if char['name'] == chosen_char['name']:
                                chosen_char = char
                                break

                    st += f"\n{chosen_char['name']} стреляет в этом раунде боя\n"
                    self.chosen_char = chosen_char
                    self.stage += 1
                case 2:
                    # (2) Кидается дайс на выбор цели для выстрела бойца. На этот дайс ничего не влияет, это строго рандом: d2 или d3 - в зависимости от того,
                    # сколько осталось бойцов в команде противника
                    if self.chosen_char['team'] == 1:
                        self.target = random.choice(self.team2)
                    else:
                        self.target = random.choice(self.team1)
                    st += f"{self.chosen_char['name']} выбрал целью {self.target['name']}\n"
                    self.stage += 1
                case 3:
                    # (3) После того, как цель выстрела выбрана - совершается встречная проверка [Стрельба] vs [Уклонение].
                    # При равенстве побеждает уклоняющаяся сторона.
                    shooting = 0
                    for _ in range(self.chosen_char['shooting']):
                        shooting += random.randint(1, 6)
                    evasion = 0
                    for _ in range(self.target['evasion']):
                        evasion += random.randint(1, 6)
                    if shooting > evasion:
                        st += f"{self.chosen_char['name']} попал в {self.target['name']} (стрельба {shooting} > {evasion} уклонение)"
                        self.stage += 1
                    else:
                        st += f"{self.chosen_char['name']} промахнулся по {self.target['name']} и не нанес урона. Стрельба {shooting} <= {evasion} уклонение"
                        self.round_number += 1
                        self.stage = 1
                        if self.round_number > 20:
                            st += '\nВремя убивает\n'
                            for char in self.team1 + self.team2:
                                char['hp'] -= 1
                                if char['hp'] <= 0:
                                    if char['team'] == 1:
                                        self.team1.remove(char)

                                    else:
                                        self.team2.remove(char)

                case 4:
                    # (4) В случае, если выстрел оказался успешным - стреляющий кидает свой [Урон].
                    # Результат броска вычитается из очков здоровья цели. Если очки здоровья цели обнулились - цель считается выбитой из боя.
                    damage = 0
                    for _ in range(self.chosen_char['damage']):
                        damage += random.randint(1, 6)
                    st += f"И нанес {damage}[{self.chosen_char['damage']}d6] урона\n"
                    self.target['hp'] -= damage
                    if self.target['hp'] <= 0:
                        st += f"{self.target['name']} выбит из боя\n"
                        if self.target['team'] == 1:
                            for char in self.team1:
                                if char['name'] == self.target['name']:
                                    self.team1.remove(char)
                                    break
                        else:
                            for char in self.team2:
                                if char['name'] == self.target['name']:
                                    self.team2.remove(char)
                                    break
                    else:
                        st += f"{self.target['name']} осталось {self.target['hp']} очков здоровья\n"
                    self.round_number += 1
                    self.stage = 1
                    if self.round_number > 20:
                        st += '\nВремя убивает\n'
                        for char in self.team1 + self.team2:
                            char['hp'] -= 1
                            if char['hp'] <= 0:
                                if char['team'] == 1:
                                    self.team1.remove(char)

                                else:
                                    self.team2.remove(char)

                # (5) Если в каждой из команд осталось хотя бы по одному игроку - вернись в начало.
            await i.response.edit_message(content=f'{self.get_str(st)}')
            if len(self.team1) == 0 and len(self.team2) == 0:
                await i.followup.send(content=f"Ничья")
                await i.message.edit(view=None)
            elif len(self.team1) == 0:
                await i.followup.send(content=f"Команда {self.team2_name} победила")
                await i.message.edit(view=None)
            elif len(self.team2) == 0:
                await i.followup.send(content=f"Команда {self.team1_name} победила")
                await i.message.edit(content=self.get_str(st))
        else:
            await i.response.edit_message(content=f'')
            # (1) Каждый боец, участвующий в бою, прокидывает свою характеристику [Здоровье]. Результат броска умножается на [2]. Итоговый результат равен количеству очков здоровья каждого бойца на этот бой.
            st = ''
            st += 'Подсчитываю очки здоровья\n'
            for char in self.team1 + self.team2:
                hp = 0
                for _ in range(char['health']):
                    hp += random.randint(1, 6)
                hp *= 2
                st += f"{char['name']} получил {hp}[{char['health']}d6 * 2] очков здоровья\n"
                char['hp'] = hp
                char['max_hp'] = hp
            # (2) Каждый боец, участвующий в бою, прокидывает свою характеристику [Инициатива], результат броска делится на [4] с округлением вверх.
            # Итоговый результат равен бонусу на бросок инициативы, который совершается в каждом раунде (подробнее - ниже).
            st += '\nПодсчитываю бонусы инициативы\n'
            for char in self.team1 + self.team2:
                initiative_buff = 0
                for _ in range(char['initiative']):
                    initiative_buff += random.randint(1, 6)
                initiative_buff = math.ceil(initiative_buff / 4)
                if initiative_buff:
                    st += f"{char['name']} получил {initiative_buff}[{char['initiative']}d6 / 4] бонус инициативы\n"
                char['initiative_bonus'] = initiative_buff
            await i.followup.send(content=st)
            self.stage = 1

    def get_str(self, action=''):
        st = 'Раунд ' + str(self.round_number) + '\n'
        st += f"Команда {self.team1_name}:\n"
        for char in self.team1:
            st += f"{char['name']} {char['hp']}/{char['max_hp']}HP\n"
        st += f"\nКоманда {self.team2_name}:\n"
        for char in self.team2:
            st += f"{char['name']} {char['hp']}/{char['max_hp']}HP\n"
        st += f"\n{action}\n"

        return st

