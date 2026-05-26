[English](README.md) | **中文**

# esxi-skill

为 [Claude Code](https://claude.ai/code) / [Codex CLI](https://github.com/openai/codex) 等 AI agent 提供的 **VMware ESXi & vSphere 管理 skill**，底层走 `govc`。

本仓库是该 skill 的**上游工程**。真正被 AI agent 加载的 skill 内容在 [`esxi/`](esxi/) 子目录里 —— 那是安装时要放进 agent skills 目录的部分。

---

## 为什么需要这个 skill

`govc` 是 VMware 官方的 Go CLI，覆盖 vSphere 400+ 命令、40+ 分类。功能强，但 LLM 直接用容易翻车：

- 命令语法幻觉
- 退回到不合适的工具（PowerCLI、手动 SSH）
- 用过时的 `PascalCase` jq 路径（`govc 0.30+` 已切到 `camelCase`）
- 把快照当备份用、破坏性操作不确认
- 密码泄漏到 chat log 和 shell history

`esxi-skill` 把 LLM 用 `govc` 时需要的"运维常识"打包：触发规则、安全护栏、按平台分的凭据管理、常见任务 recipe、故障排查参考。

## 能干什么

- **VM 生命周期**：创建 / 克隆（含 linked + cloud-init）/ 开关机 / 销毁 / 迁移
- **快照**：创建 / 回滚 / 合并，带"长生命快照会膨胀"警告
- **存储**：浏览 / 上传下载 / 容量报告
- **主机**：维护模式 / esxcli 透传 / 服务控制
- **网络**：vSwitch / DVS / port group
- **OVA/OVF**：导入 / 导出
- **批量操作**：健康检查、批量迁移、CSV 驱动建机

## 设计亮点

- **只读凭据消费者** —— skill 永不写密码。用户用 OS 原生命令存（macOS `security` / Linux `secret-tool` / Windows DPAPI PowerShell），skill 只读
- **跨平台**：macOS（主力，已测）、Linux（libsecret）、Windows（DPAPI 文件）
- **零 pip 依赖** —— 纯 Python 3.7+ stdlib
- **单一 Python 入口** [`esxi/scripts/esxi.py`](esxi/scripts/esxi.py)，三个子命令：`preflight` / `setup` / `g`
- **`os.execvpe` 包装器** —— Python 进程被 `govc` 替换，密码只在 `govc` 进程 env 里活几毫秒

## 快速安装

```bash
git clone https://github.com/<owner>/esxi-skill.git
# 然后把 skill 子目录 symlink 到你的 agent skills 目录：
ln -s "$(pwd)/esxi-skill/esxi" ~/.claude/skills/esxi          # Claude Code
ln -s "$(pwd)/esxi-skill/esxi" ~/.codex/skills/esxi           # Codex CLI
```

完整安装步骤 + 按平台的前置依赖：**[SETUP.md](SETUP.md)**

## 目录结构

```
esxi-skill/                       ← 本仓库（"项目"层）
├── README.md                     # 英文项目说明
├── README.zh-CN.md               # ← 你在这（中文项目说明）
├── SETUP.md                      # 安装与首次配置
├── CHANGELOG.md                  # 版本变更
├── CONTRIBUTING.md               # 怎么提 issue / PR
├── VERSION
├── LICENSE                       # MIT
├── .github/workflows/            # CI: markdown + python 语法检查
└── esxi/                         ← skill 本身（这部分会被安装）
    ├── SKILL.md                  # Claude 加载的 skill 指令
    ├── scripts/
    │   └── esxi.py               # 包装器：preflight / setup / g
    ├── references/               # 渐进式加载的文档
    │   ├── govc-reference.md
    │   ├── common-operations.md
    │   ├── setup-commands.md
    │   └── troubleshooting.md
    └── evals/
        └── evals.json            # 测试 prompts（需要真 ESXi 才能跑）
```

## 当前状态

- **macOS**：在真 ESXi 8.0.1 上跑通端到端
- **Linux**：代码路径完整，**未在真 Linux 主机验证**
- **Windows**：DPAPI 文件方案设计 + code review 过，**未在真 Windows 验证**

变更历史见 **[CHANGELOG.md](CHANGELOG.md)**

## 贡献

欢迎提 PR — bug 报告、新 recipe、Linux/Windows 验证、references 内容补充。详见 **[CONTRIBUTING.md](CONTRIBUTING.md)**

## 许可

MIT — 详见 [LICENSE](LICENSE)
