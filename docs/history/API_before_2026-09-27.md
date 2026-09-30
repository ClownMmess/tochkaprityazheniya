# Контракт API

Версия: **draft 1, зафиксирован 23 сентября 2026 года**.

Базовый путь: `/api/v1`.

Все даты и время передаются в ISO 8601. Денежные значения — целые рубли. Идентификаторы внутренних сущностей — UUID. `max_user_id`, `max_chat_id` и внешние идентификаторы хранятся без преобразования в JavaScript `number`, если есть риск потери точности.

## Авторизация

### `POST /auth/max`

Frontend передаёт исходную строку `window.WebApp.initData`:

```json
{
  "init_data": "query_id=...&user=...&auth_date=...&hash=..."
}
```

Backend проверяет HMAC-подпись и допустимый возраст `auth_date`, создаёт или обновляет пользователя и возвращает короткоживущую сессию:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "uuid",
    "max_user_id": "123456789",
    "first_name": "Анна",
    "onboarding_completed": false
  }
}
```

`initDataUnsafe` разрешено использовать только для предварительного отображения интерфейса, но не для доверенной авторизации.

## Метаданные

### `GET /meta`

Возвращает поддерживаемые города, категории, интересы, жанры и возрастные группы.

## Профиль

### `GET /me/preferences`

### `PUT /me/preferences`

```json
{
  "age_group": "18_24",
  "interests": ["stand-up", "music", "art"],
  "genres": ["rock", "indie"],
  "favorite_artists": ["Исполнитель 1", "Исполнитель 2"]
}
```

Запись полностью заменяет текущий набор предпочтений. Неизвестные значения категорий отклоняются с `422`.

## Каталог

### `GET /events`

Параметры:

- `city=krd|msk`;
- `date_from`, `date_to`;
- `categories` — список;
- `price_max`;
- `age_max` — максимальное допустимое возрастное ограничение события;
- `is_free`;
- `query` — обычный текстовый поиск без LLM;
- `page`, `page_size`.

Ответ:

```json
{
  "items": [
    {
      "id": "uuid",
      "title": "Название события",
      "city": "krd",
      "starts_at": "2026-09-26T18:00:00+03:00",
      "place_name": "Площадка",
      "price_min": 800,
      "price_max": 1500,
      "price_text": "800–1500 ₽",
      "age_restriction": 18,
      "categories": ["stand-up"],
      "image_url": "https://...",
      "source": {
        "name": "KudaGo",
        "url": "https://...",
        "updated_at": "2026-09-23T10:00:00Z"
      }
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 42
}
```

### `GET /events/{event_id}`

Возвращает полную карточку, все актуальные сеансы и состояние `is_tracked` текущего пользователя.

## Естественный поиск

### `POST /search/natural`

Запрос:

```json
{
  "text": "Хотим вдвоём вечером в субботу, до 3000 рублей, любим стендап",
  "city": "krd"
}
```

Структура `SearchIntent`:

```json
{
  "city": "krd",
  "date_from": "2026-09-26",
  "date_to": "2026-09-26",
  "time_of_day": "evening",
  "party_size": 2,
  "budget_total": 3000,
  "budget_per_person": null,
  "categories": ["stand-up"],
  "genres": [],
  "artists": [],
  "free_only": false,
  "hard_constraints": ["city", "date", "budget"],
  "unparsed_terms": []
}
```

Ответ содержит `intent`, `results`, `llm_status` и `relaxations`.

Каждая рекомендация:

```json
{
  "event": {},
  "score": 82,
  "reasons": [
    "проходит вечером в выбранную дату",
    "стоимость для двоих не превышает 3000 ₽",
    "совпадает с интересом «стендап»"
  ]
}
```

Если результатов нет, сервер последовательно пересчитывает количество событий при ослаблении одного ограничения. Он предлагает только варианты с `estimated_count > 0`.

## Отслеживание

### `GET /me/tracked-events`

### `PUT /me/tracked-events/{event_id}`

```json
{
  "remind_before_minutes": 1440
}
```

Создаёт или обновляет отслеживание. Повторный запрос идемпотентен. После успешного действия создаётся задание немедленного подтверждения в MAX и задание будущего напоминания.

### `DELETE /me/tracked-events/{event_id}`

Удаляет отслеживание и отменяет ещё не выполненные напоминания.

### `GET /events/{event_id}/community`

Возвращает `invite_link`, только если пользователь отслеживает событие и для него существует запись `event_chats`.

## Совместный выбор

### `POST /group-choices`

```json
{
  "title": "Куда идём в субботу",
  "event_ids": ["uuid-1", "uuid-2", "uuid-3"]
}
```

Сервер требует ровно три различных актуальных события и возвращает непрогнозируемый публичный token:

```json
{
  "id": "uuid",
  "public_token": "random-token",
  "deep_link": "https://max.ru/BOT_NAME?startapp=choice_random-token"
}
```

### `GET /group-choices/{public_token}`

Возвращает три события, количество голосов, голос текущего пользователя и победителя.

### `PUT /group-choices/{public_token}/vote`

```json
{
  "event_id": "uuid-2"
}
```

Один пользователь имеет один голос, но может изменить его. Победитель P0 — событие с максимальным количеством голосов. При равенстве используется стабильный порядок `recommendation_score DESC, event_id ASC`.

## MAX webhook

### `POST /max/webhook`

Не использует пользовательский JWT. Проверяет заголовок `X-Max-Bot-Api-Secret`.

Обработчик:

1. проверяет secret и базовую структуру Update;
2. предотвращает повторную обработку одного Update;
3. создаёт job;
4. возвращает `200`;
5. worker выполняет бизнес-логику.

Неизвестные типы событий отвечают `200` и безопасно игнорируются.

## Ошибки

Единый формат:

```json
{
  "error": {
    "code": "event_not_found",
    "message": "Событие не найдено",
    "request_id": "uuid",
    "details": {}
  }
}
```

Коды P0:

- `invalid_max_init_data`;
- `event_not_found`;
- `event_not_actual`;
- `invalid_filter`;
- `invalid_group_choice`;
- `not_tracking_event`;
- `llm_unavailable` — возвращается только если невозможен и fallback;
- `external_service_unavailable`.

## Основные таблицы

`users`, `user_preferences`, `favorite_artists`, `event_sources`, `events`, `event_occurrences`, `event_categories`, `event_artists`, `import_runs`, `tracked_events`, `group_choices`, `group_choice_events`, `votes`, `event_chats`, `jobs`, `moderation_decisions`.

Обязательные ограничения:

- `UNIQUE(event_sources.id, events.external_id)`;
- `UNIQUE(tracked_events.user_id, tracked_events.event_id)`;
- `UNIQUE(votes.group_choice_id, votes.user_id)`;
- `UNIQUE(group_choice_events.group_choice_id, group_choice_events.event_id)`;
- `UNIQUE(processed_max_update_id)` или эквивалентная идемпотентность webhook.

