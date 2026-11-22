#!/usr/bin/env python3
"""Tool executor that runs INSIDE the sandbox container.

The host sends one JSON request on stdin: {"op": ..., "args": {...}, "limits": {...}}
and reads one JSON reply on stdout: {"ok": bool, "output": str}.
Because every file operation happens here, the host never opens a model-supplied path.
"""
import json
import os
import signal
import subprocess
import sys

WORK = "/work"


def clip(text, limits):
    cap = int(limits.get("tool_output_chars", 8000))
    if len(text) <= cap:
        return text
    head = int(limits.get("tool_output_head", 5000))
    tail = int(limits.get("tool_output_tail", 3000))
    cut = len(text) - head - tail
    return text[:head] + "\n[... %d characters truncated ...]\n" % cut + text[-tail:]


def resolve(path):
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be a non-empty string")
    p = path if os.path.isabs(path) else os.path.join(WORK, path)
    p = os.path.normpath(p)
    if not (p == WORK or p.startswith(WORK + "/") or p.startswith("/tmp/")):
        raise ValueError("path must be inside /work (got %s)" % path)
    return p


def read_file(args, limits):
    p = resolve(args.get("path"))
    if os.path.isdir(p):
        raise ValueError("%s is a directory; use run_command with ls" % args.get("path"))
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        lines = f.read().split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    total = len(lines)
    max_lines = int(limits.get("read_file_max_lines", 400))
    start = int(args.get("start_line") or 1)
    if start < 1:
        start = 1
    end = int(args.get("end_line") or (start + max_lines - 1))
    end = min(end, start + max_lines - 1, total)
    if total == 0:
        return "(empty file)"
    if start > total:
        raise ValueError("start_line %d is past the end of the file (%d lines)" % (start, total))
    body = "\n".join("%5d\t%s" % (i, lines[i - 1]) for i in range(start, end + 1))
    note = ""
    if end < total or start > 1:
        note = "\n[showing lines %d-%d of %d; use start_line/end_line for the rest]" % (start, end, total)
    return clip(body + note, limits)


def write_file(args, limits):
    p = resolve(args.get("path"))
    content = args.get("content")
    if not isinstance(content, str):
        raise ValueError("content must be a string")
    d = os.path.dirname(p)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return "wrote %d bytes to %s" % (len(content.encode("utf-8")), args.get("path"))


def edit_file(args, limits):
    p = resolve(args.get("path"))
    old = args.get("old_string")
    new = args.get("new_string")
    if not isinstance(old, str) or not isinstance(new, str):
        raise ValueError("old_string and new_string must be strings")
    if old == "":
        raise ValueError("old_string must not be empty; use write_file to create a file")
    if old == new:
        raise ValueError("old_string and new_string are identical")
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    count = text.count(old)
    if count == 0:
        raise ValueError("old_string was not found in %s; it must match the file exactly, "
                         "including whitespace" % args.get("path"))
    if count > 1 and not args.get("replace_all"):
        raise ValueError("old_string occurs %d times in %s; add more context to make it unique "
                         "or set replace_all=true" % (count, args.get("path")))
    text = text.replace(old, new) if args.get("replace_all") else text.replace(old, new, 1)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return "edited %s (%d replacement%s)" % (args.get("path"), count if args.get("replace_all") else 1,
                                             "s" if (args.get("replace_all") and count != 1) else "")


def run_command(args, limits):
    cmd = args.get("command")
    if not isinstance(cmd, str) or not cmd.strip():
        raise ValueError("command must be a non-empty string")
    default_t = int(limits.get("cmd_timeout_default_s", 60))
    max_t = int(limits.get("cmd_timeout_max_s", 120))
    try:
        timeout = int(args.get("timeout_s") or default_t)
    except (TypeError, ValueError):
        timeout = default_t
    timeout = max(1, min(timeout, max_t))
    proc = subprocess.Popen(["bash", "-lc", cmd], cwd=WORK, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, start_new_session=True)
    timed_out = False
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        out, _ = proc.communicate()
    text = out.decode("utf-8", errors="replace")
    head = "exit_code: %s" % ("timeout after %ds (process killed)" % timeout if timed_out else proc.returncode)
    return head + "\n" + clip(text, limits) if text else head + "\n(no output)"


OPS = {"read_file": read_file, "write_file": write_file, "edit_file": edit_file, "run_command": run_command}


def main():
    try:
        req = json.loads(sys.stdin.read())
        op = req.get("op")
        if op not in OPS:
            raise ValueError("unknown tool %r" % op)
        args = req.get("args")
        if not isinstance(args, dict):
            raise ValueError("arguments must be a JSON object")
        out = OPS[op](args, req.get("limits") or {})
        reply = {"ok": True, "output": out}
    except Exception as e:  # every failure becomes a tool error the model can read
        reply = {"ok": False, "output": "ERROR: %s" % e}
    sys.stdout.write(json.dumps(reply))


if __name__ == "__main__":
    main()
