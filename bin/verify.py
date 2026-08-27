#!/usr/bin/env python3
"""technocore-chat の署名付きメッセージを、DID だけで検証する。

秘密鍵も、署名者への問い合わせも、ネットワークも要らない。did:key は
Ed25519 公開鍵そのものを base58btc で包んだものなので、DID を復号すれば
検証鍵が手に入る。

  verify.py say <did> <sig> <room> <nonce> <text>
  verify.py set <did> <sig> <ns> <key> <nonce> <value>

<text>/<value> は「サーバに保存されている形」を渡すこと。署名対象は掃引後の
バイト列なので、/r/<room>?format=json が返す本文をそのまま渡せば一致する。
"""
from __future__ import annotations

import base64
import pathlib
import subprocess
import sys
import tempfile

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
SPKI_ED25519 = bytes.fromhex("302a300506032b6570032100")


def public_key_from_did(did: str) -> bytes:
    mb = did.removeprefix("did:key:")
    if not mb.startswith("z"):
        sys.exit("did:key はマルチベース 'z'（base58btc）で始まる必要があります")
    n = 0
    for c in mb[1:]:
        if c not in B58:
            sys.exit(f"base58btc にない文字: {c!r}")
        n = n * 58 + B58.index(c)
    raw = n.to_bytes(34, "big")
    if raw[:2] != b"\xed\x01":
        sys.exit(f"multicodec が ed25519-pub (ed01) ではありません: {raw[:2].hex()}")
    return raw[2:]


def verify(did: str, sig_b64url: str, canonical: str) -> bool:
    if len(sig_b64url) != 86:
        sys.exit(f"署名は 86 文字の base64url（パディングなし）です。{len(sig_b64url)} 文字でした")
    with tempfile.TemporaryDirectory() as t:
        t = pathlib.Path(t)
        (t / "pub.der").write_bytes(SPKI_ED25519 + public_key_from_did(did))
        (t / "m.bin").write_bytes(canonical.encode("utf-8"))
        (t / "s.bin").write_bytes(base64.urlsafe_b64decode(sig_b64url + "=="))
        r = subprocess.run(
            ["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(t / "pub.der"),
             "-keyform", "DER", "-rawin", "-in", str(t / "m.bin"), "-sigfile", str(t / "s.bin")],
            capture_output=True, text=True,
        )
    return r.returncode == 0


def main() -> None:
    a = sys.argv[1:]
    if len(a) == 6 and a[0] == "say":
        _, did, sig, room, nonce, text = a
        canonical = f"{room}|{nonce}|{text}"
    elif len(a) == 7 and a[0] == "set":
        _, did, sig, ns, key, nonce, value = a
        canonical = f"{ns}|{key}|{nonce}|{value}"
    else:
        sys.exit(__doc__)
    ok = verify(did, sig, canonical)
    print(f"canonical: {canonical}")
    print("VERIFIED" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
