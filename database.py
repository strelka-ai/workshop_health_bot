import os
import datetime
from peewee import PostgresqlDatabase, Model, PrimaryKeyField, TextField, \
    DoubleField, IntegerField, BooleanField, DateTimeField, BareField

from playhouse.postgres_ext import PostgresqlExtDatabase, JSONField, BinaryJSONField
from dotenv import load_dotenv, dotenv_values

load_dotenv()

config = {
    **dict(dotenv_values()),
    **dict(os.environ),
}

# соединение с БД
db = PostgresqlExtDatabase(
    config['POSTGRES_DB'],
    user=config['POSTGRES_USER'],
    password=config['POSTGRES_PASSWORD'],
    host=config['DB_HOST'],
    autocommit=True,
    autorollback=True
)


class BaseModel(Model):
    '''
    Базовый класс моделей
    '''

    class Meta:
        database = db


class User(BaseModel):
    '''
    Модель пользователя
    '''

    id = PrimaryKeyField(null=False)
    is_bot = BooleanField(null=True)
    first_name = TextField(null=True)
    last_name = TextField(null=True)
    username = TextField(null=True)
    language_code = TextField(null=True)
    ts = DateTimeField(default=datetime.datetime.now)

    class Meta:
        db_table = "user"


class Chat(BaseModel):
    '''
    Модель чата
    '''

    id = PrimaryKeyField(null=False)
    type = TextField(null=True)
    user_id = IntegerField()

    class Meta:
        db_table = "chat"


class Session(BaseModel):
    '''
    Модель сессии
    '''

    chat_id = PrimaryKeyField(null=False)
    node_name = TextField(null=True)
    ts = DateTimeField(default=datetime.datetime.now)
    tags = BinaryJSONField(null=True)

    class Meta:
        db_table = "session"


class Message(BaseModel):
    '''
    Модель сообщений
    '''

    id = PrimaryKeyField(null=False)
    chat_id = IntegerField()
    type = TextField(null=True)
    date = IntegerField(null=True)

    text = TextField(null=True)
    button = TextField(null=True)
    location = BinaryJSONField(null=True)

    class Meta:
        db_table = "message"


def init_tables():
    '''
    Инициализация моделей
    :return:
    '''

    User.create_table()
    Chat.create_table()
    Session.create_table()
    Message.create_table()
