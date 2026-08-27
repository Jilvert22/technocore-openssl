#!/bin/bash
# Technocore 専用の使い捨て Ed25519 identity を作る。
# 秘密鍵はパスフレーズ暗号化。パスフレーズは openssl が直接聞くので、
# スクリプトにも履歴にも Claude のコンテキストにも残らない。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PEM="$ROOT/keys/identity.pem"

if [ -f "$PEM" ]; then
  echo "既に $PEM があります。上書きすると DID が変わり、それまでの署名履歴と切り離されます。" >&2
  echo "作り直すなら手動で退避してから実行してください。" >&2
  exit 1
fi

umask 077
echo "パスフレーズを3回聞かれます: 設定2回 + DID導出のための読み出し1回（すべて同じもの）" 
openssl genpkey -algorithm ed25519 -aes256 -out "$PEM"
chmod 600 "$PEM"

# DID は公開情報なので平文でキャッシュする（毎回パスフレーズを聞かないため）
"$ROOT/bin/tc.py" did --derive > "$ROOT/keys/did.txt"
echo
echo "作成しました:"
echo "  秘密鍵: $PEM (0600, パスフレーズ暗号化)"
echo "  DID:    $(cat "$ROOT/keys/did.txt")"
echo
echo "!! この2つを別々にバックアップしてください。復旧サービスはありません。"
echo "!! iCloud/Dropbox/git に置かないこと。"
