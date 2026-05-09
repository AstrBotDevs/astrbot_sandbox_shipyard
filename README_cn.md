# astrbot_sandbox_shipyard

英文版说明：[`README.md`](./README.md)

`astrbot_sandbox_shipyard` 是一个基于 AstrBot 通用 sandbox provider 机制实现的插件，用来提供 `shipyard` 运行时。

它适合需要经典远程沙箱能力的场景，支持 shell、Python 和文件系统操作。

## 功能特性

- 为 AstrBot 提供 `shipyard` 沙箱运行时。
- 支持 shell、Python、文件系统能力。
- 沙箱启动时会同步本地 AstrBot skills。
- 支持配置会话 TTL 和最大会话数量。

## 依赖要求

- 需要使用已经支持外部 sandbox provider 插件的 AstrBot 版本。
- 依赖 `requirements.txt` 中的 `shipyard-python-sdk`。
- 需要可访问的 Shipyard 服务地址。
- 需要有效的 Shipyard Access Token。

## 安装方式

把插件克隆到 AstrBot 的插件目录：

```bash
git clone https://github.com/zouyonghe/astrbot_sandbox_shipyard.git data/plugins/astrbot_sandbox_shipyard
```

然后重启 AstrBot，或重新加载插件。

## 配置方法

先在 AstrBot 核心配置中启用 sandbox，并把运行时设置为 `shipyard`：

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

插件支持的配置项：

| 键名 | 说明 |
| --- | --- |
| `shipyard_endpoint` | Shipyard API 地址。 |
| `shipyard_access_token` | Shipyard 访问令牌。 |
| `shipyard_ttl` | 会话 TTL，单位秒。 |
| `shipyard_max_sessions` | 最大会话数量。 |

## 使用说明

- 该插件适合远程执行命令、运行 Python、读写文件等场景。
- 它不会注册浏览器自动化工具，也不会提供 GUI 工具。
- 插件启用后，把 `provider_settings.sandbox.booter` 设置为 `shipyard`，AstrBot 就会把 sandbox 请求路由到这个运行时。

## 限制说明

- 不包含浏览器自动化能力。
- 不包含截图、鼠标、键盘等 GUI 能力。
- 依赖外部 Shipyard 服务正常运行且可访问。

## 仓库地址

- GitHub: https://github.com/zouyonghe/astrbot_sandbox_shipyard
