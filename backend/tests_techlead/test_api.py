from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from app.main import create_app
from app.config import Settings
from app.ports import Bindings


def make(jobs=None):
    engine=MagicMock()
    app=create_app(Settings(max_webhook_secret='testsecret'),Bindings(jobs=jobs),engine)
    return TestClient(app),engine

def test_health_database_success_and_failure():
    client,engine=make()
    assert client.get('/health').json()=={'status':'ok','database':'ok'}
    engine.connect.side_effect=OperationalError('SELECT 1',{},Exception())
    assert client.get('/health').status_code==503

UPDATE={'update_type':'message_created','timestamp':1800000000000,'message':{'recipient':{'chat_id':-42,'chat_type':'chat'},'sender':{'user_id':9007199254740993},'body':{'mid':'mid-1','text':'Привет'}}}

def test_webhook_secret_queue_only_and_dedupe_key():
    jobs=AsyncMock();client,_=make(jobs)
    assert client.post('/api/v1/max/webhook',json=UPDATE).status_code==403
    for _ in range(2):
        assert client.post('/api/v1/max/webhook',json=UPDATE,headers={'X-Max-Bot-Api-Secret':'testsecret'}).status_code==200
    calls=jobs.enqueue_webhook.call_args_list
    assert calls[0].args==calls[1].args
    assert calls[0].args[1]['user_id']=='9007199254740993'

def test_unknown_ack_and_database_failure_not_ack():
    client,_=make()
    headers={'X-Max-Bot-Api-Secret':'testsecret'}
    assert client.post('/api/v1/max/webhook',json={'update_type':'future_type'},headers=headers).status_code==200
    assert client.post('/api/v1/max/webhook',json=UPDATE,headers=headers).status_code==503

def test_no_fake_catalog_and_no_input_echo():
    client,_=make()
    assert client.get('/api/v1/events').status_code==404
    r=client.post('/api/v1/auth/max',json={'init_data':{'secret':'do-not-echo'}})
    assert r.status_code==422 and 'do-not-echo' not in r.text
