import hmac
import json
from contextlib import asynccontextmanager
from uuid import uuid4
import httpx
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from app.config import Settings
from app.ports import load_bindings
from app.auth.validation import verify_init_data
from app.auth.session import issue_session, TTL
from app.auth.dependencies import current_user_id
from app.bot.updates import normalize_update
from app.integrations.llm.adapter import OllamaAdapter

class AuthRequest(BaseModel):
    init_data: str = Field(min_length=1, max_length=16384)



def create_app(settings: Settings | None = None, bindings=None, engine=None) -> FastAPI:
    settings = settings or Settings()
    bindings = bindings or load_bindings(settings.app_bindings_factory, settings)
    from app.db.base import make_engine
    engine = engine or bindings.engine or make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app):
        async with httpx.AsyncClient() as client:
            app.state.llm = OllamaAdapter(client, settings.llm_base_url, settings.llm_model, enabled=settings.llm_enabled,timeout_seconds=settings.llm_timeout_seconds)
            yield
        engine.dispose()

    app = FastAPI(title='Точка притяжения', version='1.3.1', lifespan=lifespan,
                  docs_url='/api/docs',openapi_url='/api/openapi.json',redoc_url=None)
    app.state.settings, app.state.bindings = settings, bindings
    from sqlalchemy.orm import sessionmaker
    app.state.sessions = bindings.sessions or sessionmaker(engine, expire_on_commit=False)

    @app.middleware('http')
    async def request_id(request: Request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers['X-Request-ID'] = request.state.request_id
        response.headers.setdefault('Cache-Control', 'no-store')
        return response

    def error(request, code, status, message=None):
        return JSONResponse({'error': {'code': code, 'message': message or code,
            'request_id': getattr(request.state, 'request_id', str(uuid4())), 'details': {}}}, status_code=status)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        messages={
            'invalid_filter':'Проверьте выбранные условия и поля профиля.',
            'invalid_session':'Сессия завершилась. Войдите снова.',
            'invalid_max_init_data':'Не удалось подтвердить вход. Откройте приложение заново из MAX.',
            'event_not_found':'Событие не найдено.',
            'event_not_actual':'Этот сеанс уже завершён или недоступен в источнике.',
            'not_tracking_event':'Сначала начните отслеживать этот сеанс.',
            'invalid_group_choice':'Выберите от 2 до 5 разных мероприятий из каталога.',
            'choice_not_found':'Голосование по этой ссылке не найдено.',
            'choice_expired':'Срок голосования закончился. Создайте новый выбор.',
            'demo_disabled':'Тестовые события недоступны в этом режиме.',
            'external_service_unavailable':'Сервис временно недоступен.',
        }
        code=str(exc.detail)
        return error(request,code,exc.status_code,messages.get(code))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Do not echo raw init_data, message text or submitted credentials.
        return error(request, 'invalid_filter', 422, 'Проверьте параметры запроса')

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        return error(request, 'external_service_unavailable', 503, 'Сервис временно недоступен')

    @app.get('/health')
    def health():
        try:
            with engine.connect() as conn: conn.execute(text('SELECT 1'))
            return {'status': 'ok', 'database': 'ok'}
        except SQLAlchemyError:
            return JSONResponse({'status': 'unavailable', 'database': 'unavailable'}, status_code=503)

    @app.post('/api/v1/auth/max')
    async def auth(body: AuthRequest):
        if not settings.max_bot_token or len(settings.session_secret) < 32:
            raise HTTPException(503, 'external_service_unavailable')
        try: user = verify_init_data(body.init_data, settings.max_bot_token)
        except ValueError: raise HTTPException(401, 'invalid_max_init_data') from None
        if not bindings.users: raise HTTPException(503, 'external_service_unavailable')
        saved = await bindings.users.upsert_max_user(user)
        return {'access_token': issue_session(saved['id'], settings.session_secret),
                'token_type': 'bearer', 'expires_in': TTL, 'user': saved}

    @app.post('/api/v1/max/webhook')
    async def webhook(request: Request):
        supplied = request.headers.get('X-Max-Bot-Api-Secret', '')
        if not settings.max_webhook_secret:
            raise HTTPException(503, 'external_service_unavailable')
        if not hmac.compare_digest(supplied.encode(), settings.max_webhook_secret.encode()):
            raise HTTPException(403, 'invalid_webhook_secret')
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 262144: raise HTTPException(413, 'invalid_update')
        try:
            data = json.loads(raw)
            if not isinstance(data, dict) or not isinstance(data.get('update_type'), str):
                raise ValueError()
            update = normalize_update(data)
        except (ValueError, TypeError, KeyError):
            raise HTTPException(422, 'invalid_update') from None
        if update is None: return {'ok': True}
        if not bindings.jobs: raise HTTPException(503, 'external_service_unavailable')
        key, payload = update
        # Transaction commits before acknowledging. No LLM/MAX requests here.
        await bindings.jobs.enqueue_webhook(key, payload)
        return {'ok': True}

    for router in bindings.routers:
        app.include_router(router, prefix='/api/v1')
    from app.api.images import router as image_router
    app.include_router(image_router,prefix='/api/v1')

    # Unknown endpoints are explicit errors, never an empty successful catalogue.
    @app.api_route('/api/v1/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE'],include_in_schema=False)
    async def missing_integration(path: str, request: Request):
        return error(request, 'not_found', 404, 'Маршрут не найден')

    return app

app = create_app()
