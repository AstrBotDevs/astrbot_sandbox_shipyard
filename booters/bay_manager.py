from __future__ import annotations

import asyncio
from typing import Any

import aiodocker
import aiohttp

from astrbot.api import logger

BAY_IMAGE = "soulter/shipyard-bay:latest"
DEFAULT_SHIP_IMAGE = "soulter/shipyard-ship:latest"
DEFAULT_SHIP_NETWORK = "shipyard"
BAY_CONTAINER_NAME = "shipyard"
BAY_LABEL = "astrbot.shipyard.managed"
BAY_PORT = 8156
HEALTH_TIMEOUT_S = 60
HEALTH_POLL_INTERVAL_S = 2


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
    ) -> None:
        self._endpoint_url = endpoint_url.rstrip("/")
        self._access_token = access_token
        self._image = image
        self._ship_image = ship_image
        self._docker_network = docker_network.strip()
        self._host_port = host_port
        self._docker: aiodocker.Docker | None = None
        self._container: Any = None

    async def ensure_running(self) -> str:
        await self._open_docker()
        await self._ensure_docker_network()
        await self._pull_required_images()

        existing = await self._find_managed_container()
        if existing is not None:
            self._container = await self._docker.containers.get(existing["Id"])
            if not self._container_env_matches(existing):
                logger.info("[Shipyard] Recreating Bay container because configuration changed")
                await self._container.delete(force=True)
                existing = None

        if existing is not None:
            if not existing.get("State", {}).get("Running"):
                logger.info("[Shipyard] Starting existing Bay container")
                await self._container.start()
            await self.wait_healthy()
            return self._endpoint_url

        if self._docker_network:
            self._endpoint_url = f"http://shipyard:{BAY_PORT}"
        else:
            self._endpoint_url = f"http://127.0.0.1:{self._host_port}"

        logger.info(
            "[Shipyard] Starting Bay container: image=%s network=%s",
            self._image,
            self._docker_network or "host-port",
        )
        config = {
            "Image": self._image,
            "Labels": {BAY_LABEL: "true"},
            "Env": self._container_env(),
            "ExposedPorts": {f"{BAY_PORT}/tcp": {}},
            "HostConfig": self._host_config(),
        }
        self._container = await self._docker.containers.create_or_replace(
            BAY_CONTAINER_NAME,
            config,
        )
        await self._container.start()
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

    async def _ensure_docker_network(self) -> None:
        network_name = self._docker_network or DEFAULT_SHIP_NETWORK
        assert self._docker is not None
        try:
            networks = await self._docker.networks.list()
        except Exception as exc:
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
            await self._docker.networks.create({"Name": network_name, "Driver": "bridge"})
            logger.info("[Shipyard] Created Docker network: %s", network_name)
        except Exception as exc:
            logger.warning("[Shipyard] Failed to create Docker network %s: %s", network_name, exc)

    async def wait_healthy(self, timeout: int = HEALTH_TIMEOUT_S) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        last_error = ""
        async with aiohttp.ClientSession() as session:
            while loop.time() < deadline:
                try:
                    async with session.get(
                        f"{self._endpoint_url}/health",
                        timeout=aiohttp.ClientTimeout(total=3),
                    ) as resp:
                        if resp.status == 200:
                            return
                        last_error = f"HTTP {resp.status}"
                except Exception as exc:
                    last_error = str(exc)
                await asyncio.sleep(HEALTH_POLL_INTERVAL_S)
        raise TimeoutError(
            f"Shipyard Bay did not become healthy within {timeout}s (last error: {last_error})"
        )

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
        ]
        if self._docker_network:
            env.append(f"DOCKER_NETWORK={self._docker_network}")
        return env

    def _host_config(self) -> dict[str, Any]:
        config: dict[str, Any] = {
            "Binds": [
                "astrbot_shipyard_bay_data:/app/data",
                "/var/run/docker.sock:/var/run/docker.sock:ro",
            ],
            "RestartPolicy": {"Name": "unless-stopped"},
        }
        if self._docker_network:
            config["NetworkMode"] = self._docker_network
        else:
            config["PortBindings"] = {
                f"{BAY_PORT}/tcp": [{"HostPort": str(self._host_port)}]
            }
        return config

    def _container_env_matches(
        self,
        container_info: dict[str, Any],
    ) -> bool:
        existing = self._env_map(container_info.get("Config", {}).get("Env") or [])
        desired = self._env_map(self._container_env())
        if not self._docker_network:
            return (
                existing.get("DOCKER_NETWORK") is None
                and all(existing.get(key) == value for key, value in desired.items())
            )
        return (
            existing.get("DOCKER_NETWORK") == self._docker_network
            and all(existing.get(key) == value for key, value in desired.items())
        )

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
