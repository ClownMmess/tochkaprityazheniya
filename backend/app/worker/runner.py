import asyncio
import logging
import signal
import httpx
from app.config import Settings
from app.ports import load_bindings
from app.bot.dispatcher import Dispatcher
from app.integrations.max.client import MaxClient, MaxAPIError

log = logging.getLogger("worker")

async def process_one(store, dispatch) -> bool:
    job = await store.claim(lease_seconds=90)
    if job is None: return False
    try:
        async with asyncio.timeout(45):
            await dispatch(job)
    except MaxAPIError as exc:
        if exc.status == 429 and job.attempts < 5:
            await store.retry(job, exc.retry_after, "max_rate_limit")
        elif exc.status >= 500:
            # Could have been accepted upstream: do not send again blindly.
            await store.review(job, "delivery_unknown")
        else:
            await store.fail(job, "max_rejected")
    except (httpx.TransportError, TimeoutError):
        await store.review(job, "delivery_unknown")
    except (KeyError, ValueError, TypeError):
        await store.fail(job, "invalid_job_payload")
    except Exception:
        # Do not log exception data: third-party exceptions can contain payloads.
        await store.review(job, "worker_error")
    else:
        await store.complete(job)
    return True

async def main():
    settings = Settings()
    bindings = load_bindings(settings.app_bindings_factory, settings)
    if not bindings.jobs or not bindings.bot:
        log.error("Worker blocked: configure APP_BINDINGS_FACTORY; see START_HERE_RU.md")
        return
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try: loop.add_signal_handler(signum, stop.set)
        except NotImplementedError: pass
    async with httpx.AsyncClient() as client:
        from app.integrations.max.preview import PreviewMaxClient
        max_client = PreviewMaxClient() if settings.demo_mode else MaxClient(client, settings.max_bot_token)
        dispatch = Dispatcher(max_client, bindings.bot, settings.max_bot_name)
        while not stop.is_set():
            try:
                await bindings.jobs.purge_expired_payloads()
                worked = await process_one(bindings.jobs, dispatch)
            except Exception:
                log.error("Queue unavailable; retrying without logging payload")
                worked = False
            if not worked:
                try: await asyncio.wait_for(stop.wait(), 2)
                except TimeoutError: pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
