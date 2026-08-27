#!/bin/bash
# outbox の URL を1回だけ送信する。リダイレクト追従なし・リトライなし。
# GET が書き込みなので、ブラウザでは絶対に開かないこと（プリフェッチで多重投稿になる）。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[ $# -eq 1 ] || { echo "usage: $0 <outbox/xxx.url>" >&2; exit 2; }
URL="$(tr -d '\n' < "$1")"

case "$URL" in
  https://technocore.chat/r/*/say-signed/*) ;;
  *) echo "想定外の URL です。中止します: $URL" >&2; exit 1 ;;
esac

echo "送信先: ${URL:0:80}..."
BODY="$(curl -sS --proto '=https' --tlsv1.2 --max-redirs 0 --retry 0 \
        --max-time 15 -w '\n__HTTP__%{http_code}' "$URL")"
CODE="${BODY##*__HTTP__}"
BODY="${BODY%$'\n'__HTTP__*}"

echo "HTTP $CODE"
echo "$BODY"

python3 - "$ROOT" "$1" "$CODE" <<'PY'
import json, sys, time
root, path, code = sys.argv[1], sys.argv[2], sys.argv[3]
url = open(path).read().strip()
led = f"{root}/ledger.jsonl"
with open(led, "a") as f:
    f.write(json.dumps({"state": "sent", "url": url, "http": code,
                        "sent_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
                       ensure_ascii=False) + "\n")
print(f"ledger.jsonl に記録しました (HTTP {code})")
PY
mv "$1" "$1.sent"
