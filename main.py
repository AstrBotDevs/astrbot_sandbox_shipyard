from astrbot.api import logger
from astrbot.api.star import Context, Star, register
from astrbot.core.computer.computer_client import (
    cleanup_sandbox_provider,
    detach_sandbox_provider,
    register_sandbox_provider,
)

from .provider import ShipyardSandboxProvider


@register(
    "astrbot_sandbox_shipyard",
    "AstrBot Team",
    "为 AstrBot 提供 Shipyard 沙盒运行时。",
    "0.1.0",
)
class ShipyardSandboxRuntimePlugin(Star):
    def __init__(self, context: Context, config=None) -> None:
        super().__init__(context)
        self.provider = ShipyardSandboxProvider(plugin_config=config)
        register_sandbox_provider(self.provider, replace=True)

    async def terminate(self) -> None:
        provider_id = getattr(getattr(self, "provider", None), "provider_id", None)
        if not provider_id:
            return
        try:
            await cleanup_sandbox_provider(provider_id)
        except Exception:
            logger.warning(
                "Shipyard sandbox provider cleanup failed during termination: provider=%s",
                provider_id,
                exc_info=True,
            )
            raise
        finally:
            detach_sandbox_provider(provider_id)
