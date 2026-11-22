"""Layered configuration.

Layers, lowest precedence first:

1. tessera.config.defaults.DEFAULTS
2. the YAML file (--config, else $TESSERA_CONFIG, else /etc/tessera/tessera.yaml)
3. environment variables listed in tessera.config.env.OVERRIDES
4. command-line flags (see tessera.cli)

Mappings from the YAML file are merged key by key into the defaults; every
other value replaces the one below it. Environment variables and flags each
set a single key. After merging, durations become float seconds and sizes
become int bytes.
"""
import copy
import os

from tessera.config import env
from tessera.config.defaults import DEFAULTS
from tessera.util import parse_duration, parse_size

DEFAULT_PATH = "/etc/tessera/tessera.yaml"

DURATION_KEYS = frozenset([
    "api.idempotency_ttl", "api.request_timeout", "jobs.max_runtime",
    "retry.base_delay", "retry.max_delay", "worker.poll_interval", "worker.lease_ttl",
    "leader.lease_ttl", "leader.renew_every", "storage.statement_timeout",
])
SIZE_KEYS = frozenset(["api.max_body_bytes", "jobs.max_payload_bytes"])
INT_KEYS = frozenset(["api.port", "worker.concurrency", "retry.max_attempts", "storage.pool_size"])
FLOAT_KEYS = frozenset(["retry.multiplier"])
LIST_KEYS = frozenset(["worker.queues"])
CHOICES = {
    "jobs.payload_overflow": ("reject", "spill"),
    "logging.format": ("text", "json"),
}

# Keys renamed since 0.9. The old spellings are still accepted in YAML files.
RENAMED = {
    "storage.dsn": "storage.url",
    "jobs.max_payload": "jobs.max_payload_bytes",
    "retry.factor": "retry.multiplier",
    "retry.cap": "retry.max_delay",
}

POLICY_FIELDS = ("max_attempts", "base_delay", "multiplier", "max_delay")


class ConfigError(Exception):
    pass


class Config:
    """Read-only attribute view over the merged configuration tree."""

    def __init__(self, data, path=""):
        object.__setattr__(self, "_data", data)
        object.__setattr__(self, "_path", path)

    def __getattr__(self, name):
        try:
            value = self._data[name]
        except KeyError:
            raise AttributeError("no config key %s%s" % (self._path, name)) from None
        if isinstance(value, dict):
            return Config(value, "%s%s." % (self._path, name))
        return value

    def __setattr__(self, name, value):
        raise AttributeError("configuration is read-only")

    def __getitem__(self, name):
        return self._data[name]

    def get(self, name, default=None):
        return self._data.get(name, default)

    def as_dict(self):
        return copy.deepcopy(self._data)


def load_config(path=None, environ=None, cli=None):
    """Build the effective configuration. `cli` maps dotted keys to flag values."""
    environ = os.environ if environ is None else environ
    data = copy.deepcopy(DEFAULTS)
    path = path or environ.get(env.CONFIG_FILE) or DEFAULT_PATH
    if os.path.exists(path):
        _merge(data, _rename_legacy(_read_yaml(path)), "")
    elif path != DEFAULT_PATH:
        raise ConfigError("config file not found: %s" % path)
    for key, value in env.overrides(environ).items():
        _set(data, key, value)
    for key, value in (cli or {}).items():
        if value is not None:
            _set(data, key, value)
    return Config(_coerce(data))


def _read_yaml(path):
    import yaml

    with open(path, encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    if not isinstance(loaded, dict):
        raise ConfigError("%s: the top level must be a mapping" % path)
    return loaded


def _rename_legacy(tree):
    tree = copy.deepcopy(tree)
    for old, new in RENAMED.items():
        section, old_key = old.split(".")
        new_key = new.split(".")[1]
        block = tree.get(section)
        if isinstance(block, dict) and old_key in block:
            block.setdefault(new_key, block.pop(old_key))
    policies = (tree.get("retry") or {}).get("policies") or {}
    for policy in policies.values():
        if not isinstance(policy, dict):
            continue
        for old, new in RENAMED.items():
            section, old_key = old.split(".")
            if section == "retry" and old_key in policy:
                policy.setdefault(new.split(".")[1], policy.pop(old_key))
    return tree


def _merge(base, over, prefix):
    for key, value in over.items():
        if prefix == "" and key not in base:
            raise ConfigError("unknown config section: %s" % key)
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _merge(base[key], value, prefix + key + ".")
        else:
            base[key] = copy.deepcopy(value)


def _set(data, dotted, value):
    section, key = dotted.split(".", 1)
    if section not in data:
        raise ConfigError("unknown config section: %s" % section)
    data[section][key] = value


def _coerce(data):
    for keys, fn in ((DURATION_KEYS, parse_duration), (SIZE_KEYS, parse_size), (INT_KEYS, int),
                     (FLOAT_KEYS, float), (LIST_KEYS, _as_list)):
        for dotted in keys:
            _apply(data, dotted, fn)
    for dotted, allowed in CHOICES.items():
        section, key = dotted.split(".")
        if data[section][key] not in allowed:
            raise ConfigError("%s must be one of: %s" % (dotted, ", ".join(allowed)))
    for name, policy in data["retry"]["policies"].items():
        unknown = sorted(set(policy) - set(POLICY_FIELDS))
        if unknown:
            raise ConfigError("retry.policies.%s: unknown keys %s" % (name, ", ".join(unknown)))
        for field in ("base_delay", "max_delay"):
            if field in policy:
                policy[field] = parse_duration(policy[field])
        if "multiplier" in policy:
            policy["multiplier"] = float(policy["multiplier"])
        if "max_attempts" in policy:
            policy["max_attempts"] = int(policy["max_attempts"])
    return data


def _apply(data, dotted, fn):
    section, key = dotted.split(".")
    try:
        data[section][key] = fn(data[section][key])
    except (TypeError, ValueError) as exc:
        raise ConfigError("%s: %s" % (dotted, exc)) from None


def _as_list(value):
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return list(value)
