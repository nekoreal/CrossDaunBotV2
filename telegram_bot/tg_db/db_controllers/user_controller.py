from ..import session_scope
from ..models.tg_user import TelegramUser
from .at_user_tag_controller import create_at_user_tag


def get_user(tg_id):
    '''
    :param tg_id:
    :return:
    will create if not create
    '''
    with session_scope() as session:
        user = session.query(TelegramUser).filter_by(tg_id=tg_id).first()
        if user is None:
            user = TelegramUser(tg_id=tg_id)
            session.add(user)
            session.commit()
        return user.to_dict()

def get_user_tags_by_tg_id(tg_id):
    with session_scope() as session:
        user = session.query(TelegramUser).filter_by(tg_id=tg_id).first()
        return [at.tag.tag for at in user.at_user_tag]

def add_tag_to_user(user_id, tag_name):
    return create_at_user_tag(user_id=user_id, tag_name=tag_name)

