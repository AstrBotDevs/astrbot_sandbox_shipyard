from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Mapping
from secrets import token_urlsafe
from typing import Any
from urllib.parse import urlparse, urlunparse

from astrbot.api import logger
from astrbot.core.computer.booters.base import ComputerBooter
from astrbot.core.computer.sandbox_timeouts import resolve_sandbox_timeout
from astrbot.core.star.context import Context

from .booters.bay_manager import (
    BAY_IMAGE,
    DEFAULT_SHIP_IMAGE,
    ShipyardBayContainerManager,
)
from .booters.shipyard import ShipyardBooter
from .booters.value_utils import coerce_bool

BootHook = Callable[[Context, str, str, dict], Awaitable[ComputerBooter]]
DEFAULT_SHIPYARD_ENDPOINT = "http://127.0.0.1:8156"
_AUTO_START_ENDPOINTS = {
    # Shipyard service-name endpoints are for Docker network mode;
    # localhost is the host-port default path.
    ("http", "shipyard", 8156),
    ("http", "127.0.0.1", 8156),
    ("http", "localhost", 8156),
}


def _normalize_shipyard_endpoint(endpoint: str) -> tuple[str, bool]:
    raw = (endpoint or "").strip() or DEFAULT_SHIPYARD_ENDPOINT
    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.hostname:
        logger.warning("[Shipyard] Invalid endpoint ignored: %s", raw)
        return DEFAULT_SHIPYARD_ENDPOINT, True
    try:
        port = parsed.port
    except ValueError:
        logger.warning("[Shipyard] Invalid endpoint ignored: %s", raw)
        return DEFAULT_SHIPYARD_ENDPOINT, True
    netloc = parsed.hostname
    if port is not None:
        netloc = f"{netloc}:{port}"
    path = "" if parsed.path == "/" else parsed.path.rstrip("/")
    normalized = urlunparse(
        (
            parsed.scheme.lower(),
            netloc,
            path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )
    supports_auto_start = (
        parsed.scheme.lower(),
        parsed.hostname.lower(),
        port,
    ) in _AUTO_START_ENDPOINTS
    return normalized, supports_auto_start


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
        self._auto_start_access_token = token_urlsafe(32)

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
        endpoint_url, supports_auto_start = _normalize_shipyard_endpoint(
            str(merged.get("shipyard_endpoint") or "")
        )
        docker_network = str(merged.get("shipyard_docker_network") or "").strip()
        auto_start_raw = merged.get("shipyard_auto_start", None)
        auto_start_requested = (
            True
            if auto_start_raw is None
            else coerce_bool(auto_start_raw, default=False)
        )
        auto_start_bay = auto_start_requested and supports_auto_start
        if auto_start_requested and not supports_auto_start:
            logger.warning(
                "[Shipyard] Auto-start requested via shipyard_auto_start=%r but endpoint %r does not support auto-start; disabling auto-start.",
                auto_start_raw,
                endpoint_url,
            )
        access_token = str(merged.get("shipyard_access_token", "") or "").strip()
        return {
            "endpoint_url": endpoint_url,
            "access_token": access_token
            or (self._auto_start_access_token if auto_start_bay else ""),
            "ttl": resolve_sandbox_timeout(
                merged,
                "sandbox_ttl",
                aliases=("shipyard_ttl",),
                default=3600,
            ),
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
        merged = self._merged_sandbox_config(context, session_id)
        return resolve_sandbox_timeout(
            merged,
            "sandbox_idle_timeout",
            aliases=("shipyard_idle_timeout",),
            default=0.0,
        )

    async def create_booter(
        self, context: Context, session_id: str, sandbox_id: str, config: dict
    ) -> ComputerBooter:
        if self._boot_hook is not None:
            return await self._boot_hook(context, session_id, sandbox_id, config)

        endpoint_url, access_token = await self._resolve_endpoint_and_token(config)

        client = ShipyardBooter(
            endpoint_url=endpoint_url,
            access_token=access_token,
            ttl=int(config.get("ttl", 3600)),
            session_num=int(config.get("session_num", 10)),
        )
        await client.boot(uuid.uuid5(uuid.NAMESPACE_DNS, session_id).hex)
        return client

    async def _resolve_endpoint_and_token(self, config: dict) -> tuple[str, str]:
        endpoint_url = str(config.get("endpoint_url") or "").strip()
        access_token = str(config.get("access_token") or "").strip()

        if not config.get("auto_start_bay"):
            return endpoint_url, access_token

        bay_manager = ShipyardBayContainerManager(
            endpoint_url=endpoint_url,
            access_token=access_token,
            image=str(config.get("bay_image") or BAY_IMAGE),
            ship_image=str(config.get("ship_image") or DEFAULT_SHIP_IMAGE),
            docker_network=str(config.get("docker_network") or "").strip(),
        )
        try:
            endpoint_url = await bay_manager.ensure_running()
        finally:
            await bay_manager.close_client()

        return endpoint_url, access_token

    async def destroy_booter(self, booter: ComputerBooter, record: dict) -> None:
        destroy = getattr(booter, "destroy", None)
        if not callable(destroy):
            await booter.shutdown()
            return

        await destroy()
