# astrbot_sandbox_shipyard

Chinese version: [`README_cn.md`](./README_cn.md)

`astrbot_sandbox_shipyard` is an AstrBot sandbox runtime plugin that adds the `shipyard` provider through the generic sandbox provider API.

It is intended for users who want a classic remote sandbox with shell, Python, and filesystem support.

## Features

- Provides the `shipyard` sandbox runtime for AstrBot.
- Supports shell, Python, and filesystem operations.
- Syncs local AstrBot skills into the sandbox when the sandbox boots.
- Supports configurable session TTL and maximum session count.

## Requirements

- An AstrBot build that supports external sandbox provider plugins.
- The Python dependency from `requirements.txt`: `shipyard-python-sdk`.
- A reachable Shipyard service endpoint.
- A valid Shipyard access token.

## Installation

Clone the plugin into AstrBot's plugin directory:

```bash
git clone https://github.com/zouyonghe/astrbot_sandbox_shipyard.git data/plugins/astrbot_sandbox_shipyard
```

Then restart AstrBot or reload plugins.

## Configuration

Enable sandbox runtime in AstrBot and select this provider:

```json
{
  "provider_settings": {
    "computer_use_runtime": "sandbox",
    "sandbox": {
      "booter": "shipyard"
    }
  }
}
```

Provider-specific options:

| Key | Description |
| --- | --- |
| `shipyard_endpoint` | Shipyard API endpoint. |
| `shipyard_access_token` | Access token for Shipyard. |
| `shipyard_ttl` | Session TTL in seconds. |
| `shipyard_max_sessions` | Maximum number of sessions. |

## Usage Notes

- This plugin is suitable for command execution, Python execution, and file operations in a remote sandbox.
- It does not register browser tools or GUI tools.
- After the plugin is enabled, set `provider_settings.sandbox.booter` to `shipyard` to route AstrBot sandbox requests to this runtime.

## Limitations

- Browser automation is not included.
- GUI-specific tools such as screenshot, mouse, and keyboard are not included.
- The runtime depends on an external Shipyard service being healthy and reachable.

## Repository

- GitHub: https://github.com/zouyonghe/astrbot_sandbox_shipyard
