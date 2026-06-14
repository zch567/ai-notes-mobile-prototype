import pytest

from app.provider_config import ProviderConfig, create_provider
from app.providers import ProviderChunk
from app.providers import model_provider


def test_provider_config_loads_lanxin_without_exposing_key(tmp_path, monkeypatch):
    secrets = tmp_path / "api"
    secrets.write_text(
        "MODEL_PROVIDER=lanxin\n"
        "LANXIN_API_KEY=secret-value\n"
        "LANXIN_BASE_URL=https://example.test/v1\n"
        "LANXIN_MODEL=test-model\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("BACKEND_SECRETS_FILE", str(secrets))
    monkeypatch.delenv("LANXIN_API_KEY", raising=False)
    config = ProviderConfig.load()

    assert config.lanxin_api_key == "secret-value"
    assert config.status()["lanxin"]["configured"] is True
    assert "secret-value" not in str(config.status())


def test_explicit_lanxin_requires_credentials(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKEND_SECRETS_FILE", str(tmp_path / "missing"))
    monkeypatch.delenv("LANXIN_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="Lanxin is not configured"):
        create_provider("lanxin")


def test_explicit_lanxin_builds_provider(tmp_path, monkeypatch):
    secrets = tmp_path / "api"
    secrets.write_text("LANXIN_API_KEY=secret\nLANXIN_MODEL=blue-test\n", encoding="utf-8")
    monkeypatch.setenv("BACKEND_SECRETS_FILE", str(secrets))
    monkeypatch.delenv("LANXIN_API_KEY", raising=False)

    provider = create_provider("lanxin")

    assert provider.name == "lanxin"
    assert provider.model == "blue-test"
    assert provider.timeout_seconds == 90
    assert provider.retries == 1


def test_lanxin_provider_retries_transient_failure(monkeypatch):
    calls = []

    def fake_post_json(url, body, api_key, timeout_seconds=None):
        calls.append(timeout_seconds)
        if len(calls) == 1:
            raise RuntimeError("transient")
        return {"choices": [{"message": {"content": '{"topic":"RAG","summary":"ok"}'}}]}

    monkeypatch.setattr(model_provider, "post_json", fake_post_json)
    monkeypatch.setattr(model_provider.time, "sleep", lambda _seconds: None)
    provider = model_provider.OpenAICompatibleProvider(
        name="lanxin",
        base_url="https://example.test/v1",
        api_key="secret",
        model="blue-test",
        timeout_seconds=90,
        retries=1,
    )
    chunk = ProviderChunk(
        id="s1",
        sourceId="source",
        title="source",
        text="RAG 使用检索结果约束生成。",
        sourceType="text",
        fileName="source.md",
    )

    _result, log = provider.generate_json([chunk])

    assert calls == [90, 90]
    assert log.status == "success"
    assert log.fallbackUsed is False
