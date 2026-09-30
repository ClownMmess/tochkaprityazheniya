# Отчёт технического лидера

Дата: 25.09.2026. Основание: первый промпт из `prompty_dlya_komandy_MAX.md`, README, DECISIONS, API, TASKS. Исходного репозитория и реализации Ани не предоставлено; создан отдельный переносимый комплект.

**Итог: собственный код техлида подготовлен и проверен доступными автоматическими проверками. Все задачи проекта выполненными НЕ объявляются. Полный P0, реальные сообщения MAX, БД-очередь, публикация, видео и репетиции ещё не подтверждены.**

## Что проверено фактически

| Проверка | Результат |
|---|---|
| Python compileall backend + scripts | PASS |
| `pytest -q` в backend | 43 PASS; один warning об устаревшем транспорте TestClient, не ошибка |
| Контрольные русскоязычные запросы | 20/20 PASS для fallback на фиксированной дате 25.09.2026 |
| JSON Schema / Pydantic, ошибочный ответ, один retry | PASS на имитированном HTTP Ollama |
| Реальная qwen2.5:3b | НЕ ПРОВЕРЕНО — Ollama/модели нет |
| HMAC, stale/future timestamp, duplicate params, large IDs, JWT | PASS |
| Webhook secret, неизвестные типы, одинаковый dedupe key | PASS; UNIQUE/SQL-транзакция требует адаптера Ани |
| Worker: success, 429, delivery_unknown, отмена notification | PASS с test double хранилища; PostgreSQL не подменён тестами |
| Модерация: неизвестный чат, правило, отсутствие текста в metadata | PASS |
| Клиент MAX: Authorization, точный ID, success:false | PASS на httpx MockTransport; настоящий MAX не вызван |
| `npm run build --prefix frontend` | PASS: TypeScript + Vite production build |
| `npm test --prefix frontend` | 4 PASS: query encoding, zero price, deep link, unsafe URL |
| Запуск FastAPI | PASS, ASGI startup выполнен |
| `/health` с успехом/ошибкой БД | PASS unit-тест с контролируемым connection; настоящая PostgreSQL не запускалась |
| Docker Compose | Конфигурация написана; `docker compose up/config` НЕ ВЫПОЛНЕНЫ — Docker отсутствует |
| Браузерный UI smoke | BLOCKED — Chromium отсутствует; его скачивание вернуло повреждённый архив |
| Мобильный и веб MAX, Cloudflare, два аккаунта | НЕ ПРОВЕРЕНО |

Нет измерений качества настоящей модели, скорости на ноутбуке, результата live MAX API или реального сквозного прохождения. Тесты не являются подтверждением этих свойств.

## Матрица всех задач техлида

| Дата | Задача | Что подготовлено | Оставшийся блокер / приёмка |
|---|---|---|---|
| 23.09 | Репозиторий и структура | Монорепозиторий frontend/backend/docs/seed/scripts | Нет URL общего git remote; не создан общий удалённый репозиторий |
| 23.09 | Утверждение документов | Прочитаны, сохранены оригиналы; расхождения вынесены в INTEGRATION.md | Согласование форм JSON и DB ports с Аней |
| 23.09 | Проверка token и username | `scripts/bot_manage.py inspect` | Запуск с локальным .env пользователя |
| 23.09 | Тестовая группа, бот-администратор | Инструкция и проверка membership | Создание группового чата с аккаунта Ани; реальный chat_id/invite_link |
| 23.09 | React → API → PostgreSQL skeleton | Compose, Dockerfile, nginx, /health, статус UI | Реальный запуск Docker/PostgreSQL на ноутбуке |
| 23.09 | Ollama / cloudflared | Инструкции установки и preflight | Установка на ноутбуке, загрузка модели |
| 24.09 | Каталог, карточки, фильтры, source/updated_at | Frontend написан, TS/build проходят | Реальные endpoints/данные и визуальный прогон |
| 25.09 | MAX initData | HMAC, срок, duplicate keys, JWT, router | upsert users из backend Ани, живой вход MAX |
| 25.09 | Onboarding / профиль | Экран чтения/сохранения, защитные состояния | Preferences/meta JSON Ани и повторный вход |
| 25.09 | Ollama и SearchIntent | Adapter, Schema, fallback, 20 fixtures, live evaluator | Настоящая модель + бизнес-фильтрация Ани |
| 26.09 | Пустая выдача | UI предложений estimated_count > 0, применение filters | Согласованный воспроизводимый relaxation response |
| 26.09 | MAX client / worker confirmations и reminders | Клиент и runner/dispatcher готовы | Реализация jobs/notification adapter Ани, живое сообщение |
| 27.09 | Совместный выбор | Выбор трёх, создание, просмотр, голосование, обновление | Group choice API Ани, тест второго аккаунта |
| 27.09 | Deep link / sharing | startapp, shareMaxContent, clipboard fallback | Реальный bot username и MAX Bridge на устройствах |
| 28.09 | Webhook / dispatch | Проверка secret, normalize, dedupe key, enqueue, быстрый ответ | Транзакционный JobStore, HTTPS и live update |
| 28.09 | Гибридная модерация | Правило повторяющихся ссылок, LLM allow/warn/delete/review, fail-safe review | event_chats, журнал Ани, права удаления, живой чат |
| 28.09 | Полный P0 / freeze | Таблица приёмки в DEMO.md | Блокируется интеграцией; freeze не объявлен |
| 29.09 | Мобильный/веб прогон | Сценарий UI smoke и ручная приёмка | Браузер/MAX и полный backend |
| 29.09 | Tunnel / webhook | Рабочие команды, скрипт регистрации/инспекции | Ноутбук, cloudflared, MAX token и публичный URL |
| 29.09 | Резервное видео | Подготовлен сценарий записи | Нужен стабильный реальный стенд; видео не записано |
| 30.09 | Критические исправления | Проверки и граница P0/P1 | Ошибки живого прогона ещё неизвестны |
| 30.09 | Финальный tunnel / MAX | Инструкция обновления URL/подписки | Реальное выполнение перед защитой |
| 30.09 | Три репетиции | Тайминг 2–3 минуты и таблица отметок | Требуются команда и работающий стенд |

## Отчёты по этапам для команды

**Этап 1 — skeleton.** Созданы root Dockerfile/Compose/env, frontend Dockerfile/nginx/Vite, app/config.py/main.py, /health. Проверка: production build, unit success/failure health. От Ани: исходный repository и миграции; блокер живой проверки — Docker в этой среде отсутствует.

**Этап 2 — auth и LLM.** Созданы `backend/app/auth/*`, `integrations/llm/*`, 20 fixtures и evaluator. Проверены HMAC/JWT, fallback и обработка ошибочных ответов. От Ани: upsert users и потребитель SearchIntent с реальными taxonomy IDs. Блокер — её код и Ollama на ноутбуке.

**Этап 3 — бот и worker.** Созданы `integrations/max/client.py`, `bot/*`, `worker/runner.py`, `app/ports.py`. Проверены операции на имитированном HTTP/Store; никаких сообщений людям в ходе подготовки не отправлялось. От Ани: PostgreSQL JobStore/BotStore по предложенным интерфейсам. Блокер — реальный token остаётся только у пользователя, отсутствуют chat_id и хранилище.

**Этап 4 — frontend.** Созданы App/Profile/components, shared api/types/filters/max и стили. Проверка: tsc/Vite, 4 unit-теста. От Ани: уточнения JSON из INTEGRATION.md и API/seed. Блокер — UI smoke и реальное MAX окружение ещё не проверены.

**Этап 5 — сборка и передача.** Добавлены START_HERE, INTEGRATION, DEMO, SOURCES, отчёт, локальные скрипты, dependency lock. Готов переносимый архив исходников. Нужны merge с реальным backend, локальная проверка Docker и согласование недостающего контракта; после них возможны live-исправления и защита.

## Что прислать для продолжения

Архив текущего общего репозитория или доступный checkout, включая код Ани, её миграции, requirements и примеры реальных ответов meta/events/preferences/group-choices/relaxations. Секреты, .env и приватные данные в архив не включать. Если общего репозитория ещё нет, этот комплект можно взять за основу и сначала согласовать INTEGRATION.md.

Доступ к token и аккаунтам не заменяется передачей их в чат: проверка выполняется локальными скриптами. Для диагностики достаточно обезличенного вывода команды и HTTP-кода.
