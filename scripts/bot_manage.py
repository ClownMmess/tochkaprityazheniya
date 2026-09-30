"""Local .env only. inspect is read-only; subscribe changes webhook configuration.
Run from root: python scripts/bot_manage.py inspect
"""
import argparse,asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import httpx
from app.config import Settings
from app.integrations.max.client import MaxClient,MaxAPIError

async def run(args):
    s=Settings()
    if not s.max_bot_token: raise SystemExit('Set MAX_BOT_TOKEN in local .env; do not paste it into chat.')
    async with httpx.AsyncClient() as http:
        client=MaxClient(http,s.max_bot_token)
        if args.command=='inspect':
            me=await client.me()
            print(json.dumps({k:me.get(k) for k in ['user_id','name','first_name','username','is_bot']},ensure_ascii=False,indent=2))
        elif args.command=='subscribe':
            if not s.public_app_url.startswith('https://'):raise SystemExit('Set PUBLIC_APP_URL in .env')
            await client.subscribe(s.public_app_url.rstrip('/')+'/api/v1/max/webhook',s.max_webhook_secret)
            print('Webhook registered. Verify with the subscriptions command and a real MAX update.')
        elif args.command=='subscriptions':
            data=await client.subscriptions()
            print(json.dumps([{'url':x.get('url'),'update_types':x.get('update_types')} for x in data.get('subscriptions',[])],ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['inspect','subscribe','subscriptions'])
    try:asyncio.run(run(p.parse_args()))
    except MaxAPIError as e:raise SystemExit(f'MAX returned HTTP {e.status}; inspect token/permissions locally.')
    except httpx.HTTPError:raise SystemExit('Network/TLS failure. Verify the official MAX certificate instructions; do not disable TLS verification.')
