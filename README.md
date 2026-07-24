# 超脑 Super Brain

> AI Agent 认知增强系统 —— 持久记忆、知识图谱、SimHash 语义搜索、自检修复。

中文名「**超脑**」，英文仓库名 `super-brain`。一个给 AI Agent 用的「第二大脑」：跨会话长期记忆、语义检索、知识图谱、自动自检与修复，纯 Python 标准库、零外部依赖。

## 直接访问

- GitHub 仓库：https://github.com/A1m1ng777888/super-brain
- 最新版本：**v3.9.6**

## 核心能力

- **持久记忆引擎**：对话即入库，跨会话不丢上下文
- **知识图谱**：实体关系自动抽取，支持 Mermaid 导出
- **三进制哈希 + RRF 秩融合搜索**：多路召回融合，语义检索更准
- **分类管线 / 感知增强 / 推理引擎**：结构化处理信息
- **自检与修复**：内置 12 项自检，发现问题可 surgical 修补
- **Obsidian 双向同步**：记忆可落地到本地知识库

## 安装（作为 WorkBuddy Skill）

```bash
git clone https://github.com/A1m1ng777888/super-brain.git ~/.workbuddy/skills/super-brain
```

克隆后在 WorkBuddy 中加载 `super-brain` skill 即可使用。

## 许可

MIT —— 见 [LICENSE](LICENSE)。

## 版本历史

详见 [CHANGELOG.md](CHANGELOG.md)。
