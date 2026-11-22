"""Blind judging packets, verdict validation, score arithmetic, and the generated reports.

Claude writes verdicts; everything else here is mechanical so that totals are never done by hand.
Stdlib only; must run on Python 3.9.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import shutil
from pathlib import Path

MAX_PROMPT_CHARS = 14000
MAX_DIFF_CHARS = 40000
MAX_ANSWER_CHARS = 60000


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def squeeze(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def read_text(path, default=""):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return default


def read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# blinding
# ---------------------------------------------------------------------------
def name_tokens(models_dir):
    """Words that could reveal which model produced an answer (from every model.json on disk)."""
    words = set()
    for mj in Path(models_dir).glob("*/model.json"):
        meta = read_json(mj, {}) or {}
        for field in ("key", "display_name", "publisher", "architecture", "slug"):
            for w in re.split(r"[^A-Za-z0-9.]+", str(meta.get(field) or "")):
                w = w.strip(".").lower()
                if len(w) >= 4 and not w.isdigit() and w not in ("gguf", "bench", "none", "xhigh", "2bit", "4bit"):
                    words.add(w)
    return sorted(words, key=len, reverse=True)


def scrub(text, tokens):
    for w in tokens:
        text = re.sub(re.escape(w), "[model]", text, flags=re.I)
    return text


def clip_middle(text, limit, what):
    if len(text) <= limit:
        return text
    head, tail = int(limit * 0.6), int(limit * 0.3)
    return "%s\n\n[... %d characters of %s omitted from this packet ...]\n\n%s" % (
        text[:head], len(text) - head - tail, what, text[-tail:])


# ---------------------------------------------------------------------------
# scoring helpers
# ---------------------------------------------------------------------------
def criteria_of(test):
    return test.get("score", {}).get("judge") or []


def validate_verdict(test, verdict, packet_text):
    """Return a list of problems (empty when the verdict is acceptable)."""
    problems = []
    crit = verdict.get("criteria")
    if not isinstance(crit, dict):
        return ["verdict has no 'criteria' object"]
    wanted = {c["id"]: c for c in criteria_of(test)}
    for cid in crit:
        if cid not in wanted:
            problems.append("unknown criterion %r" % cid)
    haystack = squeeze(packet_text)
    for cid, c in wanted.items():
        v = crit.get(cid)
        if not isinstance(v, dict):
            problems.append("%s: missing" % cid)
            continue
        pts = v.get("points")
        lo, hi, step = float(c.get("min", 0)), float(c["max"]), float(c.get("step", 0.5))
        if isinstance(pts, bool) or not isinstance(pts, (int, float)):
            problems.append("%s: points must be a number" % cid)
            continue
        if pts < lo - 1e-9 or pts > hi + 1e-9:
            problems.append("%s: %s is outside %s..%s" % (cid, pts, lo, hi))
        if abs(round((pts - lo) / step) * step - (pts - lo)) > 1e-9:
            problems.append("%s: %s is not on the %s step grid" % (cid, pts, step))
        if not squeeze(v.get("reason")):
            problems.append("%s: a one-sentence reason is required" % cid)
        absence = c.get("evidence") == "absence"
        needs_quote = (pts < hi - 1e-9) if absence else (pts > lo + 1e-9)
        quote = squeeze(v.get("quote"))
        if needs_quote and len(quote) < 8:
            problems.append("%s: a quote from the packet is required for %s points" % (cid, pts))
        elif quote and quote not in haystack:
            problems.append("%s: the quote does not occur in the packet: %r" % (cid, quote[:80]))
    return problems


def judge_points(test, verdict):
    total = 0.0
    for c in criteria_of(test):
        total += float(((verdict or {}).get("criteria") or {}).get(c["id"], {}).get("points") or 0)
    return round(total, 3)


def run_score(test, run, verdict):
    """(total, scripted, judged, state) for one run. state: ok | judge_pending | na | engine_failure."""
    status = run.get("status")
    scripted = (run.get("scripted") or {}).get("points")
    if status == "na":
        return None, None, None, "na"
    if status == "engine_failure":
        return 0.0, 0.0, 0.0, "engine_failure"
    scripted = float(scripted or 0)
    if not criteria_of(test):
        return min(10.0, max(0.0, scripted)), scripted, None, "ok"
    if verdict is None:
        return min(10.0, max(0.0, scripted)), scripted, None, "judge_pending"
    judged = judge_points(test, verdict)
    return round(min(10.0, max(0.0, scripted + judged)), 3), scripted, judged, "ok"


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    mid = len(xs) // 2
    return xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2.0


def fmt(x, digits=1, dash="-"):
    if x is None:
        return dash
    s = ("%." + str(digits) + "f") % x
    return s.rstrip("0").rstrip(".") if "." in s else s


def collect(models_dir, tests, suite):
    """Everything known about every model: {slug: {...}}."""
    out = {}
    by_id = {t["id"]: t for t in tests}
    core_cats = list(suite["core_weights"])
    for mdir in sorted(Path(models_dir).iterdir()) if Path(models_dir).exists() else []:
        if not (mdir / "runs").exists():
            continue
        meta = read_json(mdir / "model.json", {}) or {}
        rows, stale = [], []
        for tid, test in by_id.items():
            tdir = mdir / "runs" / tid
            seeds = []
            for sdir in sorted(tdir.iterdir()) if tdir.exists() else []:
                run = read_json(sdir / "run.json")
                if not run or not sdir.name.startswith("s"):
                    continue
                if run.get("test_hash") != test["hash"]:
                    stale.append("%s/%s" % (tid, sdir.name))
                    continue
                verdict = read_json(sdir / "verdict.json")
                if verdict and (verdict.get("test_hash") != test["hash"] or verdict.get("judge_hash") != test["judge_hash"]):
                    verdict = None
                total, scripted, judged, state = run_score(test, run, verdict)
                seeds.append({"seed": sdir.name, "run": run, "verdict": verdict, "check": read_json(sdir / "check.json", {}),
                              "total": total, "scripted": scripted, "judged": judged, "state": state})
            states = {s["state"] for s in seeds}
            row = {"test": test, "seeds": seeds,
                   "state": "not_run" if not seeds else "na" if states == {"na"} else
                            "judge_pending" if "judge_pending" in states else "ok",
                   "score": mean([s["total"] for s in seeds]),
                   "spread": (max(s["total"] for s in seeds if s["total"] is not None)
                              - min(s["total"] for s in seeds if s["total"] is not None))
                   if len([s for s in seeds if s["total"] is not None]) > 1 else None}
            rows.append(row)
        cats = {}
        for cat in list(suite["categories"]):
            trows = [r for r in rows if r["test"]["category"] == cat]
            scored = [r for r in trows if r["score"] is not None]
            cats[cat] = {
                "tests": len(trows), "scored": len(scored),
                "pct": (mean([r["score"] for r in scored]) * 10.0) if scored else None,
                "complete": bool(trows) and all(r["state"] == "ok" for r in trows),
                "na": bool(trows) and all(r["state"] == "na" for r in trows),
            }
        weights = suite["core_weights"]
        have = [c for c in core_cats if cats[c]["pct"] is not None]
        core = sum(cats[c]["pct"] * weights[c] for c in have) / float(sum(weights[c] for c in have)) if have else None
        core_complete = all(cats[c]["complete"] for c in core_cats)
        counters = {"valid": 0, "attempts": 0}
        wall, agent_times, tps = 0.0, [], []
        n_seeds = set()
        for r in rows:
            for s in r["seeds"]:
                n_seeds.add(s["seed"])
                m = s["run"].get("metrics") or {}
                wall += s["run"].get("wall_s") or 0
                c = m.get("counters")
                if c:
                    counters["valid"] += c.get("tool_calls_valid", 0)
                    counters["attempts"] += c.get("tool_calls", 0) + c.get("malformed_text_calls", 0)
                    agent_times.append(s["run"].get("wall_s"))
                if m.get("gen_tps"):
                    tps.append(m["gen_tps"])
        speed = read_json(mdir / "speed.json", {}) or {}
        l1 = next((s["run"].get("metrics", {}).get("prompt_tps") for r in rows if r["test"]["id"].startswith("L1")
                   for s in r["seeds"]), None)
        out[mdir.name] = {
            "slug": mdir.name, "meta": meta, "rows": rows, "stale": stale, "cats": cats,
            "core": core, "core_complete": core_complete, "partial": len(have) < len(core_cats) or any(
                cats[c]["scored"] < cats[c]["tests"] for c in core_cats),
            "vision": cats.get("vision", {}).get("pct"), "vision_na": cats.get("vision", {}).get("na"),
            "tool_validity": (counters["valid"] / float(counters["attempts"])) if counters["attempts"] else None,
            "gen_tps": speed.get("gen_tps_median") or median(tps), "ttft_s": speed.get("ttft_s_median"),
            "prompt_tps_long": l1, "suite_wall_s": wall, "agentic_time_s": median(agent_times),
            "seeds": sorted(n_seeds), "judge_models": sorted({
                s["verdict"].get("judge_model") for r in rows for s in r["seeds"]
                if s["verdict"] and s["verdict"].get("judge_model")}),
        }
    return out


# ---------------------------------------------------------------------------
# packets
# ---------------------------------------------------------------------------
def build_packets(root, models_dir, tests, render_prompt, batch, only_slug=None, anchors=2, rejudge=False):
    """Write blind packets for every run that still needs judging. Returns (batch dir, {test id: count})."""
    tokens = name_tokens(models_dir)
    bdir = Path(root) / "judging" / batch
    if bdir.exists():
        raise SystemExit("judging batch %s already exists" % bdir)
    mapping, counts = {}, {}
    for test in tests:
        if not criteria_of(test):
            continue
        todo, judged = [], []
        for mdir in sorted(Path(models_dir).iterdir()):
            if not (mdir / "runs" / test["id"]).exists():
                continue
            for sdir in sorted((mdir / "runs" / test["id"]).iterdir()):
                run = read_json(sdir / "run.json")
                if not run or run.get("status") != "ok" or run.get("test_hash") != test["hash"]:
                    continue
                prior = read_json(sdir / "verdict.json")
                has = bool(prior) and prior.get("test_hash") == test["hash"] \
                    and prior.get("judge_hash") == test["judge_hash"]
                if has and not rejudge:
                    judged.append((mdir.name, sdir))
                elif not only_slug or mdir.name == only_slug:
                    todo.append((mdir.name, sdir))
        if not todo:
            continue
        tdir = bdir / test["id"]
        tdir.mkdir(parents=True)
        rubric = read_text(test["dir"] / "rubric.md")
        (tdir / "RUBRIC.md").write_text(rubric)
        write_json(tdir / "CRITERIA.json", criteria_of(test))
        prompt = clip_middle(render_prompt(test), MAX_PROMPT_CHARS, "the task's input")
        picks = [(slug, sdir, False) for slug, sdir in todo] + [(slug, sdir, True) for slug, sdir in judged[:anchors]]
        picks.sort(key=lambda p: sha(p[0] + str(p[1]) + batch))   # shuffle so order reveals nothing
        for slug, sdir, is_anchor in picks:
            run = read_json(sdir / "run.json")
            check = read_json(sdir / "check.json", {}) or {}
            blind = secrets.token_hex(3)
            while blind in mapping:
                blind = secrets.token_hex(3)
            parts = ["# Packet %s (%s)" % (blind, test["id"]), "",
                     "## Task given to the model", "", prompt, "",
                     "## Scripted check results", "",
                     "- how the run ended: `%s`" % run.get("end_reason"),
                     "- scripted points: %s of %s" % (check.get("points"), check.get("max"))]
            for cid, d in (check.get("detail") or {}).items():
                parts.append("  - `%s`: %s of %s" % (cid, d.get("points"), d.get("max")))
            if check.get("tampered"):
                parts.append("- protected files the model edited or deleted (restored before checking): %s"
                             % ", ".join(check["tampered"]))
            if check.get("notes"):
                parts += ["- check notes:", "", "```json", json.dumps(check["notes"], indent=1, ensure_ascii=False)[:6000], "```"]
            answer = read_text(sdir / "response.md")
            parts += ["", "## The model's answer" + (" (its finish summary)" if test["mode"] == "agentic" else ""), "",
                      clip_middle(scrub(answer, tokens), MAX_ANSWER_CHARS, "the answer") or "(empty)"]
            if (sdir / "workspace.diff").exists():
                diff = scrub(read_text(sdir / "workspace.diff"), tokens)
                parts += ["", "## Diff of the model's changes", "", "```diff",
                          clip_middle(diff, MAX_DIFF_CHARS, "the diff") or "(no changes)", "```"]
            text = "\n".join(parts) + "\n"
            (tdir / (blind + ".md")).write_text(text)
            mapping[blind] = {"slug": slug, "test": test["id"], "seed": sdir.name, "anchor": is_anchor,
                              "packet_hash": sha(text), "judge_hash": test["judge_hash"], "test_hash": test["hash"]}
        counts[test["id"]] = len(picks)
    if mapping:
        write_json(bdir / "map.json", mapping)
    return bdir, counts


def ingest_verdicts(root, models_dir, tests, judge_model, when):
    """Validate every verdict file in judging/, store the good ones next to their runs. Returns a report."""
    by_id = {t["id"]: t for t in tests}
    report = {"stored": 0, "anchors": [], "problems": [], "missing": []}
    jroot = Path(root) / "judging"
    for bdir in sorted(jroot.iterdir()) if jroot.exists() else []:
        mapping = read_json(bdir / "map.json")
        if not mapping:
            continue
        for blind, info in mapping.items():
            test = by_id.get(info["test"])
            tdir = bdir / info["test"]
            vpath = tdir / (blind + ".verdict.json")
            if test is None or (tdir / (blind + ".done")).exists():
                continue
            if not vpath.exists():
                report["missing"].append("%s/%s/%s" % (bdir.name, info["test"], blind))
                continue
            verdict = read_json(vpath)
            packet = read_text(tdir / (blind + ".md"))
            if verdict is None:
                report["problems"].append("%s/%s/%s: not valid JSON" % (bdir.name, info["test"], blind))
                continue
            problems = validate_verdict(test, verdict, packet)
            if info["test_hash"] != test["hash"] or info["judge_hash"] != test["judge_hash"]:
                problems.append("the test or its rubric changed after this packet was built")
            if problems:
                report["problems"] += ["%s/%s/%s: %s" % (bdir.name, info["test"], blind, p) for p in problems]
                continue
            rdir = Path(models_dir) / info["slug"] / "runs" / info["test"] / info["seed"]
            new_total = judge_points(test, verdict)
            if info.get("anchor"):
                old = read_json(rdir / "verdict.json")
                if old:
                    delta = new_total - judge_points(test, old)
                    report["anchors"].append({"test": info["test"], "packet": blind, "delta": round(delta, 2),
                                              "drift": abs(delta) > 1.0})
                (tdir / (blind + ".done")).write_text("anchor\n")
                continue
            stored = {"test": info["test"], "test_hash": test["hash"], "judge_hash": test["judge_hash"],
                      "packet_hash": info["packet_hash"], "batch": bdir.name, "packet": blind,
                      "judge_model": judge_model, "judged_at": when, "criteria": verdict["criteria"],
                      "notes": verdict.get("notes"), "judged_points": new_total}
            write_json(rdir / "verdict.json", stored)
            (tdir / (blind + ".done")).write_text("stored\n")
            report["stored"] += 1
    return report


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------
STATE_NOTE = {"judge_pending": "judge pending", "na": "n/a", "engine_failure": "engine failure", "not_run": "not run"}


def render_scorecard(m, suite):
    meta = m["meta"]
    host = meta.get("host") or {}
    q = meta.get("quantization") or {}
    L = ["# Scorecard: %s" % (meta.get("display_name") or m["slug"]), "",
         "Generated by `bench.py score`. Do not edit by hand.", "",
         "| | |", "|---|---|",
         "| Model key | `%s` |" % meta.get("key"),
         "| Format / quantisation | %s / %s |" % (meta.get("format"), q.get("name")),
         "| Parameters / size | %s / %.1f GB |" % (meta.get("params"), (meta.get("size_bytes") or 0) / 1e9),
         "| Reasoning level | %s%s |" % (meta.get("reasoning_level"),
                                         "" if not meta.get("reasoning_effort_sent") else " (sent as reasoning_effort)"),
         "| Context loaded | %s |" % ((meta.get("load_config") or {}).get("context_length")),
         "| Sampler | %s |" % ", ".join("%s %s" % kv for kv in (meta.get("sampler") or {}).items()),
         "| LM Studio / engines | %s / %s |" % (host.get("lmstudio_app"), ", ".join(host.get("engines") or [])),
         "| Hardware | %s, %s GB RAM, %s |" % (host.get("chip"), host.get("ram_gb"), host.get("os")),
         "| Suite | %s v%s%s |" % (suite["suite"], suite["version"], "" if suite.get("frozen") else " (not frozen)"),
         "| Runs per test | %d%s |" % (len(m["seeds"]) or 0, " (single run: scores carry sampling noise)"
                                       if len(m["seeds"]) <= 1 else ""),
         ""]
    core_note = "" if m["core_complete"] else " (provisional: %s)" % (
        "some tests not run" if m["partial"] else "judging not finished")
    L += ["## Scores", "",
          "**Core score: %s / 100**%s" % (fmt(m["core"]), core_note), "",
          "| Category | Weight | Score | Tests scored |", "|---|---|---|---|"]
    for cat, label in suite["categories"].items():
        c = m["cats"][cat]
        w = suite["core_weights"].get(cat)
        L.append("| %s | %s | %s | %d of %d |" % (label, "%d%%" % w if w else "separate",
                                                  "n/a" if c["na"] else fmt(c["pct"]), c["scored"], c["tests"]))
    L += ["", "| Test | Scripted | Judged | Total | Ended | Time | Notes |", "|---|---|---|---|---|---|---|"]
    for r in m["rows"]:
        t = r["test"]
        if not r["seeds"]:
            L.append("| %s | - | - | - | - | - | not run |" % t["id"])
            continue
        for s in r["seeds"]:
            run = s["run"]
            notes = []
            if s["state"] in STATE_NOTE:
                notes.append(STATE_NOTE[s["state"]])
            flags = run.get("flags") or {}
            if flags.get("tampered"):
                notes.append("edited protected files")
            if (flags.get("swap_mb_after") or 0) - (flags.get("swap_mb_before") or 0) > 512:
                notes.append("swap grew; timings unreliable")
            if len(r["seeds"]) > 1:
                notes.append(s["seed"])
            smax = (run.get("scripted") or {}).get("max")
            jmax = sum(c["max"] for c in criteria_of(t))
            L.append("| %s | %s | %s | %s | %s | %s | %s |" % (
                t["id"], "-" if s["scripted"] is None else "%s / %s" % (fmt(s["scripted"], 2), fmt(smax, 2)),
                "-" if not jmax else ("pending / %s" % fmt(jmax, 2) if s["judged"] is None else
                                      "%s / %s" % (fmt(s["judged"], 2), fmt(jmax, 2))),
                "-" if s["total"] is None else "**%s**" % fmt(s["total"], 2), run.get("end_reason") or "-",
                "%ds" % (run.get("wall_s") or 0), "; ".join(notes)))
    L += ["", "## Speed and reliability", "",
          "Reported separately; none of this changes a score.", "",
          "| | |", "|---|---|",
          "| Generation speed (speed probe, median) | %s tokens/s |" % fmt(m["gen_tps"]),
          "| Time to first token (speed probe, median) | %s s |" % fmt(m["ttft_s"], 2),
          "| Prompt processing on the long log (L1) | %s tokens/s |" % fmt(m["prompt_tps_long"]),
          "| Median time per agentic test | %s min |" % fmt((m["agentic_time_s"] or 0) / 60.0 if m["agentic_time_s"] else None),
          "| Total time for all recorded runs | %s min |" % fmt(m["suite_wall_s"] / 60.0),
          "| Load time | %s s |" % fmt(meta.get("last_load_seconds")),
          "| Tool-call validity in agentic tests | %s |" % ("-" if m["tool_validity"] is None
                                                             else "%d%%" % round(m["tool_validity"] * 100)),
          ""]
    if m["stale"]:
        L += ["Runs ignored because their test changed afterwards: %s." % ", ".join(m["stale"]), ""]
    L += ["## Evidence per test", ""]
    for r in m["rows"]:
        t = r["test"]
        for s in r["seeds"]:
            if s["state"] == "na":
                continue
            L += ["### %s%s" % (t["id"], " (%s)" % s["seed"] if len(r["seeds"]) > 1 else ""), ""]
            detail = (s["check"] or {}).get("detail") or {}
            if detail:
                L.append("Scripted: " + "; ".join("`%s` %s/%s" % (k, fmt(d.get("points"), 3), fmt(d.get("max"), 3))
                                                  for k, d in detail.items()) + ".")
            v = s["verdict"]
            if v:
                L.append("")
                for c in criteria_of(t):
                    e = (v.get("criteria") or {}).get(c["id"]) or {}
                    line = "- `%s`: **%s** of %s. %s" % (c["id"], fmt(e.get("points"), 2), fmt(c["max"], 2),
                                                         squeeze(e.get("reason")))
                    if squeeze(e.get("quote")):
                        line += " Quote: \"%s\"" % squeeze(e.get("quote"))[:300].replace("|", "\\|")
                    L.append(line)
            elif criteria_of(t):
                L.append("")
                L.append("Judged criteria: pending.")
            L.append("")
    return "\n".join(L) + "\n"


def render_leaderboard(models, suite, when):
    rows = sorted(models.values(), key=lambda m: (m["core"] is None, -(m["core"] or 0)))
    cats = list(suite["core_weights"])
    L = ["# Leaderboard", "",
         "Generated by `bench.py score` on %s. Do not edit by hand." % when, "",
         "Suite `%s` v%s%s. Core = %s. Vision is reported separately so that Core means the same for every model." % (
             suite["suite"], suite["version"], "" if suite.get("frozen") else " (not frozen yet)",
             " + ".join("%d%% %s" % (suite["core_weights"][c], suite["categories"][c].lower()) for c in cats)), "",
         "| Model | Core | " + " | ".join(suite["categories"][c] for c in cats)
         + " | Vision | Tool calls valid | Tokens/s | Suite time | Runs |",
         "|---|---|" + "---|" * len(cats) + "---|---|---|---|---|"]
    for m in rows:
        core = fmt(m["core"])
        if not m["core_complete"] and m["core"] is not None:
            core += "*"
        spreads = [r["spread"] for r in m["rows"] if r["spread"] is not None]
        L.append("| `%s` | **%s** | %s | %s | %s | %s | %s min | %s |" % (
            m["slug"], core, " | ".join(fmt(m["cats"][c]["pct"]) for c in cats),
            "n/a" if m["vision_na"] else fmt(m["vision"]),
            "-" if m["tool_validity"] is None else "%d%%" % round(m["tool_validity"] * 100),
            fmt(m["gen_tps"]), fmt(m["suite_wall_s"] / 60.0, 0),
            "%d%s" % (len(m["seeds"]), "" if not spreads else ", spread up to %s" % fmt(max(spreads)))))
    notes = []
    if any(not m["core_complete"] and m["core"] is not None for m in rows):
        notes.append("`*` provisional: not every test has been run and judged for that model.")
    if any(len(m["seeds"]) <= 1 for m in rows):
        notes.append("Models with one run per test carry sampling noise of a few points; treat small gaps as ties. "
                     "MLX models do not honour the seed, so their runs are samples, not replays.")
    engines = {tuple((m["meta"].get("host") or {}).get("engines") or []) for m in rows}
    apps = {(m["meta"].get("host") or {}).get("lmstudio_app") for m in rows}
    if len(engines) > 1 or len(apps) > 1:
        notes.append("Rows were produced on different LM Studio or engine versions; compare with care.")
    judges = sorted({j for m in rows for j in m["judge_models"]})
    if judges:
        notes.append("Judged by: %s." % ", ".join(judges))
    stale = [m["slug"] for m in rows if m["stale"]]
    if stale:
        notes.append("Some runs were ignored because their test changed afterwards: %s." % ", ".join(stale))
    if notes:
        L += [""] + ["- " + n for n in notes]
    return "\n".join(L) + "\n"


README_START, README_END = "<!-- results:start -->", "<!-- results:end -->"


def render_readme_block(models, suite, when):
    """The results section of README.md: a ranking and a per-test table, for readers new to the project."""
    rows = sorted(models.values(), key=lambda m: (m["core"] is None, -(m["core"] or 0)))
    cats = list(suite["core_weights"])

    def link(m):
        return "[%s](models/%s/SCORECARD.md)" % (m["meta"].get("display_name") or m["slug"], m["slug"])

    def star(m):
        return "*" if not m["core_complete"] and m["core"] is not None else ""

    L = ["| # | Model | Build | Size | Reasoning | Core | " + " | ".join(suite["categories"][c].split()[0] for c in cats)
         + " | Vision | Tokens/s | Full suite |",
         "|---|---|---|---|---|---|" + "---|" * len(cats) + "---|---|---|"]
    for i, m in enumerate(rows, 1):
        meta = m["meta"]
        L.append("| %d | %s | %s %s | %.1f GB | %s | **%s%s** | %s | %s | %s | %s min |" % (
            i, link(m), str(meta.get("format") or "-").upper(), (meta.get("quantization") or {}).get("name") or "",
            (meta.get("size_bytes") or 0) / 1e9, meta.get("reasoning_level") or "-", fmt(m["core"]), star(m),
            " | ".join(fmt(m["cats"][c]["pct"]) for c in cats), "n/a" if m["vision_na"] else fmt(m["vision"]),
            fmt(m["gen_tps"]), fmt(m["suite_wall_s"] / 60.0, 0)))
    tests = [r["test"] for r in rows[0]["rows"]] if rows else []
    L += ["", "Points per test (each test is worth 10):", "",
          "| Model | " + " | ".join("`%s`" % t["id"].split("-")[0] for t in tests) + " |",
          "|---|" + "---|" * len(tests)]
    for m in rows:
        L.append("| %s%s | %s |" % (link(m), star(m), " | ".join(
            "n/a" if r["state"] == "na" else fmt(r["score"]) for r in m["rows"])))
    notes = []
    if any(star(m) for m in rows):
        notes.append("`*` Provisional: some tests are not run or not judged yet. Points that are still pending "
                     "count as zero, so a provisional score can only go up.")
    hosts = sorted({"%s with %s GB RAM, LM Studio %s" % (h.get("chip"), h.get("ram_gb"), h.get("lmstudio_app"))
                    for h in ((m["meta"].get("host") or {}) for m in rows) if h})
    notes.append("Updated %s. Suite v%s%s.%s One run per test unless a scorecard says otherwise, so gaps of a "
                 "few points are ties." % (when, suite["version"], "" if suite.get("frozen") else " (not frozen yet)",
                                           " Measured on %s." % "; ".join(hosts) if hosts else ""))
    return "\n".join(L + [""] + ["- " + n for n in notes]) + "\n"


def update_readme(root, block):
    """Replace the generated block between the markers in README.md. No markers, no change."""
    path = Path(root) / "README.md"
    text = read_text(path)
    a, b = text.find(README_START), text.find(README_END)
    if a < 0 or b < a:
        return
    new = text[:a + len(README_START)] + "\n" + block + text[b:]
    if new != text:
        path.write_text(new, encoding="utf-8")


def write_reports(root, models_dir, tests, suite, when):
    models = collect(models_dir, tests, suite)
    update_readme(root, render_readme_block(models, suite, when))
    for slug, m in models.items():
        (Path(models_dir) / slug / "SCORECARD.md").write_text(render_scorecard(m, suite))
        write_json(Path(models_dir) / slug / "scores.json", {
            "slug": slug, "suite_version": suite["version"], "generated": when,
            "core": m["core"], "core_complete": m["core_complete"],
            "categories": {c: m["cats"][c]["pct"] for c in m["cats"]}, "vision_na": m["vision_na"],
            "tests": {r["test"]["id"]: {"score": r["score"], "state": r["state"], "spread": r["spread"]} for r in m["rows"]},
            "tool_call_validity": m["tool_validity"], "gen_tps": m["gen_tps"], "suite_wall_s": m["suite_wall_s"],
        })
    (Path(root) / "LEADERBOARD.md").write_text(render_leaderboard(models, suite, when))
    return models
