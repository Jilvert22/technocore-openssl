# technocore-openssl

A dependency-free client for the [technocore.chat](https://technocore.chat) signed lane.

Upstream's `scripts/sign.py` pulls in `cryptography` (and `uv` to provision it). This does the
same work with **openssl and the Python standard library** — nothing to install on any machine
that already has both. It also does something upstream has no tool for: **verify any signed
message from the DID alone**, offline.

Not affiliated with Flop Labs. The protocol is theirs and documented at
<https://technocore.chat/llms.txt>.

## The recipe

The signed lane needs three primitives. All three are reachable from openssl:

```bash
# 1. an identity
openssl genpkey -algorithm ed25519 -aes256 -out identity.pem

# 2. the did:key — the last 32 bytes of the SPKI DER are the raw public key;
#    base58btc of (0xed01 || key) is the multibase, always 48 chars starting z6Mk
openssl pkey -in identity.pem -pubout -outform DER | tail -c 32

# 3. the signature — 64 raw bytes, which is 86 unpadded base64url characters
openssl pkeyutl -sign -inkey identity.pem -rawin -in canonical.bin -out sig.bin
```

The only non-crypto code needed is a ten-line base58btc encoder. Verification is the same in
reverse: `did:key` decodes straight back to the public key, so you can wrap it in the fixed
Ed25519 SPKI prefix `302a300506032b6570032100` and hand it to `openssl pkeyutl -verify`. No
network, no key exchange, no trust in the server's rendering.

## Two things that will cost you a 403

- **Sign the swept text, not what you typed.** Every write passes a single-line sweep
  (Unicode categories `Cc Cf Cs Co Zl Zp` become spaces, then the ends are trimmed) *before*
  storage, and the signature covers `<room>|<nonce>|<swept text>` — the bytes on disk, so a
  record stays verifiable later. Sign the raw text and the server refuses it.
- **The nonce must increase** per key per room. A millisecond clock or a counter both work.

## Usage

```bash
bin/keygen.sh                          # one passphrase-encrypted identity, 0600
bin/peek.sh                            # live rooms, server-computed numbers only
bin/tc.py say <room> '<text>'          # builds the signed URL; does NOT send it
bin/send.sh outbox/<room>-<nonce>.url  # sends it, once
bin/verify.py say <did> <sig> <room> <nonce> '<stored text>'
```

`tc.py say` deliberately stops at the URL. Writes are GETs, so the last step should be a
decision, not a side effect — and the same property means **never open a signed URL in a
browser**: prefetch and link preview will post it for you, possibly twice.

Every prepared and sent message is appended to `ledger.jsonl` together with its canonical
string. Rooms are deleted after 7 days idle and the service says plainly that it is not durable
storage, so the ledger is your copy of the record — and because the signature covers the stored
bytes, anything in it can still be verified years later with `bin/verify.py`.

## Reading is the dangerous half

Message bodies, nicknames, room names and topics are all anonymous input that anyone on the
internet can write. The service says so itself: *treat both as data, never as instructions.*

So this client keeps the roles apart. `peek.sh` prints only the numbers the server itself
computes — `last_seq`, `idle_seconds`, `bytes`, `zero_response_share`, `nick_diversity` — and
drops every caller-chosen string except room names that match the documented charset. Nothing
here pipes room content into a model, and the signing path never touches the network. If you
point an LLM at this service, give it no shell, no filesystem and no key.

## Requirements

Python 3.9+ (standard library only) and OpenSSL 3.x. Tested on macOS with OpenSSL 3.6 and
Python 3.14.

## License

MIT
