from uuid import uuid5, NAMESPACE_URL
from sqlalchemy import select
from app.models import *

def stable(kind, value): return str(uuid5(NAMESPACE_URL, "max-afisha/"+kind+"/"+str(value)))
TAXONOMY={
 "theatre":("Театр",[("drama","Драма"),("comedy","Комедия"),("musical","Мюзиклы"),("classic","Классика"),("modern","Современный театр"),("experimental","Экспериментальный театр")]),
 "music":("Музыка",[("rock","Рок"),("jazz","Джаз"),("classical","Классика"),("indie","Инди"),("hip-hop","Рэп / хип-хоп"),("electronic","Электроника"),("pop","Поп-музыка"),("acoustic","Акустика")]),
 "cinema":("Кино",[("documentary","Документальное"),("animation","Анимация"),("film-comedy","Комедии"),("thriller","Триллеры"),("fantasy","Фантастика"),("film-club","Киноклубы")]),
 "art":("Музеи и искусство",[("museums","Музеи"),("painting","Живопись"),("photo","Фотография"),("contemporary-art","Современное искусство"),("history","История"),("design","Дизайн")]),
 "humor":("Юмор",[("standup","Стендап"),("improv","Импровизация"),("open-mic","Открытый микрофон")]),
 "education":("Узнать новое",[("lecture","Лекции"),("workshop","Мастер-классы"),("science","Наука"),("craft","Керамика и ремёсла"),("language-club","Разговорные клубы")]),
 "leisure":("Прогулки и город",[("parks","Парки и сады"),("architecture","Архитектура"),("excursions","Экскурсии"),("fairs","Ярмарки и маркеты"),("festivals","Фестивали")]),
 "games":("Игры и компания",[("anticafe","Антикафе"),("board-games","Настольные игры"),("quests","Квесты"),("quizzes","Квизы"),("mafia","Мафия"),("vr","VR и видеоигры")]),
 "active":("Активный отдых",[("attractions","Аттракционы"),("sports","Спортивные события"),("dance","Танцы"),("skating","Катки"),("climbing","Скалодромы")]),
 "family":("С детьми",[("family-shows","Семейные спектакли"),("circus","Цирк"),("kids-workshops","Детские мастер-классы"),("animals","Животные и природа")]),
 "nightlife":("Вечеринки",[("party","Вечеринки"),("dj","DJ-сеты"),("karaoke","Караоке")])}
CATEGORY_GENRES={'museum':'museums','park':'parks','landmark':'architecture','tour':'excursions','fair':'fairs','festival':'festivals','anticafe':'anticafe','board-games':'board-games','quest':'quests','amusement':'attractions','sport':'sports','circus':'circus','party':'party'}
CATEGORIES={"theater":("Театр","theatre"),"concert":("Концерт","music"),"exhibition":("Выставка","art"),"cinema":("Кино","cinema"),"stand-up":("Стендап","humor"),"education":("Обучение","education"),"entertainment":("Развлекательные программы","leisure"),"festival":("Фестиваль","leisure"),"sport":("Спорт","active"),"circus":("Цирк","family")}
CATEGORIES.update({'museum': ('Музей', 'art'), 'park': ('Парки и сады', 'leisure'),
                   'landmark': ('Достопримечательности', 'leisure'), 'fair': ('Ярмарки и маркеты', 'leisure'),
                   'amusement': ('Аттракционы', 'active'), 'anticafe': ('Антикафе', 'games'), 'board-games': ('Настольные игры', 'games'), 'quest': ('Квесты', 'games'), 'tour': ('Экскурсии', 'leisure'), 'kids': ('С детьми', 'family'), 'party': ('Вечеринки', 'nightlife')})
SOURCE_URLS = {'KudaGo': 'https://kudago.com', 'StandUp Cafe': 'https://standupcafe.ru',
              'BASE': 'https://base-club.com', 'КРОП Арена': 'https://arenahall.info',
              'VK Stadium': 'https://vk-stadium.ru', 'KASSIR.RU': 'https://kassir.ru',
              'ВДНХ': 'https://vdnh.ru', 'Музей «Гараж»': 'https://garagemca.org',
              'Timepad': 'https://timepad.ru', 'Nethouse': 'https://afisha.nethouse.ru'}

from app.integrations.sources.local_places import LOCAL_SOURCES
SOURCE_URLS.update({name:config[0] for name,config in LOCAL_SOURCES.items()})

# Official source dictionary; additional UI category stand-up is assigned only from explicit title text.
from pathlib import Path
import json
for candidate in [Path(__file__).resolve().parents[2]/'seed/kudago_categories.json',Path(__file__).resolve().parents[3]/'seed/kudago_categories.json']:
    if candidate.exists():
        for entry in json.loads(candidate.read_text()):
            if entry['slug'] not in CATEGORIES:CATEGORIES[entry['slug']]=(entry['name'],'leisure')
        break

def bootstrap(s):
    from app.services.locations import CITIES
    for slug,(name,region) in CITIES.items():
        if not s.get(City,stable("city",slug)):s.add(City(id=stable("city",slug),slug=slug,name=name,country="Россия",region=CITIES[region][0]))
    for slug,name in [("under_18","До 18"),("18_24","18–24"),("25_35","25–35"),("35_plus","35+")]:
        if not s.get(AgeGroup,stable("age",slug)):s.add(AgeGroup(id=stable("age",slug),slug=slug,name=name))
    for slug,(name,children) in TAXONOMY.items():
        ident=stable("interest",slug)
        item=s.get(Interest,ident)
        if not item:s.add(Interest(id=ident,slug=slug,name=name))
        else:item.name=name
        s.flush()
        for child,label in children:
            item=s.get(InterestCategory,stable("interest-category",child))
            if not item:s.add(InterestCategory(id=stable("interest-category",child),interest_id=ident,slug=child,name=label))
            else:item.name=label;item.interest_id=ident
    s.flush()
    for slug,(name,parent) in CATEGORIES.items():
        item=s.get(Category,stable("category",slug))
        if not item:s.add(Category(id=stable("category",slug),slug=slug,name=name,interest_id=stable("interest",parent)))
        else:item.name=name;item.interest_id=stable("interest",parent)
    for name,url in SOURCE_URLS.items():
        if not s.get(EventSource,stable("source",name)):s.add(EventSource(id=stable("source",name),name=name,base_url=url,is_active=True))
    s.flush()
