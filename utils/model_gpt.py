from openai import OpenAI
from random import randint as rnd
from config import MODEL_AI_API_KEY
client = OpenAI(
    base_url="https://api.langdock.com/openai/eu/v1",
    api_key=MODEL_AI_API_KEY,
)

def askgpt(text='Hello',maxt=300):
    completion = client.chat.completions.create(
        model='gpt-5.1',
        messages=[ {"role":"user", "content":text} ],
        max_completion_tokens=maxt
    )
    return  (completion.choices[0].message.content)

def dialoggpt(text='Hello', sender='Андрей' ):
    obraz=['аниме кошкадевочка','яндере тян','цундере тян','быдло','деревенщина', 'истиричная женщина','зануда, который всех поправляет' ]
    nobraz=obraz[rnd(0,len(obraz)-1)]
    s=(f'Идет диалог в беседе. Ты в образе {nobraz}  {"и говоришь на старо словянском языке" if rnd(0,5)==3 else ''}  , ты должен отвечать следуя образу, образ должен прослеживаться в твоем сообщении. '
       f'Вот последнее сообщение в диалоге {text} от человека по имени {sender}.'
       f' Ты должен как-то влиться в диалог.{"Обязательно добавь маты. Минимум 3 мата" if rnd(0,1) else ""}' )
    if rnd(0,10)==6:
        s=(f"Ты политический руководитель красной армии и стоишь перед ротой тупых солдат, которые должны отправиться в бой. "
           f"Ты услашал разговор в строю. Солдат{sender} сказал: {text}. Обьясни им простым языком "
           f"марксистко-ленинистких позиций о необходимости этого боя. Обязательно добавь маты")
    completion = client.chat.completions.create(
        model='gpt-4.1',
        messages=[ {"role":"user", "content":s} ]
    )
    return  (completion.choices[0].message.content)

