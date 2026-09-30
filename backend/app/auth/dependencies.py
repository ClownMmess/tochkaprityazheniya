from fastapi import Request, HTTPException
from app.auth.session import verify_session

def current_user_id(request: Request) -> str:
    value = request.headers.get('authorization', '')
    if not value.startswith('Bearer '): raise HTTPException(401, 'invalid_session')
    try: ident=verify_session(value[7:], request.app.state.settings.session_secret)
    except ValueError: raise HTTPException(401, 'invalid_session') from None
    from app.models import User
    with request.app.state.sessions() as s:
        user=s.get(User,ident)
        if not user or (not request.app.state.settings.demo_mode and user.max_user_id.startswith('demo_')):
            raise HTTPException(401,'invalid_session')
    return ident
