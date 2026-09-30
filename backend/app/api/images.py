"""Same-origin posters, fetched only from trusted source hosts and bounded in size."""
import asyncio,hashlib,time
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID
import httpx
from fastapi import APIRouter,Request,HTTPException
from fastapi.responses import Response
from app.models import Event
router=APIRouter();gate=asyncio.Semaphore(4)
CACHE=Path('/tmp/max-afisha-posters')
HOSTS={'storage.yandexcloud.net','events.nethouse.ru','afisha.nethouse.ru','media.kudago.com','base-club.com','static.tildacdn.com','arenahall.info','standupcafe.ru','cdn.timepad.ru','ucarecdn.com','cdn.kassir.ru','img.kassir.ru','s3.vdnh.ru','cdn-ec-static.garagemca.org','static.wixstatic.com','loft-to-play-igrai.ru','vistavka-cvetov-krasnodar.ru','dunyashamarket.ru'}
TYPES={'image/jpeg','image/png','image/webp','image/gif'}
@router.get('/events/{event_id}/image',include_in_schema=False)
async def event_image(event_id:UUID,request:Request):
    with request.app.state.sessions() as s:
        event=s.get(Event,str(event_id));url=event.image_url if event else None
    if not url or urlparse(url).scheme!='https' or urlparse(url).hostname not in HOSTS:raise HTTPException(404,'image_unavailable')
    key=hashlib.sha256(url.encode()).hexdigest();file=CACHE/key;kind=CACHE/(key+'.type')
    async with gate:
        if file.exists() and kind.exists() and time.time()-file.stat().st_mtime<604800:
            return Response(file.read_bytes(),media_type=kind.read_text(),headers={'Cache-Control':'public, max-age=86400'})
        try:
            async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
                async with client.stream('GET',url) as r:
                    r.raise_for_status();mime=r.headers.get('content-type','').split(';')[0]
                    if mime not in TYPES:raise ValueError('not_image')
                    chunks=[];size=0
                    async for chunk in r.aiter_bytes():
                        size+=len(chunk)
                        if size>8*1024*1024:raise ValueError('image_too_large')
                        chunks.append(chunk)
                    data=b''.join(chunks)
            CACHE.mkdir(exist_ok=True);file.write_bytes(data);kind.write_text(mime)
            return Response(data,media_type=mime,headers={'Cache-Control':'public, max-age=86400'})
        except (httpx.HTTPError,ValueError,OSError):raise HTTPException(404,'image_unavailable')
