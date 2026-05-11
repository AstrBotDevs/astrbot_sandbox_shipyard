from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from astrbot.api import logger
from astrbot.core.computer.booters.base import ComputerBooter
from astrbot.core.star.context import Context

from .booters.bay_manager import (
    BAY_IMAGE,
    DEFAULT_SHIP_IMAGE,
    ShipyardBayContainerManager,
)
from .booters.shipyard import ShipyardBooter

BootHook = Callable[[Context, str, str, dict], Awaitable[ComputerBooter]]
DEFAULT_SHIPYARD_ENDPOINT = "http://shipyard:8156"


def _resolve_shipyard_endpoint(config: Mapping[str, Any]) -> str:
    endpoint = str(config.get("shipyard_endpoint") or "").strip()
    return endpoint or DEFAULT_SHIPYARD_ENDPOINT


class ShipyardSandboxProvider:
    provider_id = "shipyard"
    capabilities = {"shell", "python", "filesystem"}
    tool_names: set[str] = set()

    def __init__(
        self,
        boot_hook: BootHook | None = None,
        *,
        plugin_config: Mapping[str, Any] | None = None,
    ) -> None:
        self.plugin_config: dict[str, Any] = (
            dict(plugin_config) if plugin_config is not None else {}
        )
        self._boot_hook = boot_hook

    def _merged_sandbox_config(self, context: Context, session_id: str) -> dict:
        """Return sandbox config with plugin_config as base and user settings overriding."""
        config = context.get_config(umo=session_id)
        merged = dict(self.plugin_config)
        sandbox_cfg = config.get("provider_settings", {}).get("sandbox", {})
        if isinstance(sandbox_cfg, dict):
            merged.update(sandbox_cfg)
        else:
            logger.warning(
                "[Computer] Expected dict for provider_settings.sandbox, got %s. Ignoring.",
                type(sandbox_cfg).__name__,
            )
        return merged

    def build_create_config(self, context: Context, session_id: str) -> dict:
        merged = self._merged_sandbox_config(context, session_id)
        endpoint_url = _resolve_shipyard_endpoint(merged)
        docker_network = str(merged.get("shipyard_docker_network") or "").strip()
        auto_start_bay = bool(merged.get("shipyard_auto_start", True)) and endpoint_url in {
            DEFAULT_SHIPYARD_ENDPOINT,
            "http://127.0.0.1:8156",
            "http://localhost:8156",
        }
        access_token = str(merged.get("shipyard_access_token", "") or "").strip()
        return {
            "endpoint_url": endpoint_url,
            "access_token": access_token or ("secret-token" if auto_start_bay else ""),
            "ttl": merged.get("shipyard_ttl", 3600),
            "session_num": merged.get("shipyard_max_sessions", 10),
            "auto_start_bay": auto_start_bay,
            "docker_network": docker_network,
            "bay_image": str(merged.get("shipyard_bay_image") or BAY_IMAGE),
            "ship_image": str(merged.get("shipyard_ship_image") or DEFAULT_SHIP_IMAGE),
        }

    def build_connect_info(self, sandbox_name: str, config: dict) -> dict:
        return {"name": sandbox_name, "endpoint_url": config.get("endpoint_url")}

    def update_connect_info(self, record: dict, *, sandbox_name: str) -> dict:
        connect_info = dict(record.get("connect_info") or {})
        connect_info["name"] = sandbox_name
        return connect_info

    def get_idle_timeout(self, context: Context, session_id: str) -> float:
        return 0.0

    async def create_booter(
        self, context: Context, session_id: str, sandbox_id: str, config: dict
    ) -> ComputerBooter:
        if self._boot_hook is not None:
            return await self._boot_hook(context, session_id, sandbox_id, config)
        endpoint_url = str(config.get("endpoint_url") or "").strip()
        access_token = str(config.get("access_token") or "").strip()
        if config.get("auto_start_bay"):
            bay_manager = ShipyardBayContainerManager(
                endpoint_url=endpoint_url,
                access_token=access_token,
                image=str(config.get("bay_image") or BAY_IMAGE),
                ship_image=str(config.get("ship_image") or DEFAULT_SHIP_IMAGE),
                docker_network=str(config.get("docker_network") or "").strip(),
            )
            endpoint_url = await bay_manager.ensure_running()
            await bay_manager.close_client()
        client = ShipyardBooter(
            endpoint_url=endpoint_url,
            access_token=access_token,
            ttl=int(config.get("ttl", 3600)),
            session_num=int(config.get("session_num", 10)),
        )
        await client.boot(uuid.uuid5(uuid.NAMESPACE_DNS, session_id).hex)
        return client

    async def destroy_booter(self, booter: ComputerBooter, record: dict) -> None:
        destroy = getattr(booter, "destroy", None)
        if callable(destroy):
            await destroy()
            return
        await booter.shutdown()
