import json
from pathlib import Path
from datetime import date
import httpx,pytest
from app.integrations.llm.adapter import OllamaAdapter
from app.integrations.llm.fallback import parse_fallback
from app.integrations.llm.schemas import SearchIntent

CATEGORIES={'stand-up','concert','exhibition','theater'}
CASES=json.loads(Path(__file__).with_name('search_cases.json').read_text())

@pytest.mark.parametrize('case',CASES,ids=[str(i+1) for i in range(len(CASES))])
def test_twenty_control_queries_fallback(case):
    actual=parse_fallback(case['text'],case['city'],date.fromisoformat(case['today']),CATEGORIES).model_dump(mode='json')
    for k,v in case['expected'].items(): assert actual[k]==v

async def test_bad_json_exactly_one_retry_then_fallback():
    calls=[]
    def handler(req):
        calls.append(req)
        assert json.loads(req.content)['response_format']['json_schema']['schema']['additionalProperties'] is False
        return httpx.Response(200,json={'choices':[{'message':{'content':'{"event":"made up"}'}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        intent,status=await OllamaAdapter(client,'http://localhost/v1','test').search('Завтра вдвоём до 3000','msk',CATEGORIES,today=date(2026,9,25))
    assert len(calls)==2 and status=='fallback' and intent.budget_total==3000

async def test_valid_model_output_and_unknown_taxonomy():
    intent=SearchIntent(city='msk',categories=['concert'])
    def handler(req):return httpx.Response(200,json={'choices':[{'message':{'content':intent.model_dump_json()}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        llm=OllamaAdapter(client,'http://localhost/v1','test')
        assert (await llm.search('концерт','msk',CATEGORIES))[1]=='ok'
        assert (await llm.search('концерт','msk',set()))[1]=='fallback'

async def test_offline_moderation_does_not_delete():
    def handler(req): raise httpx.ConnectError('offline')
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        decision=await OllamaAdapter(client,'http://localhost/v1','test').moderate('Спорный текст')
    assert decision.action=='review'

async def test_low_confidence_delete_is_review():
    def handler(req):return httpx.Response(200,json={'choices':[{'message':{'content':'{"action":"delete","reason_code":"abuse","confidence":0.5}'}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        decision=await OllamaAdapter(client,'http://localhost/v1','test').moderate('текст')
    assert decision.action=='review'


async def test_model_cannot_remove_explicit_user_constraints():
    wrong=SearchIntent(city='krd',categories=['concert'],party_size=1)
    def handler(req):return httpx.Response(200,json={'choices':[{'message':{'content':wrong.model_dump_json()}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        intent,status=await OllamaAdapter(client,'http://localhost/v1','test').search('хочу сводить девушку на свидание на стендап или в театр до 5000','msk',CATEGORIES)
    assert status=='ok' and intent.city=='msk' and intent.party_size==2
    assert set(intent.categories)=={'stand-up','theater'} and intent.budget_total==5000

@pytest.mark.parametrize('text,expected',[('театр, но не концерты',['theater']),('стендап или театр',['stand-up','theater']),('стендап-концерт',['stand-up'])])
def test_or_and_scoped_negation(text,expected):
    parsed=parse_fallback(text,'msk',date(2026,9,29),CATEGORIES)
    assert parsed.categories==expected
