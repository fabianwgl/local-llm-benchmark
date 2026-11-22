"""Docker sandbox, the agent tool loop, the sub-case loop, and hidden-check execution.

Stdlib only; must run on Python 3.9.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import time
import uuid
from pathlib import Path

from lmstudio import InfraError

EXCLUDE_DIRS = ["target", "node_modules", "__pycache__", ".pytest_cache", ".git", ".mypy_cache"]
MAX_SNAPSHOT_BYTES = 200 * 1024 * 1024
MAX_FILE_BYTES = 20 * 1024 * 1024


def _tool(name, desc, props, required):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required}}}


_PATH = {"type": "string", "description": "File path, relative to /work"}
TOOLS = [
    _tool("read_file",
          "Read a text file. Returns numbered lines, at most 400 per call; use start_line and end_line for long files.",
          {"path": _PATH, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}}, ["path"]),
    _tool("write_file",
          "Create or overwrite a file with the given content. Parent directories are created.",
          {"path": _PATH, "content": {"type": "string"}}, ["path", "content"]),
    _tool("edit_file",
          "Replace an exact string in a file. old_string must match the file exactly, including whitespace, "
          "and must be unique unless replace_all is true.",
          {"path": _PATH, "old_string": {"type": "string"}, "new_string": {"type": "string"},
           "replace_all": {"type": "boolean"}}, ["path", "old_string", "new_string"]),
    _tool("run_command",
          "Run a bash command in /work. Returns the exit code and combined output. Default timeout 60 s, maximum 120 s.",
          {"command": {"type": "string"}, "timeout_s": {"type": "integer"}}, ["command"]),
    _tool("finish",
          "End the task. Call this once the work is complete, or if you cannot make further progress.",
          {"summary": {"type": "string", "description": "What you changed and why, in a few sentences."}},
          ["summary"]),
]
TOOL_NAMES = [t["function"]["name"] for t in TOOLS]
REQUIRED = {t["function"]["name"]: t["function"]["parameters"]["required"] for t in TOOLS}

NUDGE_MALFORMED = ("Your last reply contained text that looks like a tool call, but it was not a valid function "
                   "call, so nothing was executed. Call tools through the function-calling interface. If the task "
                   "is complete, call the finish tool.")
NUDGE_NO_ACTION = ("Your last reply did not call a tool, so nothing happened. Continue the task by calling a tool. "
                   "If the task is complete, call the finish tool with a summary.")
NUDGE_LENGTH = ("Your last reply hit the per-step output limit and was cut off before any tool call, so nothing "
                "was executed. Reply more briefly and call a tool.")

_CALL_PATTERNS = [
    re.compile(r"<\s*/?\s*tool_call", re.I), re.compile(r"\[TOOL_REQUEST\]", re.I),
    re.compile(r"<\|?\s*tool[_ ]?call", re.I), re.compile(r"<function\s*=", re.I),
    re.compile(r"\"(?:name|tool|function)\"\s*:\s*\"(?:%s)\"" % "|".join(TOOL_NAMES)),
    re.compile(r"\b(?:%s)\s*\(\s*[\{\"']" % "|".join(TOOL_NAMES)),
]


def looks_like_tool_call(text):
    return any(p.search(text or "") for p in _CALL_PATTERNS)


def est_tokens(chars):
    return -(-chars // 3)  # deliberately conservative


def _docker(args, timeout=120, input_bytes=None):
    try:
        return subprocess.run(["docker"] + args, capture_output=True, timeout=timeout, input=input_bytes)
    except subprocess.TimeoutExpired:
        raise InfraError("docker %s timed out" % " ".join(args[:3]))
    except OSError as e:
        raise InfraError("cannot run docker: %s" % e)


def _limits_flags(suite):
    sb = suite["sandbox"]
    return ["--network", "none", "--memory", sb["memory"], "--cpus", str(sb["cpus"]),
            "--pids-limit", str(sb["pids_limit"])]


def _env_flags(env):
    flags = []
    for k, v in (env or {}).items():
        flags += ["-e", "%s=%s" % (k, v)]
    return flags


class Sandbox:
    """One long-lived container per agentic test. Nothing on the host is mounted."""

    def __init__(self, suite, workspace_src=None, env=None):
        self.suite = suite
        self.src = workspace_src
        self.env = env or {}
        self.name = "bench-" + uuid.uuid4().hex[:12]
        self.started = False

    def start(self):
        p = _docker(["run", "-d", "--name", self.name] + _limits_flags(self.suite)
                    + ["--security-opt", "no-new-privileges"] + _env_flags(self.env)
                    + [self.suite["sandbox"]["image"], "sleep", "infinity"])
        if p.returncode != 0:
            raise InfraError("docker run failed: %s" % p.stderr.decode("utf-8", "replace")[-400:])
        self.started = True
        if self.src:
            p = _docker(["cp", str(self.src) + "/.", self.name + ":/work"])
            if p.returncode != 0:
                raise InfraError("docker cp failed: %s" % p.stderr.decode("utf-8", "replace")[-400:])
            p = _docker(["exec", "-u", "0", self.name, "chown", "-R", "bench:bench", "/work"])
            if p.returncode != 0:
                raise InfraError("chown failed: %s" % p.stderr.decode("utf-8", "replace")[-400:])
        return self

    def tool(self, op, args, limits):
        """Execute one tool call inside the container. Returns (ok, output text)."""
        req = json.dumps({"op": op, "args": args, "limits": limits}).encode("utf-8")
        backstop = int(limits.get("cmd_timeout_max_s", 120)) + 45
        try:
            p = subprocess.run(["docker", "exec", "-i", "-u", "bench", "-w", "/work", self.name,
                                "python3", "/opt/bench/tool.py"], input=req, capture_output=True, timeout=backstop)
        except subprocess.TimeoutExpired:
            _docker(["exec", "-u", "0", self.name, "pkill", "-KILL", "-u", "bench"], timeout=30)
            return False, "ERROR: the tool did not return within %d seconds and was killed" % backstop
        except OSError as e:
            raise InfraError("cannot run docker exec: %s" % e)
        try:
            reply = json.loads(p.stdout.decode("utf-8", "replace"))
            return bool(reply.get("ok")), str(reply.get("output"))
        except ValueError:
            err = p.stderr.decode("utf-8", "replace")[-300:]
            if "No such container" in err or "is not running" in err:
                raise InfraError("sandbox container died: %s" % err)
            return False, "ERROR: tool execution failed: %s" % (err or "no output")

    def snapshot(self, dest_tar):
        """Write a tar of /work (build directories excluded) to dest_tar."""
        cmd = ["exec", "-u", "0", self.name, "tar", "-C", "/work"]
        for d in EXCLUDE_DIRS:
            cmd += ["--exclude=./%s" % d, "--exclude=*/%s" % d]
        cmd += ["-cf", "-", "."]
        with open(dest_tar, "wb") as out:
            try:
                p = subprocess.run(["docker"] + cmd, stdout=out, stderr=subprocess.PIPE, timeout=300)
            except subprocess.TimeoutExpired:
                raise InfraError("snapshot timed out")
        if p.returncode not in (0, 1):
            raise InfraError("snapshot failed: %s" % p.stderr.decode("utf-8", "replace")[-300:])

    def stop(self):
        if self.started:
            try:
                _docker(["rm", "-f", self.name], timeout=60)
            except InfraError:
                pass
            self.started = False


class FakeSandbox:
    """Stand-in used by the harness self-tests: canned tool output, no Docker."""

    def __init__(self, outputs=None):
        self.outputs = outputs or {}
        self.calls = []

    def tool(self, op, args, limits):
        self.calls.append((op, args))
        return True, self.outputs.get(op, "ok")


# ---------------------------------------------------------------------------
# workspace snapshots
# ---------------------------------------------------------------------------
def safe_extract(tar_path, dest):
    """Extract regular files and directories only; refuse anything that could escape dest."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    total = 0
    skipped = []
    with tarfile.open(tar_path) as tf:
        for m in tf:
            name = os.path.normpath(m.name)
            if name in (".", "") or name.startswith("..") or os.path.isabs(name):
                continue
            target = dest / name
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif m.isfile():
                if m.size > MAX_FILE_BYTES or total + m.size > MAX_SNAPSHOT_BYTES:
                    skipped.append(name)
                    continue
                total += m.size
                target.parent.mkdir(parents=True, exist_ok=True)
                src = tf.extractfile(m)
                with open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
                os.chmod(target, 0o755 if (m.mode & 0o111) else 0o644)
            else:
                skipped.append(name)
    return skipped


def tree_hashes(root):
    root = Path(root)
    out = {}
    if root.is_file():
        return {"": hashlib.sha256(root.read_bytes()).hexdigest()}
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file() and not any(part in EXCLUDE_DIRS for part in p.relative_to(root).parts):
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def restore_protected(protected, fixture, final):
    """Record which protected fixture files the model edited or deleted, then put them back.

    Adding new files next to protected ones (a new regression test, say) is not tampering.
    """
    tampered = []
    for rel in protected or []:
        rel = rel.rstrip("/")
        a = Path(fixture) / rel
        files = [a] if a.is_file() else sorted(p for p in a.rglob("*") if p.is_file()) if a.is_dir() else []
        for src in files:
            sub = src.relative_to(fixture)
            if any(part in EXCLUDE_DIRS for part in sub.parts):
                continue
            dst = Path(final) / sub
            if dst.is_file() and dst.read_bytes() == src.read_bytes():
                continue
            tampered.append(str(sub))
            if dst.is_dir():
                shutil.rmtree(dst)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return tampered


def make_diff(fixture, final):
    cmd = ["diff", "-ruN"]
    for d in EXCLUDE_DIRS:
        cmd += ["-x", d]
    cmd += [str(fixture), str(final)]
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=120)
    except (subprocess.TimeoutExpired, OSError):
        return "(diff failed)"
    text = p.stdout.decode("utf-8", "replace")
    return text.replace(str(fixture), "a").replace(str(final), "b")


# ---------------------------------------------------------------------------
# hidden checks
# ---------------------------------------------------------------------------
def run_check(suite, cmd, hidden_dir, lib_dir, in_dir, timeout_s, env=None):
    """Run a test's check command in a fresh container.

    /hidden, /checklib and /in are copied in (never mounted); the check writes /out/result.json.
    Returns {"ran", "exit_code", "result", "log", "error"}.
    """
    name = "bench-check-" + uuid.uuid4().hex[:12]
    out = {"ran": False, "exit_code": None, "result": None, "log": "", "error": None}
    p = _docker(["create", "--name", name] + _limits_flags(suite) + _env_flags(env)
                + [suite["sandbox"]["image"], "bash", "-lc", cmd])
    if p.returncode != 0:
        raise InfraError("docker create failed: %s" % p.stderr.decode("utf-8", "replace")[-400:])
    try:
        for src, dst in ((hidden_dir, "/hidden"), (lib_dir, "/checklib"), (in_dir, "/in")):
            if src and Path(src).exists():
                p = _docker(["cp", str(src) + "/.", "%s:%s" % (name, dst)])
                if p.returncode != 0:
                    raise InfraError("docker cp to check container failed: %s"
                                     % p.stderr.decode("utf-8", "replace")[-400:])
        try:
            p = subprocess.run(["docker", "start", "-a", name], capture_output=True, timeout=timeout_s)
            out["ran"] = True
            out["exit_code"] = p.returncode
            out["log"] = (p.stdout + p.stderr).decode("utf-8", "replace")[-60000:]
        except subprocess.TimeoutExpired as e:
            out["error"] = "check timed out after %ss" % timeout_s
            out["log"] = ((e.stdout or b"") + (e.stderr or b"")).decode("utf-8", "replace")[-60000:]
            _docker(["kill", name], timeout=60)
        p = _docker(["cp", "%s:/out/result.json" % name, "-"])
        if p.returncode == 0:
            import io
            try:
                with tarfile.open(fileobj=io.BytesIO(p.stdout)) as tf:
                    member = tf.next()
                    out["result"] = json.loads(tf.extractfile(member).read().decode("utf-8"))
            except (tarfile.TarError, ValueError, AttributeError) as e:
                out["error"] = "result.json unreadable: %s" % e
        elif not out["error"]:
            out["error"] = "check produced no /out/result.json"
    finally:
        try:
            _docker(["rm", "-f", name], timeout=60)
        except InfraError:
            pass
    return out


# ---------------------------------------------------------------------------
# the agent loop
# ---------------------------------------------------------------------------
def _usage_tokens(res):
    """(prompt_tokens, completion_tokens, estimated?) for one chat result."""
    usage = res.get("usage") or {}
    pt, ct = usage.get("prompt_tokens"), usage.get("completion_tokens")
    if pt is not None and ct is not None:
        return pt, ct, False
    ct = est_tokens(len(res.get("content") or "") + len(res.get("reasoning") or "")
                    + sum(len(json.dumps(c)) for c in res.get("tool_calls") or []))
    return pt, ct, True


def sanitize_calls(calls):
    """Split raw tool calls into (calls safe to send back in history, per-call parse info)."""
    sent, info = [], []
    for i, c in enumerate(calls):
        fn = c.get("function") or {}
        name = fn.get("name") or ""
        raw = fn.get("arguments") or ""
        cid = c.get("id") or "call_%d_%s" % (i, uuid.uuid4().hex[:6])
        parsed, err = None, None
        try:
            parsed = json.loads(raw) if raw.strip() else {}
            if not isinstance(parsed, dict):
                err, parsed = "arguments must be a JSON object", None
        except ValueError as e:
            err = "arguments are not valid JSON (%s)" % e
        # Empty arguments (a reply cut off by max_tokens mid-call) must go back as "{}": LM Studio
        # answers HTTP 500 to a history entry whose arguments are "" (seen with MLX Qwen models).
        sent.append({"id": cid, "type": "function",
                     "function": {"name": name, "arguments": raw if err is None and raw.strip() else "{}"}})
        info.append({"id": cid, "name": name, "raw_arguments": raw, "args": parsed, "error": err})
    return sent, info


def run_agent(chat, make_payload, prompt_text, system_text, sandbox, limits, context_length, log, deadline):
    """Drive one agentic test.

    chat(payload, deadline) -> chat result dict (lmstudio.Client.chat_stream shape).
    make_payload(messages, max_tokens) -> request payload (model, sampler, seed).
    log(event dict) appends to the transcript.
    Returns a dict: end_reason, summary, steps, counters, tokens, per_step.
    """
    messages = [{"role": "system", "content": system_text}, {"role": "user", "content": prompt_text}]
    step_max = int(limits["agent_step_max_tokens"])
    c = {"tool_calls": 0, "tool_calls_valid": 0, "invalid_json": 0, "unknown_tool": 0, "missing_args": 0,
         "tool_errors": 0, "malformed_text_calls": 0, "no_action_replies": 0, "length_cutoffs": 0,
         "nudges": 0, "dropped_calls": 0}
    out = {"end_reason": None, "summary": None, "steps": 0, "counters": c, "per_step": [],
           "prompt_tokens_last": None, "completion_tokens_total": 0, "reasoning_chars_total": 0,
           "usage_estimated": False}
    last_prompt = None
    chars_since = 0
    consecutive = 0

    def end(reason):
        out["end_reason"] = reason
        log({"type": "end", "reason": reason})
        return out

    def nudge(text, kind):
        nonlocal consecutive, chars_since
        c["nudges"] += 1
        consecutive += 1
        if consecutive > int(limits["nudges_consecutive"]) or c["nudges"] > int(limits["nudges_total"]):
            return False
        messages.append({"role": "user", "content": text})
        chars_since += len(text)
        log({"type": "nudge", "kind": kind, "text": text})
        return True

    while True:
        if out["steps"] >= int(limits["agent_max_steps"]):
            return end("step_cap")
        if out["completion_tokens_total"] >= int(limits["agent_total_completion_tokens"]):
            return end("token_budget")
        if time.monotonic() >= deadline:
            return end("wall_clock")
        if last_prompt is not None:
            projected = last_prompt + est_tokens(chars_since) + step_max + int(limits["context_margin_tokens"])
            if projected > context_length:
                return end("context_exhausted")

        payload = make_payload(messages, step_max)
        payload["tools"] = TOOLS
        payload["tool_choice"] = "auto"
        res = chat(payload, deadline)
        out["steps"] += 1

        if res.get("error"):
            status = res["error"].get("status")
            body = res["error"].get("body") or ""
            if re.search(r"context (length|size)|exceed_context", body, re.I):
                log({"type": "server_error", "error": res["error"]})
                return end("context_exhausted")
            raise InfraError("chat error HTTP %s: %s" % (status, body[:300]))
        if res.get("aborted") == "idle_timeout":
            raise InfraError("no data from the server for the idle timeout")

        pt, ct, estimated = _usage_tokens(res)
        out["usage_estimated"] = out["usage_estimated"] or estimated
        out["completion_tokens_total"] += ct or 0
        out["reasoning_chars_total"] += len(res.get("reasoning") or "")
        if pt is not None:
            # A small shrink is the chat template re-rendering earlier turns once a newer user message
            # exists (seen with Qwen after a nudge: 58120 -> 58008). Real truncation removes far more.
            if last_prompt is not None and pt < last_prompt - max(512, last_prompt // 50):
                raise InfraError("server truncated the conversation (prompt tokens fell from %d to %d)"
                                 % (last_prompt, pt))
            last_prompt = pt
            out["prompt_tokens_last"] = pt
        sent_calls, call_info = sanitize_calls(res.get("tool_calls") or [])
        t = res.get("timing") or {}
        out["per_step"].append({"step": out["steps"], "prompt_tokens": pt, "completion_tokens": ct,
                                "ttft_s": t.get("ttft_s"), "total_s": t.get("total_s"),
                                "finish_reason": res.get("finish_reason"), "tool_calls": len(call_info),
                                "reasoning_chars": len(res.get("reasoning") or "")})
        log({"type": "assistant", "step": out["steps"], "content": res.get("content") or "",
             "reasoning": res.get("reasoning") or "", "tool_calls": call_info,
             "finish_reason": res.get("finish_reason"), "aborted": res.get("aborted"),
             "usage": res.get("usage"), "timing": t})

        if res.get("aborted") == "wall_clock":
            return end("wall_clock")
        if res.get("aborted") == "degenerate_loop":
            return end("degenerate_loop")

        assistant = {"role": "assistant", "content": res.get("content") or ""}
        if sent_calls:
            assistant["tool_calls"] = sent_calls
        messages.append(assistant)
        chars_since = len(assistant["content"]) + sum(len(json.dumps(x)) for x in sent_calls)

        if not call_info:
            text = res.get("content") or ""
            if res.get("finish_reason") == "length":
                c["length_cutoffs"] += 1
                ok = nudge(NUDGE_LENGTH, "length")
            elif looks_like_tool_call(text):
                c["malformed_text_calls"] += 1
                ok = nudge(NUDGE_MALFORMED, "malformed")
            else:
                c["no_action_replies"] += 1
                ok = nudge(NUDGE_NO_ACTION, "no_action")
            if not ok:
                return end("no_action")
            continue

        consecutive = 0
        finished = False
        max_calls = int(limits["max_tool_calls_per_reply"])
        for i, ci in enumerate(call_info):
            c["tool_calls"] += 1
            name, args = ci["name"], ci["args"]
            if finished or i >= max_calls:
                c["dropped_calls"] += 1
                result = ("ERROR: not executed (%s)" %
                          ("the task was already finished" if finished else
                           "more than %d tool calls in one reply" % max_calls))
            elif name not in TOOL_NAMES:
                c["unknown_tool"] += 1
                result = "ERROR: unknown tool %r. Available tools: %s" % (name, ", ".join(TOOL_NAMES))
            elif ci["error"]:
                c["invalid_json"] += 1
                result = "ERROR: %s. Nothing was executed; call the tool again with valid JSON arguments." % ci["error"]
            else:
                missing = [k for k in REQUIRED[name] if k not in args]
                if missing:
                    c["missing_args"] += 1
                    result = "ERROR: missing required argument(s): %s" % ", ".join(missing)
                elif name == "finish":
                    c["tool_calls_valid"] += 1
                    out["summary"] = str(args.get("summary"))
                    finished = True
                    result = "ok"
                else:
                    c["tool_calls_valid"] += 1
                    ok, result = sandbox.tool(name, args, limits)
                    if not ok:
                        c["tool_errors"] += 1
            messages.append({"role": "tool", "tool_call_id": ci["id"], "content": result})
            chars_since += len(result)
            log({"type": "tool_result", "step": out["steps"], "id": ci["id"], "name": name, "output": result})
        if finished:
            return end("finished")


# ---------------------------------------------------------------------------
# sub-case loop (canned tool results)
# ---------------------------------------------------------------------------
def run_cases(chat, make_payload, spec, limits, log, deadline):
    """Run every sub-case in a cases.json spec. Returns {case_id: {turns, final_text, ...}}."""
    tools_by_name = spec.get("tools") or {}
    results = {}
    for case in spec["cases"]:
        cid = case["id"]
        messages = []
        if case.get("system"):
            messages.append({"role": "system", "content": case["system"]})
        messages.append({"role": "user", "content": case["user"]})
        tool_defs = [{"type": "function", "function": dict(tools_by_name[n], name=n)} for n in case.get("tools") or []]
        # A canned result is a string, a list consumed in order (the last one repeats), or
        # {"by_arg": "service", "results": {"auth": "...", ...}, "default": "..."} keyed on one argument.
        canned = {k: (v if isinstance(v, dict) else list(v) if isinstance(v, list) else [v])
                  for k, v in (case.get("tool_results") or {}).items()}
        turns = []
        rec = {"turns": turns, "final_text": "", "end": None}
        max_turns = int(case.get("max_turns") or limits["cases_max_turns"])
        for _ in range(max_turns):
            if time.monotonic() >= deadline:
                rec["end"] = "wall_clock"
                break
            payload = make_payload(messages, int(case.get("max_tokens") or limits["cases_turn_max_tokens"]))
            if tool_defs:
                payload["tools"] = tool_defs
                payload["tool_choice"] = "auto"
            if case.get("response_format"):
                payload["response_format"] = case["response_format"]
            res = chat(payload, deadline)
            if res.get("error"):
                status = res["error"].get("status")
                if status and status >= 500:
                    raise InfraError("chat error HTTP %s: %s" % (status, (res["error"].get("body") or "")[:300]))
                rec["end"] = "request_error"
                turns.append({"error": res["error"]})
                log({"type": "case_error", "case": cid, "error": res["error"]})
                break
            if res.get("aborted") == "idle_timeout":
                raise InfraError("no data from the server for the idle timeout")
            sent_calls, call_info = sanitize_calls(res.get("tool_calls") or [])
            turn = {"content": res.get("content") or "", "tool_calls": call_info,
                    "finish_reason": res.get("finish_reason"), "aborted": res.get("aborted"),
                    "usage": res.get("usage"), "timing": res.get("timing"),
                    "reasoning_chars": len(res.get("reasoning") or "")}
            turns.append(turn)
            log({"type": "case_turn", "case": cid, "turn": len(turns), "content": turn["content"],
                 "reasoning": res.get("reasoning") or "", "tool_calls": call_info,
                 "finish_reason": turn["finish_reason"], "usage": turn["usage"], "timing": turn["timing"]})
            rec["final_text"] = turn["content"]
            if res.get("aborted"):
                rec["end"] = res["aborted"]
                break
            if not call_info:
                rec["end"] = "text"
                break
            assistant = {"role": "assistant", "content": turn["content"], "tool_calls": sent_calls}
            messages.append(assistant)
            for ci in call_info:
                if ci["error"]:
                    result = "ERROR: %s" % ci["error"]
                else:
                    queue = canned.get(ci["name"])
                    if queue is None:
                        result = case.get("default_tool_result", "ERROR: unknown tool %r" % ci["name"])
                    elif isinstance(queue, dict):
                        key = str((ci["args"] or {}).get(queue.get("by_arg")))
                        result = queue.get("results", {}).get(key, queue.get("default", "ERROR: not found: %s" % key))
                    else:
                        result = queue.pop(0) if len(queue) > 1 else queue[0]
                ci["result"] = result
                messages.append({"role": "tool", "tool_call_id": ci["id"], "content": result})
        else:
            rec["end"] = "max_turns"
        results[cid] = rec
    return results
