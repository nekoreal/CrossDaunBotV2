from sqlite3 import IntegrityError

from ..import session_scope
from ..models.tg_at_user_tag import UserTagAssociation
from ..models.tg_user import TelegramUser
from .tag_controller import get_tag

from ..models.tg_teg import TelegramTag


def create_at_user_tag(user_id, tag_name:str):
    '''
    :param user_id:
    :param tag_name:
    :return:
    '''
    try:
        with session_scope() as session:
            tag = session.query(TelegramTag).filter_by(tag=tag_name).first()
            if tag is None:
                tag = TelegramTag(tag=tag_name)
                session.add(tag)
            if session.query(UserTagAssociation).filter_by(user_id=user_id, tag_id=tag.id).first():
                return f"Связь {tag_name} уже есть"
            at_user_tag = UserTagAssociation(user_id=user_id, tag_id=tag.id)
            session.add(at_user_tag)
    except Exception as e:
        return "Неверные данные"
    return f"Связь {tag_name} была создана"

def delete_at_user_tag(user_id, tag_name:str):
    try:
        with session_scope() as session:
            tag = session.query(TelegramTag).filter_by(tag=tag_name).first()
            if tag is None:
                tag = TelegramTag(tag=tag_name)
                session.add(tag)
            if session.query(UserTagAssociation).filter_by(user_id=user_id, tag_id=tag.id).delete():
                return f"Связь {tag_name} удалена"
            return "Такой связи нету"
    except Exception as e:
        return "Ошибка удаления"

