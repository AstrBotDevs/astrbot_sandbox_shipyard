# astrbot_sandbox_shipyard

<div align="center">

English ｜ <a href="./README_cn.md">简体中文</a>

</div>

`astrbot_sandbox_shipyard` is the Shipyard sandbox driver plugin for AstrBot. It is intended for deployments that already run a Shipyard service and want Agents to execute commands, run Python, and read or write files in a remote sandbox.

## Key Features

1. 🛡️ Provides the `shipyard` sandbox driver for AstrBot.
2. 💻 Supports shell, Python, and file operations.
3. 📦 Syncs local AstrBot Skills when the sandbox boots.
4. ⏱️ Supports configurable session TTL and maximum session count.

## Quick Start

### Install the Plugin

Clone the plugin into AstrBot's plugin directory:

```bash
git clone https://github.com/zouyonghe/astrbot_sandbox_shipyard.git data/plugins/astrbot_sandbox_shipyard
```

Then restart AstrBot, or reload plugins from the plugin management page.

### Enable the Shipyard Sandbox Driver

Enable sandbox mode in AstrBot and select the `shipyard` sandbox driver:

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

## Configuration

| Key | Description |
| --- | --- |
| `shipyard_endpoint` | Shipyard API endpoint. Defaults to `http://127.0.0.1:8156`. |
| `shipyard_access_token` | Access token for Shipyard. |
| `shipyard_ttl` | Session TTL in seconds. |
| `shipyard_max_sessions` | Maximum number of sessions. |

If AstrBot runs in Docker Compose and the Bay service is reachable by container name, set `shipyard_docker_network` to that compose network instead of using the host loopback default.

## Best For

- This plugin is suitable for remote command execution, Python execution, and file operations.
- It does not register browser tools or GUI tools.
- After the plugin is enabled, set `provider_settings.sandbox.booter` to `shipyard` to route AstrBot sandbox requests to it.

## Requirements and Limitations

- AstrBot must support external sandbox driver plugins.
- The Python dependency from `requirements.txt`: `shipyard-python-sdk`.
- A reachable Shipyard service endpoint is required.
- A valid Shipyard access token is required.
- Browser automation is not included.
- GUI-specific tools such as screenshot, mouse, and keyboard are not included.
- The runtime depends on an external Shipyard service being healthy and reachable.

## Repository

- GitHub: https://github.com/zouyonghe/astrbot_sandbox_shipyard
