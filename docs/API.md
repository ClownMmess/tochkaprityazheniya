# API 1.2 — схема Ани от 27.09.2026

Base path: `/api/v1`. OpenAPI доступен на `/api/openapi.json`, интерактивная документация — `/api/docs`. Снимок спецификации — `docs/openapi.json`. Текущий файл заменяет контракт из `docs/history/API_before_2026-09-27.md`.

Авторизация: `Authorization: Bearer ACCESS_TOKEN`. JWT хранится только в памяти интерфейса; при обновлении вкладки вход повторяется через MAX или разрешённый demo-режим. MAX ID — строка, внутренние ID — UUID. Время — ISO 8601 с UTC offset, отображение — МСК.

## Маршруты

| Метод и путь | Доступ | Назначение |
|---|---|---|
| `GET /health` (без base path) | Общий | SELECT 1, состояние API и БД |
| `GET /runtime` | Общий | Режим, имя бота, наличие LLM, число актуальных уникальных реальных событий по городам |
| `POST /auth/max` | Подписанный initData | Проверка MAX HMAC и выдача JWT |
| `POST /auth/demo` | Только DEMO_MODE | Вход pavel / anya, в production отключён |
| `GET /meta` | Общий | Города, категории, возрастные группы, иерархия интересов, организаторы |
| `GET /me/preferences` | JWT | Текущие настройки |
| `PUT /me/preferences` | JWT | Замена настроек и нормализованных связей |
| `GET /events` | Общий / JWT опционально | Страница уникальных событий с ближайшим подходящим сеансом |
| `GET /events/{event_id}` | Общий / JWT опционально | Мероприятие с ближайшим актуальным сеансом и всеми датами |
| `GET /occurrences/{occurrence_id}` | Общий / JWT опционально | Конкретный сеанс, описание и все даты мероприятия |
| `POST /search/natural` | Общий / JWT опционально | Текст → валидированный intent → запрос в БД |
| `POST /search/intent` | Общий / JWT опционально | Применение полного intent, в том числе ослабленного |
| `GET /me/tracked-events` | JWT | Активное отслеживание |
| `PUT /me/tracked-events/{occurrence_id}` | JWT | Включить / изменить напоминание; повтор идемпотентен |
| `DELETE /me/tracked-events/{occurrence_id}` | JWT | Отменить tracking и ожидающие уведомления, HTTP 204 |
| `GET /me/notifications` | JWT | Последние уведомления и состояния доставки |
| `GET /occurrences/{occurrence_id}/community` | JWT + tracking | Настоящая ссылка зарегистрированного чата или null |
| `GET /occurrences/{occurrence_id}/calendar.ics` | Общий | Календарный файл |
| `POST /occurrences/{occurrence_id}/report` | JWT | Сообщить о неточности; одно обращение на пользователя/сеанс |
| `POST /group-choices` | JWT | Создать выбор от 2 до 5 разных мероприятий/сеансов |
| `GET /group-choices/{token}` | Общий / JWT опционально | Варианты, голоса, лидер, агрегированные совпадения профилей |
| `PUT /group-choices/{token}/vote` | JWT | Один изменяемый голос участника |
| `POST /max/webhook` | Webhook secret | Нормализация update, дедупликация, сохранение job, HTTP 200 |

Опциональный JWT добавляет персонализацию и признак отслеживания. Невалидный присланный JWT отклоняется, а не считается анонимным запросом.

## Вход и профиль

`POST /auth/max`: `{"init_data":"ИСХОДНАЯ_СТРОКА_WEBAPP"}`. Frontend не пересобирает её из `initDataUnsafe`.

`POST /auth/demo`: `{"user":"pavel"}` или `{"user":"anya"}`. Ответ содержит `access_token`, `token_type`, `expires_in`, `user`. У user: `id`, `max_user_id`, `first_name`, `onboarding_completed`.

`PUT /me/preferences`:

```json
{
  "age_group_id": "UUID_ИЗ_META",
  "budget_min": 0,
  "budget_max": 2500,
  "interest_ids": [],
  "interest_category_ids": [],
  "organizer_ids": []
}
```

Массивы в JSON — представление M2M-связей, а не массивы в БД. Неизвестные UUID отклоняются. Родительский интерес добавляется при выборе его дочерней категории. Возрастная группа обязательна для завершения onboarding.

## Каталог и сеансы

`GET /events` принимает `city=msk|krd`, `date_from`, `date_to`, повторяемый `categories=slug`, `price_max`, `age_max`, `is_free`, `query`, `page` (от 1), `page_size` (1–100), `show_demo` (только разрешённый demo-режим).

Ответ: `{"items":[...],"page":1,"page_size":20,"total":123}`.

Карточка содержит разные ключи `id` (мероприятие) и `occurrence_id` (сеанс), title, city, starts_at, ends_at, place_name, address, price_min/max/text, is_free, age_restriction, categories, category_name, image_url, status, is_demo, is_tracked, remind_at, organizers и source.

`source` содержит name, url, updated_at (null, если источник не сообщает время изменения), fetched_at. `description` и список `occurrences` добавляются в деталях.

Фильтр даты проверяет пересечение интервалов. В выдачу входят ACTIVE, доступные в источнике, ещё не завершившиеся сеансы. Неизвестные цена/возраст исключаются при соответствующем строгом фильтре. Длительные интервалы не считаются вечерними сеансами по времени первой исторической даты.

## Естественный поиск

`POST /search/natural?show_demo=false`:

```json
{"text":"Стендап в Москве в субботу вдвоём до 3000 рублей","city":"msk"}
```

SearchIntent: city, date_from/to, time_of_day, party_size, budget_total, budget_per_person, categories (slugs), interest_categories (slugs), organizers (точные имена), free_only, hard_constraints, unparsed_terms. В 1.1 добавлены `performers` (поиск имени в названии/описании), `excluded_categories`, `age_max`, `price_match=from|strict`. Исполнители не сохраняются как организаторы.

Ответ: intent, total, page, page_size, results (`event`, `score`, `reasons`), llm_status (`ok`, `fallback`, `filters`), relaxations (`label`, `estimated_count`, полный `intent`). Для применения ослабления отправить `{"intent":{...},"show_demo":false}` в `/search/intent`.

Рекомендации получаются только из БД. Ослабление меняет одно условие и предлагается только после проверки, что оно даёт результат. Резервный парсер не обещает понимание всех пожеланий; нераспознанное не превращается в выдуманные сведения.

## Tracking, выбор, жалобы

Tracking: `{"remind_before_minutes":60}`; диапазон 1–43200. Если назначенное время уже прошло, но начало ещё впереди, напоминание назначается сразу. Повторный запрос сохраняет существующее немедленное напоминание. Для уже идущего интервала подтверждение доступно, напоминание о прошедшем начале не назначается.

Создание выбора: `{"title":"Куда идём","description":null,"occurrence_ids":["UUID1","UUID2","UUID3"]}`. Требуются от 2 до 5 разных мероприятий, доступные сеансы. Срок — 7 дней. Голос: `{"occurrence_id":"UUID"}`. Нельзя голосовать за чужой вариант или после истечения срока.

Ответ выбора: id, title, description, public_token, deep_link, web_link, events, my_vote, winner_occurrence_id, total_votes, expires_at, status. Вариант содержит event, votes и compatibility (`participants`, `matched`, `average_score`). Учитываются автор и проголосовавшие; персональные настройки других пользователей не раскрываются.

Лидер: число голосов ↓, снимок score автора при создании ↓, occurrence_id ↑. До первого голоса лидера нет. Совпадения профилей — объяснимая эвристика, не вероятность успеха встречи; они не меняют фиксированное правило ничьей.

Жалоба: `{"reason":"wrong_date"}`. Допустимые причины определены в OpenAPI; интерфейс использует `other` для общего сообщения о неточности.

## Ошибки

```json
{"error":{"code":"event_not_actual","message":"Этот сеанс уже завершён или недоступен в источнике.","request_id":"UUID","details":{}}}
```

Основные статусы: 401 — вход; 403 — нет доступа к чату/режиму; 404 — объект не найден; 409 — устаревший сеанс или закрытый выбор; 422 — некорректные условия; 503 — временная недоступность. Сырой initData и текст webhook не возвращаются в ошибках. `X-Request-ID` помогает сопоставить запрос.

## Дополнения 1.1

`GET /events`: `interest_categories` (повторяемый slug жанра), `source` (название), `venue` (часть названия площадки), `time_of_day=morning|afternoon|evening|night`, `sort=date|price`, `price_match=from|strict`. Бюджет по умолчанию сравнивается с известной минимальной ценой; strict — с известной максимальной. Неизвестная соответствующая цена не проходит фильтр.

`available_occurrences` — число подходящих сеансов выбранного события; `genres` — подтверждённые теги. Каталог объединяет повторяющиеся event_id и совпадения нормализованных названия/города/площадки без изменения исходных идентификаторов в БД. Существующие ссылки и отслеживание остаются доступны. Возможные неоднозначные совпадения можно проверить через первоисточник.

`POST /search/intent` принимает `page` и `page_size`. Для следующей страницы передайте полный ранее распознанный intent. `/search/natural` возвращает первую страницу по 20 событий и общий total. Выдача не смешивает платные/другие категории при нулевом результате. Для нескольких явно заданных категорий первые результаты чередуются по категориям.

`GET /events/{event_id}/image` отдаёт исходную афишу через сервер и кеширует её. Принимается только ID существующего события; URL от пользователя не принимается. Ограничены источник, тип и размер файла. Остальные API-ответы не кешируются.

Изменения обратно совместимы для старых карточек, tracking и выбора из трёх событий. Новый клиент использует дополнительные поля и постраничный поиск. Схема таблиц Ани сохранена, новые связи заполнены в существующих справочниках/M2M.


## Дополнения 1.2

- `GET /sources?city=msk|krd`: количество датированных карточек/мест, последнее чтение, последняя попытка, running/complete/partial/failed/snapshot/not_connected.
- `GET /runtime`: catalog_version=1.2.0, schema_version=3, horizon_end, refresh_enabled, refresh_seconds, llm_model.
- `GET /events`: добавлены age_exact, include_unknown_age, kind=event|place. age_max оставлен для совместимости как возраст посетителя; интерфейс маркировки передаёт age_exact.
- Карточка: kind, schedule_kind=session|period|place, schedule_note. starts_at=null у места; source.url относится к выбранному сеансу.
- `POST /search/natural`: необязательный context со SearchIntent для последующего уточнения. Ответ включает questions с текстом вопроса и готовыми вариантами intent. При нераспознанном формате выдаётся вопрос без случайной подборки.
- SearchIntent: venue_type, age_exact, keywords, corrected_text.
- Пагинация API сохранена, фронтенд использует её для автоматической подгрузки и объединения без повторов. Порядок дат сохраняется независимо от профиля; score объясняет совпадение, не переставляет даты.
- Календарь для undated place возвращает 409. Сохранение места создаёт подтверждение без даты и не создаёт event_reminder.

Актуальная полная схема: openapi.json / `/api/docs`.
