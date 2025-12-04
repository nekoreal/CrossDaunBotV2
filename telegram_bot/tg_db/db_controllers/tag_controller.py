
from ..import session_scope
from ..models.tg_teg import TelegramTag


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