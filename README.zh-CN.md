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

## 配置

这个 skill 第一次使用时会**自动完成所有前置工作**，你不用提前准备。

当你对 Claude 说"列出 ESXi 上的所有虚拟机"之类的话，它会：

1. 跑 `scripts/preflight.sh` 检测缺什么
2. 如果缺东西，Claude 会**通过聊天问你**：
   - ESXi / vCenter 地址
   - 用户名
   - 是不是自签证书？（yes/no）
   - 密码
3. 跑 `scripts/setup.sh` 完成：
   - 安装 `govc`（macOS 用 brew，Linux 用 GitHub 发布包）
   - 写配置到 `~/.config/esxi-skill/default.env`
   - 密码存到 macOS Keychain（不明文落地）
   - 用 `govc about` 验证连接
4. 最后用 `scripts/g` 包装器跑你的原始请求

### 手动初始化（可选）

```bash
echo '你的密码' | ~/.claude/skills/esxi/scripts/setup.sh 'esxi.lab' 'root' 1 'ha-datacenter'
```

四个位置参数：`<host> <user> <insecure:1|0> <datacenter>`。密码通过 stdin 传，不会进 shell history 或进程列表。

### 多 profile

有多个 ESXi / vCenter 时用 `ESXI_PROFILE`：

```bash
echo 'pw' | ESXI_PROFILE=prod ~/.claude/skills/esxi/scripts/setup.sh 'vcenter.prod' 'administrator@vsphere.local' 0
echo 'pw' | ESXI_PROFILE=lab  ~/.claude/skills/esxi/scripts/setup.sh 'esxi.lab'      'root'                       1

# 后续使用
ESXI_PROFILE=prod ~/.claude/skills/esxi/scripts/g ls vm
ESXI_PROFILE=lab  ~/.claude/skills/esxi/scripts/g ls vm
```

### （可选）在 Claude Code 设置里白名单

```json
// .claude/settings.json
{
  "permissions": {
    "allow": [
      "Bash(~/.claude/skills/esxi/scripts/g *)",
      "Bash(~/.claude/skills/esxi/scripts/preflight.sh*)"
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
├── scripts/
│   ├── preflight.sh                  # 状态检测，JSON 输出
│   ├── setup.sh                      # 装 govc + 存凭据 + 验证连接
│   └── g                             # govc 包装器（自动读 Keychain 密码）
└── references/
    ├── govc-reference.md             # 按分类的完整命令速查
    ├── common-operations.md          # 12 个实战 recipe：健康检查、克隆+cloud-init、批量迁移等
    └── troubleshooting.md            # 常见错误及修复方法
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
