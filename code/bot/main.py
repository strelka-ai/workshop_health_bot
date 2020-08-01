import telebot
from dialog import Dialog
from database import db, init_tables, User, Session
from playhouse.shortcuts import model_to_dict, dict_to_model

token = '723314573:AAH5-onyzwyA1fMDnk73GLBQ7sE2a2j_qD4'

if __name__ == '__main__':
    bot = telebot.TeleBot(token=token)

    print('Connecting to DB...')

    db.connect(reuse_if_open=True)

    init_tables()

    dialog_instance = Dialog(bot, {
        'voc': 'voc.yaml',
    })

    User.insert(
        id=1,
        is_bot=False,
        first_name=1,
        last_name=1,
        username=1,
        language_code=1
    ).on_conflict(
        conflict_target=User.id,
        preserve=(User.id,),
        update={
            User.first_name: 1,
            User.last_name: 1,
            User.username: 1,
            User.language_code: 1
        }
    ).execute()

    Session.insert(
        chat_id=1,
        node_name='begin',
        tags={
            'a': 'b'
        }
    ).on_conflict(
        conflict_target=Session.chat_id,
        preserve=(Session.chat_id,),
        update={
            'node_name': 'end',
            'tags': {
                'c': 'd'
            }
        }
    ).execute()

    # Session.update(chat_id=1, tags={'aa': 'bb'}).execute()

    data = Session.get(chat_id=1)

    data.tags = {'a': '1'}
    data.save()

    print(data.tags)

    print(f'Your token is: {token}')
    print('Start pooling...')

    dialog_instance.start()

    db.close()
