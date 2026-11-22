"""Small helpers with no dependencies on the rest of tessera: ids, durations, sizes."""
import os
import re
import time

_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"
_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|s|m|h|d)")
_DURATION_UNITS = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}
_SIZE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([kmg]i?b|b)?\s*$", re.I)
_SIZE_UNITS = {"b": 1, "kb": 1000, "mb": 1000 ** 2, "gb": 1000 ** 3,
               "kib": 1024, "mib": 1024 ** 2, "gib": 1024 ** 3}


def new_id(prefix):
    """Sortable id: a millisecond timestamp followed by 60 random bits, base32."""
    ms = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(8), "big") >> 4
    return "%s_%s%s" % (prefix, _b32(ms, 9), _b32(rand, 12))


def _b32(n, width):
    out = []
    for _ in range(width):
        n, r = divmod(n, 32)
        out.append(_ALPHABET[r])
    return "".join(reversed(out))


def parse_duration(value):
    """Seconds as a float. Bare numbers are seconds; strings may chain units ("1h30m")."""
    if isinstance(value, bool):
        raise ValueError("not a duration: %r" % (value,))
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower().replace(" ", "")
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)
    pos, total = 0, 0.0
    for m in _DURATION_PART.finditer(text):
        if m.start() != pos:
            break
        total += float(m.group(1)) * _DURATION_UNITS[m.group(2)]
        pos = m.end()
    if pos == 0 or pos != len(text):
        raise ValueError("not a duration: %r" % (value,))
    return total


def parse_size(value):
    """Bytes as an int. Accepts decimal (kB, MB, GB) and binary (KiB, MiB, GiB) units."""
    if isinstance(value, bool):
        raise ValueError("not a size: %r" % (value,))
    if isinstance(value, int):
        return value
    m = _SIZE.match(str(value))
    if not m:
        raise ValueError("not a size: %r" % (value,))
    return int(float(m.group(1)) * _SIZE_UNITS[(m.group(2) or "b").lower()])
