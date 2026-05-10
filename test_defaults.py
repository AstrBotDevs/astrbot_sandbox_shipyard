from types import SimpleNamespace

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
