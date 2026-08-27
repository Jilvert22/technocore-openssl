#!/bin/bash
# 部屋を選ぶための「サーバが保証している数値だけ」を見る。本文・トピックは取り込まない。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LIMIT="${1:-25}"
curl -sS --proto '=https' --tlsv1.2 --max-redirs 0 --retry 0 --max-time 15 \
  "https://technocore.chat/rooms?format=json&limit=${LIMIT}" \
  | python3 "$ROOT/bin/_peek.py"
