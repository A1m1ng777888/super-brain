# Super Brain (超脑) — AI Agent 认知增强系统

[![Version](https://img.shields.io/badge/version-2.0.0-blue)](https://github.com/A1m1ng777888/super-brain)
[![Python](https://img.shields.io/badge/python-3.8+-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-120%20PASS-brightgreen)](scripts/test_v2.py)
[![SkillOpt](https://img.shields.io/badge/SkillOpt-self--evolution-purple)](https://github.com/microsoft/SkillOpt)

为 AI Agent 提供**持久记忆、知识图谱、语义搜索、自检修复、自我进化**五大核心能力，解决大模型 Agent 的八大先天缺陷。

> **v2.0.0 重大更新**：融合 Microsoft SkillOpt 自我进化引擎，技能文档可像神经网络一样自动优化。

---

## 目录

- [特性](#特性)
- [v2.0.0 新特性](#v200-新特性)
- [快速开始](#快速开始)
- [核心概念](#核心概念)
- [命令参考](#命令参考)
- [架构设计](#架构设计)
- [测试](#测试)
- [配置](#配置)
- [路线图](#路线图)
- [贡献](#贡献)
- [许可证](#许可证)

---

## 特性

| 特性 | 说明 |
|------|------|
| **持久记忆引擎** | 跨会话存储/检索记忆，支持置信度、实体关联、自动合并 |
| **知识图谱** | 构建实体-关系网络，支持多跳查询、实体对齐 |
| **SimHash 语义搜索** | 64位 SimHash + TF-IDF 混合检索，纯标准库实现 |
| **五项自检系统** | 一致性/时效性/完整性/孤立节点/重复数据自动诊断 |
| **SkillOpt 自我进化** 🆕 | 自动复盘执行轨迹、验证优化技能文档（基于 Microsoft SkillOpt） |
| **执行轨迹记录** 🆕 | 三信号源加权反馈（显式/隐式/验证集），支持自我进化数据采集 |
| **Workspace 隔离** | 多项目独立知识空间，互不干扰 |
| **Token 优化** | 上下文压缩、按需加载，增强能力同时降低 Token 消耗 |
| **零依赖** | 纯 Python 标准库，无需 pip install |
| **跨平台** | Windows / macOS / Linux 均可运行 |

---

## v2.0.0 新特性

### SkillOpt 自我进化引擎

基于 [Microsoft SkillOpt](https://github.com/microsoft/SkillOpt) 论文实现，让技能文档像训练神经网络一样自我进化：

```
执行 (rollout) → 反思 (reflect) → 编辑 (edit) → 验证门控 (gate) → 更新 (update)
```

核心机制：
- **文本学习率**：控制每次编辑幅度，防止覆写有用规则
- **验证门控**：只在留出验证集上分数严格提升才接受更新
- **拒绝编辑缓冲**：记住有害方向，避免重复错误
- **三信号加权反馈**：显式反馈 (×1.0) + 隐式信号 (×0.3) + 验证集 (×0.5)

### 新增命令

```bash
# 优化任意技能
python scripts/superbrain.py skillopt optimize --skill-path path/to/SKILL.md --tasks tasks.json

# 超脑自我进化
python scripts/superbrain.py skillopt self-evolve --epochs 3

# 查看优化历史
python scripts/superbrain.py skillopt history

# 执行轨迹记录
python scripts/superbrain.py trace record --command "memory add" --feedback satisfied
python scripts/superbrain.py trace stats
```

---

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/A1m1ng777888/super-brain.git
cd super-brain

# 初始化（创建数据目录）
python scripts/superbrain.py init

# 验证安装
python scripts/test_superbrain.py   # v1 核心测试 (49项)
python scripts/test_v2.py           # v2 新功能测试 (71项)
```

预期输出：120 项测试全部 PASS。

### 第一步

```bash
# 添加一条记忆
python scripts/superbrain.py memory add \
  --type preference \
  --content "用户偏好暗色主题 IDE" \
  --entity "user" \
  --confidence 0.95

# 搜索记忆
python scripts/superbrain.py memory search "暗色主题"

# 查看统计
python scripts/superbrain.py stats

# 查看版本
python scripts/superbrain.py version
```

---

## 核心概念

### 记忆类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `fact` | 客观事实 | "项目使用 Python 3.13" |
| `preference` | 用户偏好 | "用户偏好简洁回复" |
| `event` | 发生的事件 | "2026-06-26 完成了超脑开发" |
| `relationship` | 实体关联 | "项目 Alpha 依赖于 React" |
| `task` | 待办事项 | "需要完成 Token 监测仪表盘" |
| `decision` | 已做出的决策 | "选择 SimHash 而非向量数据库" |
| `context` | 背景信息 | "用户是视觉设计专业毕业生" |

### Workspace（工作区）

不同项目拥有独立的知识空间：

```bash
# 创建项目专用工作区
python scripts/superbrain.py workspace create --name "项目-Alpha"

# 切换到该工作区
python scripts/superbrain.py workspace switch --name "项目-Alpha"

# 列出所有工作区
python scripts/superbrain.py workspace list
```

### 执行轨迹 (Trace) 🆕

记录每次 Skill 调用的完整过程，用于自我进化：

```bash
# 记录执行轨迹
python scripts/superbrain.py trace record \
  --command "memory add" \
  --input "用户偏好暗色主题" \
  --output "记忆已添加" \
  --explicit-feedback satisfied

# 查看轨迹统计
python scripts/superbrain.py trace stats
```

---

## 命令参考

### 初始化

| 命令 | 说明 |
|------|------|
| `init` | 初始化数据目录和默认 Workspace |
| `version` | 显示版本信息 |

### 记忆管理

| 命令 | 说明 |
|------|------|
| `memory add` | 添加记忆 |
| `memory list` | 列出记忆（支持 --type/--entity/--status 过滤） |
| `memory get --id ID` | 按 ID 获取单条记忆 |
| `memory search "查询"` | 语义搜索记忆 |
| `memory context "查询"` | Token 优化的上下文检索 |
| `memory update --id ID` | 更新记忆 |
| `memory delete --id ID` | 删除记忆 |
| `memory merge --id1 ID1 --id2 ID2` | 合并重复记忆 |
| `memory stats` | 记忆统计 |

### 知识图谱

| 命令 | 说明 |
|------|------|
| `graph add-node --name N --type T` | 添加节点 |
| `graph add-edge --source S --target T --type T` | 添加边 |
| `graph query "实体" --depth N` | 查询关联（支持多跳） |
| `graph list` | 列出节点或边 |
| `graph delete --name N` | 删除节点 |
| `graph stats` | 图谱统计 |

### 自检系统

| 命令 | 说明 |
|------|------|
| `selfcheck` | 运行五项诊断 |
| `selfcheck --fix` | 运行诊断并自动修复安全项 |
| `health` | 查看健康评分历史 |

### Workspace 管理

| 命令 | 说明 |
|------|------|
| `workspace list` | 列出所有 Workspace |
| `workspace create --name N` | 创建 Workspace |
| `workspace switch --name N` | 切换 Workspace |

### 自我进化 🆕

| 命令 | 说明 |
|------|------|
| `skillopt status` | 查看进化引擎状态 |
| `skillopt optimize` | 优化指定技能文档 |
| `skillopt self-evolve` | 超脑自我进化 |
| `skillopt history` | 查看优化历史 |
| `skillopt rollback` | 回滚到历史版本 |

### 执行轨迹 🆕

| 命令 | 说明 |
|------|------|
| `trace record` | 记录执行轨迹 |
| `trace list` | 列出轨迹记录 |
| `trace stats` | 轨迹统计 |
| `trace filter` | 按条件过滤轨迹 |
| `trace feedback` | 追加显式反馈 |
| `trace export` | 导出轨迹（用于优化） |

---

## 架构设计

四层十模块（v2 新增自我进化层）：

```
┌─────────────────────────────────────────────┐
│           交互层 (SKILL.md)               │
│  触发规则 │ 工作流 │ 自我进化触发        │
├─────────────────────────────────────────────┤
│           自我进化层 (v2 新增)              │
│  ┌──────────┐  ┌──────────┐            │
│  │SkillOpt  │  │ 轨迹记录  │            │
│  │ 进化引擎  │  │  模块    │            │
│  └──────────┘  └──────────┘            │
├─────────────────────────────────────────────┤
│           核心认知层                         │
│  ┌──────────┐  ┌──────────┐            │
│  │ 记忆引擎  │  │ 知识图谱  │            │
│  └──────────┘  └──────────┘            │
│  ┌──────────┐  ┌──────────┐            │
│  │ 语义检索  │  │ 自检系统  │            │
│  └──────────┘  └──────────┘            │
├─────────────────────────────────────────────┤
│           存储与基础设施层                   │
│  Workspace隔离  │  Token优化引擎          │
└─────────────────────────────────────────────┘
```

详见 [`references/architecture.md`](super-brain/references/architecture.md)。

---

## 集成方式

### 方式一：WorkBuddy 技能

将 `super-brain/` 文件夹放入 `~/.workbuddy/skills/`：

```
~/.workbuddy/skills/super-brain/
```

WorkBuddy 会自动识别 `SKILL.md` 中的触发词。

### 方式二：独立 CLI 工具

任意 Python 环境均可直接调用：

```python
import sys
sys.path.insert(0, "super-brain/scripts")
from sb_memory import add_memory, search_memories

add_memory(
    content="这是一条记忆",
    mem_type="fact",
    entity="project-x",
    confidence=0.9
)
results = search_memories("记忆", limit=5)
```

### 方式三：MCP Server（即将支持）

包装为 MCP Server 后，任何支持 MCP 的 Agent 平台均可调用。

---

## 测试

```bash
cd scripts
python test_superbrain.py   # v1 核心测试 (49项)
python test_v2.py           # v2 新功能测试 (71项)
```

测试覆盖：
- SimHash 确定性/区分度
- 中英文混合分词
- 记忆 CRUD + 过滤 + 搜索
- 知识图谱节点/边/查询
- 自检系统五项检查
- 重复检测（两阶段策略）
- Workspace 管理
- **SkillOpt 优化循环** 🆕
- **三信号加权反馈** 🆕
- **编辑预算衰减** 🆕
- **验证门控机制** 🆕
- **执行轨迹记录/过滤/导出** 🆕

---

## 配置

环境变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SUPERBRAIN_DATA_DIR` | 数据目录路径 | `~/.workbuddy/super-brain` |

配置文件 (`config.json`):

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `version` | 版本号 | `2.0.0` |
| `skillopt.learning_rate` | 文本学习率 | `0.3` |
| `skillopt.batch_size` | 批次大小 | `5` |
| `skillopt.validation_threshold` | 验证门控阈值 | `0.05` |

---

## 路线图

| 优先级 | 功能 | 状态 |
|--------|------|------|
| ~~P0~~ | ~~SkillOpt 自我进化引擎~~ | ✅ v2.0.0 已完成 |
| P1 | 感知增强系统（主动提醒） | 📋 规划中 |
| P2 | 向量化检索升级（可选嵌入模型） | 📋 规划中 |
| P3 | Token 监测仪表盘 | 📋 规划中 |
| P4 | 多模态记忆（图片/文件摘要） | 📋 规划中 |
| P5 | 记忆导出/跨设备同步 | 📋 规划中 |

---

## 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

---

## 许可证

[MIT License](LICENSE)

---

## 致谢

- **Microsoft SkillOpt** — 自我进化框架 (https://github.com/microsoft/SkillOpt)
- SimHash 算法：Moses Charikar
- TF-IDF：经典信息检索算法
- 设计灵感：认知科学中的"记忆层级模型"

---

**v2.0.0** · 2026-06-27 · 纯本地 · 零网络 · 零外部依赖
