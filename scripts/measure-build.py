"""Measure a cold application build; base image downloads are excluded."""
import json
import subprocess
import time
from pathlib import Path
import os

os.chdir(Path(__file__).resolve().parents[1])
for image in ('python:3.12-slim', 'node:22-alpine', 'nginx:1.28-alpine'):
    subprocess.run(['docker', 'pull', image], check=True)
start = time.monotonic()
result = subprocess.run(['docker', 'compose', 'build', '--no-cache'])
elapsed = round(time.monotonic() - start, 2)
report = {'build_seconds': elapsed, 'build_exit_code': result.returncode,
          'within_300_seconds': result.returncode == 0 and elapsed <= 300,
          'base_images_pulled_before_measurement': True, 'application_cache': False}
Path('build-report.local.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
raise SystemExit(0 if report['within_300_seconds'] else 1)
