#!/usr/bin/env python3
"""Send-only Telegram notifier for the benchmark.

CLI:     python3 base/runner/notify.py "run finished: qwen3-32b"
         echo "text" | python3 base/runner/notify.py
         python3 base/runner/notify.py --html < card.html      (Telegram HTML formatting)
         python3 base/runner/notify.py --html --edit 123 < card.html   (edit message 123, no notification)
Library: from notify import send, edit; mid = send("text"); edit(mid, "<b>new</b>", parse_mode="HTML")

Config (env vars, or a .env file in the project root; real env wins):
    TELEGRAM_BOT_TOKEN   token from @BotFather
    TELEGRAM_CHAT_ID     chat/user/channel id that receives the message

Send and edit only: never reads updates. Plain text by default; parse_mode="HTML" (CLI: --html) enables
Telegram's HTML subset. Keep formatted messages under 4096 chars: a split could cut through a tag.
Stdlib only, Python 3.9.
The token is never printed or logged.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"
MAX_LEN = 4096  # Telegram hard limit per message


class NotifyError(Exception):
    pass


def _load_env(path=ENV_FILE):
    """Parse KEY=VALUE lines. Ignores blanks, comments, `export `, and surrounding quotes."""
    out = {}
    try:
        lines = Path(path).read_text().splitlines()
    except OSError:
        return out
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, val = line.partition("=")
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key.strip()] = val
    return out


def _config():
    file_env = _load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or file_env.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID") or file_env.get("TELEGRAM_CHAT_ID")
    missing = [n for n, v in (("TELEGRAM_BOT_TOKEN", token), ("TELEGRAM_CHAT_ID", chat)) if not v]
    if missing:
        raise NotifyError("missing %s (set in %s or the environment)" % (", ".join(missing), ENV_FILE))
    return token, chat


def _chunks(text, size=MAX_LEN):
    """Split on line breaks where possible so no message exceeds Telegram's limit."""
    while len(text) > size:
        cut = text.rfind("\n", 0, size)
        if cut <= 0:
            cut = size
        yield text[:cut]
        text = text[cut:].lstrip("\n")
    if text:
        yield text


def _post(token, chat, text, parse_mode=None, message_id=None):
    """sendMessage, or editMessageText when message_id is given. Returns Telegram's result object."""
    payload = {"chat_id": chat, "text": text, "disable_web_page_preview": True}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if message_id is not None:
        payload["message_id"] = int(message_id)
    req = urllib.request.Request(
        "https://api.telegram.org/bot%s/%s" % (token, "sendMessage" if message_id is None else "editMessageText"),
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as e:
        # The Telegram error body says why (bad chat id, bot blocked, ...). Never echo the URL: it has the token.
        try:
            desc = json.load(e).get("description", "")
        except Exception:
            desc = ""
        raise NotifyError("telegram HTTP %s: %s" % (e.code, desc or e.reason)) from None
    except (urllib.error.URLError, OSError) as e:
        raise NotifyError("network error: %s" % getattr(e, "reason", type(e).__name__)) from None
    if not body.get("ok"):
        raise NotifyError("telegram refused: %s" % body.get("description", "unknown"))
    return body.get("result")


def send(text, parse_mode=None):
    """Send `text` (split if over 4096 chars). parse_mode: None (plain), "HTML" or "MarkdownV2".
    Returns the message_id of the last part sent. Raises NotifyError on any failure."""
    text = text.strip()
    if not text:
        raise NotifyError("empty message")
    token, chat = _config()
    mid = None
    for part in _chunks(text):
        mid = (_post(token, chat, part, parse_mode) or {}).get("message_id")
    return mid


def edit(message_id, text, parse_mode=None):
    """Replace the text of a message this bot sent earlier. Edits do not notify the chat.
    The text must fit in one message. An unchanged text is not an error."""
    text = text.strip()
    if not text:
        raise NotifyError("empty message")
    if len(text) > MAX_LEN:
        raise NotifyError("an edited message must fit in %d chars" % MAX_LEN)
    token, chat = _config()
    try:
        _post(token, chat, text, parse_mode, message_id=message_id)
    except NotifyError as e:
        if "message is not modified" not in str(e):
            raise


def main(argv):
    parse_mode, message_id = None, None
    while argv and argv[0] in ("--html", "--edit"):
        if argv[0] == "--html":
            parse_mode, argv = "HTML", argv[1:]
        else:
            if len(argv) < 2:
                print("--edit needs a message_id", file=sys.stderr)
                return 2
            message_id, argv = argv[1], argv[2:]
    text = " ".join(argv) if argv else (sys.stdin.read() if not sys.stdin.isatty() else "")
    if not text.strip():
        print("usage: notify.py [--html] [--edit MESSAGE_ID] <message>   (or pipe text on stdin)", file=sys.stderr)
        return 2
    try:
        if message_id is None:
            mid = send(text, parse_mode)
            print("sent (message_id %s)" % mid)
        else:
            edit(message_id, text, parse_mode)
            print("edited (message_id %s)" % message_id)
    except NotifyError as e:
        print("notify failed: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
