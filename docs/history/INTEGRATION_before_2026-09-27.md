# Предложения по интеграции с Аней — требуют согласования

Исходные `API.md`, `DECISIONS.md`, `TASKS.md` сохранены без изменений. Реализации моделей, миграций, importer и бизнес-роутеров во вложениях нет. Этот комплект не создаёт параллельную схему БД. Согласование ниже — блокер полной интеграции, а не скрытое изменение API.

## Точные стыки

| Файл / сторона | Поле или функция | Причина | Обратная совместимость |
|---|---|---|---|
| Новый `backend/app/bindings.py`, совместная интеграция | `build(settings) -> app.ports.Bindings` | Связать готовые модели и роутеры Ани с auth и worker техлида | Новый модуль; существующие маршруты не меняются |
| `backend/app/ports.py`, техлид | `UserStore.upsert_max_user(VerifiedUser)` | После HMAC получить внутренний UUID пользователя | Возвращает точно `user` из API.md; MAX ID строкой |
| Модель `users`, Аня | Уникальный `max_user_id`, UUID `id`, `first_name`, `onboarding_completed` | Идемпотентное создание пользователя и корректный профиль | Уточнение существующей сущности; конкретная миграция только после сверки моделей |
| Модель `jobs`, Аня | Семантика полей из таблицы ниже | Дедупликация, отмена, retry и очистка текста | Предложение, не применённая миграция; имена можно сопоставить в адаптере |
| `event_chats`, Аня | Поиск зарегистрированного `max_chat_id` | Не модерировать посторонние группы | Соответствует текущему решению D-001 |
| `moderation_decisions`, Аня | Upsert по `job_id`, enum action/reason_code/execution | Не хранить текст и не создавать повторные записи | Поля/enum требуется согласовать; текст не добавляется |
| `backend/app/api/routers/*`, Аня | `APIRouter` со своими относительными маршрутами | `main.py` подключает с общим `/api/v1` | Префикс добавляется ровно один раз |

В `.env` после реализации адаптера: `APP_BINDINGS_FACTORY=app.bindings:build`.
Фабрика синхронная, создаёт объекты адаптеров, без сетевых запросов. Методы интерфейсов асинхронные: использовать async engine или выносить блокирующий SQLAlchemy в threadpool. Синхронный SQL в event loop недопустим.

`Bindings.users`, `.jobs`, `.bot` реализуют Protocol из `backend/app/ports.py`; `.routers` — список роутеров. API и worker вызывают одну фабрику из одного образа. Фабрика не должна вызывать `create_all` — схемой управляет Alembic Ани.

Auth-зависимость для защищённых endpoint: `from app.main import current_user_id` может создавать цикл при загрузке фабрики; используйте вынесенную функцию `app.auth.dependencies.current_user_id`. Не принимать user_id из JSON как идентичность пользователя. Все действия профиля, tracking, создания подборки и голосования защищены этой dependency. Публичность каталога и GET подборки отдельно согласовать.

Естественный поиск в роутере Ани:

```python
intent, llm_status = await request.app.state.llm.search(
    body.text, body.city, categories=allowed_category_ids, genres=allowed_genre_ids
)
# Дальше только SQL-фильтрация, ranking, причины и relaxations сервиса Ани.
# Выводить intent.unparsed_terms клиенту, не скрывать fallback.
```

## Контракт хранилища jobs

| Поле / смысл | Требование |
|---|---|
| `id` | UUID |
| `kind` | `max_update`, `tracking_confirmation`, `event_reminder` |
| `dedupe_key` | UNIQUE; digest от normalize_update для webhook; отдельные ключи tracking |
| `payload` | JSONB. Для webhook только нормализованные необходимые поля; временный текст |
| `status` | pending / processing / done / failed / cancelled / review |
| `run_at` | TIMESTAMPTZ, часы UTC |
| `attempts` | Инкремент атомарно при получении задания |
| `lease_token`, `locked_until` | Новый UUID lease при claim, защита от завершения устаревшим worker |
| `last_error_code` | Только короткий фиксированный код, без exception/body/token |
| `payload_expires_at` | Конечный TTL временного текста, предложение: 15 минут |

`enqueue_webhook` в транзакции выполняет INSERT ON CONFLICT DO NOTHING, commit до возврата. UNIQUE остаётся после удаления текста: повторный webhook через часы не создаёт новое задание. Не удалять dedupe tombstone раньше окончания окна повторов MAX; для MVP сохранять на весь хакатон. Возвращаемое bool означает новое/уже существующее задание.

`claim(90)` использует `FOR UPDATE SKIP LOCKED` и атомарный UPDATE + RETURNING. Транзакция закрывается до HTTP/LLM. Claim только `pending` с `run_at <= now()`, валидным payload TTL; вернуть `Job`, attempts уже увеличен. Запускать ровно один worker P0: лимитер MAX локальный в процессе.

`complete`, `fail`, `review`: UPDATE с WHERE id + lease_token + status=processing; в этой же транзакции удалить полный payload (или как минимум все поля текста), сохранить только безопасные метаданные. `retry` сохраняет временный payload, ставит pending/run_at, ограничивает попытки и не продлевает TTL. Не применять retry после отмены.

`purge_expired_payloads`: до очередного claim очистить текст истёкших pending/retry/terminal jobs. Незавершённые просроченные lease переводить в review и очищать текст: внешний POST мог выполниться перед падением процесса. Автоматически пересылать такое сообщение нельзя. Активный lease не очищать посередине работы; верхняя граница обработки — 45 секунд, lease — 90 секунд. При полностью выключенном worker TTL-cleanup выполняется первым действием после запуска; для жёсткой гарантии удаления в момент TTL требуется DB-задача, не реализованная в этом MVP.

`BotStore.notification(job)` повторно проверяет active tracking, актуальность события/сеанса и отмену job. Возвращает `None` либо `{"max_user_id":"...","text":"..."}`. Текст формируется исключительно из БД. Payload напоминания содержит ссылки на tracking/event/occurrence, не старую копию текста. DELETE tracking и отмена pending jobs — одна транзакция. Уже отправленное сообщение отменить невозможно; остаётся короткое окно между последней проверкой и MAX POST.

`BotStore.record_moderation` — upsert по job_id. Данные: chat_id/message_id/user_id/action/reason_code/confidence/execution. Свободного reason и исходного текста нет. `review` — метаданные для ручного просмотра сообщения в самом MAX; интерфейс администратора не входит в P0.

Гарантия доставки: идемпотентный приём webhook и at-most-one автоматическая попытка при неоднозначном результате отправки. Exactly-once внешнего MAX POST обещать нельзя: при timeout или падении после отправки состояние review, ручная проверка. Только явный 429 безопасно повторяется (до 5 попыток с Retry-After).

## Неопределённые в API.md формы ответов

Ниже **предложения**, под которые написаны типы `frontend/src/shared/types.ts`. До согласования нельзя объявлять frontend интегрированным. Если Аня уже выбрала другую форму, изменить только адаптер типов/чтения frontend, не её API молча.

| Endpoint | Предлагаемый ответ / сериализация |
|---|---|
| GET meta | `{cities,categories,interests,genres,age_groups}`; каждое поле — массив `{id,label}` |
| GET me/preferences | Объект PUT из API.md; у нового пользователя пустые массивы и пустая age_group |
| GET events/{id} | Поля карточки + `description`, `address`, `is_tracked`, `occurrences:[{id,starts_at,ends_at}]`; description — обычный текст |
| GET me/tracked-events | `{items:[Event],page,page_size,total}`; P0 список целиком, без отдельной пагинации UI |
| GET events/{id}/community | `{invite_link: string|null}`; контроль tracking на сервере |
| GET group-choices/{token} | `{id,title,public_token,deep_link,events:[{event:Event,votes:number}],my_vote:string|null,winner_event_id:string|null}` |
| GET events query categories | Повторяющиеся параметры `categories=a&categories=b` (типичный FastAPI list) |
| search/natural relaxations | `{label,estimated_count,filters}`; `filters` — **полный** эквивалентный набор GET /events фильтров, после ослабления одного ограничения |

Особенно важно про relaxations: UI открывает GET /events, поэтому сервер может выдать кнопку только если оставшиеся ограничения выражаются этими фильтрами. Условия времени/исполнителя, не представимые GET /events, нельзя молча терять. Для них требуется согласовать отдельный повторный поиск по SearchIntent; этот контракт сейчас отсутствует. До этого возвращать только воспроизводимые кнопки, обычные ручные фильтры доступны всегда. `estimated_count` проверять тем же запросом, которым затем загружается результат.

Коды ошибок auth/session/webhook (`invalid_session`, `invalid_webhook_secret`, `invalid_update`) — предлагаемые дополнения к списку API.md; общий конверт сохранён. В исходный API.md не внесены.

## Приёмка совместной части

1. Реальные миграции Ани проходят на чистой PostgreSQL, реальные seed ≥20 событий со ссылками/датой выгрузки.
2. Auth upsert даёт один UUID при повторном входе и не меняет preferences.
3. Два одновременных одинаковых webhook → одна строка jobs; повтор после redaction → та же строка.
4. Два конкурирующих claim не получают одну job; чужой lease не завершает задание.
5. DELETE tracking отменяет pending reminder; worker после отмены ничего не отправляет.
6. После done/failed/review/cancelled/TTL текст отсутствует в jobs и moderation_decisions.
7. Два реальных MAX пользователя проходят сценарий из DEMO.md.
