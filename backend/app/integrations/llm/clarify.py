"""Small, actionable follow-up questions. Each answer preserves existing constraints."""
from datetime import timedelta
from app.integrations.llm.fallback import guard_explicit


def merge_context(previous, answer):
    result=guard_explicit(previous,answer)
    if answer.party_size>1:result.party_size=answer.party_size
    result.unparsed_terms=answer.unparsed_terms
    return result


def questions(intent, today):
    def option(label, text, **patch):
        updated=intent.model_copy(update=patch)
        return {'label':label,'text':text,'intent':updated.model_dump(mode='json')}
    if not intent.categories and not intent.performers and not intent.keywords:
        return [{'question':'Какой отдых хочется?', 'options':[
            option('Музей или выставка','Хочу в музей',categories=['museum','exhibition'],venue_type='museum'),
            option('Концерт','Хочу на концерт',categories=['concert']),
            option('Стендап','Хочу на стендап',categories=['stand-up']),
            option('Театр','Хочу в театр',categories=['theater']),
            option('Парк и аттракционы','Хочу в парк или на аттракционы',categories=['park','amusement'])]}]
    if intent.categories==['concert'] and not intent.interest_categories and not intent.performers and not intent.keywords:
        return [{'question':'Какую музыку предпочитаете?', 'options':[
            option('Рэп / хип-хоп','Рэп и хип-хоп',interest_categories=['hip-hop']),
            option('Рок','Рок',interest_categories=['rock']),option('Джаз','Джаз',interest_categories=['jazz']),
            option('Любую','Любой жанр',interest_categories=[])]}]
    if not intent.date_from and not intent.date_to:
        offset=(5-today.weekday())%7 if today.weekday()!=6 else 0
        saturday=today+timedelta(days=offset)
        return [{'question':'На какой день ищем? Сейчас показаны все подходящие варианты.', 'options':[
            option('Сегодня','Сегодня',date_from=today,date_to=today),
            option('Завтра','Завтра',date_from=today+timedelta(days=1),date_to=today+timedelta(days=1)),
            option('Выходные','В выходные',date_from=saturday,date_to=saturday+timedelta(days=0 if today.weekday()==6 else 1)),
            option('В ближайший месяц','В ближайший месяц',date_from=today,date_to=today+timedelta(days=30))]}]
    if intent.budget_total is None and intent.budget_per_person is None and not intent.free_only:
        return [{'question':'Какой бюджет на человека?', 'options':[
            option('Бесплатно','Бесплатно',free_only=True),
            option('До 1500 ₽','До 1500 ₽ на человека',budget_per_person=1500),
            option('До 3000 ₽','До 3000 ₽ на человека',budget_per_person=3000)]}]
    return []
