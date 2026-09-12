
from sqlalchemy import func, select 
from typing import Optional
from ..import session_scope
from ..models.photo import Photo, Category 
import uuid 
from s3 import s3_client
import math

def generate_s3_key() -> str:  
    return uuid.uuid4().hex  

def find_category_by_name(category_name: str) -> dict | None:
    with session_scope() as session:
        category = session.query(Category).filter_by(name=category_name).first()
        if category:
            return category.to_dict()
        else:
            return None

def get_count_unsorted():
    with session_scope() as session:  # Замените на вашу логику получения сессии
        stmt = select(func.count(1)).where(Photo.category_id.is_(None))
        return session.scalar(stmt) or 0

def add_or_find_category(category_name: str, session_from_call) -> Category|dict|None:
    """Если передать сессию, вернется Category модель бд
       Если НЕ передать сессию вернется Category.dict()
       category_name не может быть чисто цифрами""" 
    if "/" in category_name:
        return None
    try:
        category_name=int(category_name)
        return None
    except:
        pass
    if session_from_call:
        return add_category_logic(category_name=category_name, session=session_from_call)
    with session_scope() as session: 
        return add_category_logic(category_name=category_name, session=session).to_dict()

def get_all_categories_names() -> list[str]:
    with session_scope() as session:
        results = (
            session.query( Category )    
            .all()
        ) 
        return [ category.name for category in results ] or None

def add_category_logic(category_name: str, session):
    category=(session.query(Category).filter_by(name=category_name).first())
    if  category :
        return category
    category = Category(name=category_name)
    session.add(category)
    session.flush()
    return category


def get_all_categories() -> list[tuple[str, int]]:
    with session_scope() as session:
        results = (
            session.query(
                Category.id,
                Category.name,
                func.count(Photo.id).label("photo_count"),
            )
            .outerjoin(Photo, Category.id == Photo.category_id)
            .group_by(Category.id, Category.name)
            .order_by(func.count(Photo.id).desc())  
            .all()
        )
 
        return [
            (f"{name} (ID {cat_id})", photo_count)
            for cat_id, name, photo_count in results
        ]

def get_all_categories_dict() :
    with session_scope() as session:
        results = (
            session.query(
                Category.id,
                Category.name,
                func.count(Photo.id).label("photo_count"),
            )
            .outerjoin(Photo, Category.id == Photo.category_id)
            .group_by(Category.id, Category.name)
            .order_by(func.count(Photo.id).desc())  
            .all()
        ) 
        return [
            {
                "category_id":cat_id,
                "name":name,
                "photo_count":photo_count
            }
            for cat_id, name, photo_count in results
        ]


def photo_urls_paginate(
    category_id: int,
    page: int = 1,
    limit: int = 32
) -> dict:
    """
    Возвращает список фотографий выбранной категории с presigned URL из S3,
    а также метаданные пагинации (total, pages_total и т.д.).
    """
    if page < 1:
        page = 1
    if limit < 1:
        limit = 25
    if limit > 64: 
        limit==64
    offset = (page - 1) * limit

    with session_scope() as session: 
        total = (
            session.query(func.count(Photo.id))
            .filter(Photo.category_id == category_id)
            .scalar() or 0
        ) 
        photos = (
            session.query(Photo)
            .filter(Photo.category_id == category_id)
            .order_by(Photo.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        ) 
        items = []
        for photo in photos:
            presigned_url = s3_client.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': s3_client.bucket_name,
                    'Key': photo.file_path
                },
                ExpiresIn=900   
            ) 
            items.append({
                "id": photo.id,
                "tg_id": photo.tg_id,
                "category_id": photo.category_id,
                "file_url": presigned_url
            }) 
        pages_total = math.ceil(total / limit) if total > 0 else 1 
        return {
            "total": total,
            "page": page,
            "limit": limit,
            "pages_total": pages_total,
            "items": items
        }
        

def add_photo(
        tg_id: int,
        file_bytes: bytes,
        category_name: str | None = None
) -> bool:
    with session_scope() as session: 
        if category_name is None:
            category_id = None
        else:
            category = add_or_find_category(category_name=category_name, session_from_call=session)
            if not category:
                session.rollback()
                return False
            category_id= category.id
        file_path = str(category_id) + "/" + generate_s3_key()
        photo = Photo(tg_id=tg_id, file_path=file_path, category_id=category_id)
        session.add(photo)
            
        if not s3_client.upload_file(file_bytes=file_bytes, file_path=file_path):
            session.rollback()
            return False 
        
        session.commit()
        return True


def move_photo_to_category(photo_id: int, category_name: str|None) -> bool:
    with session_scope() as session:
        photo = session.query(Photo).filter_by(id=photo_id).first()
        if not photo:
            return False
        category_id=None
        if  category_name: 
            category = add_or_find_category(category_name=category_name, session_from_call=session)
            category_id= category.id 

        photo.category_id = category_id
        old_file_path = photo.file_path
        new_file_path = str(category_id) + "/" + generate_s3_key()
        photo.file_path = new_file_path
        if not s3_client.move_file(old_file_path=old_file_path, new_file_path=new_file_path):
            session.rollback()
            return False

        session.commit() 
        return True

def delete_photo(photo_id: int) -> bool:
    with session_scope() as session:
        photo = session.query(Photo).filter_by(id=photo_id).first()
        if not photo:
            return False
        file_path = photo.file_path
        session.delete(photo)
        if not s3_client.delete_file(file_path=file_path):
            session.rollback()
            return False
        session.commit()
        return True


def get_photo_by_id(photo_id:int) -> dict:
    with session_scope() as session:
        photo = (
            session.query(Photo)
            .filter(Photo.id == photo_id)
            .first()
        )
        if not photo: return None
        photo_bytes = s3_client.download_file(photo.file_path)
        return {
                        "id": photo.id,
                        "tg_id": photo.tg_id,
                        "category": photo.category.name if photo.category else None,
                        "file_bytes": photo_bytes
                    } if photo_bytes else None

    
    
def get_random_photo(
        with_category: bool = True,
        category:str = None
) -> dict | None:
    with session_scope() as session: 
        if category:
            photo = (
                session.query(Photo)
                .join(Photo.category)
                .filter(Category.name == category)
                .order_by(func.random())
                .first()
            )
        elif with_category:
            photo = (
                session.query(Photo)
                .filter(Photo.category_id.is_not(None))
                .order_by(func.random())
                .first()
            )
        else:
            photo = (
                session.query(Photo)
                .filter(Photo.category_id.is_(None))
                .order_by(func.random())
                .first()
            )
        if photo:
            photo_bytes = s3_client.download_file(file_path=photo.file_path)
            return {
                "id": photo.id,
                "tg_id": photo.tg_id,
                "category": photo.category.name if photo.category else None,
                "file_bytes": photo_bytes
            }

 
def get_random_photo_url(
        with_category: bool = True
) -> str | None:
    with session_scope() as session:
        if with_category:
            photo = (
                session.query(Photo)
                .filter(Photo.category_id.is_not(None))
                .order_by(func.random())
                .first()
            )
        else:
            photo = (
                session.query(Photo)
                .filter(Photo.category_id.is_(None))
                .order_by(func.random())
                .first()
            )
        if photo:
            presigned_url = s3_client.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': s3_client.bucket_name,
                    'Key': photo.file_path
                },
                ExpiresIn=900   
            )
            return {
                        "id": photo.id,
                        "tg_id": photo.tg_id,
                        "category": photo.category.name if photo.category else None,
                        "file_url": presigned_url
                    } 
        else:
            return None