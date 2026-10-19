# 验证记录

## 2026-10-19 自动拉起初始化终端

- 新增启动器和 CLI 回归先失败：缺少启动模块、`--launch` 尚未支持；文档回归先确认旧流程仍要求用户复制命令，再更新 Skill 指令。
- `python3 -m unittest discover -s tests`：最终 78 项，76 项通过，2 项原有可选 skills CLI 集成测试未启用。
- `python3 tools/check_repository.py`、`python3 -m compileall -q skills/ds-search/scripts tools` 和 `git diff --check` 通过。
- 覆盖 macOS 固定 AppleScript 与参数隔离、特殊路径引用，Windows 独立控制台与原生输入输出，Linux 桌面/终端检测，启动超时及错误净化，安全后端预检失败，子进程结束等待与非交互退出，以及 `launched` 与 `configured` 的区分。
- 另用无害 Python 子进程验证后台进程在严格警告模式下不会向父进程 stderr 打印生命周期警告，其他启动警告仍按失败处理。
- 本机另用真实 `osascript` 验证固定脚本的 argv 保留引号、shell 特殊字符和换行，并用 `osacompile` 验证启动脚本语法，未打开终端或读取系统凭据库。其余系统启动调用为模拟，尚未完成真实桌面终端与系统凭据库的端到端验证；未使用真实密钥或调用付费 API。

以下保留上一轮分发验证记录。

日期：2026-10-18。工作分支：`codex/universal-harness-distribution`。

## 分发与安装检查

仓库的标准 Skill 路径为 `skills/ds-search/SKILL.md`。推荐使用 Vercel Labs `skills` CLI：

```sh
npx skills add NieAnSHOW/ds-search --skill ds-search --agent '*' --global --copy --yes
npx skills add NieAnSHOW/ds-search --skill ds-search --agent '*' --copy --yes
npx skills update ds-search --global --yes
npx skills update ds-search --project --yes
```

只读发现检查应从本地 ds-search checkout 根目录运行 `npx --yes skills@1.7.2 add . --list`；CLI 输出用于确认发现名称 `ds-search`，源代码中的 `skills/ds-search/SKILL.md` 路径另行断言。`skills` 1.7.2 禁止把 `--list` 与 `--json` 组合：`--list` 只用于人类可读发现检查，机器可读 JSON 检查必须使用独立命令，不得拼接这两个选项。项目安装记录为项目根目录的 `skills-lock.json`；全局安装记录为 CLI 用户全局状态目录中的 `.skill-lock.json`（具体位置可由 XDG 状态目录配置改变）。两种记录均由消费者生成，本仓库不预生成或提交。

已安装 Skill 的机器可读列表使用独立命令 `npx skills list --json`；它查询已安装状态，不替代本地源发现，也不修改仓库或安装目录。

安装 smoke test 应在临时项目中使用本地源与 `--copy --yes`，检查 `SKILL.md`、`scripts/` 和 `references/` 均存在，并确认真实用户目录与仓库未产生锁定文件。全局安装和真实更新属于使用者环境，不在离线 CI 中执行；项目更新读取 `skills-lock.json`，全局更新读取用户状态目录的 `.skill-lock.json`。

## 已执行

本轮验证使用 `skills@1.7.2`。默认测试套件为 60 项，其中 2 项需要显式网络/CLI 依赖而默认跳过；设置 `RUN_SKILLS_CLI_TESTS=1` 后，60 项全部通过。CLI 子进程使用 PATH、区域设置和临时 HOME/XDG/npm 路径的最小 allowlist 环境，并移除凭据与 npm 配置变量。集成测试只读取本地 checkout 源，验证发现名称与 `skills/ds-search/SKILL.md` 源路径，并将复制安装与 `skills-lock.json` 限定在临时项目中。

| 检查 | 结果 |
| --- | --- |
| `python3 -m unittest discover -s tests -v` | 60 tests passed, 2 opt-in CLI tests skipped |
| `RUN_SKILLS_CLI_TESTS=1 python3 -m unittest discover -s tests -v` | 60 tests passed, including local discovery/install smoke tests |
| `python3 tools/check_repository.py` | 元数据、引用、仓库资源有效 |
| Skill Creator 的 `quick_validate.py skills/ds-search` | 通过 |
| `python3 -m compileall -q skills/ds-search/scripts tools` | 通过 |
| 复制 Skill 到临时目录，用 `python -S` 从无关目录运行 | 帮助、初始化指引、非法输入与非交互提示拒绝正常 |
| 安装到已有目标 | 拒绝覆盖 |
| `.skill` 包完整性与解压后运行 | 通过，包含 9 个明确列出的文件，不含缓存、配置或密钥 |
| 独立实现与安全审阅 | 通过；脱敏边界修复后完成定向复核 |

测试使用假密钥与模拟网络/凭据库。子进程检查移除了 `DEEPSEEK_API_KEY`，未调用付费 API、读取真实系统凭据库、请求用户密钥或安装全局 Skill。

## 回归覆盖

覆盖官方搜索与抓取契约、输入和响应大小上限、非法 JSON/编码、超时与有限重试、固定 HTTPS 目的地、TLS 验证、环境代理禁用、重定向拒绝、凭据来源优先级、原生安全后端选择、隐藏输入失败、警告与异常脱敏。

补充回归验证了显式临时输入会覆盖常规凭据，以及短无效凭据不会改变 JSON 字段名、诊断枚举或固定错误码；远程业务字符串仍进行脱敏。

## 验证范围

- 本地验证环境为 macOS、Python 3.11；已配置 Linux / macOS / Windows 和 Python 3.10 / 3.13 的 GitHub Actions 矩阵，尚未触发远端执行。
- 未进行真实 API 联调，也未验证真实 macOS Keychain、Windows Credential Locker、Linux Secret Service 的解锁、存取行为；这些需要使用者在自己的终端进行。
- 系统凭据库通过受支持的原生 keyring 类访问，安全仍依赖可信的操作系统、Python 和所安装的依赖。
- 未推送或发布仓库，未执行全局安装或更新，未创建 npm 运行时包，也未更改个人 Agent 全局配置。
