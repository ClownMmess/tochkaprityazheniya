# Первый запуск и последовательность работы техлида

Ближайшая задача на 30–90 минут: **запустить skeleton и получить зелёный статус React → FastAPI /health → PostgreSQL**. Не подключать одновременно модель, импорт и бота до этой проверки. Код следующих шагов уже подготовлен в отдельных модулях, включать его по проверкам ниже.

## 1. Что проверить на компьютере

Предполагается Windows 10/11, PowerShell. Docker Desktop должен быть запущен и использовать Linux containers/WSL2. Для Docker-сборки Node на ноутбуке необязателен; для локальной разработки frontend нужен Node 22. Python 3.12 нужен для скриптов. Git нужен для общего репозитория.

```powershell
wsl --status
docker version
docker compose version
python --version
node --version
npm --version
git --version
ollama --version
cloudflared --version
```

Установщики и системные требования — только официальные ссылки в SOURCES.md. После установки Ollama/cloudflared открыть новый терминал. `python scripts/preflight.py` проверяет наличие Docker Compose, Ollama и cloudflared без чтения токена.

Этот запуск в среде подготовки проверил Python/Node, но Docker/Ollama/cloudflared здесь отсутствуют. Не считать эти компоненты установленными на вашем ноутбуке.

## 2. Дерево файлов первого шага

```text
max-afisha/
  compose.yaml
  Dockerfile
  .env.example
  frontend/
    Dockerfile
    nginx.conf
    package.json
    package-lock.json
    index.html
    src/main.tsx
    src/App.tsx
    src/style.css
  backend/
    requirements.txt
    requirements.lock
    app/config.py
    app/main.py
    app/worker/runner.py
  docs/
  seed/README.md
  scripts/init_env.py
```

Все эти файлы созданы в комплекте; вручную копировать код по сообщениям не требуется. Полный список модулей — FILES.txt.

## 3. Локальные секреты и skeleton

Распаковать архив, открыть PowerShell **в каталоге max-afisha**.

```powershell
python scripts/init_env.py
docker compose config --quiet
docker compose up --build -d db api frontend
docker compose ps
curl.exe --fail http://localhost:8080/health
```

`init_env.py` создаёт .env с независимыми случайными паролем БД, JWT secret и webhook secret; не выводит их и не перезаписывает существующий файл. `MAX_BOT_TOKEN` пока может быть пустым. Полный `docker compose config` может вывести секреты — для проверки используйте `--quiet`.

Открыть `http://localhost:8080`. Критерий первого шага: frontend открывается, `/health` возвращает HTTP 200 с database=ok, статус в шапке «Сервис доступен». Проверка ошибки: остановить db, повторить запрос — HTTP 503; затем запустить db обратно. Миграции не нужны для SELECT 1.

```powershell
docker compose stop db
curl.exe -i http://localhost:8080/health
docker compose start db
```

Если сборка не работает — сохранить вывод конкретной команды без `.env`; диагностировать ошибку. Не менять архитектуру. При уже существующей базе смена POSTGRES_PASSWORD в `.env` не меняет пароль внутри тома: согласовать пароль, не удалять том с данными.

## 4. Локальные тесты

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r backend/requirements.lock
cd backend
..\.venv\Scripts\python -m pytest -q
cd ..
npm ci --prefix frontend
npm run build --prefix frontend
npm test --prefix frontend
```

Для UI smoke со строго синтетическими ответами (не реальный MAX): установить Playwright отдельно, запустить frontend и тест во втором терминале.

```powershell
npm install --prefix frontend --no-save playwright
cd frontend
npx playwright install chromium
cd ..
npm run dev --prefix frontend -- --host 127.0.0.1
# Второй терминал, из корня:
node frontend/scripts/smoke.cjs
```

В среде подготовки браузер не установился (загрузка вернула повреждённый архив), поэтому этот UI smoke **не засчитан**. Не заменяет тестирование внутри MAX.

## 5. Подключение Ани

Перед слиянием передать `docs/INTEGRATION.md`. Получить её репозиторий, модели/миграции и точные JSON ответов. Встроить фабрику Bindings в согласованное место, заполнить `APP_BINDINGS_FACTORY`. Защищённые роутеры используют `app.auth.dependencies.current_user_id`. Auth выдаёт JWT только после реальной записи пользователя в БД.

Выполнить миграции из репозитория Ани, затем importer/seed её командами. `alembic upgrade head` выполнять только после появления её alembic.ini, migrations и зависимостей: в этом комплекте их намеренно нет. Добавить Alembic и зависимости importer в общий lock при merge.

Пересобрать API/worker после merge. После подключения adapter — `docker compose up --build -d`. Worker должен оставаться работающим. Для него предусмотрен один процесс; не масштабировать до общего распределённого лимитера.

Критерий: GET events отдаёт реальные данные, source/updated_at видны, сохранение preferences переживает повторный вход, tracking отменяет pending jobs, выбор требует три уникальных актуальных события.

## 6. Ollama и контрольные запросы

```powershell
ollama pull qwen2.5:3b
ollama list
```

Ollama должен быть доступен контейнеру по `http://host.docker.internal:11434/v1`. На Windows Docker Desktop это адрес хоста. Если соединение отклоняется, сверить настройку слушающего адреса OLLAMA_HOST и локального firewall по официальной инструкции; не выставлять Ollama в публичный tunnel.

Для `scripts/evaluate_llm.py`, запускаемого на **хосте**, временно указать хостовый URL в переменной текущего PowerShell (не переписывать контейнерное значение .env):

```powershell
$env:LLM_BASE_URL = 'http://127.0.0.1:11434/v1'
.venv\Scripts\python scripts/evaluate_llm.py
Remove-Item Env:LLM_BASE_URL
```

Скрипт проверяет 20 фиксированных запросов, дату 25.09.2026 и обязательные ожидаемые поля. Код выхода 0 только если ответы получены от модели и совпали с ожиданиями. Fallback не выдаётся за успех модели. Холодный старт qwen может не уложиться в 5 секунд: прогреть заранее; timeout не увеличивать молча.

## 7. Проверка настоящего бота и группы

В локальном `.env` заполнить MAX_BOT_TOKEN из кабинета. Не вставлять его в скрипт/терминальную команду/чат. Затем:

```powershell
.venv\Scripts\python scripts/bot_manage.py inspect
```

Сверить username/имя с командным ботом, записать username в MAX_BOT_NAME. Аня со своего аккаунта открывает бота и запускает диалог. С её аккаунта создать тестовую группу, добавить этого бота администратором с чтением сообщений и удалением, получить chat_id и invite_link. Аня заносит связь в event_chats своей миграцией/служебной командой. Эта часть требует действий в MAX, из архива она автоматически не выполняется.

```powershell
.venv\Scripts\python scripts/bot_manage.py inspect --chat-id -123456
```

Заменить демонстрационный ID фактическим. Проверить is_admin и permissions. Тестовое личное сообщение отправлять только своему тестовому аккаунту, уже начавшему диалог:

```powershell
.venv\Scripts\python scripts/bot_manage.py send-test --user-id 123456
```

Критерий — сообщение реально получено нужным аккаунтом, а не только успешный HTTP.

## 8. Cloudflare, mini-app и webhook

Только после локального прохода, в отдельном терминале:

```powershell
cloudflared tunnel --url http://localhost:8080
```

Скопировать выданный HTTPS URL в PUBLIC_APP_URL локального .env и настройки мини-приложения MAX. Держать процесс работающим. После смены env обновить процессы:

```powershell
docker compose up -d --force-recreate api worker
.venv\Scripts\python scripts/bot_manage.py subscribe
.venv\Scripts\python scripts/bot_manage.py subscriptions
```

Webhook: `https://<выданный-домен>/api/v1/max/webhook`, secret из .env. Подписка запрашивает bot_started/message_created/message_edited. Проверить внешний `/health`, открытие приложения из MAX, фактическое поступление job. Неверный secret должен давать 403; неизвестный тип — 200; недоступная очередь — 503, без ложного подтверждения приёма.

Quick Tunnel меняет URL после перезапуска. Перед финальной демонстрацией запустить один раз, обновить mini-app и subscription и не перезапускать без нужды. Для MAX API сохраняется проверка TLS; при ошибке доверия сертификату пользоваться официальной инструкцией, не `verify=False`.

## 9. Репозиторий и обмен

Если общий git-репозиторий ещё не создан:

```powershell
git init
git add .
git status
```

Убедиться, что `.env`, node_modules, .venv отсутствуют в staged. Затем commit и подключение адреса вашего реального remote. URL репозитория и пользователи GitHub не были предоставлены, поэтому remote/публикация здесь не созданы. Если репозиторий уже есть, переносить изменения отдельной веткой, не копировать поверх непроверенных файлов Ани.
