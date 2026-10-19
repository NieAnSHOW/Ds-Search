# 通用 Harness 分发设计

## 背景与目标

当前 `ds-search` 已经能够通过 DeepSeek 官方 Search / Fetch API 工作，但 README 和 Skill 指令把 Codex 当成默认宿主，安装说明主要依赖手工复制。目标是让同一个 `skills/ds-search` 目录适用于不同 Harness，并让用户通过 Vercel Labs `skills` CLI 完成发现、安装、更新和多 Agent 目标选择。

成功标准：

1. `npx skills add NieAnSHOW/ds-search --skill ds-search --agent '*' --global --copy --yes` 能从 GitHub 仓库发现并安装 Skill。
2. `npx skills update ds-search --global --yes` 能使用安装记录更新 Skill；项目级安装也有等价命令。
3. Skill 的触发说明、README、初始化文案和安全边界不依赖某个单一 Harness；Codex 只作为可选示例。
4. `agents/openai.yaml` 仍可为 Codex 提供 UI 元数据，但不会成为其他 Harness 的运行时依赖。
5. 不引入 npm 运行时包、不提交消费者生成的 `skills-lock.json`、不改变现有 API 客户端或密钥安全边界。

## 已核实的外部契约

已在 2026-10-18 使用 `npx skills` 1.7.2 和其官方文档核对：

- 发现规则包含仓库根目录的 `skills/` 容器，最多向下查找三层；`skills/ds-search/SKILL.md` 是标准布局。
- GitHub 源安装：`npx skills add owner/repo`；`--skill ds-search` 选择具体 Skill；`--agent '*'` 选择所有支持的 Agent；`--global` 选择用户级范围；`--copy` 复制文件而不是建立符号链接；`--yes` 跳过确认。
- 更新：`npx skills update [skills...]`，`--global` / `--project` 选择范围，`--yes` 跳过范围确认。
- `--list` 可在不修改目标目录的情况下检查仓库发现结果；`skills` 1.7.2 禁止把 `--list` 与 `--json` 组合，`--json` 用于安装结果或已安装列表的机器可读输出。
- 安装器为消费者维护锁定记录，记录来源、Skill 路径和目录哈希。仓库不应预生成某个消费者的 `skills-lock.json`。
- `agents/openai.yaml` 是产品特定的可选 UI 元数据；其他 Harness 可忽略 `agents/` 目录。

## 方案与取舍

### 推荐：保持标准 Skill 目录，README 以 `npx skills` 为首选

保持现有 `skills/ds-search/`、`SKILL.md`、`references/` 和 `scripts/`；只调整文案、元数据和验证。README 给出全局安装、项目安装、指定 Agent、全部 Agent、更新和列出 Skill 的命令。Skill 主体描述“当前 Harness 的 Skill 运行时”和相对路径，不写死 Codex 目录或会话重启步骤。

优点是零迁移、符合官方发现规则、可保留现有 Codex 元数据和 Python 安全客户端。代价是 `npx skills` 的安装位置和支持的 Harness 清单由外部 CLI 控制，本仓库不应复制或维护它的目标目录映射。

### 不采用：发布 npm 运行时包

可以增加 `package.json`、npm 发布流程和 JS 包入口，但本项目的实际 Skill 文件和 Python 客户端不需要 Node 运行时；这会把“Skill 分发”与“客户端执行”混在一起，也会增加版本和供应链维护面。

### 不采用：为每个 Harness 建独立副本

为 Claude、Codex、Cursor 等分别维护内容会导致指令漂移、安全修复遗漏和更新路径分裂。统一 Skill 源配合 CLI 的 Agent 目标选择已经满足需求。

## 文件与行为变更

- `README.md`：将安装部分改为 `npx skills` 首选，提供 GitHub 源、全局/项目范围、`--agent`、`--copy`、`--list` 发现和独立的 `--json` 机器可读检查，以及 `update` 示例；将“在 Codex 中调用”改为通用 Harness 调用，并保留一个 Codex 示例。
- `skills/ds-search/SKILL.md`：删除“在 Codex 中”之类宿主假设，明确 Skill 由 Harness 注入，脚本路径相对 Skill 根目录；保留显式 `$ds-search` 只作为支持该语法 Harness 的示例，不把它当作通用触发格式。
- `skills/ds-search/agents/openai.yaml`：保留，且不添加其他 Harness 的伪元数据。其 `default_prompt` 继续面向 Codex UI，但 README 说明它是可选产品元数据。
- `docs/design.md`：补充标准布局和 `npx skills` 分发约束，修正 Codex 专用表述。
- `docs/verification.md`：加入 `npx skills add . --list` 发现检查和临时项目安装检查；说明更新命令依赖消费者的锁定记录。
- `tests/`：增加不联网的文档/布局检查，以及对 README 命令和标准 Skill 路径的可验证检查。不会在 CI 中修改用户全局目录或访问真实 GitHub 安装状态。
- `.gitignore`：继续忽略消费者锁定文件和本地安装产物（若本仓库测试生成临时文件，使用临时目录）。

## 安全与更新边界

`npx skills` 只负责下载和放置 Skill 文件；它不接触 DeepSeek API Key。README 必须提醒用户检查来源仓库、使用 `--copy` 时审阅实际文件，并在更新前理解 `skills` CLI 的锁定来源。Skill 自身继续禁止把密钥放入对话、命令参数、stdin 业务 JSON 或普通文件。

更新由 `skills` CLI 根据消费者记录获取同一来源的最新目录内容；本仓库不自行执行自动更新、不覆盖用户未授权的全局目录，也不把更新行为混入 Python 客户端。

## 验证策略

1. 在仓库本地运行 `npx --yes skills@1.7.2 add . --list`，断言 CLI 发现名为 `ds-search`，并独立断言源路径为 `skills/ds-search/SKILL.md`；不把 `--json` 与 `--list` 组合。
2. 在隔离临时项目中使用本地源和 `--copy --yes` 安装，断言 `SKILL.md`、脚本和参考文件齐全，且未创建真实用户配置。
3. 检查 README 和 Skill 的本地链接、仓库布局、frontmatter、openai.yaml 和脚本路径。
4. 运行默认 60 项客户端/安全/文档测试（其中 2 项 CLI 集成测试默认跳过），并在 `RUN_SKILLS_CLI_TESTS=1` 下运行完整 60 项；不调用真实 API、不读取系统凭据库、不修改用户全局 Harness 目录。
5. 在 README 中明确真实 GitHub 安装与更新命令，标注 `skills-lock.json` 由消费者生成，并说明 `--agent '*'` 受本机 `skills` CLI 版本支持范围影响。

## 兼容性限制

- 不同 Harness 是否加载 Skill、何时刷新已安装内容、是否支持项目级或全局级目录由 `npx skills` 和目标 Harness 决定；本仓库只提供标准 Skill 源。
- Codex 的 `agents/openai.yaml` 不会给其他 Harness 提供 UI；这不影响它们读取 `SKILL.md`。
- `npx skills` 的更新需要先完成一次带锁定记录的安装；直接复制目录的用户应改用 CLI 安装，或手动重新复制仓库目录。
