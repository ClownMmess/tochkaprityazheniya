"""Real model gate, not just a fallback test. Run after `ollama pull qwen2.5:3b`."""
import asyncio,json,sys
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import httpx
from app.config import Settings
from app.integrations.llm.adapter import OllamaAdapter

async def run():
    settings=Settings()
    cases=json.loads(Path('backend/tests_techlead/search_cases.json').read_text())
    failures=0
    async with httpx.AsyncClient() as client:
        llm=OllamaAdapter(client,settings.llm_base_url,settings.llm_model)
        for i,c in enumerate(cases,1):
            intent,status=await llm.search(c['text'],c['city'],{'stand-up','concert','exhibition','theater'},today=date.fromisoformat(c['today']))
            actual=intent.model_dump(mode='json')
            matched=all(actual[k]==v for k,v in c['expected'].items())
            ok=matched and status=='ok'
            failures+=not ok
            print(json.dumps({'case':i,'passed':ok,'llm_status':status,'matched':matched,'intent':actual},ensure_ascii=False))
    return int(failures>0)
if __name__=='__main__':raise SystemExit(asyncio.run(run()))
