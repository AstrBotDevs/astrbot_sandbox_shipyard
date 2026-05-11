from types import SimpleNamespace

import pytest

from data.plugins.astrbot_sandbox_shipyard import main as plugin_main
from data.plugins.astrbot_sandbox_shipyard.booters import shipyard as shipyard_booter
from data.plugins.astrbot_sandbox_shipyard.booters.bay_manager import (
    ShipyardBayContainerManager,
)
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


def test_shipyard_provider_defaults_match_documented_legacy_endpoint():
    assert DEFAULT_SHIPYARD_ENDPOINT == "http://shipyard:8156"


def test_shipyard_provider_enables_auto_start_for_default_endpoint():
    provider = ShipyardSandboxProvider()
    context = SimpleNamespace(
        get_config=lambda umo: {"provider_settings": {"sandbox": {}}}
    )

    config = provider.build_create_config(context, "dashboard")

    assert config["auto_start_bay"] is True
    assert config["bay_image"] == "soulter/shipyard-bay:latest"
    assert config["ship_image"] == "soulter/shipyard-ship:latest"
    assert config["docker_network"] == ""


def test_shipyard_provider_uses_docker_network_when_configured():
    provider = ShipyardSandboxProvider()
    context = SimpleNamespace(
        get_config=lambda umo: {
            "provider_settings": {
                "sandbox": {
                    "shipyard_docker_network": "astrbot_network",
                }
            }
        }
    )

    config = provider.build_create_config(context, "dashboard")

    assert config["auto_start_bay"] is True
    assert config["docker_network"] == "astrbot_network"
    assert config["endpoint_url"] == "http://shipyard:8156"


def test_shipyard_provider_does_not_auto_start_for_explicit_external_endpoint():
    provider = ShipyardSandboxProvider()
    context = SimpleNamespace(
        get_config=lambda umo: {
            "provider_settings": {
                "sandbox": {"shipyard_endpoint": "http://example.com:8156"}
            }
        }
    )

    config = provider.build_create_config(context, "dashboard")

    assert config["endpoint_url"] == "http://example.com:8156"
    assert config["auto_start_bay"] is False
    assert config["docker_network"] == ""


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


@pytest.mark.asyncio
async def test_shipyard_bay_manager_pulls_bay_and_ship_images():
    calls = []

    class FakeImages:
        async def inspect(self, image):
            calls.append(("inspect", image))
            raise RuntimeError("missing")

        async def pull(self, image):
            calls.append(("pull", image))

    manager = ShipyardBayContainerManager(
        endpoint_url="http://shipyard:8156",
        access_token="token",
    )
    manager._docker = SimpleNamespace(images=FakeImages())

    await manager._pull_required_images()

    assert calls == [
        ("inspect", "soulter/shipyard-bay:latest"),
        ("pull", "soulter/shipyard-bay:latest"),
        ("inspect", "soulter/shipyard-ship:latest"),
        ("pull", "soulter/shipyard-ship:latest"),
    ]


@pytest.mark.asyncio
async def test_shipyard_bay_manager_pulls_ship_image_when_reusing_existing_container(
    monkeypatch,
):
    calls = []

    class FakeImages:
        async def inspect(self, image):
            calls.append(("inspect", image))
            if image == "soulter/shipyard-ship:latest":
                raise RuntimeError("missing")

        async def pull(self, image):
            calls.append(("pull", image))

    class FakeContainers:
        async def get(self, container_id):
            calls.append(("get", container_id))
            class FakeContainer:
                async def delete(self, force=False):
                    calls.append(("delete", force))

                async def start(self):
                    calls.append(("start", None))

            return FakeContainer()

    manager = ShipyardBayContainerManager(
        endpoint_url="http://shipyard:8156",
        access_token="token",
    )
    manager._docker = SimpleNamespace(images=FakeImages(), containers=FakeContainers())

    async def fake_open_docker():
        calls.append(("open_docker", None))

    async def fake_find_container():
        calls.append(("find", None))
        return {
            "Id": "existing",
            "State": {"Running": True},
            "Config": {"Env": manager._container_env()},
        }

    async def fake_wait_healthy():
        calls.append(("healthy", None))

    monkeypatch.setattr(manager, "_open_docker", fake_open_docker)
    monkeypatch.setattr(manager, "_find_managed_container", fake_find_container)
    monkeypatch.setattr(manager, "wait_healthy", fake_wait_healthy)

    await manager.ensure_running()

    assert ("pull", "soulter/shipyard-ship:latest") in calls
    assert calls.index(("pull", "soulter/shipyard-ship:latest")) < calls.index(
        ("find", None)
    )


def test_shipyard_bay_manager_omits_docker_network_for_local_host_port():
    manager = ShipyardBayContainerManager(
        endpoint_url="http://127.0.0.1:8156",
        access_token="token",
    )

    env = manager._container_env()

    assert "DOCKER_NETWORK=shipyard" not in env
    assert not any(item.startswith("DOCKER_NETWORK=") for item in env)


def test_shipyard_bay_manager_uses_configured_docker_network():
    manager = ShipyardBayContainerManager(
        endpoint_url="http://shipyard:8156",
        access_token="token",
        docker_network="astrbot_network",
    )

    env = manager._container_env()
    host_config = manager._host_config()

    assert "DOCKER_NETWORK=astrbot_network" in env
    assert host_config["NetworkMode"] == "astrbot_network"
    assert "PortBindings" not in host_config


@pytest.mark.asyncio
async def test_shipyard_bay_manager_creates_configured_docker_network_when_missing():
    calls = []

    class FakeNetworks:
        async def list(self):
            calls.append(("list", None))
            return []

        async def create(self, config):
            calls.append(("create_network", config["Name"]))

    manager = ShipyardBayContainerManager(
        endpoint_url="http://shipyard:8156",
        access_token="token",
        docker_network="shipyard",
    )
    manager._docker = SimpleNamespace(networks=FakeNetworks())

    await manager._ensure_docker_network()

    assert calls == [("list", None), ("create_network", "shipyard")]


@pytest.mark.asyncio
async def test_shipyard_bay_manager_creates_default_ship_network_for_host_mode():
    calls = []

    class FakeNetworks:
        async def list(self):
            calls.append(("list", None))
            return []

        async def create(self, config):
            calls.append(("create_network", config["Name"]))

    manager = ShipyardBayContainerManager(
        endpoint_url="http://127.0.0.1:8156",
        access_token="token",
    )
    manager._docker = SimpleNamespace(networks=FakeNetworks())

    await manager._ensure_docker_network()

    assert calls == [("list", None), ("create_network", "shipyard")]


@pytest.mark.asyncio
async def test_shipyard_bay_manager_recreates_container_when_network_env_is_stale(
    monkeypatch,
):
    calls = []

    class FakeContainer:
        async def delete(self, force=False):
            calls.append(("delete", force))

        async def start(self):
            calls.append(("start", None))

    class FakeContainers:
        async def get(self, container_id):
            calls.append(("get", container_id))
            return FakeContainer()

        async def create_or_replace(self, name, config):
            calls.append(("create", name, config["Env"]))
            return FakeContainer()

    manager = ShipyardBayContainerManager(
        endpoint_url="http://shipyard:8156",
        access_token="token",
    )
    manager._docker = SimpleNamespace(containers=FakeContainers())

    async def fake_open_docker():
        calls.append(("open_docker", None))

    async def fake_pull_images():
        calls.append(("pull", None))

    async def fake_find_container():
        calls.append(("find", None))
        return {
            "Id": "existing",
            "State": {"Running": True},
            "Config": {"Env": ["DOCKER_NETWORK=shipyard"]},
        }

    async def fake_wait_healthy():
        calls.append(("healthy", manager._endpoint_url))

    monkeypatch.setattr(manager, "_open_docker", fake_open_docker)
    monkeypatch.setattr(manager, "_pull_required_images", fake_pull_images)
    monkeypatch.setattr(manager, "_find_managed_container", fake_find_container)
    monkeypatch.setattr(manager, "wait_healthy", fake_wait_healthy)

    await manager.ensure_running()

    assert ("delete", True) in calls
    create_call = next(call for call in calls if call[0] == "create")
    assert not any(item.startswith("DOCKER_NETWORK=") for item in create_call[2])
    assert ("healthy", "http://127.0.0.1:8156") in calls


@pytest.mark.asyncio
async def test_shipyard_booter_closes_client_when_create_ship_fails(monkeypatch):
    closed = False

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def create_ship(self, **kwargs):
            raise RuntimeError("create failed")

        async def close(self):
            nonlocal closed
            closed = True

    monkeypatch.setattr(shipyard_booter, "ShipyardClient", FakeClient)

    booter = shipyard_booter.ShipyardBooter(
        endpoint_url="http://shipyard:8156",
        access_token="token",
    )

    with pytest.raises(RuntimeError, match="create failed"):
        await booter.boot("session-a")

    assert closed is True


@pytest.mark.asyncio
async def test_shipyard_booter_destroy_deletes_ship_before_closing_client(monkeypatch):
    calls = []

    class FakeResponse:
        status = 200

        async def text(self):
            return ""

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeSession:
        def delete(self, url):
            calls.append(("delete", url))
            return FakeResponse()

    class FakeClient:
        def __init__(self, **kwargs):
            self.endpoint_url = kwargs["endpoint_url"].rstrip("/")

        async def create_ship(self, **kwargs):
            del kwargs
            return SimpleNamespace(id="ship-123", shell=None, fs=None, python=None)

        async def _get_session(self):
            calls.append(("session", None))
            return FakeSession()

        async def close(self):
            calls.append(("close", None))

    monkeypatch.setattr(shipyard_booter, "ShipyardClient", FakeClient)

    booter = shipyard_booter.ShipyardBooter(
        endpoint_url="http://shipyard:8156/",
        access_token="token",
    )
    await booter.boot("session-a")

    await booter.destroy()

    assert calls == [
        ("session", None),
        ("delete", "http://shipyard:8156/ship/ship-123"),
        ("close", None),
    ]


@pytest.mark.asyncio
async def test_shipyard_provider_destroy_booter_prefers_destroy():
    calls = []

    class FakeBooter:
        async def destroy(self):
            calls.append("destroy")

        async def shutdown(self):
            calls.append("shutdown")

    provider = ShipyardSandboxProvider()

    await provider.destroy_booter(FakeBooter(), {})

    assert calls == ["destroy"]
