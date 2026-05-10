from types import SimpleNamespace

from data.plugins.astrbot_sandbox_shipyard.provider import ShipyardSandboxProvider


def test_shipyard_provider_defaults_to_local_endpoint_when_unconfigured():
    provider = ShipyardSandboxProvider()
    context = SimpleNamespace(
        get_config=lambda umo: {"provider_settings": {"sandbox": {}}}
    )

    config = provider.build_create_config(context, "dashboard")

    assert config["endpoint_url"] == "http://127.0.0.1:8114"
