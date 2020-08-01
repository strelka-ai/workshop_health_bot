import os
import telebot
from dialog import Dialog
from database import db, init_tables
from dotenv import load_dotenv, dotenv_values
from threading import Thread

from sanic import Sanic
from sanic.response import json


class Bot(Thread):
    worker_count = 0

    def __init__(self) -> None:
        super().__init__()

        Bot.worker_count += 1

        self.setDaemon(True)
        self.setName('Bot %s' % Bot.worker_count)

    def run(self):
        load_dotenv()

        config = {
            **dict(dotenv_values()),
            **dict(os.environ),
        }

        token = config['TOKEN']
        bot = telebot.TeleBot(token=token)

        print('Connecting to DB...')

        db.connect(reuse_if_open=True)

        init_tables()

        dialog_instance = Dialog(bot, {
            'voc': config['VOC_FILE'],
        })

        print(f'Your token is: {token}')
        print('Start pooling...')

        dialog_instance.start()

        db.close()


app = Sanic("hello_example")


@app.route("/")
async def test(request):
    return json({"hello": "world"})

if __name__ == '__main__':
    bot = Bot()
    bot.start()

    app.run(host="0.0.0.0", port=80)