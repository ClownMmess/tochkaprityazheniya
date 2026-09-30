from unittest.mock import AsyncMock
import httpx
from app.worker.runner import process_one
from app.ports import Job
from app.bot.dispatcher import Dispatcher
from app.bot.moderation import quick_rule
from app.integrations.max.client import MaxAPIError, MaxClient

JOB=Job('id','lease','max_update',{'chat_type':'chat','chat_id':'-42','message_id':'mid','user_id':'12','text':'привет'},1)

async def test_success_ack_and_rate_limit_retry():
    store=AsyncMock();store.claim.return_value=JOB
    await process_one(store,AsyncMock())
    store.complete.assert_awaited_once_with(JOB)
    store=AsyncMock();store.claim.return_value=JOB
    await process_one(store,AsyncMock(side_effect=MaxAPIError(429,60)))
    store.retry.assert_awaited_once_with(JOB,60,'max_rate_limit')
    store.complete.assert_not_called()

async def test_ambiguous_delivery_not_resent():
    store=AsyncMock();store.claim.return_value=JOB
    await process_one(store,AsyncMock(side_effect=httpx.ReadTimeout('hidden text')))
    store.review.assert_awaited_once_with(JOB,'delivery_unknown')
    store.retry.assert_not_called()

async def test_unregistered_chat_is_ignored():
    maxc,llm,store=AsyncMock(),AsyncMock(),AsyncMock()
    store.is_event_chat.return_value=False
    await Dispatcher(maxc,llm,store,'bot')(JOB)
    llm.moderate.assert_not_called();maxc.delete.assert_not_called()

async def test_moderation_metadata_contains_no_message_text():
    maxc,llm,store=AsyncMock(),AsyncMock(),AsyncMock()
    store.is_event_chat.return_value=True
    spam=Job('id','lease','max_update',{**JOB.payload,'text':'https://spam.invalid ' * 5},1)
    await Dispatcher(maxc,llm,store,'bot')(spam)
    maxc.delete.assert_awaited_once_with('mid');llm.moderate.assert_not_called()
    for call in store.record_moderation.call_args_list:
        assert 'text' not in call.args[1] and 'spam.invalid' not in str(call.args[1])

async def test_cancelled_reminder_not_sent():
    maxc,llm,store=AsyncMock(),AsyncMock(),AsyncMock();store.notification.return_value=None
    await Dispatcher(maxc,llm,store,'bot')(Job('id','lease','event_reminder',{},1))
    maxc.send.assert_not_called()

async def test_max_authorization_recipient_and_false_success():
    requests=[]
    def handler(req):
        requests.append(req)
        return httpx.Response(200,json={'success':False} if req.method=='DELETE' else {'message':{'body':{'mid':'1'}}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        maxc=MaxClient(client,'test-secret')
        await maxc.send('test',user_id='9007199254740993')
        assert requests[0].headers['Authorization']=='test-secret'
        assert requests[0].url.params['user_id']=='9007199254740993'
        try: await maxc.delete('mid')
        except MaxAPIError as exc: assert exc.status==400
        else: assert False,'success:false must not be acknowledged'

def test_single_link_not_automatically_deleted():
    assert quick_rule('Билеты здесь: https://example.com') is None
