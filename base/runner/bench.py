#!/usr/bin/env python3
"""Local LLM benchmark runner for LM Studio.

Usage: python3 base/runner/bench.py <command> [options]   (see --help)
Stdlib only; must run on Python 3.9.
"""
from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import json
import os
import platform
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lmstudio  # noqa: E402
from lmstudio import Client, InfraError  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "base"
TESTS = BASE / "tests"
MODELS = ROOT / "models"
JUDGING = ROOT / "judging"


def load_suite():
    with open(BASE / "suite.json") as f:
        return json.load(f)


SUITE = load_suite()
LIMITS = SUITE["limits"]


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def write_json(path, obj):
    """Write JSON atomically (tmp file + rename)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def sh(cmd, timeout=60):
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (p.stdout or "").strip()
    except (subprocess.TimeoutExpired, OSError):
        return ""


def slug_for(info, reasoning=None):
    """models/<slug> name: <model>__<format>-<quant>__r-<reasoning level>.

    The level is the model's shipped default unless a variant was requested with --reasoning.
    """
    name = info["key"].split("/")[-1]
    fmt = info.get("format") or "unknown"
    quant = ((info.get("quantization") or {}).get("name") or "unknown").lower()
    level = reasoning or ((info.get("capabilities") or {}).get("reasoning") or {}).get("default") or "none"
    return "%s__%s-%s__r-%s" % (name, fmt, quant, level)


def host_facts():
    engines = []
    for line in sh("NO_COLOR=1 %s runtime ls" % lmstudio.LMS).splitlines():
        if "✓" in line:
            engines.append(line.split()[0])
    mem = sh("sysctl -n hw.memsize")
    return {
        "chip": sh("sysctl -n machdep.cpu.brand_string"),
        "ram_gb": round(int(mem) / 2 ** 30) if mem.isdigit() else None,
        "os": "macOS %s" % platform.mac_ver()[0],
        "lmstudio_app": sh('/usr/libexec/PlistBuddy -c "Print :CFBundleShortVersionString" '
                           '"/Applications/LM Studio.app/Contents/Info.plist"'),
        "engines": engines,
    }


def swap_used_mb():
    out = sh("sysctl -n vm.swapusage")  # total = 2048.00M  used = 1024.00M  free = ...
    try:
        used = out.split("used =")[1].split()[0]
        return float(used.rstrip("MG")) * (1024 if used.endswith("G") else 1)
    except (IndexError, ValueError):
        return None


def png_rgb(width, height, pixel_fn):
    """Encode an RGB PNG with the stdlib only. pixel_fn(x, y) -> (r, g, b)."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            raw.extend(pixel_fn(x, y))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def base_payload(identifier, messages, max_tokens, seed, reasoning=None):
    p = {"model": identifier, "messages": messages, "max_tokens": max_tokens, "seed": seed}
    p.update(SUITE["sampler"])
    if reasoning:
        p["reasoning_effort"] = reasoning  # undocumented on this endpoint, verified by `probe`
    return p


def is_context_error(err):
    """True when a chat error says the prompt does not fit the loaded context window."""
    import re
    return bool(err) and bool(re.search(r"context (length|size)|exceed_context", err.get("body") or "", re.I))


def ensure_model(client, key, announce=True, reasoning=None):
    """Load `key` alone with the suite's fixed settings (or confirm it already is). Returns ctx dict."""
    info = client.model_info(key)
    slug = slug_for(info, reasoning)
    identifier = "bench-" + slug
    ctx_len = SUITE["context_length"]
    ok, _ = client.verify_loaded(identifier, ctx_len)
    load_s = None
    if not ok:
        if announce:
            print("loading %s (context %d) ..." % (key, ctx_len), flush=True)
        load_s, _ = client.load(key, ctx_len, identifier)
        if announce:
            print("loaded in %.1fs" % load_s, flush=True)
    mdir = MODELS / slug
    mdir.mkdir(parents=True, exist_ok=True)
    mpath = mdir / "model.json"
    meta = read_json(mpath, {}) or {}
    _, inst = client.verify_loaded(identifier, ctx_len)
    meta.update({
        "slug": slug, "key": key, "identifier": identifier,
        "display_name": info.get("display_name"), "publisher": info.get("publisher"),
        "architecture": info.get("architecture"), "format": info.get("format"),
        "quantization": info.get("quantization"), "params": info.get("params_string"),
        "size_bytes": info.get("size_bytes"), "capabilities": info.get("capabilities"),
        "reasoning_level": reasoning or ((info.get("capabilities") or {}).get("reasoning") or {}).get("default"),
        "reasoning_effort_sent": reasoning,
        "load_config": inst.get("config") if isinstance(inst, dict) else None,
        "sampler": SUITE["sampler"], "host": host_facts(), "updated": now_iso(),
    })
    if load_s is not None:
        meta["last_load_seconds"] = round(load_s, 1)
    write_json(mpath, meta)
    return {"key": key, "slug": slug, "identifier": identifier, "info": info, "dir": mdir,
            "vision": bool((info.get("capabilities") or {}).get("vision")), "load_s": load_s,
            "reasoning": reasoning}


# ---------------------------------------------------------------------------
# probe: how does this model actually behave over the API?
# ---------------------------------------------------------------------------
PROBE_TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"},
                           "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}},
            "required": ["city"],
        },
    },
}]


def _brief(res):
    return {
        "content": res["content"][:400], "reasoning_chars": len(res["reasoning"]),
        "reasoning_field": res["reasoning_field"], "tool_calls": res["tool_calls"],
        "finish_reason": res["finish_reason"], "usage": res["usage"], "aborted": res["aborted"],
        "error": res["error"], "timing": res["timing"], "gen_tps": lmstudio.gen_speed(res),
    }


def cmd_probe(args):
    client = Client(SUITE["server"])
    m = ensure_model(client, args.model)
    ident = m["identifier"]
    out = {"model": args.model, "slug": m["slug"], "when": now_iso(), "host": host_facts(),
           "load_seconds": m["load_s"], "suite_version": SUITE["version"]}

    def ask(messages, max_tokens=1024, seed=1, extra=None, capture=None, deadline=None):
        p = base_payload(ident, messages, max_tokens, seed)
        if extra:
            p.update(extra)
        return client.chat_stream(p, idle_timeout=600, deadline=deadline, capture=capture)

    def step(name, fn):
        print("probe: %s ..." % name, flush=True)
        try:
            out[name] = fn()
        except InfraError as e:
            out[name] = {"infra_error": str(e)}
        print("   ", json.dumps(out[name])[:300], flush=True)

    def basic():
        cap = []
        r = ask([{"role": "user", "content": "Reply with exactly: OK"}], capture=cap)
        b = _brief(r)
        b["first_chunks"] = cap[:3]
        b["last_chunks"] = cap[-2:]
        return b

    def seed_repeat():
        # reasoning is switched off here so the answers are short and directly comparable
        msg = [{"role": "user", "content": "Write one imaginative sentence about a lighthouse."}]
        off = {"reasoning_effort": "none"}
        a = ask(msg, seed=7, extra=off, max_tokens=2000)
        b = ask(msg, seed=7, extra=off, max_tokens=2000)
        c = ask(msg, seed=8, extra=off, max_tokens=2000)
        return {"same_seed_identical": bool(a["content"]) and a["content"] == b["content"],
                "different_seed_differs": a["content"] != c["content"],
                "a": a["content"][:200], "b": b["content"][:200], "c": c["content"][:200]}

    def reasoning_switch():
        msg = [{"role": "user", "content": "What is 17 * 23? Answer with the number only."}]
        res = {"baseline": _brief(ask(msg))}
        variants = {
            "reasoning_effort_none": {"reasoning_effort": "none"},
            "reasoning_effort_low": {"reasoning_effort": "low"},
            "reasoning_obj_low": {"reasoning": {"effort": "low"}},
            "reasoning_off": {"reasoning": "off"},
            "enable_thinking_false": {"enable_thinking": False},
            "chat_template_kwargs": {"chat_template_kwargs": {"enable_thinking": False}},
        }
        for name, extra in variants.items():
            b = _brief(ask(msg, extra=extra))
            res[name] = {"reasoning_chars": b["reasoning_chars"], "content": b["content"][:80],
                         "error": b["error"], "completion_tokens": (b["usage"] or {}).get("completion_tokens")}
        return res

    def tools():
        msgs = [{"role": "user", "content": "What is the weather in Paris right now? Use the tool."}]
        r1 = ask(msgs, extra={"tools": PROBE_TOOLS, "tool_choice": "auto"})
        res = {"first": _brief(r1)}
        if r1["tool_calls"]:
            tc = r1["tool_calls"][0]
            msgs2 = msgs + [
                {"role": "assistant", "content": r1["content"] or "", "tool_calls": r1["tool_calls"]},
                {"role": "tool", "tool_call_id": tc["id"], "content": '{"city":"Paris","temp_c":18,"sky":"cloudy"}'},
            ]
            res["after_result"] = _brief(ask(msgs2, extra={"tools": PROBE_TOOLS, "tool_choice": "auto"}))
        r3 = ask([{"role": "user", "content": "Get the weather for Paris and for Tokyo. Call the tool once per city, both in this reply."}],
                 extra={"tools": PROBE_TOOLS, "tool_choice": "auto"})
        res["parallel"] = _brief(r3)
        res["parallel_count"] = len(r3["tool_calls"])
        return res

    def image():
        png = png_rgb(256, 256, lambda x, y: (220, 30, 30) if x < 128 else (30, 60, 220))
        url = "data:image/png;base64," + base64.b64encode(png).decode()
        r = ask([{"role": "user", "content": [
            {"type": "text", "text": "The image has a left half and a right half. Reply exactly as: left=<color> right=<color>"},
            {"type": "image_url", "image_url": {"url": url}}]}], max_tokens=6000)
        b = _brief(r)
        b["sees_image"] = "red" in r["content"].lower() and "blue" in r["content"].lower()
        return b

    def structured():
        # Known quirk: with reasoning on, some engines put the constrained JSON in the reasoning channel.
        schema = {"name": "person", "strict": True, "schema": {
            "type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name", "age"], "additionalProperties": False}}
        msg = [{"role": "user", "content": "Extract the person as JSON: 'Marta Kowalski turned 34 last week.'"}]
        res = {}
        for label, extra in (("reasoning_default", {}), ("reasoning_none", {"reasoning_effort": "none"})):
            e = {"response_format": {"type": "json_schema", "json_schema": schema}}
            e.update(extra)
            r = ask(msg, extra=e, max_tokens=4000)

            def parses(text):
                try:
                    return isinstance(json.loads(text), dict)
                except ValueError:
                    return False
            res[label] = {"json_in_content": parses(r["content"]), "json_in_reasoning": parses(r["reasoning"]),
                          "content": r["content"][:200], "reasoning": r["reasoning"][:200], "error": r["error"]}
        return res

    def abort_then_ask():
        t0 = time.monotonic()
        r = ask([{"role": "user", "content": "Count from 1 to 3000, one number per line."}], max_tokens=8000,
                deadline=time.monotonic() + 4)
        t1 = time.monotonic()
        r2 = ask([{"role": "user", "content": "Reply with exactly: OK"}], max_tokens=256)
        return {"aborted": r["aborted"], "abort_after_s": round(t1 - t0, 1),
                "next_request_total_s": r2["timing"]["total_s"], "next_content": r2["content"][:40]}

    steps = [("basic", basic), ("seed_repeat", seed_repeat), ("reasoning_switch", reasoning_switch),
             ("tools", tools), ("structured", structured), ("abort_then_ask", abort_then_ask)]
    if m["vision"]:
        steps.insert(4, ("image", image))
    for name, fn in steps:
        step(name, fn)

    if args.overflow:
        def overflow():
            client.load(args.model, 4096, ident)
            filler = " ".join("The quick brown fox %d jumps over the lazy dog." % i for i in range(900))
            p = base_payload(ident, [{"role": "user", "content": "Secret word: PELICAN.\n" + filler +
                                      "\nWhat was the secret word at the very start? One word."}], 200, 1)
            r = client.chat_stream(p, idle_timeout=300)
            b = _brief(r)
            b["note"] = "loaded at 4096 context; prompt is roughly 10k tokens"
            return b
        step("overflow_at_4096", overflow)
        client.unload_all()

    write_json(m["dir"] / "probe.json", out)
    print("wrote", m["dir"] / "probe.json")
    if args.unload:
        client.unload_all()


# ---------------------------------------------------------------------------
# tests on disk
# ---------------------------------------------------------------------------
CATEGORY_ORDER = ["agentic", "swe", "long", "general", "vision"]
HASH_SKIP = {"__pycache__", ".DS_Store", "target", "node_modules", ".pytest_cache"}


def _digest(paths, extra=""):
    h = hashlib.sha256()
    for path in paths:
        path = Path(path)
        files = [path] if path.is_file() else sorted(f for f in path.rglob("*") if f.is_file()) if path.is_dir() else []
        for f in files:
            if any(part in HASH_SKIP for part in f.parts):
                continue
            h.update(str(f.relative_to(path if path.is_dir() else path.parent)).encode())
            h.update(b"\0")
            h.update(f.read_bytes())
            h.update(b"\0")
    h.update(extra.encode())
    return h.hexdigest()[:16]


def test_hashes(tdir, t):
    """Three fingerprints of a test.

    run:   everything the model sees or is limited by. If it changes, old runs no longer count.
    check: the scripted grading. If it changes, the check is simply re-applied to the saved output.
    judge: the rubric and judged criteria. If it changes, old verdicts no longer count.
    """
    suite_part = json.dumps({k: SUITE[k] for k in ("context_length", "sampler", "limits", "system_prompts")},
                            sort_keys=True)
    run_part = json.dumps({k: t.get(k) for k in ("mode", "prompt", "workspace", "inputs", "env", "limits", "requires")},
                          sort_keys=True)
    run = _digest([tdir / t.get("prompt", "prompt.md"), tdir / t.get("workspace", "workspace"), tdir / "input",
                   tdir / "cases.json"], suite_part + run_part)
    check_part = json.dumps({"check": t.get("check"), "checks": t.get("score", {}).get("checks"),
                             "protected": t.get("protected")}, sort_keys=True)
    check = _digest([tdir / "hidden", TESTS / "_lib"], check_part)
    judge = _digest([tdir / "rubric.md"], json.dumps(t.get("score", {}).get("judge"), sort_keys=True))
    return run, check, judge


def load_tests(selected=None):
    tests = []
    for d in sorted(TESTS.iterdir()):
        if d.name.startswith("_") or not (d / "test.json").exists():
            continue
        t = read_json(d / "test.json")
        if t is None:
            raise SystemExit("unreadable test.json in %s" % d)
        t["dir"] = d
        t["hash"], t["check_hash"], t["judge_hash"] = test_hashes(d, t)
        tests.append(t)
    tests.sort(key=lambda t: (CATEGORY_ORDER.index(t["category"]), t["id"]))
    if selected:
        want = [s.strip() for s in selected.split(",") if s.strip()]
        picked = []
        for w in want:
            hit = [t for t in tests if t["id"] == w or t["id"].split("-")[0] == w]
            if not hit:
                raise SystemExit("no test matches %r" % w)
            picked += [t for t in hit if t not in picked]
        tests = picked
    return tests


def scripted_max(test):
    total = 0.0
    for spec in (test.get("score", {}).get("checks") or {}).values():
        total += spec if isinstance(spec, (int, float)) else spec["points"]
    return total


def judge_max(test):
    return sum(c["max"] for c in test.get("score", {}).get("judge") or [])


def score_checks(test, values):
    """Map check results (bool or 0..1) onto points. Returns (points, detail)."""
    detail, total = {}, 0.0
    values = values or {}
    for cid, spec in (test.get("score", {}).get("checks") or {}).items():
        pts = spec if isinstance(spec, (int, float)) else spec["points"]
        req = None if isinstance(spec, (int, float)) else spec.get("requires")
        v = values.get(cid, False)
        frac = 1.0 if v is True else 0.0 if v is False or v is None else max(0.0, min(1.0, float(v)))
        if req and not values.get(req):
            frac = 0.0
        got = round(pts * frac, 3)
        detail[cid] = {"value": v, "points": got, "max": pts}
        total += got
    return round(total, 3), detail


def render_prompt(test):
    """prompt.md with {{include:PATH}} directives expanded (paths relative to the test folder)."""
    tdir = test["dir"]
    text = (tdir / test.get("prompt", "prompt.md")).read_text(encoding="utf-8")

    def sub(m):
        rel = m.group(1).strip()
        p = (tdir / rel).resolve()
        if tdir.resolve() not in p.parents or "hidden" in Path(rel).parts or Path(rel).name == "rubric.md":
            raise SystemExit("%s: include %r is not allowed" % (test["id"], rel))
        return p.read_text(encoding="utf-8")

    import re
    return re.sub(r"\{\{include:([^}]+)\}\}", sub, text)


def user_content(test, prompt):
    images = [i for i in test.get("inputs") or [] if i.get("kind") == "image"]
    if not images:
        return prompt, prompt
    parts = [{"type": "text", "text": prompt}]
    shown = [{"type": "text", "text": prompt}]
    for i in images:
        raw = (test["dir"] / i["path"]).read_bytes()
        mime = "image/png" if i["path"].lower().endswith(".png") else "image/jpeg"
        parts.append({"type": "image_url",
                      "image_url": {"url": "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode())}})
        shown.append({"type": "image", "path": i["path"], "sha256": hashlib.sha256(raw).hexdigest()[:16]})
    return parts, shown


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------
def do_check(test, rdir, end_reason=None):
    """Run the test's hidden check against the artifacts saved in rdir. Returns the check.json dict."""
    import agent
    import shutil
    import tempfile
    check = test.get("check")
    smax = scripted_max(test)
    out = {"ran": False, "exit_code": None, "error": None, "checks": {}, "notes": {}, "tampered": [],
           "points": 0.0, "max": smax, "detail": {}, "check_hash": test["check_hash"]}
    if not check:
        return out
    tmp = Path(tempfile.mkdtemp(prefix="bench-in-"))
    try:
        if (rdir / "response.md").exists():
            shutil.copy2(rdir / "response.md", tmp / "response.md")
        if (rdir / "cases.json").exists():
            shutil.copy2(rdir / "cases.json", tmp / "cases.json")
        if (rdir / "workspace.tgz").exists():
            final = tmp / "workspace"
            agent.safe_extract(rdir / "workspace.tgz", final)
            fixture = test["dir"] / test.get("workspace", "workspace")
            out["tampered"] = agent.restore_protected(test.get("protected"), fixture, final)
        write_json(tmp / "meta.json", {"test": test["id"], "end_reason": end_reason, "tampered": out["tampered"]})
        r = agent.run_check(SUITE, check["cmd"], test["dir"] / "hidden", TESTS / "_lib", tmp,
                            int(check.get("timeout_s") or LIMITS["check_timeout_s"]), env=test.get("env"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out["ran"], out["exit_code"], out["error"] = r["ran"], r["exit_code"], r["error"]
    result = r["result"] or {}
    out["checks"] = result.get("checks") or {}
    out["notes"] = result.get("notes") or {}
    out["points"], out["detail"] = score_checks(test, out["checks"])
    write_text(rdir / "check.log", r["log"])
    return out


# ---------------------------------------------------------------------------
# running tests
# ---------------------------------------------------------------------------
def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    mid = len(xs) // 2
    return xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2.0


def _single_metrics(res):
    usage = res.get("usage") or {}
    t = res.get("timing") or {}
    pt = usage.get("prompt_tokens")
    return {
        "prompt_tokens": pt, "completion_tokens": usage.get("completion_tokens"),
        "reasoning_chars": len(res.get("reasoning") or ""), "answer_chars": len(res.get("content") or ""),
        "ttft_s": t.get("ttft_s"), "ttfa_s": t.get("ttfa_s"), "total_s": t.get("total_s"),
        "gen_tps": lmstudio.gen_speed(res),
        "prompt_tps": (pt / t["ttft_s"]) if pt and t.get("ttft_s") else None,
        "finish_reason": res.get("finish_reason"),
    }


def _attempt(client, m, test, seed, rdir):
    import agent
    import gzip
    import shutil
    import tempfile
    if rdir.exists():
        shutil.rmtree(rdir)
    rdir.mkdir(parents=True)
    ctx_len = SUITE["context_length"]
    reloaded = False
    ok, _ = client.verify_loaded(m["identifier"], ctx_len)
    if not ok:
        client.load(m["key"], ctx_len, m["identifier"])
        reloaded = True
    limits = dict(LIMITS)
    limits.update(test.get("limits") or {})
    swap0 = swap_used_mb()
    started, t_start = now_iso(), time.time()
    tlog = open(rdir / "transcript.jsonl", "a")

    def log(ev):
        ev["t"] = round(time.time() - t_start, 3)
        tlog.write(json.dumps(ev, ensure_ascii=False) + "\n")
        tlog.flush()

    def make_payload(messages, max_tokens):
        return base_payload(m["identifier"], messages, max_tokens, seed, m.get("reasoning"))

    def chat(payload, deadline):
        if SUITE["canary"] in json.dumps(payload):
            raise SystemExit("ABORT: canary string found in a request for %s; a hidden file leaked into the prompt"
                             % test["id"])
        return client.chat_stream(payload, idle_timeout=limits["http_idle_timeout_s"], deadline=deadline)

    mode = test["mode"]
    metrics, end_reason = {}, None
    try:
        if mode == "single":
            prompt = render_prompt(test)
            content, shown = user_content(test, prompt)
            system = SUITE["system_prompts"]["single"]
            max_tokens = int(limits.get("max_tokens") or limits["single_max_tokens"])
            payload = make_payload([{"role": "system", "content": system}, {"role": "user", "content": content}],
                                   max_tokens)
            write_json(rdir / "request.json", {"system": system, "user": shown, "max_tokens": max_tokens,
                                               "seed": seed, "sampler": SUITE["sampler"]})
            res = chat(payload, time.monotonic() + limits["single_wall_clock_s"])
            if res.get("error") and not is_context_error(res["error"]):
                raise InfraError("chat error HTTP %s: %s" % (res["error"].get("status"),
                                                              (res["error"].get("body") or "")[:300]))
            if res.get("aborted") == "idle_timeout":
                raise InfraError("no data from the server for the idle timeout")
            log({"type": "assistant", "content": res["content"], "reasoning": res["reasoning"],
                 "finish_reason": res["finish_reason"], "aborted": res["aborted"], "usage": res["usage"],
                 "timing": res["timing"]})
            write_text(rdir / "response.md", res["content"])
            if res["reasoning"]:
                write_text(rdir / "reasoning.md", res["reasoning"])
            fr = res.get("finish_reason")
            end_reason = res.get("aborted") or ("completed" if fr in ("stop", None) else fr)
            if res.get("error"):
                end_reason = "context_overflow"  # the prompt itself does not fit: a suite problem, flagged loudly
                print("  WARNING: %s does not fit the context window: %s" % (test["id"], res["error"]["body"][:200]))
            metrics = _single_metrics(res)
        elif mode == "agentic":
            fixture = test["dir"] / test.get("workspace", "workspace")
            system = SUITE["system_prompts"]["agentic"].format(max_steps=limits["agent_max_steps"])
            prompt = render_prompt(test)
            write_json(rdir / "request.json", {"system": system, "user": prompt, "tools": agent.TOOLS,
                                               "max_tokens_per_step": limits["agent_step_max_tokens"],
                                               "seed": seed, "sampler": SUITE["sampler"]})
            sb = agent.Sandbox(SUITE, fixture, env=test.get("env")).start()
            tar = rdir / "workspace.tar"
            try:
                result = agent.run_agent(chat, make_payload, prompt, system, sb, limits, ctx_len, log,
                                         time.monotonic() + limits["agent_wall_clock_s"])
                sb.snapshot(tar)
            finally:
                sb.stop()
            with open(tar, "rb") as src, gzip.open(rdir / "workspace.tgz", "wb") as dst:
                shutil.copyfileobj(src, dst)
            tar.unlink()
            tmp = Path(tempfile.mkdtemp(prefix="bench-final-"))
            try:
                agent.safe_extract(rdir / "workspace.tgz", tmp)
                write_text(rdir / "workspace.diff", agent.make_diff(fixture, tmp))
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
            end_reason = result["end_reason"]
            write_text(rdir / "response.md", result["summary"] or "(the model never called finish)")
            c = result["counters"]
            attempts = c["tool_calls"] + c["malformed_text_calls"]
            steps = result["per_step"]
            metrics = {
                "steps": result["steps"], "completion_tokens": result["completion_tokens_total"],
                "prompt_tokens_last": result["prompt_tokens_last"],
                "reasoning_chars": result["reasoning_chars_total"], "usage_estimated": result["usage_estimated"],
                "model_time_s": round(sum(s["total_s"] or 0 for s in steps), 1),
                "gen_tps": _median([(s["completion_tokens"] / (s["total_s"] - s["ttft_s"]))
                                    for s in steps if s["completion_tokens"] and s["ttft_s"] is not None
                                    and s["total_s"] and s["total_s"] - s["ttft_s"] > 0.05]),
                "counters": c,
                "tool_call_validity": round(c["tool_calls_valid"] / attempts, 3) if attempts else None,
            }
        elif mode == "cases":
            spec = read_json(test["dir"] / "cases.json")
            write_json(rdir / "request.json", {"cases": [c["id"] for c in spec["cases"]], "seed": seed,
                                               "sampler": SUITE["sampler"]})
            results = agent.run_cases(chat, make_payload, spec, limits, log,
                                      time.monotonic() + limits["cases_wall_clock_s"])
            write_json(rdir / "cases.json", results)
            lines, calls, valid, toks, tps = [], 0, 0, 0, []
            for cid, rec in results.items():
                lines.append("## %s (%s)\n" % (cid, rec["end"]))
                for i, turn in enumerate(rec["turns"], 1):
                    for tc in turn.get("tool_calls") or []:
                        calls += 1
                        valid += 1 if tc["error"] is None else 0
                        lines.append("turn %d call: %s(%s)\n" % (i, tc["name"], tc["raw_arguments"]))
                    if turn.get("content"):
                        lines.append("turn %d text: %s\n" % (i, turn["content"]))
                    u = turn.get("usage") or {}
                    toks += u.get("completion_tokens") or 0
                    tm = turn.get("timing") or {}
                    if u.get("completion_tokens") and tm.get("ttft_s") is not None and tm["total_s"] - tm["ttft_s"] > 0.05:
                        tps.append(u["completion_tokens"] / (tm["total_s"] - tm["ttft_s"]))
            write_text(rdir / "response.md", "\n".join(lines))
            end_reason = "completed"
            metrics = {"cases": len(results), "completion_tokens": toks, "tool_calls": calls,
                       "tool_calls_json_valid": valid, "gen_tps": _median(tps)}
        else:
            raise SystemExit("unknown mode %r in %s" % (mode, test["id"]))
    finally:
        tlog.close()

    check = do_check(test, rdir, end_reason)
    write_json(rdir / "check.json", check)
    run = {
        "suite": SUITE["suite"], "suite_version": SUITE["version"], "test": test["id"],
        "test_version": test.get("version", 1), "test_hash": test["hash"], "category": test["category"],
        "model": {"key": m["key"], "slug": m["slug"]}, "seed": seed, "sampler": SUITE["sampler"],
        "context_length": ctx_len, "status": "ok", "end_reason": end_reason,
        "started": started, "finished": now_iso(), "wall_s": round(time.time() - t_start, 1),
        "metrics": metrics,
        "flags": {"reloaded": reloaded, "tampered": check["tampered"], "swap_mb_before": swap0,
                  "swap_mb_after": swap_used_mb()},
        "scripted": {"points": check["points"], "max": check["max"]},
    }
    write_json(rdir / "run.json", run)
    return run


def run_one(client, m, test, seed, rdir):
    for attempt in (1, 2):
        try:
            return _attempt(client, m, test, seed, rdir)
        except InfraError as e:
            print("  infra error (attempt %d): %s" % (attempt, e), flush=True)
            err = str(e)
            if attempt == 1:
                try:
                    client.load(m["key"], SUITE["context_length"], m["identifier"])
                    continue
                except InfraError as e2:
                    err = "%s; reload failed: %s" % (err, e2)
            rdir.mkdir(parents=True, exist_ok=True)
            run = {"suite": SUITE["suite"], "suite_version": SUITE["version"], "test": test["id"],
                   "test_version": test.get("version", 1), "test_hash": test["hash"],
                   "category": test["category"], "model": {"key": m["key"], "slug": m["slug"]}, "seed": seed,
                   "status": "engine_failure", "end_reason": "engine_failure", "error": err,
                   "finished": now_iso(), "metrics": {}, "flags": {},
                   "scripted": {"points": 0.0, "max": scripted_max(test)}}
            write_json(rdir / "run.json", run)
            return run


SPEED_PROMPT = ("Explain how a hash map works, including how collisions are handled and what happens when it "
                "resizes. Write about 300 words.")


def speed_probe(client, m, force=False):
    path = m["dir"] / "speed.json"
    if path.exists() and not force:
        return read_json(path)
    print("speed probe ...", flush=True)
    runs = []
    for i in range(4):  # the first is a discarded warm-up
        p = base_payload(m["identifier"], [{"role": "user", "content": SPEED_PROMPT}], 700, 100 + i,
                         m.get("reasoning"))
        res = client.chat_stream(p, idle_timeout=600, deadline=time.monotonic() + 600)
        if i:
            runs.append(_single_metrics(res))
    out = {"when": now_iso(), "prompt": SPEED_PROMPT, "runs": runs,
           "gen_tps_median": _median([r["gen_tps"] for r in runs]),
           "ttft_s_median": _median([r["ttft_s"] for r in runs]),
           "load_seconds": m.get("load_s")}
    write_json(path, out)
    return out


def remove_stale_containers(max_age_s=4 * 3600):
    """Remove sandbox containers left behind by a run that was killed (anything older than four hours)."""
    names = sh("docker ps -a --filter name=bench- --format '{{.Names}}'").split()
    removed = 0
    for name in names:
        created = sh("docker inspect -f '{{.Created}}' %s" % name)
        try:
            when = datetime.datetime.strptime(created[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            continue
        if (datetime.datetime.now(datetime.timezone.utc) - when).total_seconds() > max_age_s:
            sh("docker rm -f %s" % name)
            removed += 1
    return removed


def cmd_run(args):
    client = Client(SUITE["server"])
    tests = load_tests(args.tests)
    if sh("docker info --format '{{.ServerVersion}}'") == "":
        raise SystemExit("Docker is not running; the sandbox and the checks need it")
    stale = remove_stale_containers()
    if stale:
        print("removed %d sandbox container(s) left over from an earlier run" % stale)
    m = ensure_model(client, args.model, reasoning=args.reasoning)
    seeds = [int(s) for s in args.seeds.split(",")] if args.seeds else SUITE["seeds"]
    if not args.no_speed:
        sp = speed_probe(client, m)
        print("speed: %.1f tok/s median, first token after %.2fs" % (sp["gen_tps_median"] or 0,
                                                                     sp["ttft_s_median"] or 0), flush=True)
    for seed in seeds:
        for test in tests:
            rdir = m["dir"] / "runs" / test["id"] / ("s%d" % seed)
            prior = read_json(rdir / "run.json")
            if prior and not args.force:
                if prior.get("test_hash") == test["hash"]:
                    print("%-22s s%d  already done, skipping" % (test["id"], seed), flush=True)
                    continue
                print("%-22s s%d  the test changed since the last run; running it again" % (test["id"], seed),
                      flush=True)
            needs = test.get("requires") or []
            if "vision" in needs and not m["vision"]:
                write_json(rdir / "run.json", {
                    "suite": SUITE["suite"], "suite_version": SUITE["version"], "test": test["id"],
                    "test_version": test.get("version", 1), "test_hash": test["hash"],
                    "category": test["category"], "model": {"key": m["key"], "slug": m["slug"]}, "seed": seed,
                    "status": "na", "end_reason": "no_vision", "finished": now_iso(), "metrics": {}, "flags": {},
                    "scripted": {"points": None, "max": scripted_max(test)}})
                print("%-22s s%d  n/a (model has no vision)" % (test["id"], seed), flush=True)
                continue
            print("%-22s s%d  running ..." % (test["id"], seed), flush=True)
            run = run_one(client, m, test, seed, rdir)
            print("%-22s s%d  %s  end=%s  scripted %s/%s  %.0fs" % (
                test["id"], seed, run["status"], run["end_reason"], run["scripted"]["points"],
                run["scripted"]["max"], run.get("wall_s") or 0), flush=True)
    if args.unload:
        client.unload_all()
        print("model unloaded")


def iter_runs(slug=None, tests=None):
    """Yield (slug, test, seed, rdir, run.json) for every finished run on disk."""
    by_id = {t["id"]: t for t in load_tests(tests)}
    for mdir in sorted(MODELS.iterdir()) if MODELS.exists() else []:
        if not mdir.is_dir() or (slug and mdir.name != slug):
            continue
        for tid, test in by_id.items():
            tdir = mdir / "runs" / tid
            if not tdir.exists():
                continue
            for sdir in sorted(tdir.iterdir()):
                run = read_json(sdir / "run.json")
                if run and sdir.name.startswith("s"):
                    yield mdir.name, test, int(sdir.name[1:]), sdir, run


def recheck(slug=None, tests=None, force=False, dry_run=False, quiet=False):
    """Re-apply scripted checks to saved output. Returns (redone, changed)."""
    redone = changed = 0
    for mslug, test, seed, rdir, run in iter_runs(slug, tests):
        if run.get("status") != "ok" or run.get("test_hash") != test["hash"]:
            continue
        old = read_json(rdir / "check.json", {}) or {}
        if not force and old.get("check_hash") == test["check_hash"]:
            continue
        new = do_check(test, rdir, run.get("end_reason"))
        redone += 1
        same = old.get("checks") == new["checks"] and old.get("points") == new["points"]
        if not same:
            changed += 1
        if not quiet or not same:
            print("%-40s %-24s s%d  %s/%s  %s" % (mslug, test["id"], seed, new["points"], new["max"],
                                                 "same" if same else "CHANGED (was %s)" % old.get("points")), flush=True)
        if not dry_run:
            write_json(rdir / "check.json", new)
            run["scripted"] = {"points": new["points"], "max": new["max"]}
            run.setdefault("flags", {})["tampered"] = new["tampered"]
            write_json(rdir / "run.json", run)
    return redone, changed


def cmd_check(args):
    redone, changed = recheck(args.model_slug, args.tests, force=args.all, dry_run=args.dry_run)
    print("%d check(s) re-applied, %d result(s) differ from what was stored" % (redone, changed))
    return 1 if changed and args.dry_run else 0


def cmd_status(args):
    tests = load_tests()
    slugs = [args.model_slug] if args.model_slug else sorted(
        d.name for d in MODELS.iterdir() if d.is_dir()) if MODELS.exists() else []
    for slug in slugs:
        print("\n%s" % slug)
        print("  %-22s %-5s %-15s %-18s %-9s %-8s %s" % ("test", "seed", "status", "end", "scripted", "judged", "time"))
        for t in tests:
            tdir = MODELS / slug / "runs" / t["id"]
            sdirs = sorted(tdir.iterdir()) if tdir.exists() else []
            if not sdirs:
                print("  %-22s %-5s %-15s" % (t["id"], "-", "not run"))
            for sdir in sdirs:
                run = read_json(sdir / "run.json")
                if not run:
                    print("  %-22s %-5s %-15s" % (t["id"], sdir.name, "incomplete"))
                    continue
                stale = "" if run.get("test_hash") == t["hash"] else " STALE"
                sc = run.get("scripted") or {}
                judged = "yes" if (sdir / "verdict.json").exists() else ("-" if not judge_max(t) else "no")
                print("  %-22s %-5s %-15s %-18s %-9s %-8s %s" % (
                    t["id"], sdir.name, run.get("status", "") + stale, run.get("end_reason"),
                    "%s/%s" % (sc.get("points"), sc.get("max")), judged, "%.0fs" % (run.get("wall_s") or 0)))


def cmd_sandbox_build(args):
    p = subprocess.run(["docker", "build", "-t", SUITE["sandbox"]["image"], str(BASE / "runner" / "sandbox")])
    return p.returncode


# ---------------------------------------------------------------------------
# selftest: prove the checks and the loop work, with no model involved
# ---------------------------------------------------------------------------
def _selftest_checks(tests):
    import agent
    import shutil
    import tarfile
    import tempfile
    failures = 0
    for test in tests:
        ref = test["dir"] / "hidden" / "reference"
        st = test.get("selftest") or {}
        problems = _canary_problems(test)
        if problems:
            print("%-22s FAIL: %s" % (test["id"], "; ".join(problems)))
            failures += 1
        total = scripted_max(test) + judge_max(test)
        if abs(total - float(test.get("score", {}).get("max", 10))) > 1e-9 or abs(total - 10) > 1e-9:
            print("%-22s FAIL: scripted %s + judged %s does not add up to 10" % (
                test["id"], scripted_max(test), judge_max(test)))
            failures += 1
        if not test.get("check"):
            print("%-22s (no scripted check)" % test["id"])
            continue
        if not ref.exists():
            print("%-22s FAIL: no hidden/reference" % test["id"])
            failures += 1
            continue
        cases = [("reference", True), ("baseline", False)]
        for label, is_ref in cases:
            rdir = Path(tempfile.mkdtemp(prefix="bench-selftest-"))
            try:
                if test["mode"] == "agentic":
                    tree = rdir / "tree"
                    shutil.copytree(test["dir"] / test.get("workspace", "workspace"), tree)
                    if is_ref:
                        if (ref / "workspace").exists():
                            shutil.copytree(ref / "workspace", tree, dirs_exist_ok=True)
                        for rel in (ref / "delete.txt").read_text().split() if (ref / "delete.txt").exists() else []:
                            target = tree / rel
                            if target.is_dir():
                                shutil.rmtree(target)
                            elif target.exists():
                                target.unlink()
                    with tarfile.open(rdir / "workspace.tgz", "w:gz") as tf:
                        tf.add(tree, arcname=".")
                    shutil.rmtree(tree)
                src = ref / ("response.md" if is_ref else "baseline.md")
                write_text(rdir / "response.md", src.read_text() if src.exists() else "")
                if test["mode"] == "cases":
                    src = ref / ("cases.json" if is_ref else "baseline-cases.json")
                    write_text(rdir / "cases.json", src.read_text() if src.exists() else "{}")
                chk = do_check(test, rdir, "finished" if is_ref else "selftest")
            finally:
                shutil.rmtree(rdir, ignore_errors=True)
            if is_ref:
                ok = chk["ran"] and abs(chk["points"] - chk["max"]) < 1e-6 and not chk["tampered"]
                want = "= %s" % chk["max"]
            else:
                bmax = float(st.get("baseline_max", 0))
                ok = chk["ran"] and chk["points"] <= bmax + 1e-6
                want = "<= %s" % bmax
            lost = [k for k, d in chk["detail"].items() if d["points"] < d["max"]] if is_ref else []
            print("%-22s %-9s %s  scripted %s (want %s)%s%s" % (
                test["id"], label, "ok  " if ok else "FAIL", chk["points"], want,
                "  lost: %s" % ",".join(lost) if lost else "",
                "  error: %s" % chk["error"] if chk["error"] else ""), flush=True)
            if not ok:
                failures += 1
    return failures


TEXT_SUFFIXES = {".md", ".py", ".sh", ".ts", ".js", ".rs", ".sql", ".txt", ".json", ".yaml", ".yml", ".toml", ".html"}


def _canary_problems(test):
    """The canary must mark the answer key and hidden files, and must never be visible to a model."""
    canary, tdir, out = SUITE["canary"], test["dir"], []
    if canary not in (tdir / "rubric.md").read_text(errors="replace") if (tdir / "rubric.md").exists() else True:
        out.append("rubric.md is missing or lacks the canary")
    visible = [tdir / test.get("prompt", "prompt.md"), tdir / "cases.json"]
    for sub in ("workspace", "input"):
        if (tdir / sub).exists():
            visible += [f for f in (tdir / sub).rglob("*") if f.is_file()]
    for f in visible:
        if f.exists() and canary.encode() in f.read_bytes():
            out.append("canary found in model-visible file %s" % f.relative_to(tdir))
    hidden = tdir / "hidden"
    if hidden.exists():
        marked = [f for f in hidden.rglob("*") if f.is_file() and f.suffix in TEXT_SUFFIXES
                  and canary.encode() in f.read_bytes()]
        if not marked:
            out.append("no file under hidden/ carries the canary")
        if (hidden / "check.py").exists() and canary not in (hidden / "check.py").read_text(errors="replace"):
            out.append("hidden/check.py lacks the canary")
    return out


def _selftest_judging():
    """The judging pipeline on a throwaway folder: blinding, verdict validation, anchors, idempotent reports."""
    import report
    import shutil
    import tempfile
    test = next(t for t in load_tests() if judge_max(t) and t["mode"] == "agentic")
    crit = test["score"]["judge"]
    root = Path(tempfile.mkdtemp(prefix="bench-judging-"))
    models = root / "models"
    cases = []

    def fake_run(slug, answer):
        rdir = models / slug / "runs" / test["id"] / "s1"
        write_json(models / slug / "model.json", {"slug": slug, "key": "acme/" + slug.split("__")[0],
                                                  "display_name": slug.split("__")[0].capitalize()})
        write_text(rdir / "response.md", answer)
        write_text(rdir / "workspace.diff", "+test(\"regression: totals add up\", () => {})\n")
        write_json(rdir / "check.json", {"points": 6.0, "max": scripted_max(test), "detail": {}, "notes": {},
                                         "tampered": [], "check_hash": test["check_hash"]})
        write_json(rdir / "run.json", {"test": test["id"], "status": "ok", "test_hash": test["hash"], "seed": 1,
                                       "end_reason": "finished", "category": test["category"], "wall_s": 10,
                                       "scripted": {"points": 6.0, "max": scripted_max(test)}, "metrics": {}, "flags": {}})

    def verdict(points, quote):
        return {"criteria": {c["id"]: {"points": points, "quote": quote, "reason": "selftest"} for c in crit}}

    def low(quote):      # the first criterion gets one step, the rest nothing
        v = verdict(0, "")
        v["criteria"][crit[0]["id"]] = {"points": step, "quote": quote, "reason": "selftest"}
        return v

    def high(quote):     # every criterion gets its maximum
        return {"criteria": {c["id"]: {"points": c["max"], "quote": quote, "reason": "selftest"} for c in crit}}

    try:
        fake_run("zebrafin__mlx-4bit__r-on", "I am Zebrafin. The cause was per-line rounding; I fixed it and added a test.")
        fake_run("quokkanet__gguf-q4__r-on", "Quokkanet here: fixed the rounding issues and added a regression test.")
        bdir, counts = report.build_packets(root, models, [test], render_prompt, "b1")
        mapping = read_json(bdir / "map.json")
        tdir = bdir / test["id"]
        texts = {b: (tdir / (b + ".md")).read_text() for b in mapping}
        cases.append(("one packet per run", counts == {test["id"]: 2} and len(mapping) == 2))
        cases.append(("model names are scrubbed from packets",
                      not any("zebrafin" in t.lower() or "quokkanet" in t.lower() for t in texts.values())))
        cases.append(("packets contain no hidden material", not any(SUITE["canary"] in t for t in texts.values())))
        ids = sorted(mapping)
        good_quote = "and added a"   # occurs in both fake answers
        step = float(crit[0].get("step", 0.5))
        bad = [
            ("a positive award without a quote is rejected", verdict(crit[0]["max"], "")),
            ("a quote that is not in the packet is rejected", verdict(crit[0]["max"], "this text is not in the packet")),
            ("points off the step grid are rejected", verdict(step / 2.0, good_quote)),
            ("a missing criterion is rejected", {"criteria": {}}),
        ]
        for name, v in bad:
            cases.append((name, bool(report.validate_verdict(test, v, texts[ids[0]]))))
        for b in ids:
            write_json(tdir / (b + ".verdict.json"), low(good_quote))
        rep1 = report.ingest_verdicts(root, models, [test], "selftest-judge", "2000-01-01")
        rep2 = report.ingest_verdicts(root, models, [test], "selftest-judge", "2000-01-01")
        cases.append(("valid verdicts are stored once", rep1["stored"] == 2 and not rep1["problems"] and rep2["stored"] == 0))
        report.write_reports(root, models, [test], SUITE, "2000-01-01")
        first = (root / "LEADERBOARD.md").read_text() + "".join(
            (d / "SCORECARD.md").read_text() for d in sorted(models.iterdir()))
        report.write_reports(root, models, [test], SUITE, "2000-01-01")
        second = (root / "LEADERBOARD.md").read_text() + "".join(
            (d / "SCORECARD.md").read_text() for d in sorted(models.iterdir()))
        cases.append(("reports are identical when generated twice", first == second))
        slug0 = sorted(d.name for d in models.iterdir())[0]
        stored = read_json(models / slug0 / "runs" / test["id"] / "s1" / "verdict.json")
        cases.append(("the stored verdict records judge and fingerprints",
                      bool(stored) and stored["judge_model"] == "selftest-judge"
                      and stored["judge_hash"] == test["judge_hash"]
                      and abs(stored["judged_points"] - step) < 1e-9))
        fake_run("okapimax__mlx-2bit__r-on", "Fixed the rounding and added a regression test.")
        bdir2, counts2 = report.build_packets(root, models, [test], render_prompt, "b2", anchors=2)
        map2 = read_json(bdir2 / "map.json")
        anchors = [b for b, i in map2.items() if i["anchor"]]
        cases.append(("a later batch re-includes two judged packets as anchors",
                      counts2 == {test["id"]: 3} and len(anchors) == 2))
        for b, info in map2.items():
            write_json(bdir2 / test["id"] / (b + ".verdict.json"), high(good_quote) if info["anchor"] else low(good_quote))
        rep3 = report.ingest_verdicts(root, models, [test], "selftest-judge", "2000-01-01")
        moved = judge_max(test) - step
        cases.append(("anchor drift is measured and never overwrites the stored verdict",
                      rep3["stored"] == 1 and len(rep3["anchors"]) == 2
                      and all(abs(a["delta"] - moved) < 1e-9 and a["drift"] == (moved > 1.0) for a in rep3["anchors"])
                      and read_json(models / slug0 / "runs" / test["id"] / "s1" / "verdict.json") == stored))
    finally:
        shutil.rmtree(root, ignore_errors=True)
    failures = 0
    for name, ok in cases:
        print("judging: %-64s %s" % (name, "ok" if ok else "FAIL"))
        failures += 0 if ok else 1
    return failures


def _selftest_loop():
    """Exercise every branch of the agent loop with scripted replies and a fake sandbox."""
    import agent

    def reply(content="", calls=None, finish="stop", pt=1000, ct=50, aborted=None):
        tcs = [{"id": "c%d" % i, "type": "function", "function": {"name": n, "arguments": a}}
               for i, (n, a) in enumerate(calls or [])]
        return {"content": content, "reasoning": "", "tool_calls": tcs,
                "finish_reason": "tool_calls" if tcs else finish, "aborted": aborted, "error": None,
                "usage": {"prompt_tokens": pt, "completion_tokens": ct},
                "timing": {"ttft_s": 0.1, "ttfa_s": 0.2, "total_s": 1.0}}

    def drive(replies, limits=None, context=80000):
        lim = dict(LIMITS)
        lim.update(limits or {})
        it = iter(replies)
        seen = []

        def chat(payload, deadline):
            seen.append(payload)
            try:
                return next(it)
            except StopIteration:
                return reply("still thinking")
        sb = agent.FakeSandbox()
        out = agent.run_agent(chat, lambda msgs, mt: {"messages": list(msgs), "max_tokens": mt}, "task", "system",
                              sb, lim, context, lambda ev: None, time.monotonic() + 60)
        return out, sb, seen

    cases = []
    out, sb, _ = drive([reply(calls=[("read_file", '{"path":"a.txt"}')]),
                        reply(calls=[("finish", '{"summary":"done"}')])])
    cases.append(("finish ends the run", out["end_reason"] == "finished" and out["summary"] == "done"
                  and out["counters"]["tool_calls_valid"] == 2 and len(sb.calls) == 1))
    out, _, _ = drive([reply("I will read the file next.")] * 5)
    cases.append(("three text-only replies end as no_action",
                  out["end_reason"] == "no_action" and out["steps"] == 3 and out["counters"]["nudges"] == 3))
    out, _, _ = drive([reply('<tool_call>{"name":"read_file","arguments":{"path":"x"}}</tool_call>'),
                       reply(calls=[("finish", '{"summary":"ok"}')])])
    cases.append(("text that looks like a call is counted and nudged",
                  out["end_reason"] == "finished" and out["counters"]["malformed_text_calls"] == 1))
    out, sb, seen = drive([reply(calls=[("read_file", '{"path": ')]), reply(calls=[("finish", '{"summary":"ok"}')])])
    hist = seen[1]["messages"]
    cases.append(("invalid JSON arguments return an error and are not executed",
                  out["counters"]["invalid_json"] == 1 and not sb.calls
                  and hist[-1]["content"].startswith("ERROR") and hist[-2]["tool_calls"][0]["function"]["arguments"] == "{}"))
    out, sb, _ = drive([reply(calls=[("delete_everything", "{}"), ("write_file", '{"path":"a"}')]),
                        reply(calls=[("finish", '{"summary":"ok"}')])])
    cases.append(("unknown tools and missing arguments are rejected",
                  out["counters"]["unknown_tool"] == 1 and out["counters"]["missing_args"] == 1 and not sb.calls))
    out, _, _ = drive([reply(calls=[("run_command", '{"command":"ls"}')])] * 50, limits={"agent_max_steps": 5})
    cases.append(("step cap", out["end_reason"] == "step_cap" and out["steps"] == 5))
    out, _, _ = drive([reply(calls=[("run_command", '{"command":"ls"}')], ct=30000)] * 5)
    cases.append(("total output-token budget", out["end_reason"] == "token_budget" and out["steps"] == 2))
    out, _, _ = drive([reply(calls=[("run_command", '{"command":"ls"}')], pt=75000)] * 5)
    cases.append(("stops before the context window overflows",
                  out["end_reason"] == "context_exhausted" and out["steps"] == 1))
    out, _, _ = drive([reply("", finish="length"), reply(calls=[("finish", '{"summary":"ok"}')])])
    cases.append(("a cut-off reply gets the length nudge",
                  out["end_reason"] == "finished" and out["counters"]["length_cutoffs"] == 1))
    out, _, _ = drive([reply("loop", aborted="degenerate_loop")])
    cases.append(("a degenerate loop ends the run", out["end_reason"] == "degenerate_loop"))
    out, sb, _ = drive([reply(calls=[("finish", '{"summary":"ok"}'), ("run_command", '{"command":"rm -rf x"}')])])
    cases.append(("calls after finish are not executed", out["end_reason"] == "finished" and not sb.calls
                  and out["counters"]["dropped_calls"] == 1))
    try:
        drive([reply(calls=[("run_command", '{"command":"ls"}')], pt=5000),
               reply(calls=[("run_command", '{"command":"ls"}')], pt=3000)])
        cases.append(("a shrinking prompt is treated as server truncation", False))
    except InfraError:
        cases.append(("a shrinking prompt is treated as server truncation", True))
    cases.append(("repeated-tail detector fires on a loop",
                  lmstudio.repeated_tail("intro " + "the same line again and again\n" * 80)
                  and not lmstudio.repeated_tail("".join("line %d of ordinary output\n" % i for i in range(400)))))
    failures = 0
    for name, ok in cases:
        print("loop: %-58s %s" % (name, "ok" if ok else "FAIL"))
        failures += 0 if ok else 1
    return failures


def cmd_selftest(args):
    failures = 0
    if not args.tests:
        failures += _selftest_loop()
        failures += _selftest_judging()
    failures += _selftest_checks(load_tests(args.tests))
    print("\nselftest: %s" % ("all good" if not failures else "%d FAILURE(S)" % failures))
    return 1 if failures else 0


def cmd_packet(args):
    import report
    tests = load_tests(args.tests)
    batch = args.batch or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bdir, counts = report.build_packets(ROOT, MODELS, tests, render_prompt, batch, only_slug=args.model_slug,
                                        anchors=args.anchors, rejudge=args.rejudge)
    if not counts:
        print("nothing to judge: every finished run with judged criteria already has a verdict")
        return 0
    print("judging batch: %s" % bdir)
    for tid, n in counts.items():
        print("  %-26s %d packet(s)   %s" % (tid, n, bdir / tid))
    print("Judge each folder as described in base/docs/EVALUATION.md, then run: bench.py score --judge-model <id>")
    return 0


def cmd_score(args):
    import report
    tests = load_tests()
    today = datetime.date.today().isoformat()
    redone, changed = recheck(quiet=True)
    if redone:
        print("re-applied %d scripted check(s) whose grading changed (%d result(s) moved)" % (redone, changed))
    rep = report.ingest_verdicts(ROOT, MODELS, tests, args.judge_model, today)
    print("verdicts stored: %d" % rep["stored"])
    for a in rep["anchors"]:
        print("  anchor %s %s: judged points moved by %+.2f%s" % (
            a["test"], a["packet"], a["delta"], "  <-- DRIFT over 1 point: re-judge this test" if a["drift"] else ""))
    for p in rep["problems"]:
        print("  REJECTED %s" % p)
    if rep["missing"]:
        print("  packets still without a verdict: %d (%s%s)" % (
            len(rep["missing"]), ", ".join(rep["missing"][:4]), " ..." if len(rep["missing"]) > 4 else ""))
    models = report.write_reports(ROOT, MODELS, tests, SUITE, today)
    print()
    print("%-42s %-8s %-9s %-9s %-9s %-9s %-7s" % ("model", "core", "agentic", "swe", "long", "general", "vision"))
    for m in sorted(models.values(), key=lambda m: -(m["core"] or -1)):
        c = m["cats"]
        print("%-42s %-8s %-9s %-9s %-9s %-9s %-7s" % (
            m["slug"], report.fmt(m["core"]) + ("" if m["core_complete"] else "*"), report.fmt(c["agentic"]["pct"]),
            report.fmt(c["swe"]["pct"]), report.fmt(c["long"]["pct"]), report.fmt(c["general"]["pct"]),
            "n/a" if m["vision_na"] else report.fmt(m["vision"])))
    print("wrote LEADERBOARD.md and models/<slug>/SCORECARD.md  (* = provisional)")
    return 1 if rep["problems"] else 0


def cmd_models(args):
    client = Client(SUITE["server"])
    for info in client.list_models():
        if info.get("type") != "llm":
            continue
        caps = info.get("capabilities") or {}
        print("%-28s %-40s vision=%-5s reasoning=%s" % (
            info["key"], slug_for(info), caps.get("vision"), (caps.get("reasoning") or {}).get("default")))


def build_parser():
    ap = argparse.ArgumentParser(prog="bench.py", description="Local LLM benchmark runner for LM Studio")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("models", help="list LM Studio models and their benchmark slugs").set_defaults(fn=cmd_models)
    p = sub.add_parser("probe", help="record how a model behaves over the API (models/<slug>/probe.json)")
    p.add_argument("--model", required=True)
    p.add_argument("--overflow", action="store_true", help="also test context-overflow behaviour (reloads at 4096)")
    p.add_argument("--unload", action="store_true", help="unload the model afterwards")
    p.set_defaults(fn=cmd_probe)

    p = sub.add_parser("run", help="run tests one by one against a model (finished tests are skipped)")
    p.add_argument("--model", required=True, help="LM Studio model key, e.g. qwen/qwen3.8-27b")
    p.add_argument("--tests", help="comma-separated test ids or prefixes (default: all)")
    p.add_argument("--seeds", help="comma-separated seeds (default: suite.json)")
    p.add_argument("--force", action="store_true", help="re-run tests that already have results")
    p.add_argument("--no-speed", action="store_true", help="skip the speed probe")
    p.add_argument("--reasoning", help="run a reasoning variant (sent as reasoning_effort, e.g. none); "
                                       "it gets its own models/<slug> folder")
    p.add_argument("--unload", action="store_true", help="unload the model afterwards")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("check", help="re-run the scripted checks on saved results")
    p.add_argument("--model-slug")
    p.add_argument("--tests")
    p.add_argument("--all", action="store_true", help="re-apply every check, not only those whose check changed")
    p.add_argument("--dry-run", action="store_true", help="compare only; exit 1 if anything differs")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("status", help="show what has been run, checked, and judged")
    p.add_argument("--model-slug")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("selftest", help="verify every check against its reference solution, and the agent loop")
    p.add_argument("--tests")
    p.set_defaults(fn=cmd_selftest)

    p = sub.add_parser("packet", help="build blind judging packets for runs that still need a verdict")
    p.add_argument("--tests")
    p.add_argument("--model-slug", help="only this model's runs (anchors may still come from others)")
    p.add_argument("--batch", help="batch name (default: a timestamp)")
    p.add_argument("--anchors", type=int, default=2, help="already-judged packets to re-include per test (default 2)")
    p.add_argument("--rejudge", action="store_true", help="include runs that already have a verdict")
    p.set_defaults(fn=cmd_packet)

    p = sub.add_parser("score", help="validate verdicts, do the arithmetic, write SCORECARD.md and LEADERBOARD.md")
    p.add_argument("--judge-model", default="claude", help="model id of the judge, recorded with each verdict")
    p.set_defaults(fn=cmd_score)

    sub.add_parser("sandbox-build", help="build the Docker sandbox image").set_defaults(fn=cmd_sandbox_build)
    return ap


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "fn", None):
        ap.print_help()
        return 2
    try:
        return args.fn(args) or 0
    except InfraError as e:
        print("INFRA ERROR: %s" % e, file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
