from fastapi.openapi.utils import get_openapi


def configure_openapi(app, settings):
    def schema():
        if app.openapi_schema:
            return app.openapi_schema
        data = get_openapi(title=app.title, version=app.version, openapi_version='3.1.0',
            description='Персональная афиша и совместный выбор событий. '
                        'MAX initData обменивается на Bearer-сессию. '
                        'Бесплатно означает подтверждённую нулевую цену. '
                        'price_max по умолчанию ограничивает начальную цену билета. '
                        'price_match=strict ограничивает верхнюю границу диапазона.',
            routes=app.routes)
        data['servers'] = [{'url': settings.public_app_url.rstrip('/')}]
        data.setdefault('components', {})['securitySchemes'] = {
            'BearerAuth': {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT'},
            'MaxWebhookSecret': {'type': 'apiKey', 'in': 'header', 'name': 'X-Max-Bot-Api-Secret'}}
        for path, operations in data['paths'].items():
            for method, operation in operations.items():
                if method not in {'get', 'post', 'put', 'delete', 'patch'}:
                    continue
                if path == '/api/v1/max/webhook':
                    operation['security'] = [{'MaxWebhookSecret': []}]
                elif path.startswith('/api/v1/me/') or path.endswith('/community') or (
                    path.startswith('/api/v1/group-choices') and method != 'get'):
                    operation['security'] = [{'BearerAuth': []}]
                elif path in {'/api/v1/events', '/api/v1/search/natural', '/api/v1/search/intent', '/api/v1/discovery'} or path.startswith(('/api/v1/occurrences/', '/api/v1/events/', '/api/v1/group-choices/')):
                    operation['security'] = [{}, {'BearerAuth': []}]
                if path == '/api/v1/auth/demo':
                    operation['description'] = 'Только локальный DEMO_MODE=true. В production возвращает 404.'
                if method == 'delete' and path.startswith('/api/v1/me/tracked-events/'):
                    operation['responses']['204'] = {'description': 'Отслеживание отменено. Тело отсутствует.'}
        app.openapi_schema = data
        return data
    app.openapi = schema
