from types import SimpleNamespace

import pytest

from data.plugins.astrbot_sandbox_shipyard import main as plugin_main
from data.plugins.astrbot_sandbox_shipyard import provider as shipyard_provider
from data.plugins.astrbot_sandbox_shipyard.booters import shipyard as shipyard_booter
from data.plugins.astrbot_sandbox_shipyard.booters.bay_manager import (
    BAY_CONTAINER_NAME,
    BAY_PORT,
    ShipyardBayContainerManager,
)
from data.plugins.astrbot_sandbox_shipyard.booters.shipyard import (
    ShipyardShellWrapper,
)
from data.plugins.astrbot_sandbox_shipyard.provider import (
    DEFAULT_SHIPYARD_ENDPOINT,
    ShipyardSandboxProvider,
)


def _make_fake_bay_containers(calls):
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
            calls.append(("create", name, config["HostConfig"]))
            return FakeContainer()

    return FakeContainers()


def test_shipyard_provider_defaults_to_local_endpoint_when_unconfigured():
    provider = ShipyardSandboxProvider()
    context = SimpleNamespace(
        get_config=lambda umo: {"provider_settings": {"sandbox": {}}}
    )

    config = provider.build_create_config(context, "dashboard")

    assert config["endpoint_url"] == DEFAULT_SHIPYARD_ENDPOINT


def test_shipyard_provider_defaults_match_documented_local_endpoint():
    assert DEFAULT_SHIPYARD_ENDPOINT == "http://127.0.0.1:8156"


def test_shipyard_provider_enables_auto_start_for_default_endpoint():
    provider = ShipyardSandboxProvider()
    context = SimpleNamespace(
        get_config=lambda umo: {"provider_settings": {"sandbox": {}}}
    )

    config = provider.build_create_config(context, "dashboard")

    assert config["auto_start_bay"] is True
    assert config["access_token"]
    assert config["access_token"] != "secret-token"
    assert config["bay_image"] == "soulter/shipyard-bay:latest"
    assert config["ship_image"] == "soulter/shipyard-ship:latest"
    assert config["docker_network"] == ""


def test_shipyard_provider_auto_starts_with_saved_local_endpoint_without_flag():
    provider = ShipyardSandboxProvider(
        plugin_config={
            "shipyard_endpoint": "http://127.0.0.1:8156",
            "shipyard_access_token": "buding123",
            "shipyard_ttl": 3600,
            "shipyard_max_sessions": 10,
        }
    )
    context = SimpleNamespace(
        get_config=lambda umo: {"provider_settings": {"sandbox": {}}}
    )

    config = provider.build_create_config(context, "dashboard")

    assert config["endpoint_url"] == "http://127.0.0.1:8156"
    assert config["access_token"] == "buding123"
    assert config["auto_start_bay"] is True


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
    assert config["endpoint_url"] == "http://127.0.0.1:8156"


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


def test_shipyard_provider_warns_when_auto_start_endpoint_is_unsupported(monkeypatch):
    warnings = []

    def fake_warning(*args, **kwargs):
        warnings.append((args, kwargs))

    monkeypatch.setattr(shipyard_provider.logger, "warning", fake_warning)
    provider = ShipyardSandboxProvider()
    context = SimpleNamespace(
        get_config=lambda umo: {
            "provider_settings": {
                "sandbox": {
                    "shipyard_endpoint": "http://example.com:8156",
                    "shipyard_auto_start": "true",
                }
            }
        }
    )

    config = provider.build_create_config(context, "dashboard")

    assert config["auto_start_bay"] is False
    assert warnings


def test_shipyard_provider_normalizes_local_endpoint_for_auto_start():
    provider = ShipyardSandboxProvider()
    context = SimpleNamespace(
        get_config=lambda umo: {
            "provider_settings": {
                "sandbox": {"shipyard_endpoint": " http://localhost:8156/ "}
            }
        }
    )

    config = provider.build_create_config(context, "dashboard")

    assert config["endpoint_url"] == "http://localhost:8156"
    assert config["auto_start_bay"] is True


def test_shipyard_provider_preserves_endpoint_path_when_normalizing():
    provider = ShipyardSandboxProvider()
    context = SimpleNamespace(
        get_config=lambda umo: {
            "provider_settings": {
                "sandbox": {"shipyard_endpoint": "http://localhost:8156/api?token=1"}
            }
        }
    )

    config = provider.build_create_config(context, "dashboard")

    assert config["endpoint_url"] == "http://localhost:8156/api?token=1"


def test_shipyard_provider_warns_on_malformed_endpoint(monkeypatch):
    warnings = []

    def fake_warning(*args, **kwargs):
        warnings.append((args, kwargs))

    monkeypatch.setattr(shipyard_provider.logger, "warning", fake_warning)
    provider = ShipyardSandboxProvider()
    context = SimpleNamespace(
        get_config=lambda umo: {
            "provider_settings": {
                "sandbox": {"shipyard_endpoint": "http://localhost:notaport"}
            }
        }
    )

    config = provider.build_create_config(context, "dashboard")

    assert config["endpoint_url"] == DEFAULT_SHIPYARD_ENDPOINT
    assert config["auto_start_bay"] is True
    assert warnings


def test_shipyard_provider_warns_on_endpoint_missing_scheme(monkeypatch):
    warnings = []

    def fake_warning(*args, **kwargs):
        warnings.append((args, kwargs))

    monkeypatch.setattr(shipyard_provider.logger, "warning", fake_warning)
    provider = ShipyardSandboxProvider()
    context = SimpleNamespace(
        get_config=lambda umo: {
            "provider_settings": {"sandbox": {"shipyard_endpoint": "shipyard:8156"}}
        }
    )

    config = provider.build_create_config(context, "dashboard")

    assert config["endpoint_url"] == DEFAULT_SHIPYARD_ENDPOINT
    assert config["auto_start_bay"] is True
    assert warnings


def test_shipyard_provider_warns_on_endpoint_missing_host(monkeypatch):
    warnings = []

    def fake_warning(*args, **kwargs):
        warnings.append((args, kwargs))

    monkeypatch.setattr(shipyard_provider.logger, "warning", fake_warning)
    provider = ShipyardSandboxProvider()
    context = SimpleNamespace(
        get_config=lambda umo: {
            "provider_settings": {"sandbox": {"shipyard_endpoint": "http:///"}}
        }
    )

    config = provider.build_create_config(context, "dashboard")

    assert config["endpoint_url"] == DEFAULT_SHIPYARD_ENDPOINT
    assert config["auto_start_bay"] is True
    assert warnings


def test_shipyard_provider_disables_auto_start_for_false_string():
    provider = ShipyardSandboxProvider()
    context = SimpleNamespace(
        get_config=lambda umo: {
            "provider_settings": {"sandbox": {"shipyard_auto_start": "false"}}
        }
    )

    config = provider.build_create_config(context, "dashboard")

    assert config["auto_start_bay"] is False


def test_shipyard_provider_disables_auto_start_for_unknown_string():
    provider = ShipyardSandboxProvider()
    context = SimpleNamespace(
        get_config=lambda umo: {
            "provider_settings": {"sandbox": {"shipyard_auto_start": "maybe"}}
        }
    )

    config = provider.build_create_config(context, "dashboard")

    assert config["auto_start_bay"] is False


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

    manager = ShipyardBayContainerManager(
        endpoint_url="http://shipyard:8156",
        access_token="token",
    )
    manager._docker = SimpleNamespace(
        images=FakeImages(), containers=_make_fake_bay_containers(calls)
    )

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


def test_shipyard_bay_manager_uses_default_ship_network_for_local_host_port():
    manager = ShipyardBayContainerManager(
        endpoint_url="http://127.0.0.1:8156",
        access_token="token",
    )

    env = manager._container_env()

    assert "DOCKER_NETWORK=shipyard" in env


@pytest.mark.asyncio
async def test_shipyard_bay_manager_health_timeout_includes_endpoint_and_mode(
    monkeypatch,
):
    class FakeLoop:
        def __init__(self):
            self.now = 0.0

        def time(self):
            self.now += 0.6
            return self.now

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def get(self, url, timeout):
            del url, timeout
            raise ConnectionError("connection refused")

    async def fake_sleep(delay):
        del delay

    monkeypatch.setattr(
        "data.plugins.astrbot_sandbox_shipyard.booters.bay_manager.asyncio.get_running_loop",
        lambda: FakeLoop(),
    )
    monkeypatch.setattr(
        "data.plugins.astrbot_sandbox_shipyard.booters.bay_manager.asyncio.sleep",
        fake_sleep,
    )
    monkeypatch.setattr(
        "data.plugins.astrbot_sandbox_shipyard.booters.bay_manager.aiohttp.ClientSession",
        lambda: FakeSession(),
    )
    manager = ShipyardBayContainerManager(
        endpoint_url="http://127.0.0.1:8156",
        access_token="token",
    )

    with pytest.raises(TimeoutError) as exc_info:
        await manager.wait_healthy(timeout=1)

    message = str(exc_info.value)
    assert "http://127.0.0.1:8156/health" in message
    assert "mode=host-port" in message


def test_shipyard_bay_manager_mounts_docker_socket_by_default():
    manager = ShipyardBayContainerManager(
        endpoint_url="http://127.0.0.1:8156",
        access_token="token",
    )

    binds = manager._host_config()["Binds"]

    assert "/var/run/docker.sock:/var/run/docker.sock" in binds
    assert any(BAY_CONTAINER_NAME in bind for bind in binds)


def test_shipyard_bay_manager_can_disable_docker_socket_when_opted_out(monkeypatch):
    monkeypatch.setenv("ASTRBOT_BIND_DOCKER_SOCK", "false")
    manager = ShipyardBayContainerManager(
        endpoint_url="http://127.0.0.1:8156",
        access_token="token",
    )

    binds = manager._host_config()["Binds"]

    assert "/var/run/docker.sock:/var/run/docker.sock" not in binds


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
async def test_shipyard_bay_manager_raises_when_configured_network_list_fails():
    class FakeNetworks:
        async def list(self):
            raise RuntimeError("list failed")

    manager = ShipyardBayContainerManager(
        endpoint_url="http://shipyard:8156",
        access_token="token",
        docker_network="astrbot_network",
    )
    manager._docker = SimpleNamespace(networks=FakeNetworks())

    with pytest.raises(RuntimeError, match="Failed to list configured Docker network"):
        await manager._ensure_docker_network()


@pytest.mark.asyncio
async def test_shipyard_bay_manager_raises_when_configured_network_create_fails():
    class FakeNetworks:
        async def list(self):
            return []

        async def create(self, config):
            del config
            raise RuntimeError("create failed")

    manager = ShipyardBayContainerManager(
        endpoint_url="http://shipyard:8156",
        access_token="token",
        docker_network="astrbot_network",
    )
    manager._docker = SimpleNamespace(networks=FakeNetworks())

    with pytest.raises(
        RuntimeError, match="Failed to create configured Docker network"
    ):
        await manager._ensure_docker_network()


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
    assert "DOCKER_NETWORK=shipyard" in create_call[2]
    assert ("healthy", "http://127.0.0.1:8156") in calls


@pytest.mark.asyncio
async def test_shipyard_bay_manager_recreates_container_when_host_port_is_stale(
    monkeypatch,
):
    calls = []
    manager = ShipyardBayContainerManager(
        endpoint_url="http://127.0.0.1:8156",
        access_token="token",
    )

    manager._docker = SimpleNamespace(containers=_make_fake_bay_containers(calls))

    async def fake_open_docker():
        calls.append(("open_docker", None))

    async def fake_pull_images():
        calls.append(("pull", None))

    async def fake_find_container():
        calls.append(("find", None))
        return {
            "Id": "existing",
            "State": {"Running": True},
            "Config": {"Env": manager._container_env()},
            "HostConfig": {"PortBindings": {"8156/tcp": [{"HostPort": "18156"}]}},
        }

    async def fake_wait_healthy():
        calls.append(("healthy", manager._endpoint_url))

    monkeypatch.setattr(manager, "_open_docker", fake_open_docker)
    monkeypatch.setattr(manager, "_pull_required_images", fake_pull_images)
    monkeypatch.setattr(manager, "_find_managed_container", fake_find_container)
    monkeypatch.setattr(manager, "wait_healthy", fake_wait_healthy)

    await manager.ensure_running()

    assert ("delete", True) in calls
    assert ("start", None) in calls
    create_call = next(call for call in calls if call[0] == "create")
    assert create_call[2]["PortBindings"] == {
        f"{BAY_PORT}/tcp": [{"HostPort": str(BAY_PORT)}]
    }
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
async def test_shipyard_booter_rejects_reuse_after_failed_boot(monkeypatch):
    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def create_ship(self, **kwargs):
            raise RuntimeError("create failed")

        async def close(self):
            pass

    monkeypatch.setattr(shipyard_booter, "ShipyardClient", FakeClient)

    booter = shipyard_booter.ShipyardBooter(
        endpoint_url="http://shipyard:8156",
        access_token="token",
    )

    with pytest.raises(RuntimeError, match="create failed"):
        await booter.boot("session-a")
    with pytest.raises(RuntimeError, match="failed to boot"):
        await booter.boot("session-a")


@pytest.mark.asyncio
async def test_shipyard_booter_destroy_deletes_ship(monkeypatch):
    calls = []
    captured = {}

    class FakeResponse:
        status = 200

        async def text(self):
            return ""

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def delete(self, url):
            calls.append(("delete", url))
            return FakeResponse()

    class FakeClientSession:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeClient:
        def __init__(self, **kwargs):
            self.endpoint_url = kwargs["endpoint_url"].rstrip("/")
            self.access_token = kwargs["access_token"]

        async def create_ship(self, **kwargs):
            del kwargs
            return SimpleNamespace(id="ship-123", shell=None, fs=None, python=None)

        async def close(self):
            calls.append(("close", None))

    monkeypatch.setattr(shipyard_booter, "ShipyardClient", FakeClient)
    monkeypatch.setattr(shipyard_booter.aiohttp, "ClientSession", FakeClientSession)

    booter = shipyard_booter.ShipyardBooter(
        endpoint_url="http://shipyard:8156/",
        access_token="token",
    )
    await booter.boot("session-a")

    await booter.destroy()

    assert calls == [
        ("delete", "http://shipyard:8156/ship/ship-123"),
        ("close", None),
    ]
    assert "timeout" in captured


@pytest.mark.asyncio
async def test_shipyard_booter_shutdown_only_closes_client(monkeypatch):
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
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        def delete(self, url):
            calls.append(("delete", url))
            return FakeResponse()

    class FakeClientSession:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, exc_type, exc, tb):
            return None

    class FakeClient:
        def __init__(self, **kwargs):
            self.endpoint_url = kwargs["endpoint_url"].rstrip("/")
            self.access_token = kwargs["access_token"]

        async def create_ship(self, **kwargs):
            del kwargs
            return SimpleNamespace(id="ship-123", shell=None, fs=None, python=None)

        async def close(self):
            calls.append(("close", None))

    monkeypatch.setattr(shipyard_booter, "ShipyardClient", FakeClient)
    monkeypatch.setattr(shipyard_booter.aiohttp, "ClientSession", FakeClientSession)

    booter = shipyard_booter.ShipyardBooter(
        endpoint_url="http://shipyard:8156/",
        access_token="token",
    )
    await booter.boot("session-a")

    await booter.shutdown()

    assert calls == [("close", None)]


@pytest.mark.asyncio
async def test_shipyard_provider_destroy_booter_uses_destroy_only():
    calls = []

    class FakeBooter:
        async def destroy(self):
            calls.append("destroy")

        async def shutdown(self):
            calls.append("shutdown")

    provider = ShipyardSandboxProvider()

    await provider.destroy_booter(FakeBooter(), {})

    assert calls == ["destroy"]


@pytest.mark.asyncio
async def test_shipyard_provider_closes_bay_client_when_auto_start_fails(monkeypatch):
    closed = False

    class FakeBayManager:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def ensure_running(self):
            raise RuntimeError("docker unavailable")

        async def close_client(self):
            nonlocal closed
            closed = True

    monkeypatch.setattr(
        "data.plugins.astrbot_sandbox_shipyard.provider.ShipyardBayContainerManager",
        FakeBayManager,
    )

    provider = ShipyardSandboxProvider()
    context = SimpleNamespace(
        get_config=lambda umo: {"provider_settings": {"sandbox": {}}}
    )
    config = provider.build_create_config(context, "session-a")

    with pytest.raises(RuntimeError, match="docker unavailable"):
        await provider.create_booter(context, "session-a", "shipyard-1", config)

    assert closed is True


@pytest.mark.asyncio
async def test_shipyard_shell_wrapper_extracts_stdout_from_object_result():
    class FakeShell:
        async def exec(self, *args, **kwargs):
            del args, kwargs
            return SimpleNamespace(
                stdout="shipyard-ok",
                stderr="",
                exit_code=0,
                success=True,
                execution_id="exec-123",
                execution_time_ms=42,
                command="echo shipyard-ok",
            )

    wrapper = ShipyardShellWrapper(FakeShell())

    result = await wrapper.exec("echo shipyard-ok")

    assert result["stdout"] == "shipyard-ok"
    assert result["stderr"] == ""
    assert result["exit_code"] == 0
    assert result["success"] is True
    assert result["execution_id"] == "exec-123"


def test_shipyard_normalize_shell_result_preserves_input_dict():
    original = {
        "success": True,
        "data": {
            "stdout": "Hello Shipyard\n",
            "stderr": "",
            "return_code": 0,
            "pid": 122,
        },
    }

    payload = shipyard_booter._normalize_shell_result(original)

    assert original == {
        "success": True,
        "data": {
            "stdout": "Hello Shipyard\n",
            "stderr": "",
            "return_code": 0,
            "pid": 122,
        },
    }
    assert payload["stdout"] == "Hello Shipyard\n"
    assert payload["stderr"] == ""
    assert payload["exit_code"] == 0
    assert payload["success"] is True


@pytest.mark.asyncio
async def test_shipyard_shell_wrapper_falls_back_when_dict_method_fails():
    class FakeShellResult:
        stdout = "shipyard-ok"
        stderr = ""
        exit_code = 0

        def dict(self):
            raise RuntimeError("broken dict")

    class FakeShell:
        async def exec(self, *args, **kwargs):
            del args, kwargs
            return FakeShellResult()

    wrapper = ShipyardShellWrapper(FakeShell())

    result = await wrapper.exec("echo shipyard-ok")

    assert result["stdout"] == "shipyard-ok"
    assert result["stderr"] == ""
    assert result["exit_code"] == 0


@pytest.mark.asyncio
async def test_shipyard_shell_wrapper_extracts_stdout_from_nested_data_result():
    class FakeShell:
        async def exec(self, *args, **kwargs):
            del args, kwargs
            return {
                "success": True,
                "data": {
                    "stdout": "Hello Shipyard\n",
                    "stderr": "",
                    "return_code": 0,
                    "pid": 122,
                },
            }

    wrapper = ShipyardShellWrapper(FakeShell())

    result = await wrapper.exec('echo "Hello Shipyard"')

    assert result["stdout"] == "Hello Shipyard\n"
    assert result["stderr"] == ""
    assert result["exit_code"] == 0
    assert result["success"] is True
