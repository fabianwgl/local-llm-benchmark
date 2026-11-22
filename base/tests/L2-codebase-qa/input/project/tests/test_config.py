import pytest

from tessera.config import ConfigError, load_config, loader
from tessera.scheduler.backoff import compute_delay
from tessera.scheduler.retry import RetryPolicy


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    def make(tree):
        path = tmp_path / "tessera.yaml"
        path.write_text("# replaced by the fixture\n")
        monkeypatch.setattr(loader, "_read_yaml", lambda _: tree)
        return str(path)

    return make


def test_env_overrides_yaml(config_file):
    cfg = load_config(config_file({"retry": {"max_delay": "2m"}}), environ={"TESSERA_RETRY_MAX_DELAY": "45"})
    assert cfg.retry.max_delay == 45.0


def test_flag_overrides_env(config_file):
    cfg = load_config(config_file({}), environ={"TESSERA_API_PORT": "9000"}, cli={"api.port": 9100})
    assert cfg.api.port == 9100


def test_legacy_key_is_renamed(config_file):
    assert load_config(config_file({"retry": {"cap": "90s"}}), environ={}).retry.max_delay == 90.0


def test_unknown_section_is_rejected(config_file):
    with pytest.raises(ConfigError):
        load_config(config_file({"workers": {"concurrency": 2}}), environ={})


def test_policy_inherits_unset_fields(config_file):
    cfg = load_config(config_file({"retry": {"max_attempts": 4, "policies": {"thumb": {"base_delay": "3s"}}}}),
                      environ={})
    assert RetryPolicy.resolve(cfg.retry, "thumb") == RetryPolicy(4, 3.0, 2.0, 300.0)


def test_compute_delay_is_capped():
    assert [compute_delay(1, 2, 10, n) for n in range(1, 7)] == [1, 2, 4, 8, 10, 10]


def test_attempt_numbers_start_at_one():
    with pytest.raises(ValueError):
        compute_delay(1, 2, 10, 0)
