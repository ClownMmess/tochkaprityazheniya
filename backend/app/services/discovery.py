"""Fast autocomplete and rotating ideas grounded in the currently available catalogue."""
import random
import re
from collections import Counter
from sqlalchemy import select,func
from app.models import Event,Category,TrackedEvent,Occurrence
from app.services.catalog import query_occurrences,unique_events,warm,card,preferences,ranking
from app.services.locations import CITIES
from app.integrations.llm.fallback import correct_text,parse_fallback

IDEAS=[
 ('Смеяться весь вечер','Хочу на стендап','stand-up'),
 ('Стендап до 1500 ₽','Стендап до 1500 на человека','stand-up'),
 ('Концерт с друзьями','Нас 5 человек, хотим на концерт','concert'),
 ('На живой звук','Хочу на концерт','concert'),
 ('Музыка на выходных','Концерты в выходные','concert'),
 ('Театральный вечер','Хочу в театр','theater'),
 ('Спектакль вдвоём','Театр со второй половинкой','theater'),
 ('Театр до 2000 ₽','Театр до 2000 на человека','theater'),
 ('Свидание в музее','В музей со второй половинкой','museum'),
 ('Открыть новый музей','Хочу в музей','museum'),
 ('Заглянуть на выставку','Хочу на выставку','exhibition'),
 ('Искусство вдвоём','Выставки вдвоём','exhibition'),
 ('Поход в кино','Хочу в кино','cinema'),
 ('Кино на выходных','Кино в выходные','cinema'),
 ('Уютное антикафе','Хочу в антикафе','anticafe'),
 ('Антикафе компанией','Нас 5 человек, хотим в антикафе','anticafe'),
 ('Настолки с друзьями','Хочу в антикафе или на настольные игры','anticafe'),
 ('Прогуляться по парку','Хочу в парк','park'),
 ('Парки вдвоём','Парки со второй половинкой','park'),
 ('Красивые места города','Достопримечательности','landmark'),
 ('Посмотреть архитектуру','Достопримечательности и усадьбы','landmark'),
 ('На ярмарку','Хочу на ярмарку','fair'),
 ('Маркеты на выходных','Ярмарки в выходные','fair'),
 ('Новые впечатления','Хочу на аттракционы','amusement'),
 ('Аттракционы вдвоём','Аттракционы со второй половинкой','amusement'),
 ('Увидеть город иначе','Хочу на экскурсию','tour'),
 ('Экскурсия компанией','Нас 5 человек, хотим на экскурсию','tour'),
 ('Сделать своими руками','Хочу на мастер-класс','education'),
 ('Узнать что-то новое','Хочу на лекцию','education'),
 ('День с детьми','Мероприятия для детей','kids'),
 ('На фестиваль','Хочу на фестиваль','festival'),
 ('Выбраться на матч','Хочу на спортивное событие','sport'),
 ('Приключение в квесте','Хочу на квест','quest'),
 ('Вечеринка с друзьями','Хочу на вечеринку','party'),
 ('В цирк','Хочу в цирк','circus'),
]
MUSIC=[('Рэп / хип-хоп','Хочу на рэп концерт','hip-hop'),('Послушать джаз','Хочу на джазовый концерт','jazz'),('Рок-концерт','Хочу на рок концерт','rock'),('Классика вживую','Концерт классической музыки','classical'),('Инди-настроение','Инди концерт','indie'),('Любимые поп-песни','Концерт поп-музыки','pop')]

def discovery(s,city,nearby,user_id,seed):
    rows=unique_events(s,query_occurrences(s,city=city,include_nearby=nearby));cache=warm(s,rows,user_id)
    counts=Counter(s.get(Category,cache['events'][o.event_id].category_id).slug for o in rows)
    genres={g.slug for o in rows for g in cache['genres'][o.event_id]}
    candidates=[{'label':label,'text':text} for label,text,category in IDEAS if counts[category]]
    candidates += [{'label':label,'text':text} for label,text,genre in MUSIC if genre in genres]
    if any(o.is_free for o in rows):candidates += [{'label':'Без трат','text':'Бесплатно'},{'label':'Бесплатно на выходных','text':'Бесплатно в выходные'}]
    candidates += [{'label':'В эти выходные','text':'В эти выходные'},{'label':'Вдвоём до 3000 ₽','text':'Вдвоём до 3000 рублей'},{'label':'Планы на вечер','text':'На вечер'}]
    rng=random.Random(str(seed)+city);rng.shuffle(candidates)
    p=preferences(s,user_id) if user_id else {}
    popularity=dict(s.execute(select(Occurrence.event_id,func.count(TrackedEvent.user_id.distinct())).join(TrackedEvent,TrackedEvent.occurrence_id==Occurrence.id).where(TrackedEvent.status=='active').group_by(Occurrence.event_id)).all())
    shuffled=rows[:];rng.shuffle(shuffled)
    # Real in-app saves only. No borrowed or invented external popularity rank.
    shuffled.sort(key=lambda o:(popularity.get(o.event_id,0),ranking(s,o,p)[0]),reverse=True)
    selected=[];used=set()
    for o in shuffled:
        cat=cache['events'][o.event_id].category_id
        if cat in used:continue
        selected.append(o);used.add(cat)
        if len(selected)==4:break
    return {'ideas':candidates,'highlights':[card(s,o,user_id) for o in selected],
            'highlight_label':'Выбирают в «Точке притяжения»' if selected and all(popularity.get(o.event_id,0)>0 for o in selected) else 'Вдохновение рядом'}

def autocomplete(text,city,categories,today,nearby=False):
    intent=parse_fallback(text,city,today,categories);intent.include_nearby=nearby
    clean=text.strip();corrected=correct_text(clean);suggestions=[]
    def add(label,value):
        if value.casefold()!=clean.casefold() and value not in {v['text'] for v in suggestions}:
            suggestions.append({'label':label,'text':value})
    if corrected.casefold()!=clean.casefold():add(corrected,corrected)
    last=re.search(r'[а-яё-]+$',clean.casefold())
    if last and len(last[0])>=2:
        for word in ['концерт','стендап','антикафе','музей','театр','выставка','ярмарка','экскурсия','аттракционы','бесплатно','вдвоём','завтра']:
            if word.startswith(last[0]) and word!=last[0]:
                value=clean[:last.start()]+word;add(value,value)
    if not clean:
        for label,value in [('Концерт с друзьями','Нас 5 человек, хотим на концерт'),('В музей со второй половинкой','В музей со второй половинкой'),('Уютное антикафе','Хочу в антикафе'),('Бесплатные события','Бесплатно')]:add(label,value)
    else:
        if not intent.categories and not intent.performers and not intent.keywords:
            for label,value in [('Концерт','хочу на концерт'),('Музей','хочу в музей'),('Антикафе','хочу в антикафе')]:
                add('Выбрать формат: '+label,corrected.rstrip('., ')+', '+value)
        if re.search(r'\bдо\s*\d*\s*$',clean):
            base=re.sub(r'\bдо\s*\d*\s*$','',clean)
            for amount in [1000,2000,3000]:add(f'До {amount} ₽ на человека',base+f'до {amount} на человека')
            return {'intent':intent.model_dump(mode='json'),'suggestions':suggestions[:7]}
        if re.search(r'\bнас\s*\d*\s*$',clean):
            base=re.sub(r'\bнас\s*\d*\s*$','',clean)
            for count in [2,3,5]:add(f'{count} человек',base+f'нас {count} человек')
            return {'intent':intent.model_dump(mode='json'),'suggestions':suggestions[:7]}
        base=corrected.rstrip('., ')
        if not intent.date_from:
            add('Добавить: завтра',base+', завтра');add('Добавить: в выходные',base+', в выходные')
        if intent.budget_total is None and intent.budget_per_person is None and not intent.free_only:
            add('Бюджет: до 2000 ₽ на человека',base+', до 2000 на человека')
        if intent.party_size==1:add('Компания: 5 человек',base+', нас 5 человек')
        if intent.categories==['concert'] and not intent.interest_categories:
            add('Музыка: рэп / хип-хоп',base+', рэп');add('Музыка: джаз',base+', джаз')
    return {'intent':intent.model_dump(mode='json'),'suggestions':suggestions[:7]}
