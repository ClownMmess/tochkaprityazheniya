"""Fill public deployment metadata before freezing the source version. No secrets."""
import json,re
from pathlib import Path
from urllib.parse import urlparse
root=Path(__file__).resolve().parents[1]
url=input('Public HTTPS URL: ').strip().rstrip('/')
u=urlparse(url)
if u.scheme!='https' or not u.hostname or u.hostname.lower() in {'your_domain','localhost','127.0.0.1'} or u.username or u.password or u.query or u.fragment or u.path:
    raise SystemExit('Use https://your-domain.ru without path or credentials')
bot=input('MAX bot username without @: ').strip().lstrip('@')
if not re.fullmatch(r'[A-Za-z0-9_]+',bot):raise SystemExit('Invalid bot username')
code=input('Repository URL and commit hash, or archive name: ').strip()
team=input('Team members and roles: ').strip()
if not code or not team:raise SystemExit('Code reference and team are required')
spec=json.loads((root/'openapi.json').read_text());spec['servers']=[{'url':url}]
(root/'openapi.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2))
f=root/'DATA-API.yaml';s=f.read_text();s=re.sub(r'^base_url:.*$', 'base_url: '+json.dumps(url),s,flags=re.M);s=re.sub(r'^deployment_status:.*$','deployment_status: configured_pending_live_verification',s,flags=re.M);f.write_text(s)
info={'version':'1.3.2','app_url':url,'bot_url':'https://max.ru/'+bot+'?startapp','api_url':url+'/api/v1','openapi_url':url+'/api/openapi.json','code_reference':code,'team':team,'credentials':'Private technical submission only; no secrets here'}
(root/'submission-info.json').write_text(json.dumps(info,ensure_ascii=False,indent=2))
print('Public metadata saved. Copy it to slide 1, verify MAX, then freeze and hash the archive.')
