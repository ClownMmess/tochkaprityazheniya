from sqlalchemy.orm import sessionmaker
from app.db.base import make_engine
from app.ports import Bindings
from app.services.stores import Stores
from app.api.routes import router

def build(settings):
    engine=make_engine(settings.database_url)
    sessions=sessionmaker(engine,expire_on_commit=False)
    store=Stores(sessions,settings)
    return Bindings(users=store,jobs=store,bot=store,routers=[router],engine=engine,sessions=sessions)
