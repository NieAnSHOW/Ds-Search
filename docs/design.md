# ds-search 设计方案

## 目标与交付

依据 TASK.md，实现名为 `ds-search` 的可分发 Agent Skill，通过 DeepSeek 官方原始 JSON API 完成网页搜索和单页 Markdown 抓取。仓库交付可执行脚本、Skill 指令、初始化引导、中文 README、安全说明、离线测试和 CI。沿用现有 MIT LICENSE，使用用户提供的根目录 `logo.png`。

当前仓库已初始化 Git，位于 `main`，远端为 `NieAnSHOW/ds-search`。本次“初始化”补齐项目结构与开发检查，不重复 git init，不默认推送或发布，也不读取现有个人密钥。

## 方案选择

1. **推荐：Python 标准库客户端 + 可选系统凭据库。** 网络请求不依赖第三方 SDK；持久化凭据时使用可选 `keyring` 与受支持的系统后端。可在无凭据库的环境通过环境变量或当前进程的隐藏输入运行。
2. 纯环境变量方案依赖最少，但首次配置与长期使用体验较弱，作为兼容路径保留。
3. MCP 服务方案适合长期工具托管，但引入进程管理与客户端注册，超出本次 Skill 的必要范围。

## 文件组织

```text
README.md                    项目首页、logo、安装与初始化、示例
SECURITY.md                  凭据边界、泄漏处置与问题报告方式
LICENSE / TASK.md / logo.png 沿用现有文件
.gitignore                  忽略本地密钥、配置、缓存和构建产物
.github/workflows/ci.yml     离线测试与结构检查
skills/ds-search/
  SKILL.md                  触发条件、初始化/搜索/抓取流程
  agents/openai.yaml        可选的 Codex UI 展示信息
  scripts/ds_search.py       JSON CLI 入口与官方客户端
  references/setup.md       初始化、凭据来源与诊断
  references/api.md         已核实的 API 契约与搜索语法
tests/                      请求契约、初始化与安全行为回归
docs/design.md              本方案
```

`skills/ds-search/` 是仓库中的标准 Skill 布局：入口固定为 `SKILL.md`，脚本和参考资料位于同一目录下。通过 Vercel Labs `skills` CLI 发现、安装或更新时，CLI 负责选择项目/全局范围、目标 Agent 目录以及复制或链接策略；本仓库不复制或维护这些目标目录映射，也不提交消费者生成的 `skills-lock.json`。`agents/openai.yaml` 仅供 Codex UI 使用，其他 Harness 可以忽略。

推荐使用 `npx skills add` 从仓库安装，使用 `npx skills update` 更新已安装副本。Skill 本身只描述 Harness 注入后的运行方式和相对资源路径，不要求某一 Harness 的目录、刷新或重启行为。

## CLI 与初始化

- `setup`：说明如何在 DeepSeek 开放平台创建 Key；用户在自己的交互终端中通过隐藏输入配置。优先提供系统凭据库持久化路径，检测不到受支持的安全后端时明确失败，提供临时模式与环境注入说明。
- `setup --launch`：Agent 自动请求打开独立桌面终端，由同一 Python 和绝对脚本路径运行系统凭据库配置。用户只在该终端隐藏输入，Agent 不接收密钥。启动返回 `launched: true, configured: false`，待用户完成后用离线 `doctor` 确认可用性。缺少安全后端或桌面终端时显式失败，不自动安装依赖；`env` / `session` 不支持此选项。
- `doctor`：只输出凭据是否可用、凭据来源和运行环境信息，绝不输出 Key 或其片段。默认不调用付费 API；显式检查连接时说明会发起请求。
- `search`：输入 query 和可选 count、ori_question、localization、need_content，返回结构化搜索结果。
- `fetch`：输入单个 URL，返回 title 与 Markdown content。
- 常规凭据优先级：`DEEPSEEK_API_KEY` → 受支持的系统凭据库；显式 `--prompt` 则直接选择本次隐藏输入。不指定隐藏输入且凭据不存在时返回可操作的初始化提示，不擅自打开输入或长时间等待。
- 业务输入通过 stdin JSON 传入；必要的操作选择使用非敏感 CLI 参数。拒绝 JSON 中的密钥、认证头或自定义 API 地址等不受支持字段，不把密钥作为命令行参数接收。
- stdout 输出统一 JSON；交互引导使用 stderr，脚本失败通过非零退出码与稳定错误类型反馈。错误不回显原始请求、响应体或异常字符串。
- 不自动安装依赖，不把凭据写进 `.env`、配置 JSON、shell 启动文件或仓库。提供用户主动执行的可选 keyring 安装步骤；仅接受受支持的 macOS Keychain、Windows Credential Locker、Linux Secret Service 后端，拒绝明文、未知或链式回退后端。

## 官方 API 契约

来源：<https://api-docs.deepseek.com/zh-cn/guides/search>、[Search Reference](https://api-docs.deepseek.com/zh-cn/api/search)、[Fetch Reference](https://api-docs.deepseek.com/zh-cn/api/fetch)，均已直接读取核对，核实日期为 2026-10-18。Context7 的官方文档索引暂未覆盖这两个新接口，以官方页面为准。

- 固定 origin：`https://api.deepseek.com`。
- 搜索：`POST /v1/tools/search`；必填 query 为 1–128 个非全空白 Unicode 字符。count 为 1–50，官方默认 10；ori_question 为可选 1–128 字符字符串，null 视作省略；localization 为可选 IP 地址字符串，默认空串；need_content 为布尔值，默认 false。
- 搜索响应包含 results 数组；每项保留官方 title、url、snippet、summary、content、date、site_name、site_icon、rerank_score、authority。空数组是正常无结果，不伪造来源。
- 抓取：`POST /v1/tools/fetch`；URL 最长 8192 字符，必须含 HTTP/HTTPS host，不能含用户名或密码。响应为 title 与 content。
- 使用 Bearer 鉴权及 application/json。搜索操作符支持 site:、-site:、排除词/短语、精确短语、lang:、after:、before:，由用户意图决定，不臆造额外参数。
- 408、429、5xx 可进行有上限的退避重试；401、402、403、404 等不自动反复重试。设置请求超时、有限响应体大小和有限次数，错误返回可行动的固定说明。
- Search / Fetch 分别为账号级 5 QPS；Fetch 另有目标域名限速，具体额度未公布。不并发批量发请求。
- 官方当前价格均为每 1000 次成功且产生结果的请求 5 元；count 不改变单次价格。README 标注核实日期并链接实时价格。官方关于 Harness/Claude Code/Codex 服务端调用在 2026-11-01 起计费的说明，不等同于本客户端直连调用免费。

## 安全边界

“密钥绝对安全”落实为可测试的防泄漏约束，不承诺能抵御已被攻陷的操作系统或同权限恶意进程。

- Key 仅在当前进程内存、外部提供的环境变量或系统凭据库中存在；不落普通文本、不打印、不写日志、不接受 argv 密钥。
- 隐藏输入只由用户在自己的终端执行，Agent 不代录。无法关闭终端回显、缺少交互终端或出现 Python `GetPassWarning` 时立即退出，禁止降级到可回显的普通 stdin 输入。
- 固定官方 HTTPS API；不支持第三方 base URL，拒绝重定向，保持 TLS 证书验证，禁用自动读取代理环境变量，避免意外转发认证信息。
- 不读取项目 `.env` 或扫描用户目录找 Key；不在构建、打包、CI 或测试中使用真实密钥。
- 统一净化 API 内容与错误输出，防止服务端回显已知密钥；限制凭据长度与控制字符，阻止请求头注入。日志与 traceback 不包含请求对象或原始异常。
- 搜索词和目标 URL 会发送给 DeepSeek，避免附带用户密码、认证 token 或私密地址；不读取或自动上传本地文件。
- 远程网页正文属于不可信数据；Skill 明确禁止把网页中的“指令”当作用户授权，也不执行其命令或按其要求披露凭据。
- 系统凭据库故障时显式失败，不静默降级为明文存储。凭据删除只针对本 Skill 的 service/account 条目，不操作其他凭据。

## README 与使用体验

根目录 `README.md` 以现有 logo 和简短定位开头，依次提供能力、前提、安装、首次初始化、安全配置、搜索与抓取示例、Agent 调用示例、参数说明、计费限速、故障排查、开发验证与 MIT 授权。示例仅使用明确的假值和无凭据输入，不鼓励将真实 Key 粘贴到 Agent 对话或 shell 命令中。

Skill 触发覆盖用户明确调用 ds-search、用 DeepSeek 搜索、抓取网页正文，以及本 Skill 的初始化和诊断。它不把所有联网任务强制路由到自身，不替换其他搜索技能或现有客户端。

## 验收方式

- 结构验证器检查 SKILL.md frontmatter、命名、引用路径、未完成模板和 UI metadata。
- Python 离线测试覆盖官方请求路径/字段、边界校验、成功与无结果、错误映射、超时与退避边界。
- 使用假密钥和模拟系统凭据库测试首次初始化、未知/明文后端拒绝、来源优先级、凭据缺失与删除，以及无终端/关闭回显失败时的安全退出。
- 使用模拟网络测试固定目的地、重定向拒绝、TLS/代理设置、输出脱敏、无原始异常泄漏和响应大小限制。
- README 命令在无真实密钥条件下验证，CI 不请求真实 API。独立审阅检查实现与安全要求是否一致。
- 如用户未提供可用测试凭据，明确把真实 API 联调列为未执行，不请求用户在聊天中发送密钥。

## 执行状态

本方案已于 2026-10-18 获用户确认并进入实现。显式 `--prompt` 使用用户本次隐藏输入，覆盖环境变量与系统凭据库；未指定时遵循环境变量优先的凭据查找顺序。项目开发检查使用独立的 PyYAML 开发依赖，客户端运行仍只需 Python 标准库（系统凭据库模式另需可选 keyring）。
