#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ ! -f .env ]; then python3 scripts/init_env.py; fi
docker compose -f compose.yaml -f compose.demo.yaml up --build -d --force-recreate --wait --wait-timeout 900
printf '%s\n' 'Tochka prityazheniya 1.3.1: http://localhost:8080'
