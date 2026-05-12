from __future__ import annotations

import asyncio
import os
from enum import Enum
from typing import Any

import aiodocker
import aiohttp

from astrbot.api import logger

from .value_utils import coerce_bool

BAY_IMAGE = "soulter/shipyard-bay:latest"
DEFAULT_SHIP_IMAGE = "soulter/shipyard-ship:latest"
DEFAULT_SHIP_NETWORK = "shipyard"
BAY_CONTAINER_NAME = "shipyard"
BAY_LABEL = "astrbot.shipyard.managed"
BAY_PORT = 8156
DEFAULT_BAY_DATA_VOLUME_PREFIX = "astrbot_shipyard"
HEALTH_TIMEOUT_S = 60
HEALTH_POLL_INTERVAL_S = 2
BIND_DOCKER_SOCK_ENV = "ASTRBOT_BIND_DOCKER_SOCK"


class _BayMode(str, Enum):
    NETWORK = "network"
    HOST_PORT = "host-port"


def _env_flag(name: str, *, default: bool = False) -> bool:
    return coerce_bool(os.getenv(name), default=default)


class ShipyardBayContainerManager:
    def __init__(
        self,
        *,
        endpoint_url: str,
        access_token: str,
        image: str = BAY_IMAGE,
        ship_image: str = DEFAULT_SHIP_IMAGE,
        docker_network: str = "",
        host_port: int = BAY_PORT,
        bay_data_volume_name: str | None = None,
    ) -> None:
        self._endpoint_url = endpoint_url.rstrip("/")
        self._access_token = access_token
        self._image = image
        self._ship_image = ship_image
        self._docker_network = docker_network.strip()
        self._host_port = host_port
        self._bay_data_volume_name = (
            bay_data_volume_name
            or f"{DEFAULT_BAY_DATA_VOLUME_PREFIX}_{BAY_CONTAINER_NAME}_data"
        )
        self._docker: aiodocker.Docker | None = None
        self._container: Any = None

    async def ensure_running(self) -> str:
        await self._open_docker()
        await self._ensure_docker_network()
        await self._pull_required_images()

        desired_env = self._container_env()
        existing = await self._find_managed_container()
        self._container, reused_existing = await self._prepare_container(
            existing, desired_env
        )
        self._endpoint_url = self._effective_endpoint()
        await self._ensure_container_started(existing, reused_existing)
        await self.wait_healthy()
        return self._endpoint_url

    async def _open_docker(self) -> None:
        try:
            self._docker = aiodocker.Docker()
        except Exception as exc:
            raise RuntimeError(
                "Failed to connect to Docker daemon. Mount /var/run/docker.sock "
                "or configure an explicit Shipyard endpoint."
            ) from exc

    def _effective_network(self) -> str:
        return self._docker_network or DEFAULT_SHIP_NETWORK

    def _mode(self) -> _BayMode:
        return _BayMode.NETWORK if self._docker_network else _BayMode.HOST_PORT

    def _effective_endpoint(self) -> str:
        if self._mode() is _BayMode.NETWORK:
            return f"http://shipyard:{BAY_PORT}"
        return f"http://127.0.0.1:{self._host_port}"

    def _health_check_context(self) -> tuple[str, str]:
        health_url = f"{self._endpoint_url}/health"
        return health_url, self._mode().value

    async def _ensure_docker_network(self) -> None:
        network_name = self._effective_network()
        assert self._docker is not None
        try:
            networks = await self._docker.networks.list()
        except Exception as exc:
            if self._docker_network:
                raise RuntimeError(
                    f"Failed to list configured Docker network {network_name}"
                ) from exc
            logger.warning("[Shipyard] Failed to list Docker networks: %s", exc)
            return
        for network in networks:
            try:
                info = await network.show()
            except Exception:
                continue
            if info.get("Name") == network_name:
                return
        try:
            await self._docker.networks.create(
                {"Name": network_name, "Driver": "bridge"}
            )
            logger.info("[Shipyard] Created Docker network: %s", network_name)
        except Exception as exc:
            if self._docker_network:
                raise RuntimeError(
                    f"Failed to create configured Docker network {network_name}"
                ) from exc
            logger.warning(
                "[Shipyard] Failed to create Docker network %s: %s", network_name, exc
            )

    async def wait_healthy(self, timeout: int = HEALTH_TIMEOUT_S) -> None:
        health_url, mode = self._health_check_context()
        last_error = await self._poll_health(health_url, timeout)
        if last_error is None:
            return
        raise TimeoutError(
            f"Shipyard Bay did not become healthy within {timeout}s (last error: {last_error} for {health_url} (mode={mode}))"
        )

    async def _poll_health(self, health_url: str, timeout: int) -> str | None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        last_error = "no response received"
        async with aiohttp.ClientSession() as session:
            while loop.time() < deadline:
                try:
                    async with session.get(
                        health_url, timeout=aiohttp.ClientTimeout(total=3)
                    ) as resp:
                        if resp.status == 200:
                            return None
                        last_error = f"HTTP {resp.status}"
                except Exception as exc:
                    last_error = f"error querying: {exc!r}"
                await asyncio.sleep(HEALTH_POLL_INTERVAL_S)
        return last_error

    async def close_client(self) -> None:
        if self._docker is not None:
            await self._docker.close()
            self._docker = None

    def _container_env(self) -> list[str]:
        env = [
            f"PORT={BAY_PORT}",
            "DATABASE_URL=sqlite+aiosqlite:///./data/bay.db",
            f"ACCESS_TOKEN={self._access_token}",
            "MAX_SHIP_NUM=10",
            "BEHAVIOR_AFTER_MAX_SHIP=reject",
            f"DOCKER_IMAGE={self._ship_image}",
            "SHIP_DATA_DIR=/tmp/astrbot_shipyard/ship_mnt_data",
            "DEFAULT_SHIP_CPUS=1.0",
            "DEFAULT_SHIP_MEMORY=512m",
            f"DOCKER_NETWORK={self._effective_network()}",
        ]
        return env

    def _host_config(self) -> dict[str, Any]:
        binds: list[str] = [f"{self._bay_data_volume_name}:/app/data"]
        if _env_flag(BIND_DOCKER_SOCK_ENV, default=True):
            binds.append("/var/run/docker.sock:/var/run/docker.sock")
        config: dict[str, Any] = {
            "Binds": binds,
            "RestartPolicy": {"Name": "unless-stopped"},
        }
        if self._mode() is _BayMode.NETWORK:
            config["NetworkMode"] = self._effective_network()
        else:
            config["PortBindings"] = {
                f"{BAY_PORT}/tcp": [{"HostPort": str(self._host_port)}]
            }
        return config

    async def _prepare_container(
        self,
        existing_info: dict[str, Any] | None,
        desired_env: list[str],
    ) -> tuple[Any, bool]:
        assert self._docker is not None
        if existing_info is not None:
            container = await self._docker.containers.get(existing_info["Id"])
            if self._container_config_matches(existing_info, desired_env):
                return container, True
            logger.info(
                "[Shipyard] Recreating Bay container because configuration changed"
            )
            await container.delete(force=True)

        logger.info(
            "[Shipyard] Starting Bay container: image=%s network=%s",
            self._image,
            self._effective_network()
            if self._mode() is _BayMode.NETWORK
            else "host-port",
        )
        config = {
            "Image": self._image,
            "Labels": {BAY_LABEL: "true"},
            "Env": desired_env,
            "ExposedPorts": {f"{BAY_PORT}/tcp": {}},
            "HostConfig": self._host_config(),
        }
        return await self._docker.containers.create_or_replace(
            BAY_CONTAINER_NAME, config
        ), False

    async def _ensure_container_started(
        self,
        existing_info: dict[str, Any] | None,
        reused_existing: bool,
    ) -> None:
        if not reused_existing:
            await self._container.start()
            return
        if existing_info.get("State", {}).get("Running"):
            return
        logger.info("[Shipyard] Starting existing Bay container")
        await self._container.start()

    def _container_config_matches(
        self,
        container_info: dict[str, Any],
        desired_env: list[str],
    ) -> bool:
        if not self._container_env_matches(container_info, desired_env):
            return False
        host_config = container_info.get("HostConfig", {})
        if self._mode() == _BayMode.NETWORK:
            return host_config.get("NetworkMode") == self._effective_network()
        expected_bindings = {f"{BAY_PORT}/tcp": [{"HostPort": str(self._host_port)}]}
        return host_config.get("PortBindings") == expected_bindings

    def _container_env_matches(
        self,
        container_info: dict[str, Any],
        desired_env: list[str],
    ) -> bool:
        existing = self._env_map(container_info.get("Config", {}).get("Env") or [])
        desired = self._env_map(desired_env)
        return all(existing.get(key) == value for key, value in desired.items())

    @staticmethod
    def _env_map(items: list[str]) -> dict[str, str]:
        env: dict[str, str] = {}
        for item in items:
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            env[key] = value
        return env

    async def _find_managed_container(self) -> dict[str, Any] | None:
        assert self._docker is not None
        containers = await self._docker.containers.list(all=True)
        for container in containers:
            info = await container.show()
            labels = info.get("Config", {}).get("Labels") or {}
            names = info.get("Names") or []
            if labels.get(BAY_LABEL) == "true" or f"/{BAY_CONTAINER_NAME}" in names:
                return info
        return None

    async def _pull_required_images(self) -> None:
        await self._pull_image_if_needed(self._image, "Bay")
        await self._pull_image_if_needed(self._ship_image, "Ship")

    async def _pull_image_if_needed(self, image: str, label: str) -> None:
        assert self._docker is not None
        try:
            await self._docker.images.inspect(image)
        except Exception:
            logger.info("[Shipyard] Pulling %s image: %s", label, image)
            await self._docker.images.pull(image)
