from sqlalchemy import select
from app.models import Category, Event, Interest, InterestCategory


def interest_match(session, occurrence, user_id):
    from app.services.catalog import preferences, warm
    if not user_id:
        return {'percent': None, 'reasons': ['Войдите и выберите интересы в профиле, чтобы увидеть совпадение.']}
    key = ('match-profile', user_id)
    if key not in session.info:
        profile = preferences(session, user_id)
        topics = list(session.scalars(select(InterestCategory).where(InterestCategory.id.in_(profile['interest_category_ids']))))
        session.info[key] = profile, topics
    profile, selected_topics = session.info[key]
    if not profile['interest_ids'] and not selected_topics:
        return {'percent': None, 'reasons': ['Выберите интересы в профиле. Пока оценивать совпадение не с чем.']}
    event = session.get(Event, occurrence.event_id)
    category = session.get(Category, event.category_id)
    interest = session.get(Interest, category.interest_id) if category.interest_id else None
    event_topics = {g.id for g in warm(session, [occurrence])['genres'][event.id]}
    topics = [t for t in selected_topics if t.interest_id == category.interest_id]
    common = [t.name for t in topics if t.id in event_topics]
    if category.interest_id not in profile['interest_ids']:
        return {'percent': 0, 'reasons': [f'Направление «{interest.name if interest else category.name}» не отмечено в вашем профиле. Это событие может понравиться вам и вне выбранных интересов.']}
    if not topics:
        return {'percent': 100, 'reasons': [f'Вы выбрали всё направление «{interest.name}». Категория события соответствует этому интересу.']}
    reasons = [f'60% — совпадает направление «{interest.name}».']
    if common:
        reasons.append('40% — совпадает выбранная тема: ' + ', '.join(common) + '.')
        return {'percent': 100, 'reasons': reasons}
    reasons.append('Оставшиеся 40% не начислены: в данных события не подтверждены ваши темы — ' + ', '.join(t.name for t in topics) + '.')
    return {'percent': 60, 'reasons': reasons}
