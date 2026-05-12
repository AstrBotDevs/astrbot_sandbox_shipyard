# astrbot_sandbox_shipyard

<div align="center">

<a href="./README.md">English</a> ｜ 简体中文

</div>

`astrbot_sandbox_shipyard` 是 AstrBot 的 Shipyard 沙盒驱动插件，适合已经部署 Shipyard 服务、并希望让 Agent 远程执行命令、运行 Python、读写文件的场景。

## 主要功能

1. 🛡️ 为 AstrBot 提供 `shipyard` 沙盒驱动。
2. 💻 支持 Shell、Python 和文件操作。
3. 📦 沙盒启动时会同步本地 AstrBot Skills。
4. ⏱️ 支持配置会话 TTL 和最大会话数量。

## 快速开始

### 安装插件

把插件克隆到 AstrBot 插件目录：

```bash
git clone https://github.com/zouyonghe/astrbot_sandbox_shipyard.git data/plugins/astrbot_sandbox_shipyard
```

然后重启 AstrBot，或在插件管理页重新加载插件。

### 启用 Shipyard 沙盒驱动

先在 AstrBot 核心配置中启用沙盒模式，并把沙盒驱动设置为 `shipyard`：

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

## 配置项

| 键名 | 说明 |
| --- | --- |
| `shipyard_endpoint` | Shipyard API 地址，默认值为 `http://127.0.0.1:8156`。如果 AstrBot 和 Bay 运行在同一个 Docker 网络里，可以填写容器名或服务名。 |
| `shipyard_auto_start` | 当本机默认地址不可达时，是否自动用 Docker 拉起 Bay。默认开启。 |
| `shipyard_docker_network` | 托管 Bay 使用的 Docker 网络名。留空表示宿主机端口模式；填写网络名表示 Docker Compose 网络模式。 |
| `shipyard_bay_image` | 自动启动 Bay 时使用的镜像，默认是 `soulter/shipyard-bay:latest`。 |
| `shipyard_ship_image` | Bay 创建沙盒时使用的镜像，默认是 `soulter/shipyard-ship:latest`。 |
| `shipyard_access_token` | Shipyard 访问令牌。 |
| `shipyard_ttl` | 会话 TTL，单位秒。 |
| `shipyard_max_sessions` | 最大会话数量。 |

如果 AstrBot 运行在 Docker Compose 中，并且 Bay 服务通过容器名可达，请把 `shipyard_docker_network` 配成对应的 compose 网络，而不是直接使用本机回环地址。

## 适合场景

- 该插件适合远程执行命令、运行 Python、读写文件等场景。
- 它不会注册浏览器自动化工具，也不会提供 GUI 工具。
- 插件启用后，把 `provider_settings.sandbox.booter` 设置为 `shipyard`，AstrBot 就会把沙盒请求交给它处理。

## 依赖与限制

- 需要使用支持外部沙盒驱动插件的 AstrBot 版本。
- 依赖 `requirements.txt` 中的 `shipyard-python-sdk`。
- 需要可访问的 Shipyard 服务地址。
- 需要有效的 Shipyard Access Token。
- 不包含浏览器自动化能力。
- 不包含截图、鼠标、键盘等 GUI 能力。
- 依赖外部 Shipyard 服务正常运行且可访问。

## 排查建议

- 如果自动启动失败，请确认宿主机能访问 Docker，并且默认地址仍然是 `http://127.0.0.1:8156`。
- 如果使用 Docker Compose，请确认 `shipyard_docker_network` 与实际网络名一致。

## 仓库地址

- GitHub: https://github.com/zouyonghe/astrbot_sandbox_shipyard
