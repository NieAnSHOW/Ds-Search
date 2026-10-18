# 初始化与诊断

以下命令从 Skill 根目录运行；Python 3.10+，Windows 可用 `py -3` 替换 `python3`。如果 `keyring` 安装在虚拟环境中，所有命令都使用那个环境的 Python 绝对路径。

## 首次配置

用户在 [DeepSeek 开放平台](https://platform.deepseek.com/) 创建 API Key，并在自己的交互终端运行：

```sh
python3 scripts/ds_search.py setup --storage keyring
python3 scripts/ds_search.py doctor
```

`setup` 默认为 `--storage keyring`。缺少依赖时，用户可主动用同一解释器执行 `python3 -m pip install keyring`，建议安装在虚拟环境中。不要由 Agent 自动安装依赖或输入密钥。

仅允许 macOS Keychain、Windows Credential Locker、Linux Secret Service。缺少安全后端、凭据库锁定或读取失败时，先解决系统凭据库问题；不会退回明文存储。Linux 无桌面或容器环境通常更适合外部注入环境变量。

```sh
python3 scripts/ds_search.py setup --storage env
python3 scripts/ds_search.py setup --storage session
```

这两个命令只输出说明，不读取、不保存密钥。环境模式由用户已有的密钥管理器向执行进程注入 `DEEPSEEK_API_KEY`。不要给出包含真实值的命令，也不要写 `.env` 或 shell 启动文件。

临时模式由用户在自己的交互终端将业务 JSON 送入 `search --prompt` 或 `fetch --prompt`，再按隐藏提示输入；仅当前进程使用。Agent 不运行隐藏提示或代录凭据。终端回显无法关闭时必须换终端，不得改用明文输入。

## 来源与诊断

普通 `search` / `fetch` 按 `DEEPSEEK_API_KEY` → 受支持的系统凭据库查找凭据。缺少时立即失败，提供初始化指引；显式 `--prompt` 选择本次临时输入。错误、锁定或不受支持的后端不会被静默绕过。

`doctor` 默认离线，成功时报告凭据可用性、来源与运行环境，不显示密钥或片段；缺少凭据时返回固定错误，不附运行环境字段。若用户明确要求联网诊断，可运行 `doctor --online`：它搜索一次 DeepSeek，仅返回诊断摘要，可能产生费用。

| 问题 | 下一步 |
| --- | --- |
| 缺少凭据 | 请用户在自己的终端初始化；不要扫描项目或用户目录 |
| 安装 keyring 后仍不可用 | 核对实际执行的 Python，使用安装依赖的同一解释器 |
| 系统凭据库锁定或后端不安全 | 用户解锁或配置受支持的系统后端；无安全后端时选环境注入或用户临时模式 |
| 没有交互终端或回显关闭失败 | 用户换到本地交互终端，不把密钥作为 stdin 或 argv |
| 401 | 用户在平台检查 Key 有效性 |
| 402 | 用户检查余额和计费状态 |
| 403 | Fetch 被安全策略拒绝；检查目标网址是否符合平台安全规则 |
| 404 | 未获取到可用网页内容；检查 URL、站点访问限制、内容类型及能否生成 Markdown |
| 网络 / TLS 错误 | 检查到官方 API 的直连；不通过修改 base URL、关闭 TLS 或启用环境代理绕过 |

## 删除

仅在用户要求删除本工具凭据时运行：

```sh
python3 scripts/ds_search.py forget
```

只删除 service `ds-search`、account `deepseek-api-key` 的系统凭据库条目。外部环境变量由用户或其密钥管理器清除。若凭据泄漏，应先在 DeepSeek 平台撤销，删除本地条目不能阻止旧 Key 被继续使用。
