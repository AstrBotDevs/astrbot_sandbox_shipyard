from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from astrbot.core.computer.booters.base import ComputerBooter
from astrbot.core.star.context import Context

from .booters.shipyard import ShipyardBooter

BootHook = Callable[[Context, str, str, dict], Awaitable[ComputerBooter]]


class ShipyardSandboxProvider:
    provider_id = "shipyard"
    capabilities = {"shell", "python", "filesystem"}
    tool_names: set[str] = set()

    def __init__(self, boot_hook: BootHook | None = None) -> None:
        self._boot_hook = boot_hook

    def build_create_config(self, context: Context, session_id: str) -> dict:
        config = context.get_config(umo=session_id)
        sandbox_cfg = config.get("provider_settings", {}).get("sandbox", {})
        plugin_cfg = getattr(self, "plugin_config", None) or {}
        return {
            "endpoint_url": sandbox_cfg.get(
                "shipyard_endpoint", plugin_cfg.get("shipyard_endpoint", "")
            ),
            "access_token": sandbox_cfg.get(
                "shipyard_access_token", plugin_cfg.get("shipyard_access_token", "")
            ),
            "ttl": sandbox_cfg.get(
                "shipyard_ttl", plugin_cfg.get("shipyard_ttl", 3600)
            ),
            "session_num": sandbox_cfg.get(
                "shipyard_max_sessions", plugin_cfg.get("shipyard_max_sessions", 10)
            ),
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
        await client.sync_skills_to_sandbox()
        return client

    async def destroy_booter(self, booter: ComputerBooter, record: dict) -> None:
        await booter.shutdown()
