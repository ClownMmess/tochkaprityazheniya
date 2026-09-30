"""Configure a fresh deployment without echoing bot credentials."""
import getpass
import re
import runpy
from pathlib import Path

root = Path(__file__).resolve().parents[1]
import os
os.chdir(root)
path = root / '.env'
if not path.exists():
    runpy.run_path(str(root / 'scripts/init_env.py'), run_name='__main__')
values = {}
for line in path.read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        key, value = line.split('=', 1)
        values[key] = value
domain = input('Domain without https://: ').strip().lower()
if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', domain) or '.' not in domain:
    raise SystemExit('Enter a public domain, for example afisha.example.ru')
bot = input('MAX bot username (without @): ').strip().lstrip('@')
if not re.fullmatch(r'[A-Za-z0-9_]+', bot):
    raise SystemExit('Invalid bot username')
token = getpass.getpass('MAX bot token (hidden): ').strip()
if not token or any(ch.isspace() for ch in token) or any(ch in token for ch in "'\"$#"):
    raise SystemExit('Invalid token characters')
values.update(APP_ENV='production', DEMO_MODE='false', APP_DOMAIN=domain,
    PUBLIC_APP_URL='https://' + domain, MAX_BOT_TOKEN=token, MAX_BOT_NAME=bot,
    LLM_ENABLED='false', CATALOG_REFRESH_ENABLED='true', CATALOG_REFRESH_SECONDS='21600',
    CATALOG_LIVE_SOURCES='KudaGo')
path.write_text('\n'.join(key + '=' + value for key, value in values.items()) + '\n')
path.chmod(0o600)
print('Production settings saved. Secrets were not printed.')
