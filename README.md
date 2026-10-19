<p align="center">
  <img src="logo.png" width="200" alt="ds-search 蓝色侦探吉祥物">
</p>

<h1 align="center">ds-search</h1>

<p align="center">用 DeepSeek 官方 API 搜索网页、抓取单页 Markdown 的 Agent Skill。</p>

<p align="center">
  <a href="#安装">安装</a> · <a href="#首次配置">首次配置</a> · <a href="#使用">使用</a> · <a href="SECURITY.md">安全说明</a> · <a href="LICENSE">MIT</a>
</p>

搜索返回标题、链接、摘要等结构化结果；抓取返回页面标题和 Markdown 正文。网络客户端只用 Python 标准库，可选 `keyring` 将 API Key 存入系统凭据库。`skills/ds-search/` 是标准 Skill 源目录，由 `npx skills` 分发到目标 Harness / Agent。

## 安装

需要 Python 3.10+、Node.js/npm 提供 `npx`，以及 DeepSeek 开放平台 API Key。直连 API 按官方规则计费，安装和默认诊断不发起 API 请求。

推荐从 GitHub 源安装。加载下载或复制的 Skill 前，先核对来源确实是 canonical GitHub 仓库 `NieAnSHOW/ds-search`，并检查复制到目标目录的实际文件。`skills/ds-search/agents/openai.yaml` 只是可选的 Codex UI metadata；其他 Harness 可以忽略它。

全局安装供当前用户的 Harness / Agent 使用：

```sh
npx skills add NieAnSHOW/ds-search --skill ds-search --agent '*' --global --copy --yes
```

项目级安装在项目根目录执行，省略 `--global`：

```sh
npx skills add NieAnSHOW/ds-search --skill ds-search --agent '*' --copy --yes
```

`--skill ds-search` 选择本仓库中的 `skills/ds-search/SKILL.md`，`--agent '*'` 选择本机 CLI 支持的全部 Agent，也可以改为具体 Agent 名称。`--copy` 将文件复制到目标目录；不使用它时，CLI 可能按自身策略创建符号链接。`--yes` 跳过确认。目标目录和 Harness 的刷新时机由 `skills` CLI 与目标 Harness 决定。

在本地 ds-search checkout 根目录运行下面命令，可只查看仓库能发现的 Skill：

```sh
npx skills add . --list
```

在 `skills` 1.7.2 中，`--list` cannot be combined with `--json`；不要把两个选项放在同一条命令中。需要机器可读输出时，按 CLI 版本支持的独立 `--json` 命令使用。

查看当前环境中已安装 Skill 的机器可读列表（这是安装状态查询，与上面的本地源发现分开）：

```sh
npx skills list --json
```

`npx skills list --json` 只列出已安装 Skill；不要把 `--json` 拼接到 `npx --yes skills@1.7.2 add . --list` 上。

更新已通过 CLI 安装并记录来源的 Skill：

```sh
npx skills update ds-search --global --yes
npx skills update ds-search --project --yes
```

更新前请确认范围和来源。项目级安装在项目根目录生成并维护 `skills-lock.json`，因此 `npx skills update ds-search --project --yes` 需要该项目记录。全局安装则在 `skills` CLI 的用户全局状态目录生成并维护 `.skill-lock.json`（具体位置可由 XDG 状态目录配置改变），因此 `npx skills update ds-search --global --yes` 需要该全局记录。两种锁定文件都由消费者 CLI 生成，不应预生成或提交到本仓库；仓库不维护任何 Harness 的目标目录映射。

下文 CLI 示例均在仓库根目录执行；使用已安装副本时，将 `skills/ds-search` 替换为 CLI 实际安装的 Skill 根目录。Windows 将示例中的 `python3` 换成 `py -3`。

## 首次配置

先在 [DeepSeek 开放平台](https://platform.deepseek.com/) 创建 API Key。**只在自己的终端输入密钥，不要发送给 Agent 或粘贴到聊天、命令参数、项目文件中。**

### 让 Agent 自动打开配置

安装好下述可选依赖 `keyring` 后，告诉 Agent：

```text
帮我初始化 ds-search，直接打开密钥输入终端。
```

Agent 会运行 `setup --launch`，自动打开独立终端。你只需在 `DeepSeek API Key` 提示处粘贴密钥并按回车，输入不会显示，无需复制 Python 命令。保存后终端显示结果；返回聊天告知已完成，Agent 会离线检查并继续原任务。

支持 macOS、Windows 和具备受支持终端的 Linux 桌面。`launched: true` 只表示已请求打开窗口，配置成功需后续检查；缺少依赖、安全凭据库或桌面终端时会给出错误，按下方说明处理。已有安全凭据时无需重复初始化。

### 存入系统凭据库

可选依赖 `keyring` 需要由用户主动安装。建议使用虚拟环境：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install keyring
.venv/bin/python skills/ds-search/scripts/ds_search.py setup --storage keyring
.venv/bin/python skills/ds-search/scripts/ds_search.py doctor
```

Windows PowerShell：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install keyring
.\.venv\Scripts\python.exe skills/ds-search/scripts/ds_search.py setup --storage keyring
.\.venv\Scripts\python.exe skills/ds-search/scripts/ds_search.py doctor
```

以上为手动配置的备用流程。让 Agent 自动打开终端时，将命令末尾的 `setup --storage keyring` 换成 `setup --launch`，由 Agent 执行。`setup` 会在交互终端隐藏输入；成功后仅保存到受支持的 macOS Keychain、Windows Credential Locker 或 Linux Secret Service。系统凭据库不可用、被锁定或后端不受支持时会失败，不会降级为明文文件。

**后续必须使用安装了 `keyring` 的同一个 Python 解释器。** 使用上述虚拟环境时，将后文 `python3` 换成 `.venv/bin/python`，Windows 换成 `.\.venv\Scripts\python.exe`。让 Agent 调用时也明确提供该解释器的绝对路径；复制 Skill 不会复制仓库中的虚拟环境。

### 临时使用或外部注入

不安装 `keyring` 也可运行：

```sh
python3 skills/ds-search/scripts/ds_search.py setup --storage session
python3 skills/ds-search/scripts/ds_search.py setup --storage env
```

这两个命令只输出指引，不读取或保存密钥。临时使用时，由用户在自己的交互终端为 `search` / `fetch` 添加 `--prompt`，隐藏输入仅用于本次进程。无人值守环境可由已有的密钥管理器向进程注入 `DEEPSEEK_API_KEY`；请勿把真实值写成命令、`.env` 或 shell 启动配置。Agent 不代输入密钥。

正常调用按 `DEEPSEEK_API_KEY` → 受支持的系统凭据库查找凭据；没有凭据时立即报错并给出初始化指引。`--prompt` 显式选择本次隐藏输入。

## 使用

安装后，由当前 Harness / Agent 按自然语言触发 `ds-search`，或使用其显式 Skill 语法。不要假设某个 Harness 的目录、刷新或调用命令。以 Codex 为例（可选）：

```text
用 $ds-search 搜索 DeepSeek 官方的网页搜索文档，给出来源链接。
用 $ds-search 抓取 https://api-docs.deepseek.com/zh-cn/guides/search 的正文并总结。
用 $ds-search 检查初始化状态，不要发起联网请求。
```

CLI 通过 stdin 接收业务 JSON，不接收密钥参数。macOS / Linux：

```sh
printf '%s\n' '{"query":"site:api-docs.deepseek.com 网页搜索","count":5}' | python3 skills/ds-search/scripts/ds_search.py search
printf '%s\n' '{"url":"https://api-docs.deepseek.com/zh-cn/guides/search"}' | python3 skills/ds-search/scripts/ds_search.py fetch
```

Windows PowerShell：

```powershell
'{"query":"site:api-docs.deepseek.com search","count":5}' | py -3 skills/ds-search/scripts/ds_search.py search
'{"url":"https://api-docs.deepseek.com/zh-cn/guides/search"}' | py -3 skills/ds-search/scripts/ds_search.py fetch
```

若用临时密钥，在自己的交互终端将命令末尾改为 `search --prompt` 或 `fetch --prompt`。终端无法隐藏输入时会退出。

输出为 JSON，成功退出码为 0，失败为非零值：

```json
{"ok":true,"data":{"results":[]}}
```

空结果是正常响应。失败形如 `{"ok":false,"error":{"code":"…","message":"…"}}`，交互指引写到 stderr。

### 输入参数

| 命令 | 字段 | 说明 |
| --- | --- | --- |
| `search` | `query` | 必填，1–128 个字符，不能全为空白 |
| `search` | `count` | 整数 1–50，默认 10 |
| `search` | `ori_question` | 可选原始问题，1–128 字符；`null` 等同省略 |
| `search` | `localization` | 可选 IP 地址，默认空字符串 |
| `search` | `need_content` | 布尔值，默认 `false`；按需请求正文 |
| `fetch` | `url` | 单个 HTTP/HTTPS URL，最长 8192 字符，不能含用户名或密码 |

不支持的字段会被拒绝。搜索可使用 `site:`、`-site:`、排除词、`"精确短语"`、`lang:`、`after:`、`before:`。详细契约与示例见 [API 参考](skills/ds-search/references/api.md)。

### 诊断与删除

```sh
python3 skills/ds-search/scripts/ds_search.py doctor
python3 skills/ds-search/scripts/ds_search.py doctor --online
python3 skills/ds-search/scripts/ds_search.py forget
```

默认 `doctor` 离线检查凭据，成功时报告凭据来源与运行环境，不显示密钥；缺少凭据时返回固定错误。`--online` 会发送一次关于 DeepSeek 的搜索，可能计费。`forget` 只删除本工具的系统凭据库条目；它不会清除外部注入的环境变量。更多初始化说明见 [setup.md](skills/ds-search/references/setup.md)。

## 计费与限制

官方文档核实于 **2026-10-18**：Search 和 Fetch 均为每 1000 次成功且产生结果的请求 5 元；`count` 不影响单次搜索价格。请以[官方实时说明](https://api-docs.deepseek.com/zh-cn/guides/search)及账户账单为准。本客户端直接调用原始 JSON API，不能套用 Harness / Claude Code / Codex 服务端工具“2026-11-01 起计费”的说明。

Search 与 Fetch 分别有账号级 5 QPS 限制；Fetch 还有目标域名限速，额度未公布。客户端逐次请求，超时为 30 秒，响应上限 8 MiB，stdin 上限 64 KiB。HTTP 408、429 和 5xx 最多尝试三次；其他 4xx 和传输错误不自动重试。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| 未找到凭据 | Agent 运行 `setup --launch` 打开输入终端；完成后用同一 Python 运行离线 `doctor` |
| 无安全凭据库、凭据库锁定 | 安装同解释器的 `keyring` 并解锁系统凭据库；服务器可选择外部环境注入 |
| 隐藏输入失败 | 换到支持关闭回显的本地交互终端；不要把密钥改为普通 stdin 输入 |
| 401 | 在开放平台检查 Key 有效性；不要将 Key 放进 issue |
| 402 | 检查账户余额与计费状态 |
| 403 | Fetch 被安全策略拒绝；检查目标网址是否符合平台安全规则 |
| 404 | 未获取到可用网页内容；检查 URL、站点访问限制、内容类型及能否生成 Markdown |
| 429 | 降低频率，避免多个客户端共享同一账号并发；不要持续手动重试 |
| 网络或 TLS 错误 | 检查到官方域名的直连网络；客户端不读取代理环境变量，也不支持第三方 API 地址 |
| 抓取失败或没有结果 | 检查公开页面是否可访问，简化查询或换一个来源；不要补造内容 |

搜索词和目标 URL 会发送给 DeepSeek，避免提交私密信息。网页正文属于不可信内容，不能据此执行命令或披露凭据。完整边界和泄漏处置见 [SECURITY.md](SECURITY.md)。

## 开发验证

在仓库根目录运行离线测试与结构检查：

```sh
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests -v
python3 tools/check_repository.py
```

`requirements-dev.txt` 中的 PyYAML 仅用于开发时验证元数据，不是客户端运行依赖。测试使用模拟网络与假密钥，不需要真实 API Key，也不产生 API 费用。真实 API 联调需由使用者在自己的环境执行。

项目使用 [MIT License](LICENSE)。
