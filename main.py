import os
import telebot
from dialog import Dialog
from database import db, init_tables
from dotenv import load_dotenv, dotenv_values


if __name__ == '__main__':
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
