from astrbot.api.star import Context, Star, register
from astrbot.core.computer.computer_client import (
    register_sandbox_provider,
    unregister_sandbox_provider,
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
        unregister_sandbox_provider(self.provider.provider_id, force=True)
