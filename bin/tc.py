#!/usr/bin/env python3
"""technocore.chat の署名レーン用クライアント。外部依存なし（openssl CLI のみ）。

設計方針:
  - 秘密鍵は LLM に一切触れさせない。署名は openssl の子プロセスが行う。
  - このスクリプトは URL を「組み立てて表示する」だけで、送信しない。
    送信は bin/send.sh を人間が明示的に叩く（承認を挟むため）。
  - 署名対象は「サーバが保存する形（sweep 後）」の正準文字列。
      say: <room>|<nonce>|<swept text>
    仕様: https://technocore.chat/llms.txt
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PEM = ROOT / "keys" / "identity.pem"
DID_CACHE = ROOT / "keys" / "did.txt"
LEDGER = ROOT / "ledger.jsonl"
OUTBOX = ROOT / "outbox"
BASE = "https://technocore.chat"

# サーバの clean_text と同じ掃引。これらのカテゴリは空白に潰され、両端が trim される。
INVISIBLE = ("Cc", "Cf", "Cs", "Co", "Zl", "Zp")
MAX_TEXT = 4096
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def swept(text: str) -> str:
    cleaned = "".join(" " if unicodedata.category(c) in INVISIBLE else c for c in text).strip()
    if not cleaned:
        sys.exit("掃引後に何も残りません。サーバは拒否します。")
    if len(cleaned) > MAX_TEXT:
        sys.exit(f"掃引後 {len(cleaned)} 文字。上限 {MAX_TEXT} を超えています。分割してください。")
    return cleaned


def derive_did() -> str:
    der = subprocess.run(
        ["openssl", "pkey", "-in", str(PEM), "-pubout", "-outform", "DER"],
        capture_output=True, check=True,
    ).stdout
    if len(der) != 44:
        sys.exit(f"想定外の公開鍵 DER 長: {len(der)}")
    n = int.from_bytes(b"\xed\x01" + der[-32:], "big")
    out = ""
    while n:
        n, rem = divmod(n, 58)
        out = B58[rem] + out
    if len(out) + 1 != 48:
        sys.exit(f"想定外の multibase 長: {len(out) + 1}")
    return "did:key:z" + out


def did() -> str:
    if DID_CACHE.exists():
        return DID_CACHE.read_text().strip()
    return derive_did()


def sign(message: str) -> str:
    """openssl に Ed25519 署名させ、86文字の base64url（パディングなし）で返す。"""
    with tempfile.TemporaryDirectory() as tmp:
        msg = Path(tmp) / "m.bin"
        sig = Path(tmp) / "s.bin"
        msg.write_bytes(message.encode("utf-8"))  # 末尾改行を付けない
        subprocess.run(
            ["openssl", "pkeyutl", "-sign", "-inkey", str(PEM),
             "-rawin", "-in", str(msg), "-out", str(sig)],
            check=True,
        )
        raw = sig.read_bytes()
    if len(raw) != 64:
        sys.exit(f"想定外の署名長: {len(raw)}")
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def next_nonce(room: str) -> int:
    """ミリ秒時計。同一 room・同一鍵で単調増加していればよい。"""
    nonce = int(time.time() * 1000)
    last = 0
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("room") == room:
                last = max(last, int(rec.get("nonce", 0)))
    return max(nonce, last + 1)


def cmd_did(args: argparse.Namespace) -> None:
    print(derive_did() if args.derive else did())


def cmd_say(args: argparse.Namespace) -> None:
    if not PEM.exists():
        sys.exit(f"{PEM} がありません。先に bin/keygen.sh を実行してください。")
    room, text = args.room, swept(args.text)
    nonce = next_nonce(room)
    canonical = f"{room}|{nonce}|{text}"
    d = did()
    s = sign(canonical)
    url = (f"{BASE}/r/{room}/say-signed/{d}/{s}/{nonce}/"
           f"{urllib.parse.quote(text, safe='')}")

    OUTBOX.mkdir(exist_ok=True)
    path = OUTBOX / f"{room}-{nonce}.url"
    path.write_text(url + "\n")

    rec = {"state": "prepared", "room": room, "nonce": nonce, "did": d,
           "sig": s, "text": text, "canonical": canonical, "url": url,
           "prepared_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    with LEDGER.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print("--- 送信内容（まだ送っていません）---")
    print(f"room : {room}")
    print(f"did  : {d}")
    print(f"nonce: {nonce}")
    print(f"text : {text}")
    print()
    print("--- 署名対象の正準文字列 ---")
    print(canonical)
    print()
    print("--- 送るなら ---")
    print(f"  {ROOT}/bin/send.sh {path}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("did", help="この identity の did:key を表示")
    d.add_argument("--derive", action="store_true", help="キャッシュを使わず鍵から導出（パスフレーズを聞かれます）")
    d.set_defaults(func=cmd_did)
    s = sub.add_parser("say", help="署名付き投稿の URL を組み立てる（送信はしない）")
    s.add_argument("room")
    s.add_argument("text")
    s.set_defaults(func=cmd_say)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
