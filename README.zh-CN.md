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

1. **安装 govc**
   ```bash
   # macOS
   brew install govc

   # Linux
   curl -L -o - "https://github.com/vmware/govmomi/releases/latest/download/govc_$(uname -s)_$(uname -m).tar.gz" \
     | sudo tar -C /usr/local/bin -xvzf - govc

   govc version
   ```

2. **保存凭据**（推荐 macOS Keychain）
   ```bash
   security add-generic-password -a root -s govc-esxi.lab -w '你的密码' -U
   ```

3. **设置环境变量**（加到 `~/.zshrc`）
   ```bash
   export GOVC_URL='esxi.lab'                   # 或 vCenter FQDN
   export GOVC_USERNAME='root'                  # 或 administrator@vsphere.local
   export GOVC_INSECURE=1                       # 使用自签证书时需要
   export GOVC_DATACENTER='ha-datacenter'       # ESXi 默认值
   export GOVC_PASSWORD=$(security find-generic-password -a "$GOVC_USERNAME" -s "govc-$GOVC_URL" -w 2>/dev/null)
   ```

4. **（可选）在 Claude Code 设置里白名单 govc**
   ```json
   // .claude/settings.json
   {
     "permissions": {
       "allow": ["Bash(govc *)"]
     }
   }
   ```

5. **验证**
   ```bash
   govc about
   govc ls
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
