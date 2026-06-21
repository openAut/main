#!/usr/bin/env python3
"""Minimal Microsoft Teams <-> OpenClaw gateway webhook bridge.

Reference stub for the openAut NemoClaw channel default. Two directions:

  Teams  -> POST /teams         (Outgoing Webhook, HMAC-signed)  -> forwarded to the gateway
  agent  -> POST /to-teams      (local, from the gateway/agent)  -> Teams Incoming Webhook card

Config comes from environment (source ../../config.env first):
  TEAMS_BRIDGE_HOST, TEAMS_BRIDGE_PORT
  TEAMS_INCOMING_WEBHOOK_URL   gateway/agent -> Teams
  TEAMS_OUTGOING_SECRET        HMAC secret Teams signs Outgoing Webhook calls with
  TEAMS_TO_TEAMS_TOKEN         bearer token required for local /to-teams posts
  GATEWAY_WEBHOOK_URL          where to forward inbound Teams messages (optional)

Stdlib only — no Flask. Not production-hardened; see README security notes.
"""
import base64
import hashlib
import hmac
import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("TEAMS_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("TEAMS_BRIDGE_PORT", "8790"))
INCOMING_WEBHOOK_URL = os.environ.get("TEAMS_INCOMING_WEBHOOK_URL", "")
OUTGOING_SECRET = os.environ.get("TEAMS_OUTGOING_SECRET", "")
TO_TEAMS_TOKEN = os.environ.get("TEAMS_TO_TEAMS_TOKEN", "")
GATEWAY_WEBHOOK_URL = os.environ.get("GATEWAY_WEBHOOK_URL", "")
MAX_BODY_BYTES = int(os.environ.get("TEAMS_BRIDGE_MAX_BODY_BYTES", "65536"))


def verify_teams_signature(body: bytes, auth_header: str) -> bool:
    """Teams Outgoing Webhooks sign the raw body: 'HMAC <base64(hmac_sha256(secret, body))>'."""
    if not OUTGOING_SECRET or not auth_header.startswith("HMAC "):
        return False
    try:
        key = base64.b64decode(OUTGOING_SECRET)
    except Exception:
        return False
    digest = hmac.new(key, body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    provided = auth_header.split(" ", 1)[1].strip()
    return hmac.compare_digest(expected, provided)


def post_json(url: str, payload: dict) -> int:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status


def verify_bearer_token(auth_header: str) -> bool:
    if not TO_TEAMS_TOKEN or not auth_header.startswith("Bearer "):
        return False
    provided = auth_header.split(" ", 1)[1].strip()
    return hmac.compare_digest(TO_TEAMS_TOKEN, provided)


def parse_content_length(raw_value: str | None) -> int | None:
    try:
        return int(raw_value or "0")
    except ValueError:
        return None


def send_to_teams(text: str) -> int:
    """Post a simple MessageCard to the Teams Incoming Webhook."""
    if not INCOMING_WEBHOOK_URL:
        raise RuntimeError("TEAMS_INCOMING_WEBHOOK_URL not set")
    card = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": "openAut",
        "text": text,
    }
    return post_json(INCOMING_WEBHOOK_URL, card)


class Handler(BaseHTTPRequestHandler):
    def _reply(self, code: int, obj: dict):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        length = parse_content_length(self.headers.get("Content-Length"))
        if length is None:
            self._reply(400, {"ok": False, "error": "bad content-length"})
            return
        if length > MAX_BODY_BYTES:
            self._reply(413, {"ok": False, "error": "request body too large"})
            return
        body = self.rfile.read(length) if length else b""

        if self.path == "/teams":
            # Inbound from Teams Outgoing Webhook — verify HMAC, then forward to the gateway.
            if not verify_teams_signature(body, self.headers.get("Authorization", "")):
                self._reply(401, {"type": "message", "text": "rejected: bad signature"})
                return
            try:
                msg = json.loads(body or b"{}")
            except json.JSONDecodeError:
                self._reply(400, {"type": "message", "text": "bad json"})
                return
            text = (msg.get("text") or "").strip()
            user = (msg.get("from") or {}).get("name", "teams-user")
            if GATEWAY_WEBHOOK_URL:
                try:
                    post_json(GATEWAY_WEBHOOK_URL, {"channel": "teams", "user": user, "text": text})
                except Exception as exc:  # noqa: BLE001
                    self._reply(502, {"type": "message", "text": f"gateway error: {exc}"})
                    return
            # Teams shows the JSON reply inline in the channel.
            self._reply(200, {"type": "message", "text": "mottaget av openAut-agenten."})

        elif self.path == "/to-teams":
            # Outbound from gateway/agent -> Teams.
            if not verify_bearer_token(self.headers.get("Authorization", "")):
                self._reply(401, {"ok": False, "error": "missing or bad bearer token"})
                return
            try:
                payload = json.loads(body or b"{}")
                status = send_to_teams(payload.get("text", ""))
            except Exception as exc:  # noqa: BLE001
                self._reply(502, {"ok": False, "error": str(exc)})
                return
            self._reply(200, {"ok": True, "teams_status": status})

        else:
            self._reply(404, {"ok": False, "error": "unknown path"})

    def log_message(self, *args):  # quieter logs
        return


def main():
    if not OUTGOING_SECRET:
        print("WARN: TEAMS_OUTGOING_SECRET unset — inbound Teams requests will be rejected.")
    if not INCOMING_WEBHOOK_URL:
        print("WARN: TEAMS_INCOMING_WEBHOOK_URL unset — cannot post to Teams.")
    if not TO_TEAMS_TOKEN:
        print("WARN: TEAMS_TO_TEAMS_TOKEN unset — /to-teams requests will be rejected.")
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Teams bridge listening on http://{HOST}:{PORT}  (/teams inbound, /to-teams outbound)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
