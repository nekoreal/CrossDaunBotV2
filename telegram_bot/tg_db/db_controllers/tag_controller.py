
from ..import session_scope
from ..models.tg_teg import TelegramTag
from .. models.tg_at_user_tag import UserTagAssociation
from .. import session_scope


def get_tag(tag_name:str, create:bool=True) -> TelegramTag|None:
    '''
    :param create:
    :param tag_name:
    :return:
    will create if not create
    '''
    with session_scope() as session:
        tag = session.query(TelegramTag).filter_by(tag=tag_name).first()
        if tag is None:
            if create:
                tag = TelegramTag(tag=tag_name)
                session.add(tag)
                session.commit()
            else:
                return None
        return tag.to_dict()

from sqlalchemy import func

from sqlalchemy import func

def get_tags_with_user_counts(session):
    results = session.query(
        TelegramTag.tag,
        func.count(UserTagAssociation.user_id)
    ).outerjoin(UserTagAssociation, TelegramTag.id == UserTagAssociation.tag_id
    ).group_by(TelegramTag.id).all()
    return results

def delete_unused_tags(session):
    """
    Удаляет все теги, которые не связаны ни с одним пользователем.
    """
    unused_tags = session.query(TelegramTag).outerjoin(UserTagAssociation).filter(
        UserTagAssociation.user_id == None
    ).all()

    count = 0
    for tag in unused_tags:
        session.delete(tag)
        count += 1
    session.commit()
    return count


