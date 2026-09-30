"""Run from repository root. Never prints secrets or overwrites an existing .env."""
from pathlib import Path
import secrets

path=Path('.env')
if path.exists():
    raise SystemExit('.env already exists; kept unchanged.')
content=Path('.env.example').read_text()
password=secrets.token_urlsafe(24)
content=content.replace('local_dev_only',password)
content=content.replace('SESSION_SECRET=\n','SESSION_SECRET='+secrets.token_urlsafe(48)+'\n')
content=content.replace('MAX_WEBHOOK_SECRET=\n','MAX_WEBHOOK_SECRET='+secrets.token_urlsafe(32)+'\n')
with path.open('x') as f: f.write(content)
try: path.chmod(0o600)
except OSError: pass
print('Created .env. Add MAX_BOT_TOKEN and MAX_BOT_NAME locally. Do not share this file.')
