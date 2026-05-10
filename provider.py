from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from astrbot.api import logger
from astrbot.core.computer.booters.base import ComputerBooter
from astrbot.core.star.context import Context

from .booters.shipyard import ShipyardBooter

BootHook = Callable[[Context, str, str, dict], Awaitable[ComputerBooter]]
DEFAULT_SHIPYARD_ENDPOINT = "http://127.0.0.1:8114"


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
        return {
            "endpoint_url": _resolve_shipyard_endpoint(merged),
            "access_token": merged.get("shipyard_access_token", ""),
            "ttl": merged.get("shipyard_ttl", 3600),
            "session_num": merged.get("shipyard_max_sessions", 10),
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
        client = ShipyardBooter(**config)
        await client.boot(uuid.uuid5(uuid.NAMESPACE_DNS, session_id).hex)
        return client

    async def destroy_booter(self, booter: ComputerBooter, record: dict) -> None:
        await booter.shutdown()
