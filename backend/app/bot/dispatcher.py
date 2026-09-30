from app.ports import Job


class Dispatcher:
    def __init__(self, max_client, store, bot_name: str):
        self.max, self.store, self.bot_name = max_client, store, bot_name

    async def __call__(self, job: Job):
        if job.kind in {'tracking_confirmation', 'event_reminder'}:
            notice = await self.store.notification(job)
            if notice:
                await self.max.send(notice['text'], user_id=str(notice['max_user_id']))
            return
        if job.kind != 'max_update':
            raise ValueError('unknown_job_kind')
        payload = job.payload
        if payload.get('chat_type') != 'dialog':
            return
        if payload.get('update_type') == 'bot_started' or payload.get('text', '').strip().lower() == '/start':
            link = f'https://max.ru/{self.bot_name}?startapp' if self.bot_name else ''
            await self.max.send('Точка притяжения — события для вас и ваших друзей. Откройте афишу, сохраните событие или создайте общую подборку. ' + link, user_id=payload['user_id'])
