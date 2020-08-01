from peewee import PostgresqlDatabase, Model, PrimaryKeyField, TextField, DoubleField, IntegerField


db = PostgresqlDatabase(
    'chatbot',
    user='postgres',
    password='MwSVez5TRE0qidnz',
    host='localhost'
)


class BaseModel(Model):
    class Meta:
        database = db


class User(BaseModel):
    id = PrimaryKeyField(null=False)
    name = CharField(max_length=100)

    created_at = DateTimeField(default=datetime.datetime.now())
    updated_at = DateTimeField(default=datetime.datetime.now())

    class Meta:
        db_table = "categories"
        order_by = ('created_at',)