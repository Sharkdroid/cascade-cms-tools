import pytest
from cascade_cms_rest_mcp.config import load_environment_variables, log_directory


def test_load_environment_variables_defaults_server(monkeypatch):
    monkeypatch.setenv("CASCADE_API_KEY", "key123")
    monkeypatch.setenv("CASCADE_URL", "https://cascade.example.com")
    monkeypatch.delenv("SERVER", raising=False)

    env_vars = load_environment_variables()

    assert env_vars == {
        "API_KEY": "key123",
        "CASCADE_URL": "https://cascade.example.com",
        "SERVER": "default",
    }


def test_load_environment_variables_respects_explicit_server(monkeypatch):
    monkeypatch.setenv("CASCADE_API_KEY", "key123")
    monkeypatch.setenv("CASCADE_URL", "https://cascade.example.com")
    monkeypatch.setenv("SERVER", "PROD")

    env_vars = load_environment_variables()

    assert env_vars["SERVER"] == "PROD"


@pytest.mark.parametrize(
    "missing",
    ["CASCADE_API_KEY", "CASCADE_URL"],
)
def test_load_environment_variables_missing_var_raises_system_exit(
    monkeypatch, missing
):
    monkeypatch.setenv("CASCADE_API_KEY", "key123")
    monkeypatch.setenv("CASCADE_URL", "https://cascade.example.com")
    monkeypatch.delenv(missing, raising=False)

    with pytest.raises(SystemExit) as exc_info:
        load_environment_variables()

    assert missing in str(exc_info.value)


def test_load_environment_variables_missing_both_names_both(monkeypatch):
    monkeypatch.delenv("CASCADE_API_KEY", raising=False)
    monkeypatch.delenv("CASCADE_URL", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        load_environment_variables()

    message = str(exc_info.value)
    assert "CASCADE_API_KEY" in message
    assert "CASCADE_URL" in message


def test_log_directory_default(monkeypatch):
    monkeypatch.delenv("CASCADE_MCP_LOG_DIR", raising=False)

    assert log_directory().parts[-4:] == (
        ".local", "state", "cascade-cms-mcp", "logs",
    )


def test_log_directory_respects_override(monkeypatch, tmp_path):
    monkeypatch.setenv("CASCADE_MCP_LOG_DIR", str(tmp_path / "x"))

    assert log_directory() == tmp_path / "x"
