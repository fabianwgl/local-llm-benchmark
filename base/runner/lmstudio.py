"""LM Studio client for the benchmark runner.

Model lifecycle goes through the `lms` CLI (it exposes --parallel and --identifier, which the
REST load endpoint does not document). Inference goes through the OpenAI-compatible
POST /v1/chat/completions endpoint, always streamed, so timing is measured client-side.

Stdlib only; must run on Python 3.9.
"""
from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import time
from urllib.parse import urlparse

LMS = os.path.expanduser("~/.lmstudio/bin/lms")


class InfraError(Exception):
    """A failure that is not attributable to the model under test (server down, 5xx, ...)."""


def lms(*args, timeout=900):
    """Run the lms CLI. Returns (returncode, combined output)."""
    env = dict(os.environ, NO_COLOR="1")
    try:
        p = subprocess.run([LMS] + list(args), capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        raise InfraError("lms %s timed out after %ss" % (" ".join(args), timeout))
    except OSError as e:
        raise InfraError("cannot run lms: %s" % e)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def repeated_tail(text, min_span=1200, min_repeats=6, probe=200):
    """True if `text` ends in one block repeated back-to-back (a degenerate generation loop).

    The repeated region must span at least `min_span` characters and `min_repeats` periods.
    """
    n = len(text)
    if n < min_span + probe:
        return False
    tail = text[n - probe:]
    prev = text.rfind(tail, 0, n - 1)
    if prev < 0:
        return False
    period = (n - probe) - prev
    if period <= 0:
        return False
    repeats = max(min_repeats, -(-min_span // period))
    span = period * repeats
    if span > n:
        return False
    return text[n - span:] == text[n - period:] * repeats


class Client:
    def __init__(self, base_url="http://localhost:1234"):
        u = urlparse(base_url)
        self.host = u.hostname or "localhost"
        self.port = u.port or 80

    # ---- plain JSON helpers -------------------------------------------------
    def _request(self, method, path, body=None, timeout=60):
        conn = http.client.HTTPConnection(self.host, self.port, timeout=timeout)
        try:
            data = None
            headers = {}
            if body is not None:
                data = json.dumps(body).encode("utf-8")
                headers["Content-Type"] = "application/json"
            conn.request(method, path, body=data, headers=headers)
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8", "replace")
            return resp.status, raw
        except (OSError, http.client.HTTPException) as e:
            raise InfraError("%s %s failed: %s" % (method, path, e))
        finally:
            conn.close()

    def get_json(self, path, timeout=60):
        status, raw = self._request("GET", path, timeout=timeout)
        if status != 200:
            raise InfraError("GET %s -> HTTP %s: %s" % (path, status, raw[:300]))
        return json.loads(raw)

    # ---- model lifecycle ----------------------------------------------------
    def list_models(self):
        return self.get_json("/api/v1/models")["models"]

    def model_info(self, key):
        for m in self.list_models():
            if m.get("key") == key:
                return m
        raise InfraError("model %r is not known to LM Studio" % key)

    def loaded_instances(self):
        out = []
        for m in self.list_models():
            for inst in m.get("loaded_instances") or []:
                out.append({"key": m.get("key"), "id": inst.get("id"), "config": inst.get("config") or {}})
        return out

    def unload_all(self):
        code, out = lms("unload", "--all", timeout=180)
        deadline = time.time() + 60
        while time.time() < deadline:
            if not self.loaded_instances():
                return out
            time.sleep(1)
        raise InfraError("models still loaded after `lms unload --all`: %s" % out[-300:])

    def load(self, key, context_length, identifier, parallel=1):
        """Load exactly one instance with explicit settings. Returns seconds taken."""
        self.unload_all()
        args = ["load", key, "-c", str(context_length), "--identifier", identifier, "-y"]
        if parallel:
            args += ["--parallel", str(parallel)]
        t0 = time.monotonic()
        code, out = lms(*args, timeout=1200)
        took = time.monotonic() - t0
        if code != 0:
            raise InfraError("lms load failed (%s): %s" % (code, out[-600:]))
        ok, detail = self.verify_loaded(identifier, context_length)
        if not ok:
            raise InfraError("load verification failed: %s | lms said: %s" % (detail, out[-300:]))
        return took, out

    def verify_loaded(self, identifier, context_length):
        inst = self.loaded_instances()
        if len(inst) != 1:
            return False, "expected exactly 1 loaded instance, found %d: %s" % (len(inst), inst)
        i = inst[0]
        if i["id"] != identifier:
            return False, "loaded instance id is %r, expected %r" % (i["id"], identifier)
        # llama.cpp rounds the context up to a multiple of 256 (80000 -> 80128); MLX keeps it exact.
        ctx = i["config"].get("context_length")
        if not isinstance(ctx, int) or not (context_length <= ctx < context_length + 256):
            return False, "context_length is %r, expected %r" % (ctx, context_length)
        return True, i

    # ---- streamed chat completion -------------------------------------------
    def chat_stream(self, payload, idle_timeout=1800, deadline=None, loop_guard=True, capture=None):
        """POST /v1/chat/completions with stream=true and collect the result.

        Returns a dict with: content, reasoning, reasoning_field, tool_calls, finish_reason,
        usage, timing{ttft_s, ttfa_s, total_s}, aborted (None | degenerate_loop | wall_clock |
        idle_timeout), error (None | {status, body}), chunks.
        Raises InfraError when the server cannot be reached or drops the connection early.
        `deadline` is a time.monotonic() value. `capture`, if a list, receives raw chunk objects.
        """
        body = dict(payload)
        body["stream"] = True
        body["stream_options"] = {"include_usage": True}
        data = json.dumps(body).encode("utf-8")
        conn = http.client.HTTPConnection(self.host, self.port, timeout=idle_timeout)
        t0 = time.monotonic()
        res = {
            "content": "", "reasoning": "", "reasoning_field": None, "tool_calls": [],
            "finish_reason": None, "usage": None, "aborted": None, "error": None, "chunks": 0,
            "timing": {"ttft_s": None, "ttfa_s": None, "total_s": None},
        }
        content, reasoning, calls = [], [], {}
        t_first = t_answer = None
        guard_at = 0
        try:
            try:
                conn.request("POST", "/v1/chat/completions", body=data,
                             headers={"Content-Type": "application/json", "Accept": "text/event-stream"})
                resp = conn.getresponse()
            except socket.timeout:
                res["aborted"] = "idle_timeout"
                res["timing"]["total_s"] = time.monotonic() - t0
                return res
            except (OSError, http.client.HTTPException) as e:
                raise InfraError("chat request failed: %s" % e)
            if resp.status != 200:
                res["error"] = {"status": resp.status, "body": resp.read().decode("utf-8", "replace")[:4000]}
                res["timing"]["total_s"] = time.monotonic() - t0
                return res
            saw_done = False
            while True:
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        res["aborted"] = "wall_clock"
                        break
                    if conn.sock is not None:
                        conn.sock.settimeout(max(1.0, min(idle_timeout, remaining)))
                try:
                    line = resp.readline()
                except socket.timeout:
                    if deadline is not None and time.monotonic() >= deadline:
                        res["aborted"] = "wall_clock"
                    else:
                        res["aborted"] = "idle_timeout"
                    break
                except (OSError, http.client.HTTPException) as e:
                    raise InfraError("stream broke: %s" % e)
                if not line:
                    break
                line = line.strip()
                if not line.startswith(b"data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == b"[DONE]":
                    saw_done = True
                    break
                try:
                    obj = json.loads(chunk)
                except ValueError:
                    continue
                res["chunks"] += 1
                if capture is not None:
                    capture.append(obj)
                if isinstance(obj, dict) and obj.get("error"):
                    res["error"] = {"status": 200, "body": json.dumps(obj["error"])[:4000]}
                    continue
                if obj.get("usage"):
                    res["usage"] = obj["usage"]
                now = time.monotonic()
                for ch in obj.get("choices") or []:
                    delta = ch.get("delta") or {}
                    r = delta.get("reasoning_content")
                    field = "reasoning_content"
                    if r is None:
                        r = delta.get("reasoning")
                        field = "reasoning"
                    if r and isinstance(r, str):
                        reasoning.append(r)
                        res["reasoning_field"] = field
                        t_first = t_first or now
                    c = delta.get("content")
                    if c and isinstance(c, str):
                        content.append(c)
                        t_first = t_first or now
                        t_answer = t_answer or now
                    for tc in delta.get("tool_calls") or []:
                        idx = tc.get("index", 0)
                        slot = calls.setdefault(idx, {"id": None, "type": "function",
                                                      "function": {"name": "", "arguments": ""}})
                        if tc.get("id"):
                            slot["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        name = fn.get("name")
                        if name:
                            if not slot["function"]["name"]:
                                slot["function"]["name"] = name
                            elif name != slot["function"]["name"]:
                                slot["function"]["name"] += name
                        if fn.get("arguments"):
                            slot["function"]["arguments"] += fn["arguments"]
                        t_first = t_first or now
                        t_answer = t_answer or now
                    if ch.get("finish_reason"):
                        res["finish_reason"] = ch["finish_reason"]
                if loop_guard:
                    size = sum(len(x) for x in content) + sum(len(x) for x in reasoning)
                    if size - guard_at >= 400:
                        guard_at = size
                        if repeated_tail("".join(content)) or repeated_tail("".join(reasoning)):
                            res["aborted"] = "degenerate_loop"
                            break
            if not saw_done and res["aborted"] is None and res["error"] is None \
                    and res["finish_reason"] is None:
                raise InfraError("stream ended without [DONE] or finish_reason after %d chunks" % res["chunks"])
        finally:
            conn.close()
        t_end = time.monotonic()
        res["content"] = "".join(content)
        res["reasoning"] = "".join(reasoning)
        res["tool_calls"] = [calls[i] for i in sorted(calls)]
        res["timing"] = {
            "ttft_s": (t_first - t0) if t_first else None,
            "ttfa_s": (t_answer - t0) if t_answer else None,
            "total_s": t_end - t0,
        }
        return res


def gen_speed(res):
    """Tokens/sec for one chat_stream result, or None when it cannot be computed."""
    usage = res.get("usage") or {}
    tok = usage.get("completion_tokens")
    t = res.get("timing") or {}
    if not tok or t.get("ttft_s") is None or t.get("total_s") is None:
        return None
    span = t["total_s"] - t["ttft_s"]
    return tok / span if span > 0.05 else None
