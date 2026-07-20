#!/usr/bin/env bash
# Quick demo via Docker (no host Python needed)
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

docker compose up -d --build
docker compose run --rm --entrypoint "" python python main.py --demo --fresh

echo ""
echo "Excel written to: $(pwd)/output/invoices.xlsx"
