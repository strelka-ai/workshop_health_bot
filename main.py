import telebot
from dialog import Dialog

token = '723314573:AAH5-onyzwyA1fMDnk73GLBQ7sE2a2j_qD4'

if __name__ == '__main__':
    bot = telebot.TeleBot(token=token)

    print(f'Your token is: {token}')
    print('Start pooling...')

    dialog_instance = Dialog(bot, {
        'voc': 'voc.yaml',
    })

    dialog_instance.start()
