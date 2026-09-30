import hashlib, hmac, json
from urllib.parse import urlencode
import pytest
from app.auth.validation import verify_init_data
from app.auth.session import issue_session, verify_session

TOKEN='test-token-not-real'
NOW=1800000000

def signed(**overrides):
    d={'auth_date':str(NOW), 'user':json.dumps({'id':9007199254740993,'first_name':'Анна + А'},ensure_ascii=False)}
    d.update(overrides)
    key=hmac.digest(b'WebAppData',TOKEN.encode(),'sha256')
    d['hash']=hmac.new(key,'\n'.join(f'{k}={v}' for k,v in sorted(d.items())).encode(),hashlib.sha256).hexdigest()
    return urlencode(d)

def test_auth_precise_id_and_single_decode():
    u=verify_init_data(signed(),TOKEN,now=NOW)
    assert u.max_user_id=='9007199254740993' and u.first_name=='Анна + А'

@pytest.mark.parametrize('raw',[signed()+'&auth_date=1',signed().replace('hash=','hash=0'),signed(auth_date=str(NOW-3601)),signed(auth_date=str(NOW+31)),signed(user='{}'),'hash=%ZZ'])
def test_auth_rejects(raw):
    with pytest.raises(ValueError): verify_init_data(raw,TOKEN,now=NOW)

def test_session_signature():
    uid='550e8400-e29b-41d4-a716-446655440000'
    token=issue_session(uid,'x'*40)
    assert verify_session(token,'x'*40)==uid
    with pytest.raises(ValueError): verify_session(token,'y'*40)
