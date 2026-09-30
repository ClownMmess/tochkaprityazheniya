"""Deterministic Russian constraints. Explicit conditions also guard LLM output."""
import re
from difflib import get_close_matches
from datetime import date, timedelta
from app.integrations.llm.schemas import SearchIntent
from app.services.locations import CITY_WORDS

WEEKDAYS = {"понедельник": 0, "вторник": 1, "сред": 2, "четверг": 3, "пятниц": 4, "суббот": 5, "воскресень": 6}
CATEGORY_PATTERNS = {
    'anticafe': r'анти[ -]?кафе|тайм[ -]?(?:кафе|клуб)',
    'board-games': r'настолк|настольн.{0,8}игр|игротек',
    'museum': r'музе[йяеюи]|музеев|музейн',
    'park': r'\bпарк\w*|ботаническ.{0,8}сад',
    'landmark': r'достопримечательн|усадьб|памятник.{0,10}архитект',
    'fair': r'ярмарк|маркет\b',
    'amusement': r'аттракцион|колесо обозрения|парк развлечений|парк аттракционов',
    'stand-up': r'ст[еэ]нд[аэ]п|stand[ -]?up|cтендап',
    'theater': r'театр|театраль|спектакл|постановк',
    'concert': r'концерт|живая музыка|живую музыку',
    'exhibition': r'выстав|экспозиц',
    'cinema': r'\bкино\b|фильм|кинопоказ',
    'tour': r'экскурси|тур по|прогулк',
    'education': r'лекци|мастер[ -]?класс|воркшоп|обучени',
    'festival': r'фестивал', 'party': r'вечеринк|дискотек|рейв',
    'kids': r'для детей|с ребенком|с детьми|детск',
    'sport': r'спортив|футбол|волейбол|баскетбол|\bспорт\b',
    'quest': r'квест', 'circus': r'цирк',
}
GENRE_PATTERNS = {'hip-hop':r'хип[ -]?хоп|\bрэп|\bреп\b|hip[ -]?hop|\brap\b|трэп|\btrap\b', 'jazz':r'джаз|jazz', 'rock':r'\bрок|rock', 'electronic':r'электронн|техно|techno', 'classical':r'классическ.{0,10}музык|симфони|классик', 'pop':r'поп[ -]?музык|эстрад', 'musical':r'мюзикл', 'comedy':r'комеди', 'workshop':r'мастер[ -]?класс', 'lecture':r'лекци', 'drama':r'драматическ|\bдрама\b', 'indie':r'\bинди|indie', 'documentary':r'документальн', 'animation':r'анимац|мультфильм', 'painting':r'живопис|живопись|картин|художественн', 'photo':r'фотограф|фотовыстав', 'classic':r'классическ.{0,15}постанов', 'modern':r'современн.{0,15}постанов', 'experimental':r'экспериментальн.{0,15}постанов'}
ARTISTS = {
    'madk1d':r'madk1d|madkid|мадкид|мэдкид',
    'Boulevard Depo':r'boulevard\s*depo|бульвар\s*депо|булевард\s*депо',
    'GONE.Fludd':r'gone[.\s]*fludd|гон\s*флад',
    'ЛСП':r'\bлсп\b', 'Три дня дождя':r'три дня дождя',
    'SLAVA MARLOW':r'slava\s*marlow|слава\s*марлоу',
    'YANIX':r'yanix|яникс', 'OBLADAET':r'obladaet|обладает',
    'FRIENDLY THUG 52 NGG':r'friendly\s*thug(?:\s*52\s*ngg)?',
}

SPELLING_WORDS = ['стендап','стендапы','концерт','концерты','концертов','музей','музеи','музеев',
                 'театр','театры','спектакль','спектакли','выставка','выставки','бесплатно','ярмарка','ярмарки',
                 'экскурсия','экскурсии','аттракционы','достопримечательности','девушку','свидание','джаз','антикафе']

def correct_text(text):
    """Conservative one-edit corrections only for the event vocabulary, not arbitrary names."""
    def one_edit(a,b):
        if abs(len(a)-len(b))>1:return False
        if len(a)==len(b):
            diffs=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
            return len(diffs)==1 or (len(diffs)==2 and diffs[1]==diffs[0]+1 and a[diffs[0]]==b[diffs[1]] and a[diffs[1]]==b[diffs[0]])
        short,long=(a,b) if len(a)<len(b) else (b,a)
        return any(long[:i]+long[i+1:]==short for i in range(len(long)))
    def replace(match):
        word=match[0].casefold().replace('ё','е')
        if len(word)<5 or word in SPELLING_WORDS:return match[0]
        candidates=[v for v in get_close_matches(word,SPELLING_WORDS,n=3,cutoff=.78) if one_edit(word,v)]
        return candidates[0] if candidates else match[0]
    return re.sub(r'[а-яА-ЯёЁ]+',replace,text)

def parse_fallback(text: str, city: str, today: date, categories: set[str]) -> SearchIntent:
    corrected=correct_text(text)
    t=corrected.casefold().replace('ё','е')
    intent=SearchIntent(city=city,hard_constraints=['city'])
    if corrected.casefold()!=text.casefold():intent.corrected_text=corrected
    for slug,pattern in CITY_WORDS.items():
        if re.search(r'\b'+pattern,t):intent.city=slug;break
    day=None
    if 'послезавтра' in t:day=today+timedelta(days=2)
    elif 'завтра' in t:day=today+timedelta(days=1)
    elif 'сегодня' in t:day=today
    else:
        for key,weekday in WEEKDAYS.items():
            if key in t:
                day=today+timedelta(days=(weekday-today.weekday())%7);break
    dates=re.findall(r'\b20\d{2}-\d{2}-\d{2}\b',t)
    if dates:
        try:intent.date_from=date.fromisoformat(dates[0]);intent.date_to=date.fromisoformat(dates[-1])
        except ValueError:intent.unparsed_terms.append('Некорректная дата')
    elif 'выходн' in t:
        delta=(5-today.weekday())%7 if today.weekday()!=6 else 0
        intent.date_from=today+timedelta(days=delta);intent.date_to=intent.date_from+timedelta(days=0 if today.weekday()==6 else 1)
    elif not day and re.search(r'\bнедел',t):
        intent.date_from=today;intent.date_to=today+timedelta(days=6)
    elif not day and re.search(r'ближайш.{0,4}месяц|в этом месяце',t):
        intent.date_from=today;intent.date_to=today+timedelta(days=30)
    elif day:intent.date_from=intent.date_to=day
    if intent.date_from:intent.hard_constraints.append('date')
    for key,value in {'утро':'morning','утром':'morning','днем':'afternoon','вечер':'evening','ночью':'night','ночн':'night'}.items():
        if key in t:intent.time_of_day=value;intent.hard_constraints.append('time');break
    for word,count in {'вдвоем':2,'двоих':2,'двое':2,'втроем':3,'троих':3,'вчетвером':4,'четверых':4,'впятером':5,'пятеро':5,'пятерых':5,'вшестером':6}.items():
        if word in t:intent.party_size=count
    if re.search(r'свидани|с девушкой|с парнем|сводить девушк|сводить парня|втор.{0,3} половин',t):intent.party_size=2
    people=re.search(r'(\d{1,2})\s*(?:человек|чел\b)',t)
    if people and int(people[1])>0:intent.party_size=int(people[1])
    monies=list(re.finditer(r'(?:до|бюджет(?:ом)?|не дороже|не больше|максимум)\s*(\d+(?:[ \u00a0]\d{3})*)(?:\s*(тыс(?:яч)?\.?|к)(?=\s|[.,!]|$))?',t))
    money=monies[-1] if monies else None
    if money:
        value=int(re.sub(r'\s','',money[1]))*(1000 if money[2] else 1)
        if re.search(r'(?:на|за)\s*(?:одного|человека)|с человека|кажд',t):intent.budget_per_person=value
        else:intent.budget_total=value
        intent.hard_constraints.append('budget')
    if re.search(r'бесплат|свободный вход|вход свободный|без оплаты',t) and not re.search(r'не\s+бесплат',t):
        intent.free_only=True;intent.hard_constraints.append('free')
    for slug,pattern in CATEGORY_PATTERNS.items():
        if slug not in categories:continue
        for match in re.finditer(pattern,t):
            prefix=t[max(0,match.start()-24):match.start()]
            negative=re.search(r'(?:\bне|\bкроме|\bбез)\s+(?:(?:в|на)\s+)?$',prefix)
            target=intent.excluded_categories if negative else intent.categories
            if slug not in target:target.append(slug)
    # "стендап-концерт" is a comedy format, not an invitation to include all music.
    if 'stand-up' in intent.categories and re.search(r'(?:ст[еэ]нд[аэ]п|stand[ -]?up|cтендап)[ -]*(?:шоу[ -]*)?концерт',t):
        intent.categories=[x for x in intent.categories if x!='concert']
    intent.categories=[x for x in intent.categories if x not in intent.excluded_categories]
    # Museums are a destination; a dating wish cannot replace them with comedy/music.
    if 'museum' in intent.categories:
        intent.venue_type='museum';intent.hard_constraints.append('venue')
        if 'exhibition' in categories and 'exhibition' not in intent.excluded_categories and 'exhibition' not in intent.categories:intent.categories.append('exhibition')
    if 'amusement' in intent.categories and 'park' in intent.categories:intent.categories.remove('park')
    if 'board-games' in intent.categories and 'anticafe' in categories:
        intent.categories.append('anticafe');intent.interest_categories.append('board-games')
    if intent.categories or intent.excluded_categories:intent.hard_constraints.append('category')
    for slug,pattern in GENRE_PATTERNS.items():
        if re.search(pattern,t):intent.interest_categories.append(slug)
    if not intent.categories:
        if set(intent.interest_categories)&{'hip-hop','jazz','rock','pop','electronic','classical','indie'} and 'concert' in categories:intent.categories=['concert'];intent.hard_constraints.append('category')
        elif set(intent.interest_categories)&{'painting','photo'} and 'exhibition' in categories:intent.categories=['exhibition'];intent.hard_constraints.append('category')
    if intent.interest_categories:intent.hard_constraints.append('interest_category')
    for name,pattern in ARTISTS.items():
        if re.search(pattern,t):intent.performers.append(name)
    if intent.performers:
        if 'concert' in categories and not intent.categories:intent.categories=['concert']
        intent.hard_constraints.extend(['category','performer'])
    # An unknown latin performer is still a title constraint; it cannot turn into all concerts.
    if not intent.performers:
        names=re.findall(r'[a-z][a-z0-9.$_-]*(?:\s+[a-z][a-z0-9.$_-]*){0,3}',t)
        names=[n for n in names if not re.fullmatch(r'stand[ -]?up|jazz|rock|hip[ -]?hop|techno|rap|trap',n)]
        if names:intent.performers=names;intent.hard_constraints.append('performer')
    ages=re.findall(r'\b(0|6|12|16|18)\s*\+',t)
    child=re.search(r'(?:ребен\w*|дет\w*)\s+(\d{1,2})\s*(?:лет|год)',t)
    if ages:intent.age_exact=int(ages[-1]);intent.hard_constraints.append('age')
    elif child:intent.age_max=int(child[1]);intent.hard_constraints.append('age')
    elif 'дет' in t or 'ребен' in t:intent.age_max=12;intent.hard_constraints.append('age')
    # Preserve named Cyrillic artists/venues when a category is the only other signal.
    named=re.search(r'(?:концерт(?:е)?|выступление)\s+([а-я][а-я0-9 .-]{2,80})',t)
    if named and not intent.performers and not intent.interest_categories:
        # A leading preposition introduces place/time, never an artist name.
        name=re.split(r'(?:^|\s+)(?:до\b|завтра\b|сегодня\b|в\s|на\s|или\b|бесплатно\b|для\s|с\s|нас\s)',named[1])[0].strip(' .')
        if name and not re.search(r'хочу|девуш|друз|вечер|бюджет|классик|современн|люб[ыо]|како|хорош',name):
            intent.keywords=[name];intent.hard_constraints.append('keywords')
    if len(intent.hard_constraints)==1:intent.unparsed_terms=[text]
    try:return SearchIntent.model_validate(intent.model_dump())
    except ValueError:
        intent.date_from=intent.date_to=None;intent.unparsed_terms.append('Проверьте диапазон дат')
        return SearchIntent.model_validate(intent.model_dump())


def guard_explicit(model: SearchIntent, explicit: SearchIntent) -> SearchIntent:
    """The model may enrich vague wishes, but cannot erase explicit user constraints."""
    data=model.model_dump()
    mapping={'date':['date_from','date_to'],'budget':['budget_total','budget_per_person'],'time':['time_of_day'],'category':['categories','excluded_categories'],'free':['free_only'],'interest_category':['interest_categories'],'performer':['performers'],'age':['age_max','age_exact'],'venue':['venue_type'],'keywords':['keywords']}
    data['city']=explicit.city
    for key,fields in mapping.items():
        if key in explicit.hard_constraints:
            for field in fields:data[field]=getattr(explicit,field)
    if explicit.party_size>1:data['party_size']=explicit.party_size
    if explicit.age_max is not None:data['age_max']=explicit.age_max
    def structured_term(value):
        value=re.sub(r'^(?:в|на|город)\s+','',value.casefold().replace('ё','е').strip())
        return (any(re.fullmatch(pattern,value) for pattern in CITY_WORDS.values())
                or bool(re.fullmatch(r'(?:нас\s+)?\d+\s*(?:человек|чел\.?|участников)',value))
                or bool(explicit.categories and any(re.fullmatch(pattern+r'\w*',value) for pattern in CATEGORY_PATTERNS.values())))
    # Structured city/party/category terms must not also become title restrictions.
    for field,key in [('keywords','keywords'),('performers','performer')]:
        if key not in explicit.hard_constraints:data[field]=[v for v in data[field] if not structured_term(v)]
    data['hard_constraints']=list(dict.fromkeys([*model.hard_constraints,*explicit.hard_constraints]))
    for field,key in [('keywords','keywords'),('performers','performer')]:
        if not data[field]:data['hard_constraints']=[v for v in data['hard_constraints'] if v!=key]
    data['corrected_text']=explicit.corrected_text
    return SearchIntent.model_validate(data)
