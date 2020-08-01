import yaml
import time
import telebot
import random
import pymorphy2
from urllib.parse import urlparse
from peewee import PostgresqlDatabase
from database import Session, User, Chat, Message


def is_url(url: str):
    '''
    Фцункция, определяющая является ли данная строка URL

    :param url: собственно, строка
    :return: булево True | False
    '''

    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


class AbsNode(object):
    '''
    Это абстрактный класс, который описывает логику работы ноды
    - формирование вопроса
    - обработка ответов
    - реакцию на неверные ответы
    - и даже синтаксический разбор
    '''

    def __init__(self, dialog, message, node_name, node_config) -> None:
        '''
        Конструктор ноды
        :param dialog:
        :param message:
        :param node_name:
        :param node_config:
        '''

        super().__init__()
        self._dialog = dialog
        self._message = message
        self._name = node_name
        self._config = node_config.copy()

    @property
    def is_reset(self):
        '''
        Возвращает, является ли нода ресетом для сессии (удаляет все теги)
        :return:
        '''
        return self._config.get('reset', False)

    def _get_phrase(self, the_key='q'):
        '''
        Взять фразу из конфигурации
        :param the_key: ключ фразы, по умолчанию q -- вопрос
        :return: фраза
        '''

        phrase = self._config.get(the_key, None)

        # если фраз несколько, то берем на угад любую
        if isinstance(phrase, list):
            phrase = random.choice(phrase)

        return phrase

    def _get_answers(self):
        '''
        Взять все ответы ноды в виде списка
        :return: ответы
        '''
        answers = self._config.get('a', [])

        # если списка как такового нет, и сразу указан единственный ответ,
        # мы все равно превращаем его в список
        if not isinstance(answers, list):
            answers = [answers]

        return answers

    def _get_buttons(self, row_width=2):
        '''
        Построить кнопки в виде Telegram-клавиатуры
        :param row_width: ширина строки, по умолчанию 2 кнопки
        :return:
        '''

        message = self._message

        # специальный объект разметки, встраиваемая клавиатура
        markup = telebot.types.InlineKeyboardMarkup(row_width=row_width)

        # получаем ответы ноды
        answers = self._get_answers()

        markup_buttons = list()

        # пройдемся по ответам, пронумеровав их от 0 до N
        for i, a in enumerate(answers):

            if 'name' not in a:
                continue

            if not self._is_answer_visible(a):
                continue

            # если в GOTO указана ссылка, то сделаем специальную кнопку с внешней ссылкой
            if is_url(a['goto']):
                markup_buttons.append(telebot.types.InlineKeyboardButton(
                    text=a['name'],
                    url=a['goto']
                ))
            # если это просто кнопка, то создадим кнопку с
            else:
                payload = str(i)
                markup_buttons.append(telebot.types.InlineKeyboardButton(
                    text=a['name'],
                    callback_data=payload
                ))

        # добавляем кнопки в клавиатуру
        markup.add(*markup_buttons)

        return markup

    def _get_photo(self):
        '''
        Взять из ноды фото
        :return:
        '''
        return self._config.get('photo', None)

    def say(self):
        '''
        Сказать фразу от имени бота
        :param message: сообщение пользователя
        :return:
        '''

        message = self._message

        # собираем: фразу, фото, кнопки
        phrase = self._get_phrase()
        photo = self._get_photo()
        buttons = self._get_buttons()

        # страшно ругаемся если фразы нет
        if phrase is None:
            raise IndexError('No phrase in node {}'.format(self._name))

        # если есть фото, то это отдлеьный вид сообщения, где враза -- это подпись к фото
        if photo is not None:
            self._dialog.bot.send_photo(message.chat.id,
                                        photo=photo,
                                        caption=phrase,
                                        reply_markup=buttons)
        # иначе все штатно, шлём фразу
        else:
            self._dialog.bot.send_message(message.chat.id,
                                          text=phrase,
                                          reply_markup=buttons)

    def say_wrong(self):
        '''
        Сказать что-то на непредвиденный ответ пользователя
        :param message: сообщение пользователя
        :return:
        '''

        message = self._message

        phrase = self._get_phrase(the_key='wrong')

        if phrase is None:
            phrase = self._dialog.voc.get('wrong', None)

        if phrase is None:
            raise IndexError('No wrong phrase in node {}'.format(self._name))

        self._dialog.bot.send_message(message.chat.id, phrase)

    def save_tags(self, answer):
        '''
        Сохраняет тэги ответа в сессию пользователя
        :param answer:
        :return:
        '''

        if 'tags' not in answer:
            return

        tags = answer['tags']
        if not isinstance(tags, list):
            tags = [tags]

        self._dialog.save_tags(self._message.chat.id, tags)

    def get_tags(self):
        '''
        Возвращает все теги сессии пользователя
        :return:
        '''

        return self._dialog.get_tags(self._message.chat.id)

    def _is_answer_visible(self, answer):
        '''
        Проверяет условие "видимости" ответа, если оно логически верно -- то ответ видно
        :param answer:
        :return:
        '''
        if 'if' not in answer:
            return True

        def condition_check(condition):
            try:
                tags = self.get_tags()
                exec('condition_result = bool(' + condition + ')', tags)
                return tags['condition_result']
            except:
                return False

        return condition_check(answer['if'])

    def check_answer(self, data):
        '''
        Проверить, что же сказал пользователь, и отдать следующую ноду
        :param message: сообщение пользователя
        :param data: код кнопки, которую пользователь нажал
        :return: следующая нода или None
        '''

        message = self._message

        # берем все ответы
        answers = self._get_answers()

        # ходим по каждому из ответов
        for i, a in enumerate(answers):

            if not self._is_answer_visible(a):
                continue

            # если кнопка не нажата, ответ пользователя текстовый, и ответ ноды, как ни странно, тоже!
            # то смотрим, совпадает ли ответ морфологически
            if data is None and message.content_type == 'text' and 'words' in a:
                if self.match_words(words=a['words']):
                    self.save_tags(a)
                    return a['goto']

            # если нажали на пнопку
            if data is not None and i == int(data):
                self.save_tags(a)
                return a['goto']

            # если прислали некий тип данных, указанный в ответах (например, локация)
            if 'type' in a and a['type'] == message.content_type:
                self.save_tags(a)
                return a['goto']

        return None

    @staticmethod
    def fabric(dialog, message, node_name):
        '''
        Это фабрика нод, она умеет создавать ноды по имени
        :param dialog:
        :param message:
        :param node_name:
        :return:
        '''

        # берем конфигурацию ноды, выявляем ее тип
        node_config = dialog.get_node_config(node_name)
        node_type = node_config.get('type', 'plain')

        # ищем соответствующий класс ноды
        class_name = node_type.title() + 'Node'
        if class_name in globals():
            class_type = globals()[class_name]
            # возвращаем объект ноды
            return class_type(dialog, message, node_name, node_config)

        # ругаемся, если ничего не нашли
        raise IndexError(f'There is no node with type {node_type}')

    def match_words(self, words):
        '''
        Синтаксический анализатор, который сравнивает то что сказал пользователь с некими якорными словами
        :param message:
        :param words:
        :return:
        '''

        message = self._message

        # слова пользователя
        message_words = message.text.split(' ')

        # наши слова в ноде
        if not isinstance(words, list):
            answer_words = [words]
        else:
            answer_words = words

        # берем каждое слово в ответе ноды
        for aword in answer_words:

            # если мы находим квантор "любой ответ" то сразу же возвращаем goto этой ноды
            if aword == '*':
                return True

            # проверяем все слова в ответе пользователя
            for mword in message_words:
                a_morphs = self._dialog.morph.parse(aword.lower())
                b_morphs = self._dialog.morph.parse(mword.lower())

                # берем все формы слова в ответе ноды
                for aw in a_morphs:

                    # берем все формы слова в ответе пользователя
                    for bw in b_morphs:
                        # если слова совпали -- значит это тот самый ответ
                        if aw.normal_form == bw.normal_form:
                            return True
        return False


class PlainNode(AbsNode):
    '''
    Здесь будет логика, специфичная простой текстовой ноде
    '''
    pass


class VariantNode(AbsNode):
    '''
    Здесь будет логика, специфичная вариантам
    '''
    pass


class LocationNode(AbsNode):
    '''
    Здесь будет логика, специфичная геолокации
    '''
    pass


class Dialog(object):
    '''
    Класс, реализующий диалог чатбота
    '''

    def __init__(self, bot: telebot.TeleBot, config: dict) -> None:
        '''
        Конструктор класса диалога
        :param bot: объект бота pyTelegramBot
        :param config: словарь с конфигурацией
        '''

        super().__init__()

        self._bot = bot
        self._config = config.copy()
        self._voc = self._load_voc()
        self._variables = self._get_voc_tags()


        # здесь мы определяем ноду по умолчанию, с которой будем начинать
        # и на которую будем переходить в случае ошибки диалога
        self._default_node = self._voc.get('default', 'begin')

        # это библиотека морфологии, она нам нужна для морфоанализа слов
        self._morph = pymorphy2.MorphAnalyzer()

    @property
    def bot(self):
        return self._bot

    @property
    def voc(self):
        return self._voc

    @property
    def morph(self):
        return self._morph

    @property
    def variables(self):
        return self._variables

    def _get_voc_tags(self):
        '''
        Возвращает в качестве "переменных" диалога все возможные имена тэгов
        :return:
        '''
        variables = set()
        for node_name, node in self._voc['nodes'].items():
            answers = node.get('a', [])

            if not isinstance(answers, list):
                answers = [answers]

            for a in answers:
                tags = a.get('tags', [])

                if not isinstance(tags, list):
                    tags = [tags]

                variables.update(tags)

        return variables

    def _load_voc(self):
        '''
        Загружает словарь диалогов
        :return: словарь диалогов
        '''

        with open(self._config['voc'], 'r', encoding='utf-8') as f:
            return yaml.load(f, Loader=yaml.FullLoader)

    def get_session(self, chat_id):
        '''
        Берет текущую сессию чата, или возвращает None если ее нет
        :param chat_id: идентификатор чата
        :return: сессия (редуцирована до имени текущей ноды)
        '''

        return Session.get_or_none(chat_id)

    def new_session(self, chat_id, node_name=None, tags=None):
        '''
        Создает новую сессию
        :param chat_id:
        :param node_name:
        :param tags:
        :return:
        '''

        saving_tags = tags if tags is not None else dict()
        return Session.insert(
            node_name=node_name,
            chat_id=chat_id,
            tags=saving_tags
        ).on_conflict(
            conflict_target=Session.chat_id,
            preserve=(Session.chat_id,),
            update={
                Session.node_name: node_name,
                Session.tags: saving_tags
            }
        ).execute()

    def get_tags(self, chat_id):
        '''
        Возвращает все теги сессии диалога, даже те которые еще не отыграли: они будут с нулевыми значениями
        :param chat_id:
        :return:
        '''
        sess = self.get_session(chat_id)

        if sess is None:
            tags = {}
        elif sess.tags is None:
            tags = {}
        else:
            tags = sess.tags

        return {
            v: tags[v] if v in tags else 0
            for v in self._variables
        }

    def save_tags(self, chat_id, tags):
        '''
        Сохраняет все указанные теги в сессию
        :param chat_id:
        :param tags:
        :return:
        '''

        sess = Session.get_or_none(chat_id)
        if sess is None:
            self.new_session(chat_id)
            sess = Session.get_or_create(chat_id)
            sess_tags = {}
        else:
            sess_tags = sess.tags

        if sess_tags is None:
            sess_tags = dict()

        sess_tags.update({
            t: sess_tags[t] + 1 if t in sess_tags else 1
            for t in tags
        })

        sess.tags = sess_tags
        sess.save()

    def _play_node(self, message, node_name):
        '''
        Отыгрывает ноду, то есть пишет от имени бота ее вопрос / картинку / клавиатуру
        :param message: сообщение pyTelegramBot
        :param node_name: имя ноды
        :return: ничего
        '''

        node = AbsNode.fabric(self, message, node_name)
        node.say()

        sess = Session.get_or_none(chat_id=message.chat.id)
        if sess is None:
            self.new_session(
                chat_id=message.chat.id,
                node_name=node_name
            )
        else:
            sess.node_name = node_name
            if node.is_reset:
                sess.tags = dict()

            sess.save()

    def _play_begin(self, message):
        '''
        Отыгрывает начало общения
        :param message:
        :return:
        '''

        if message.from_user.is_bot:
            return

        User.insert(
            **message.json['from']
        ).on_conflict('ignore').execute()

        Chat.insert(
            id=message.chat.id,
            type=message.chat.type,
            user_id=message.from_user.id
        ).on_conflict('ignore').execute()

        self._play_node(message, self._default_node)

    def _save_message(self, message, data):
        '''
        Сохранение сообщения пользователя в БД
        :param message: сообщение
        :param data: код кнопки
        :return:
        '''

        content_type = message.content_type
        if content_type == 'text':
            content_type = 'plain'
        elif data is not None:
            content_type = 'variant'

        Message.insert(
            id=message.message_id,
            chat_id=message.chat.id,
            type=content_type,
            date=message.date,

            text=message.text,
            button=data,
            location=message.json.get('location', None)
        ).on_conflict('ignore').execute()

    def _dialog(self, message, data=None):
        '''
        Основной алгоритм ведения диалогов
        :param message: сообщение pyTelegramBot
        :param data: код нажатой кнопки
        :return: ничего
        '''

        # отправляем пользователю мета-сообщение "Бот печатает..."
        self._bot.send_chat_action(message.chat.id, 'typing')

        self._save_message(message, data)

        # попытаемся взять текущую ноду для данного чата
        the_session = Session.get_or_none(chat_id=message.chat.id)

        # если диалога еще нет, то идем в самое начало
        if the_session is None or the_session.node_name is None:
            self._play_begin(message)
            return

        try:

            current_node = AbsNode.fabric(self, message, the_session.node_name)

            # проверяем ответ пользователя, и определяемся со следующей нодой
            next_node = current_node.check_answer(data)

            # если нода не смогла определиться, то, скорее всего, это ошибка,
            # а значит идем в начало
            if next_node is None:
                current_node.say_wrong()
                return

            # отыгрываем следующую ноду
            self._play_node(message, next_node)

        # в случае возникновения ошибки в коде
        except (AttributeError, IndexError, KeyError, ValueError) as e:
            import traceback

            # показываем в консоли эту ошибку, чтобы мы понимали что произошло
            print(e)
            print(traceback.format_exc())

            # отыгрываем текущую ноду еще раз
            self._play_node(message, self._default_node)

    def _attach_handlers(self):
        '''
        Добавляет нашу реакцию (ведение диалога) на события чат-бота
        :return:
        '''

        # реакция на текстовые сообщения
        @self._bot.message_handler(content_types=['text', 'location'])
        def text_handler(message):
            self._dialog(message=message)

        # реакция на нажатие кнопки
        @self._bot.callback_query_handler(func=lambda call: True)
        def callback_inline(call):
            self._dialog(message=call.message, data=call.data)

    def get_node_config(self, node_name):
        '''
        Возвращает конфигурацию указанной ноды
        :param node_name: имя ноды
        :return: конфигурация
        '''

        return self._voc['nodes'][node_name]

    def start(self):
        '''
        Запускаем вселенную!
        :return:
        '''

        # привязываем обработчики событий
        self._attach_handlers()

        # запускаем бота обработчики событий
        self._bot.polling()
