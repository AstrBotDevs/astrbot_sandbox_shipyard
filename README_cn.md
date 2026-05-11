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
| `shipyard_endpoint` | Shipyard API 地址，默认值为 `http://127.0.0.1:8156`。 |
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

## 仓库地址

- GitHub: https://github.com/zouyonghe/astrbot_sandbox_shipyard
