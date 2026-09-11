# 超脑 Super Brain

> AI Agent 认知增强系统 —— 持久记忆、知识图谱、遗忘治理、自检修复、本地工作台。

中文名「**超脑**」，英文仓库名 `super-brain`。一个给 AI Agent 用的「第二大脑」：跨会话长期记忆、语义检索、知识图谱、遗忘治理与自动自检，纯 Python 标准库、零外部依赖。

## 直接访问

- GitHub 仓库：https://github.com/A1m1ng777888/super-brain
- 最新版本：**v3.13.1**

## 核心能力

| 能力 | 说明 |
|---|---|
| **持久记忆引擎** | 对话即入库，跨会话不丢上下文；写入采用「原子替换 + 冲突降级」双路径，并发写不丢 |
| **BM25 中文检索** | CJK bigram + trigram 分词、unigram 降权；单路 BM25 取代早期被噪声拖垮的多路融合 |
| **知识图谱** | 实体关系自动抽取与自动建图，支持 Mermaid 导出 |
| **遗忘治理** | 遗忘优先级 = 规模 × (1−活跃度) × 衰减因子；三档软切降权，身份/护栏记忆永久豁免 |
| **后台整合（零 LLM）** | 实体归一、近重复合并、冗长压缩、知识更新链；只出 proposal，永不自动 apply |
| **相对门控** | 阈值取候选池 salience 排名第 k 高，分布漂移免重标（scale-free） |
| **本地工作台** | 纯标准库 HTTP 服务，默认只绑 127.0.0.1；看板 / 体检趋势 / 暗色模式 / 移动端自适应 |
| **自检与修复** | 内置 12 项自检，发现问题可 surgical 修补 |
| **Obsidian 双向同步** | 记忆可落地到本地知识库 |

## 安装（作为 WorkBuddy Skill）

```bash
git clone https://github.com/A1m1ng777888/super-brain.git ~/.workbuddy/skills/super-brain
```

克隆后在 WorkBuddy 中加载 `super-brain` skill 即可使用。

首次使用建议先跑一次自检确认环境ok：

```bash
python scripts/superbrain.py selfcheck
python scripts/superbrain.py version      # 确认版本与数据目录
```

## 数据目录

默认 `~/.workbuddy/super-brain/`，可用环境变量 `SUPERBRAIN_DATA_DIR` 覆盖。
记忆按 workspace 隔离存放于 `workspaces/<name>/`；workspace 名默认由当前工作目录向上查找 `.workbuddy/` 标记推导。

> ⚠️ **在含 `.workbuddy` 的目录树下运行测试要注意**：`resolve_workspace()` 会把 cwd 所属项目解析成 workspace，测试将读写该项目的真实记忆。跑测试请用中性目录，或显式设置 `SUPERBRAIN_DATA_DIR` 指向临时目录。

## 许可

MIT —— 见 [LICENSE](LICENSE)。

## 版本历史

详见 [CHANGELOG.md](CHANGELOG.md)。
