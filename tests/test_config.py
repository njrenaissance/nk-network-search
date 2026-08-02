import pydantic
import pytest

from nkmodel.config import DEFAULTS, NKConfig, get_config


@pytest.fixture(autouse=True)
def _clear_config_cache():
    """get_config() is lru_cache-wrapped; clear it around every test so env-var
    tests in this module don't leak a cached instance into one another."""
    get_config.cache_clear()
    yield
    get_config.cache_clear()


@pytest.mark.unit
def test_defaults_populate_every_field():
    config = NKConfig()

    for field, value in DEFAULTS.items():
        assert getattr(config, field) == value


@pytest.mark.unit
def test_get_config_returns_cached_singleton():
    assert get_config() is get_config()


@pytest.mark.unit
@pytest.mark.parametrize(
    "invalid_k",
    [
        pytest.param("not-a-number", id="non_numeric_string"),
        pytest.param(None, id="none"),
    ],
)
def test_invalid_k_raises(invalid_k):
    with pytest.raises(pydantic.ValidationError):
        NKConfig(K=invalid_k)


@pytest.mark.unit
def test_invalid_scheme_raises():
    with pytest.raises(pydantic.ValidationError):
        NKConfig(scheme="bogus")


@pytest.mark.unit
def test_invalid_topology_raises():
    with pytest.raises(pydantic.ValidationError):
        NKConfig(topology="bogus")


@pytest.mark.unit
def test_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("NK_SEED", "7")

    assert get_config().seed == 7


@pytest.mark.unit
def test_real_env_var_takes_precedence_over_dotenv(tmp_path, monkeypatch):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("NK_SEED=3\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NK_SEED", "7")

    assert NKConfig().seed == 7
