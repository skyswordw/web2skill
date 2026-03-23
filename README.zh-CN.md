# web2skill

[English](https://github.com/skyswordw/web2skill/blob/main/README.md) | [简体中文](https://github.com/skyswordw/web2skill/blob/main/README.zh-CN.md)

`web2skill` 用来把封闭式 Web 应用和 SaaS 的稳定能力封装成 agent 可调用的技能。
v1 只发布一个 Python 包 `web2skill`，内置 ModelScope 技能包，同时支持从本地路径、git URL、git 子目录或 marketplace 条目安装额外技能包。

## 快速开始

### 1. 安装

```bash
pip install web2skill
python -m playwright install chromium
```

### 2. 查看内置技能

```bash
web2skill skills list
web2skill skills describe modelscope
```

### 3. 调用无需登录的 ModelScope 能力

```bash
web2skill invoke modelscope.search_models --input '{"query":"qwen"}' --json
```

### 4. 登录后调用账户相关能力

```bash
web2skill sessions login modelscope --mode interactive
web2skill sessions doctor modelscope --json
web2skill invoke modelscope.get_account_profile --input '{}' --json
```

## 你会得到什么

- 一个可安装的核心包：`web2skill`
- 内置的一方 ModelScope 技能包
- 所有调用都返回稳定 JSON，并带有 `trace_id`、`strategy_used`、`requires_human`
- 基于 Playwright storage state 的会话复用
- 每次调用都有可回放 trace
- 可安装第三方或本地技能包

## ModelScope 能力中哪些需要登录

| 能力 | 是否需要登录 | 说明 |
| --- | --- | --- |
| `modelscope.search_models` | 否 | 搜索公开模型 |
| `modelscope.get_model_overview` | 否 | 获取模型概览 |
| `modelscope.list_model_files` | 否 | 列出模型仓库文件 |
| `modelscope.get_quickstart` | 否 | 提取快速开始/用法说明 |
| `modelscope.get_account_profile` | 是 | 读取当前登录账户信息 |
| `modelscope.list_tokens` | 是 | 列出非敏感 token 元数据 |
| `modelscope.get_token` | 是 | 在显式确认后读取指定 token |
| `modelscope.create_token` | 是 | 在显式确认后创建 token |

## 首次登录

`web2skill sessions login modelscope` 支持两种模式：

- `interactive`：打开真实浏览器窗口，适合首次登录、需要验证码、二维码、MFA 或人工确认的场景。
- `import-browser`：从本地已登录的浏览器导入 cookie，适合你已经在 Chrome、Edge、Chromium 等浏览器中登录了 ModelScope 的情况。

`web2skill sessions doctor modelscope` 只检查本地 storage-state 文件是否存在且包含 cookie，不会向 ModelScope 远端确认这些 cookie 仍然有效。

## 输入示例

内联 JSON：

```bash
web2skill invoke modelscope.get_model_overview --input '{"model_slug":"Qwen/Qwen3.5-27B"}' --json
```

使用 JSON 文件：

```bash
cat > input.json <<'JSON'
{
  "model_slug": "Qwen/Qwen3.5-27B"
}
JSON
web2skill invoke modelscope.list_model_files --input @input.json --json
```

## 内置技能与自定义技能

一方技能直接随 `web2skill` 包一起发布。用户自定义技能不需要单独发 PyPI 包，可以直接安装：

```bash
web2skill skills install /path/to/skill-bundle
web2skill skills install https://github.com/your-org/your-skill-repo.git
web2skill skills install https://github.com/your-org/your-monorepo.git --subdir skills/your-skill
web2skill marketplaces add official https://raw.githubusercontent.com/skyswordw/web2skill/main/marketplace.yaml
web2skill skills search modelscope --marketplace official
web2skill skills install modelscope@official
web2skill skills update <bundle_id>
web2skill skills uninstall <bundle_id>
```

官方第一方 marketplace 清单位于 [marketplace.yaml](/Volumes/DataHouse/codes/playground/web2skill/.worktrees/pypi-onboarding-release/marketplace.yaml)。marketplace 条目会解析到一个 git 仓库和可选的 bundle 子目录，这样一个 monorepo 就可以发布多个独立可安装技能，而用户不需要手动克隆整个仓库。

## 从源码开发

如果你是在源码仓库中开发，而不是通过已发布包来使用：

```bash
uv sync --dev
uv run playwright install chromium
uv run pytest
uv run web2skill skills list
```

## 技能包目录约定

一方技能和用户安装技能都遵循同样的目录结构：

```text
<skill>/
  SKILL.md
  skill.yaml
  scripts/
    capabilities/
    session/
    lib/
  references/
  assets/
  pyproject.toml
  uv.lock
```

用户安装的技能包位于 `~/.web2skill/skills/`。

## 仓库结构

- `src/web2skill/`: 核心 runtime、浏览器支持、bundle 注册、CLI、安装器
- `skills/`: 一方技能 bundle 的源码目录
- `marketplace.yaml`: 官方第一方 marketplace 清单，供 git/subdir 安装使用
- `tests/`: unit / integration / e2e / drift 测试
- `docs/architecture/`: 架构说明
- `docs/evals/`: 评估与 smoke 文档
- `docs/quality/`: 质量门禁与发布文档
