[English](README.md) | **中文**

# esxi-skill

一个用于管理 **VMware ESXi / vSphere** 的 [Claude Code](https://claude.ai/code) 技能，基于 `govc` CLI。

专为 LLM 驱动的自动化设计：结构化 JSON 输出、启动迅速、原生支持 Unix 工具链。覆盖虚拟机生命周期、快照、存储、主机、网络、OVA 导入导出和批量操作。

## 为什么需要一个专门的 skill

`govc` 功能强大，但有 400+ 个命令分布在 40+ 个分类下。LLM 在没有上下文时要么幻觉语法，要么退回到不合适的工具（PowerCLI、手动 SSH）。这个 skill 打包了：

- **触发指引** —— Claude 知道什么时候该用它（虚拟机操作、ESXi 问题、vCenter 自动化）
- **安全规则** —— 破坏性操作需要明确确认；快照不等于备份
- **实战 recipe** —— 常用 playbook（健康检查、克隆 + cloud-init、批量创建、维护模式）
- **故障排查** —— 常见错误及解决方案
- **完整命令参考** —— 每个 `govc` 分类的参数和示例

## 安装

把本仓库克隆到 Claude Code 的 skills 目录（clone URL 在本仓库 GitHub 页面上）。

- **项目级**：克隆到 `<your-project>/.claude/skills/esxi`
- **全局（用户级）**：克隆到 `~/.claude/skills/esxi`

## 环境要求

- **Python 3.7+**（macOS 和大部分 Linux 自带；Windows 用 `winget install Python.Python.3`）
- 其他依赖（govc 二进制、Keychain 设置）由 skill 自动处理

## 配置

整个 skill 是一个 Python 模块 `esxi.py`。你对 Claude 说"列出 ESXi 上所有虚拟机"（还没配置过时）：

| 步骤 | 谁来做 | 命令 |
|---|---|---|
| 1. preflight 检测 | Claude 自动 | `python3 esxi.py preflight` |
| 2. 问 4 个非敏感字段 | Claude 在 chat 问你 | 地址/用户名/证书/datacenter |
| 3. 装 `govc` + 写配置 | Claude 自动 | `python3 esxi.py setup --host … --user … …` |
| 4. 存密码 | **你自己**在终端跑 | 第 3 步打印的命令（按 OS 不同） |
| 5. 再次 preflight + 列 VM | Claude 自动 | `python3 esxi.py preflight && python3 esxi.py g ls vm` |

第 4 步是唯一手动的部分。命令按你的 OS 自动选：

- **macOS**: `security add-generic-password -a <user> -s govc-<host> -U -w`（原生交互提示）
- **Linux**（有 libsecret）: `secret-tool store …`
- **Linux**（无 libsecret）: `read -rs` → `chmod 600` 文件
- **Windows**: `keyring`（Windows Credential Manager）装在独立 venv `%LOCALAPPDATA%\esxi-skill\venv\` 里 —— **不做全局 pip 安装**。provision 失败时回退到 DPAPI 加密文件。

### 🔐 安全设计

- Claude 自动做非敏感工作（节省打字），但把密码那一步交还给你 —— 凭据永远不经过 LLM、聊天记录、或 Claude 启动的任何进程
- `esxi.py g` 用 `os.execvpe` 把 Python 进程**替换**为 govc；密码只存在于 govc 进程的环境里，Python 进程在 exec 后就不存在了

完整 OS 命令参考见 [references/setup-commands.md](references/setup-commands.md)。

### 多 profile

多个 ESXi / vCenter 时用 `--profile` 或 `ESXI_PROFILE`：

```bash
# 创建两个 profile
python3 ~/.claude/skills/esxi/esxi.py --profile prod setup --host vcenter.prod --user administrator@vsphere.local --insecure 0
python3 ~/.claude/skills/esxi/esxi.py --profile lab  setup --host esxi.lab      --user root                       --insecure 1

# 使用（每个 profile 要各自完成一次 setup 打印的密码步骤）
python3 ~/.claude/skills/esxi/esxi.py --profile prod g ls vm
ESXI_PROFILE=lab python3 ~/.claude/skills/esxi/esxi.py g ls vm
```

### （可选）在 Claude Code 设置里白名单

```json
// .claude/settings.json
{
  "permissions": {
    "allow": [
      "Bash(python3 ~/.claude/skills/esxi/esxi.py *)"
    ]
  }
}
```

## 怎么触发

跟 Claude Code 说这类话：

- "列出 ESXi 上所有虚拟机"
- "更新 web-01 前帮我打个快照"
- "哪些 datastore 使用率超过 80%？"
- "把 esxi1.lab 上所有虚拟机迁走，我要让它进维护模式"
- "从 ubuntu-template 克隆一个叫 app-prod 的虚拟机，4 核 8G"

Claude 会直接通过 Bash 工具调用 govc，同时遵守 skill 里的安全规则（先读后改、破坏性操作先确认、优先用 JSON 输出解析）。

## 目录结构

```
esxi-skill/
├── SKILL.md                          # 主 skill —— 触发时加载
├── README.md                         # 英文说明
├── README.zh-CN.md                   # 中文说明（本文件）
├── LICENSE
├── esxi.py                           # 单一 Python 入口（所有子命令）
└── references/
    ├── govc-reference.md             # 按分类的完整命令速查
    ├── common-operations.md          # 12 个实战 recipe：健康检查、克隆+cloud-init、批量迁移等
    ├── setup-commands.md             # 各操作系统的密码存储命令参考
    └── troubleshooting.md            # 常见错误及修复方法
```

### 使用速查

```bash
python3 ~/.claude/skills/esxi/esxi.py preflight                        # JSON 状态
python3 ~/.claude/skills/esxi/esxi.py setup --host X --user root ...   # 装 govc + 写配置 + 打印密码命令
python3 ~/.claude/skills/esxi/esxi.py g ls vm                          # 跑任意 govc 命令
python3 ~/.claude/skills/esxi/esxi.py --profile lab g vm.info ...      # 用非默认 profile
```

## 安全模型

这个 skill 把 ESXi 当作**生产级关键基础设施**对待。破坏性操作（`vm.destroy`、`snapshot.remove`、`datastore.rm`、最后一台 ESXi 的维护模式）永远需要用户明确确认。Claude 会：

1. 任何修改前先执行 `vm.info` 让你看清楚目标。
2. 把即将执行的命令完整打印出来再跑。
3. 不经过确认绝不 `vm.destroy`。
4. 看到长生命周期快照会警告（磁盘膨胀、性能下降）。

详见 `SKILL.md` § *Safety Rules*。

## 什么场景**不该**用这个 skill

- **vSAN 深度管理** → 用 PowerCLI 或 vSAN REST
- **NSX-T / HCX** → 用各自的专用 CLI
- **复杂的幂等状态管理** → 用 Terraform 的 `vsphere` provider
- **只读监控大盘** → 用 Grafana + VMware exporter

这些场景：用 govc 处理 90% 的日常操作，剩下 10% 交给专用工具。

## 许可

MIT。见 [LICENSE](LICENSE)。

## 贡献

欢迎 PR。如果你有一个反复使用但还没在 `references/common-operations.md` 里的 ESXi recipe，欢迎提 issue 或 PR。
