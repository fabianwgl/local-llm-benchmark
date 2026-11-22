"""Shared helpers for hidden check scripts.

Runs INSIDE the check container as root. Model-written code is only ever executed as the
unprivileged `bench` user, and the result file lives in /out, which that user cannot write.

Layout inside the container:
  /in/response.md      the model's final answer (single-shot) or finish summary (agentic)
  /in/workspace/       the model's final tree (agentic), protected paths already restored
  /in/cases.json       recorded sub-case transcripts (cases mode)
  /in/meta.json        end reason and flags
  /hidden/             this test's hidden files
  /out/result.json     written by result()
"""
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

IN = Path("/in")
HIDDEN = Path("/hidden")
OUT = Path("/out")
WS = Path("/tmp/w")


def meta():
    try:
        return json.loads((IN / "meta.json").read_text())
    except (OSError, ValueError):
        return {}


def response_text():
    try:
        return (IN / "response.md").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def result(checks, notes=None):
    """Write the check outcome. Values are booleans or fractions between 0 and 1."""
    OUT.mkdir(exist_ok=True)
    clean = {}
    for k, v in checks.items():
        clean[k] = bool(v) if isinstance(v, bool) else max(0.0, min(1.0, float(v)))
    with open(OUT / "result.json", "w") as f:
        json.dump({"checks": clean, "notes": notes or {}}, f, indent=2)
    for k, v in clean.items():
        print("CHECK %-32s %s" % (k, v))


def prepare_workspace(overlay=None, dest=WS):
    """Copy /in/workspace to a scratch dir owned by bench, then lay hidden files over it."""
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    src = IN / "workspace"
    if src.exists():
        shutil.copytree(src, dest, symlinks=False)
    else:
        dest.mkdir(parents=True)
    if overlay:
        shutil.copytree(HIDDEN / overlay, dest, dirs_exist_ok=True)
    subprocess.run(["chown", "-R", "bench:bench", str(dest)], check=False)
    return dest


def run(cmd, cwd=WS, timeout=120, user="bench", env=None):
    """Run a shell command as an unprivileged user. Returns (exit_code or None on timeout, output)."""
    full = ["runuser", "-u", user, "--", "bash", "-lc", cmd] if user else ["bash", "-lc", cmd]
    e = dict(os.environ)
    e.update(env or {})
    try:
        p = subprocess.run(full, cwd=str(cwd), capture_output=True, timeout=timeout, env=e,
                           stdin=subprocess.DEVNULL)
        return p.returncode, (p.stdout + p.stderr).decode("utf-8", "replace")
    except subprocess.TimeoutExpired as ex:
        if user:
            subprocess.run(["pkill", "-KILL", "-u", user], check=False)
        partial = ((ex.stdout or b"") + (ex.stderr or b"")).decode("utf-8", "replace")
        return None, "TIMEOUT after %ss\n%s" % (timeout, partial)


# ---- test-runner output parsers ---------------------------------------------
_TAP = re.compile(r"^\s*(not ok|ok)\s+\d+\s+-\s+(.*?)\s*(?:#.*)?$")


def node_tests(files, cwd=WS, timeout=180, env=None):
    """Run node --test on the given files. Returns ({test name: passed}, raw output)."""
    code, out = run("node --test --test-reporter=tap %s" % " ".join(files), cwd=cwd, timeout=timeout, env=env)
    res = {}
    for line in out.splitlines():
        m = _TAP.match(line)
        if m:
            res[m.group(2).strip()] = (m.group(1) == "ok")
    return res, out


def pytest_tests(args, cwd=WS, timeout=180, env=None):
    """Run pytest. Returns ({test function name: passed}, raw output)."""
    xml = "/tmp/junit-%d.xml" % os.getpid()
    if os.path.exists(xml):
        os.unlink(xml)
    code, out = run("python3 -m pytest -q -p no:cacheprovider --junitxml=%s %s" % (xml, args),
                    cwd=cwd, timeout=timeout, env=env)
    res = {}
    try:
        for case in ET.parse(xml).getroot().iter("testcase"):
            bad = any(ch.tag in ("failure", "error", "skipped") for ch in case)
            res[case.get("name")] = not bad
    except (OSError, ET.ParseError):
        pass
    return res, out


_CARGO = re.compile(r"^test\s+(\S+)\s+\.\.\.\s+(ok|FAILED|ignored)", re.M)


def cargo_tests(args="", cwd=WS, timeout=240, env=None):
    """Run cargo test --offline. Returns ({test name: passed}, raw output)."""
    code, out = run("cargo test --offline %s 2>&1" % args, cwd=cwd, timeout=timeout, env=env)
    res = {}
    for m in _CARGO.finditer(out):
        res[m.group(1)] = (m.group(2) == "ok")
    return res, out


def group_fraction(results, names):
    """Fraction of the expected test names that passed (a missing test counts as failed)."""
    if not names:
        return 0.0
    return sum(1 for n in names if results.get(n) is True) / float(len(names))


# ---- answer parsing ---------------------------------------------------------
_FENCE = re.compile(r"```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\n(.*?)```", re.S)


def fenced_blocks(text, lang=None):
    """All fenced code blocks, in order, optionally filtered by language tag."""
    out = []
    for m in _FENCE.finditer(text or ""):
        if lang is None or m.group(1).lower() == lang.lower():
            out.append(m.group(2))
    return out


def _balanced_candidates(text):
    """Yield substrings that are balanced {...} or [...] spans, longest-first from the end."""
    opens = [i for i, ch in enumerate(text) if ch in "{["]
    for start in opens:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch in "{[":
                depth += 1
            elif ch in "}]":
                depth -= 1
                if depth == 0:
                    yield text[start:i + 1]
                    break


def extract_json(text, want=dict):
    """Best-effort: the last JSON value of type `want` in the text (fenced blocks first)."""
    text = text or ""
    for block in reversed(fenced_blocks(text)):
        try:
            v = json.loads(block)
            if isinstance(v, want):
                return v
        except ValueError:
            continue
    try:
        v = json.loads(text.strip())
        if isinstance(v, want):
            return v
    except ValueError:
        pass
    best = None
    for cand in _balanced_candidates(text):
        try:
            v = json.loads(cand)
        except ValueError:
            continue
        if isinstance(v, want) and (best is None or len(cand) >= len(best[1])):
            best = (v, cand)
    return best[0] if best else None


def norm(s):
    """Lowercase, collapse whitespace, strip surrounding punctuation and quotes."""
    s = re.sub(r"\s+", " ", str(s if s is not None else "")).strip().lower()
    return s.strip(" .,;:!?`'\"()[]")


def trailer(text, key):
    """Value of the last 'KEY: value' line in the text, or None."""
    val = None
    for line in (text or "").splitlines():
        m = re.match(r"^\s*[*`]*%s[*`]*\s*:\s*(.+?)\s*$" % re.escape(key), line, re.I)
        if m:
            val = m.group(1).strip().strip("`*")
    return val


def word_count(text):
    return len(re.findall(r"\b[\w'’-]+\b", text or ""))
