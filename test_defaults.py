from types import SimpleNamespace

import pytest

from data.plugins.astrbot_sandbox_shipyard import main as plugin_main
from data.plugins.astrbot_sandbox_shipyard.provider import (
    DEFAULT_SHIPYARD_ENDPOINT,
    ShipyardSandboxProvider,
)


def test_shipyard_provider_defaults_to_local_endpoint_when_unconfigured():
    provider = ShipyardSandboxProvider()
    context = SimpleNamespace(
        get_config=lambda umo: {"provider_settings": {"sandbox": {}}}
    )

    config = provider.build_create_config(context, "dashboard")

    assert config["endpoint_url"] == DEFAULT_SHIPYARD_ENDPOINT


def test_shipyard_provider_strips_endpoint_before_defaulting():
    provider = ShipyardSandboxProvider()
    context = SimpleNamespace(
        get_config=lambda umo: {
            "provider_settings": {"sandbox": {"shipyard_endpoint": "  "}}
        }
    )

    config = provider.build_create_config(context, "dashboard")

    assert config["endpoint_url"] == DEFAULT_SHIPYARD_ENDPOINT


@pytest.mark.asyncio
async def test_shipyard_terminate_detaches_even_if_cleanup_fails(monkeypatch):
    calls = []

    class FakeProvider:
        provider_id = "shipyard"

    async def fake_cleanup(provider_id):
        calls.append(("cleanup", provider_id))
        raise RuntimeError("cleanup failed")

    def fake_detach(provider_id):
        calls.append(("detach", provider_id))

    monkeypatch.setattr(plugin_main, "cleanup_sandbox_provider", fake_cleanup)
    monkeypatch.setattr(plugin_main, "detach_sandbox_provider", fake_detach)

    plugin = plugin_main.ShipyardSandboxRuntimePlugin.__new__(
        plugin_main.ShipyardSandboxRuntimePlugin
    )
    plugin.provider = FakeProvider()

    with pytest.raises(RuntimeError, match="cleanup failed"):
        await plugin.terminate()

    assert calls == [("cleanup", "shipyard"), ("detach", "shipyard")]
