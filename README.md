# Super Brain (超脑) — AI Agent 认知增强系统

[![Version](https://img.shields.io/badge/version-3.6.0-blue)](https://github.com/A1m1ng777888/super-brain)
[![Python](https://img.shields.io/badge/python-3.8+-green)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-74%20PASS-brightgreen)](super-brain/scripts/test_superbrain.py)
[![Architecture](https://img.shields.io/badge/architecture-5%E5%B1%8417%E6%A8%A1%E5%9D%97-orange)](super-brain/references/architecture.md)

为 AI Agent 提供**持久记忆、知识图谱、语义搜索、自动推理、关联挖掘、对话即入库、分类管线、感知增强、子Agent编排**九大核心能力，构建从感知到执行编排的完整认知增强闭环。

> **v3.6.0**：全局工作空间门控层（Global Workspace Gating）— 受 Anthropic《A Global Workspace in Language Models》(2026-07-06) 启发，记忆分冷存储与活跃工作空间两层，按显著度晋升、容量上限约束、链式点燃实现 Ignition；新增 `reasoning_intermediate` 类型与 `reason capture` 中间推理捕获；新增 `gating` 子命令与 `memory context --workspace-only`。25 项新测试 + 49 项回归全通过。
>
> **v3.5.0**：Token ROI 仪表盘全面升级（30天趋势图 + 负 ROI 诊断 + 交互式 HTML 看板）。
>
> **v3.4.x**：P0 数据安全修复（read_memories 文件损坏自动备份防丢失）。
>
> **v3.3.0**：Goal Continuation 续跑机制。
>
> **v3.2.2**：前置编配评估提升至 SOUL.md 始终在线 — Agent 收到任何任务时自主判断是否需要子Agent编配，不需用户说"拆"。
>
> **v3.2.0**：子Agent编排器 — 4维度复杂度评估 + 任务分解 + 6套工具画像 + 预算熔断 + 失败隔离。
>
> **v3.1.0**：反污染规则 + Obsidian双向同步 + 冷启动门控 + 退场生命周期 + 会话生命周期协议。

---

## 目录

- [特性总览](#特性总览)
- [v3.0.0 八大升级](#v300-八大升级)
- [快速开始](#快速开始)
- [核心概念](#核心概念)
- [命令参考](#命令参考)
- [架构设计](#架构设计)
- [测试](#测试)
- [配置](#配置)
- [路线图](#路线图)
- [集成方式](#集成方式)
- [版本历史](#版本历史)
- [贡献](#贡献)
- [许可证](#许可证)

---

## 特性总览

| 特性 | 说明 | 引入版本 |
|------|------|----------|
| **持久记忆引擎** | 跨会话存储/检索记忆，支持置信度、实体关联、自动合并、错别字纠偏、表达学习 | v1.0 |
| **知识图谱** | 构建实体-关系网络，支持多跳查询、实体对齐 | v1.0 |
| **语义搜索** | 六通道融合检索（TF-IDF + 关键词 + SimHash + 三进制哈希 + 模糊匹配 + 字词网络） | v1.0→v3.0 |
| **自检系统** | 六项诊断（一致性/时效性/完整性/孤立节点/重复数据/时间有效性）+ 自动修复 | v1.0→v2.1 |
| **SkillOpt 自我进化** | 自动复盘执行轨迹、验证门控优化技能文档 | v2.0 |
| **执行轨迹记录** | 三信号源加权反馈（显式/隐式/验证集），自我进化数据采集 | v2.0 |
| **推理引擎** | 关键点提取 + 因果分析 + 结论推导 + 决策支持 | v3.0 |
| **纠缠场** | 三通道融合关联挖掘（哈希相似度 + 共现频率 + 图谱拓扑） | v3.0 |
| **上下文记忆** | 凝聚聚类 + 跨会话线程追踪 + 按日期召回 | v3.0 |
| **感知增强** | 新颖性检测 + 信息价值评估 → learn/query/skip 决策 | v3.0 |
| **分类管线** | 定义类(365天)/闲聊类(7天)/混合类(90天)差异化衰减 | v3.0 |
| **本地长期记忆** | 对话即入库 + 零成本 O(1) 检索 + 预计算索引 | v3.0 |
| **三进制哈希字词网络** | 3^64 状态空间，~1.9 万倍区分力提升 | v3.0 |
| **反污染规则** | confidence<0.7 决策不过库、未解决错误不过库、SimHash≥0.92 去重 | v3.1 |
| **Obsidian 双向同步** | JSON→.md+[[wikilinks]] 导出 + 反向同步回写 | v3.1 |
| **冷启动门控** | memory<15 AND session<3 → 仅感知+存储，达标后自动激活 | v3.1 |
| **会话生命周期协议** | T1 启动(搜索+简报) / T2 收尾(反污染+入库) / T3 定期(7维健康扫描) | v3.1 |
| **子Agent编排器** | 4维度评估 + 任务分解 + 6套工具画像 + 预算熔断 + 失败隔离 | v3.2 |
| **Workspace 隔离** | 多项目独立知识空间，互不干扰 | v1.0 |
| **Token 优化** | 上下文压缩、按需加载、零成本检索 | v1.0 |
| **零依赖** | 纯 Python 标准库，无需 pip install | v1.0 |
| **跨平台** | Windows / macOS / Linux 均可运行 | v1.0 |

---

## v3.0.0 八大升级

### 1. 三进制哈希字词网络

传统 SimHash 是二进制（0/1），超脑 v3.0 引入**三进制哈希**（-1/0/+1），状态空间从 2^64 扩展到 3^64（~1.9 万倍区分力提升）。配合字词网络，实现更精准的语义区分。

### 2. 六通道融合搜索

六路并行检索，加权融合排序：

| 通道 | 权重 | 技术 |
|------|------|------|
| TF-IDF | 0.35 | 词频-逆文档频率 |
| 关键词 | 0.20 | 精确匹配 + 部分匹配 |
| SimHash | 0.15 | 64位相似度 |
| 三进制哈希 | 0.12 | 字词网络桶匹配 |
| 模糊匹配 | 0.10 | Levenshtein 编辑距离 |
| 字词网络 | 0.08 | 共现频率图 |

### 3. 分类管线

不同类型的信息有不同的"保质期"：

| 类型 | 半衰期 | 典型内容 | 归档阈值 |
|------|--------|----------|----------|
| 定义类 | 365 天 | 概念、事实、规则、偏好 | 衰减分 < 0.15 |
| 闲聊类 | 7 天 | 寒暄、语气词、临时应答 | 衰减分 < 0.30 |
| 混合类 | 90 天 | 半事实半讨论 | 衰减分 < 0.20 |

衰减公式：`retention = 0.5^(age/half_life) × access_boost × confidence_boost`

### 4. 感知增强

自动判断信息该「学」还是该「查」：

```
输入文本 → 信息价值评估 → 新颖性检测 → 决策(learn/query/both/skip)
```

评估维度：分类、密度、特异性、可行动性、长度惩罚。

### 5. 推理引擎

```bash
# 提炼关键点
SB reason extract --text "长文本..."

# 梳理逻辑链
SB reason logic --text "前提A，前提B..."

# 推导结论
SB reason conclude --text "观察数据..."

# 辅助决策
SB reason decide --options "选项A|选项B|选项C"
```

### 6. 纠缠场

三通道融合挖掘隐含关联：

- **哈希相似度通道**：三进制哈希桶重叠度
- **共现频率通道**：同一上下文中同时出现的概念
- **图谱拓扑通道**：知识图谱中的路径关系

### 7. 上下文记忆

- **凝聚聚类**：同主题记忆自动归拢
- **跨会话线程追踪**：`trace` 命令追溯历史对话线程
- **按日期召回**：`recall` 按时间范围召回上下文

### 8. 本地长期记忆

- **对话即入库**：`ingest` 自动从对话文本提取、分类、存储
- **零成本检索**：预计算三进制哈希索引，O(1) 查找
- **跨会话关联**：倒排索引 + 哈希桶双索引

---

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/A1m1ng777888/super-brain.git
cd super-brain

# 初始化（创建数据目录）
python super-brain/scripts/superbrain.py init

# 验证安装
python super-brain/scripts/test_superbrain.py   # v1 核心测试 (49项)
python super-brain/scripts/test_v2.py           # v2 新功能测试 (71项)
python super-brain/scripts/test_v3.py           # v3 新功能测试 (61项)
```

预期输出：181 项测试全部 PASS。

### 第一步

```bash
# v3.0 对话即入库 — 自动感知+提取+存储
python super-brain/scripts/superbrain.py longterm ingest \
  --text "项目使用 TypeScript strict 模式，全局一致性检查"

# 自动存储（记忆引擎入口）
python super-brain/scripts/superbrain.py memory auto-store \
  --text "用户偏好暗色主题 IDE"

# 六通道融合搜索
python super-brain/scripts/superbrain.py memory search "暗色主题"

# 推理引擎 — 提炼关键点
python super-brain/scripts/superbrain.py reason extract \
  --text "超脑v3.0新增了三进制哈希、六通道搜索、分类管线..."

# 纠缠场 — 挖掘关联
python super-brain/scripts/superbrain.py entangle mine \
  --concept "三进制哈希"

# 查看统计
python super-brain/scripts/superbrain.py stats

# 查看版本
python super-brain/scripts/superbrain.py version
```

---

## 核心概念

### 记忆类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `fact` | 客观事实 | "项目使用 Python 3.13" |
| `preference` | 用户偏好 | "用户偏好简洁回复" |
| `event` | 发生的事件 | "2026-06-29 完成了超脑 v3.0.0" |
| `relationship` | 实体关联 | "项目 Alpha 依赖于 React" |
| `task` | 待办事项 | "需要完成 Token 监测仪表盘" |
| `decision` | 已做出的决策 | "选择三进制哈希而非向量数据库" |
| `context` | 背景信息 | "用户是视觉设计专业毕业生" |

### Workspace（工作区）

不同项目拥有独立的知识空间：

```bash
python super-brain/scripts/superbrain.py workspace create --name "项目-Alpha"
python super-brain/scripts/superbrain.py workspace switch --name "项目-Alpha"
python super-brain/scripts/superbrain.py workspace list
```

### 记忆双时间机制（v2.1.0 引入）

每条记忆携带时间生命周期字段：

| 字段 | 说明 |
|------|------|
| `valid_from` | 记忆生效时间 |
| `valid_until` | 记忆失效时间（null = 永久有效） |
| `replaces` | 替代了哪条记忆的 ID |
| `replaced_by` | 被哪条记忆替代 |

搜索时自动降权已过期的记忆，检测冲突时自动建立替代链。

---

## 命令参考

### 初始化

| 命令 | 说明 |
|------|------|
| `init` | 初始化数据目录和默认 Workspace |
| `version` | 显示版本信息 |
| `stats` | 全局统计 |

### 记忆管理

| 命令 | 说明 | 版本 |
|------|------|------|
| `memory add` | 添加记忆 | v1.0 |
| `memory list` | 列出记忆（支持 --type/--entity/--status 过滤） | v1.0 |
| `memory get --id ID` | 按 ID 获取单条记忆 | v1.0 |
| `memory search "查询"` | 六通道融合语义搜索 | v1.0→v3.0 |
| `memory context "查询"` | Token 优化的上下文检索 | v1.0 |
| `memory update --id ID` | 更新记忆 | v1.0 |
| `memory delete --id ID` | 删除记忆 | v1.0 |
| `memory merge --id1 ID1 --id2 ID2` | 合并重复记忆 | v1.0 |
| `memory stats` | 记忆统计 | v1.0 |
| `memory auto-store --text "..."` | 自动感知+存储 | v3.0 |

### 推理引擎（v3.0 新增）

| 命令 | 说明 |
|------|------|
| `reason extract --text "..."` | 提炼关键点 |
| `reason logic --text "..."` | 梳理逻辑链 |
| `reason conclude --text "..."` | 推导结论 |
| `reason decide --options "A\|B\|C"` | 辅助决策 |

### 纠缠场（v3.0 新增）

| 命令 | 说明 |
|------|------|
| `entangle mine --concept "..."` | 三通道关联挖掘 |
| `entangle list` | 列出纠缠关系 |
| `entangle stats` | 纠缠统计 |

### 上下文记忆（v3.0 新增）

| 命令 | 说明 |
|------|------|
| `context-mem cluster` | 同主题凝聚聚类 |
| `context-mem trace --topic "..."` | 跨会话线程追踪 |
| `context-mem recall --query "..."` | 按日期/主题召回 |

### 本地长期记忆（v3.0 新增）

| 命令 | 说明 |
|------|------|
| `longterm ingest --text "..."` | 对话即入库 |
| `longterm search "查询"` | 零成本 O(1) 检索 |
| `longterm stats` | 长期记忆统计 |

### 感知增强（v3.0 新增）

| 命令 | 说明 |
|------|------|
| `perceive check --text "..."` | 新颖性检测 |
| `perceive value --text "..."` | 信息价值评估 |
| `perceive decide --text "..."` | learn/query/skip 决策 |

### 分类管线（v3.0 新增）

| 命令 | 说明 |
|------|------|
| `pipeline classify --text "..."` | 分类（定义/闲聊/混合） |
| `pipeline decay --id ID` | 查看衰减得分 |
| `pipeline archive` | 归档已过期记忆 |

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
| `selfcheck` | 运行六项诊断 |
| `selfcheck --fix` | 运行诊断并自动修复安全项 |
| `health` | 查看健康评分历史 |

### Workspace 管理

| 命令 | 说明 |
|------|------|
| `workspace list` | 列出所有 Workspace |
| `workspace create --name N` | 创建 Workspace |
| `workspace switch --name N` | 切换 Workspace |

### 自我进化（v2.0 引入）

| 命令 | 说明 |
|------|------|
| `skillopt status` | 查看进化引擎状态 |
| `skillopt optimize` | 优化指定技能文档 |
| `skillopt self-evolve` | 超脑自我进化 |
| `skillopt history` | 查看优化历史 |
| `skillopt rollback` | 回滚到历史版本 |

### 执行轨迹（v2.0 引入）

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

五层十六模块（v3.0 重构）：

```
┌─────────────────────────────────────────────────────────────┐
│  接口层  │  CLI (superbrain.py)  │  Python API             │
├─────────────────────────────────────────────────────────────┤
│  感知层  │  感知增强 (sb_perception)  │  分类管线 (sb_pipeline) │
├─────────────────────────────────────────────────────────────┤
│  认知层  │  记忆引擎 v3 (sb_memory)  │  推理引擎 (sb_reasoning) │
│         │  上下文记忆 (sb_context)  │  本地长期记忆 (sb_longterm)│
├─────────────────────────────────────────────────────────────┤
│  关联层  │  知识图谱 (sb_graph)     │  纠缠场 (sb_entanglement)│
│         │  语义搜索 v3 (sb_search)                            │
├─────────────────────────────────────────────────────────────┤
│  自愈层  │  自检系统 (sb_selfcheck) │  SkillOpt (sb_skillopt)  │
│         │  执行轨迹记录 (sb_trace)                            │
├─────────────────────────────────────────────────────────────┤
│  存储层  │  Workspace 隔离  │  三进制哈希索引  │  倒排索引    │
│         │  JSON 文件存储                                │
└─────────────────────────────────────────────────────────────┘
```

| 层 | 模块数 | 文件 |
|------|--------|------|
| 感知层 | 2 | `sb_perception.py`, `sb_pipeline.py` |
| 认知层 | 4 | `sb_memory.py`, `sb_reasoning.py`, `sb_context.py`, `sb_longterm.py` |
| 关联层 | 3 | `sb_graph.py`, `sb_entanglement.py`, `sb_search.py` |
| 自愈层 | 3 | `sb_selfcheck.py`, `sb_skillopt.py`, `sb_trace.py` |
| 存储层 | 4 | Workspace 隔离, 三进制哈希索引, JSON 文件存储, 倒排索引 |

详见 [`references/architecture.md`](super-brain/references/architecture.md)。

---

## 测试

```bash
cd super-brain/scripts
python test_superbrain.py   # v1 核心测试 (49项)
python test_v2.py           # v2 新功能测试 (71项)
python test_v3.py           # v3 新功能测试 (61项)
```

累计 181 项测试，覆盖：

- SimHash 确定性/区分度
- 三进制哈希字词网络
- 六通道融合搜索
- 中英文混合分词
- 记忆 CRUD + 过滤 + 搜索 + 自动存储
- 知识图谱节点/边/查询
- 自检系统六项检查
- 重复检测（两阶段策略）
- Workspace 管理
- SkillOpt 优化循环
- 三信号加权反馈
- 编辑预算衰减
- 验证门控机制
- 执行轨迹记录/过滤/导出
- 推理引擎（关键点/逻辑/结论/决策）
- 纠缠场（三通道融合）
- 上下文记忆（聚类/追踪/召回）
- 本地长期记忆（入库/检索）
- 感知增强（学/查决策）
- 分类管线（差异化衰减）
- 记忆双时间机制（冲突检测/替代链）

---

## 配置

环境变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `SUPERBRAIN_DATA_DIR` | 数据目录路径 | `~/.workbuddy/super-brain` |

配置文件 (`config.json`):

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `version` | 版本号 | `3.0.0` |
| `skillopt.learning_rate` | 文本学习率 | `0.3` |
| `skillopt.batch_size` | 批次大小 | `5` |
| `skillopt.validation_threshold` | 验证门控阈值 | `0.05` |

---

## 路线图

| 优先级 | 功能 | 状态 |
|--------|------|------|
| ~~P0~~ | ~~SkillOpt 自我进化引擎~~ | v2.0.0 已完成 |
| ~~P0~~ | ~~反污染规则~~ | v3.1.0 已完成 |
| ~~P0~~ | ~~子Agent编排器~~ | v3.2.0 已完成 |
| ~~P1~~ | ~~感知增强系统~~ | v3.0.0 已完成 |
| ~~P1~~ | ~~本地长期记忆~~ | v3.0.0 已完成 |
| ~~P1~~ | ~~三进制哈希字词网络~~ | v3.0.0 已完成 |
| ~~P1~~ | ~~被动触发修复~~ | v3.0.1 已完成 |
| ~~P1~~ | ~~Obsidian 双向同步~~ | v3.1.0 已完成 |
| ~~P1~~ | ~~冷启动门控~~ | v3.1.0 已完成 |
| ~~P2~~ | ~~退场生命周期~~ | v3.1.0 已完成 |
| ~~P2~~ | ~~会话生命周期协议~~ | v3.1.0 已完成 |
| P3 | Token 监测仪表盘 | 规划中 |
| P4 | 多模态记忆（图片/文件摘要） | 规划中 |
| P5 | 记忆导出/跨设备同步 | 规划中 |

---

## 集成方式

### 方式一：WorkBuddy 技能

将 `super-brain/` 文件夹放入 `~/.workbuddy/skills/`：

```
~/.workbuddy/skills/super-brain/
```

WorkBuddy 会自动识别 `SKILL.md` 中的触发词。v3.0.1 新增 12 个自然语言触发词和 8 种场景自动映射，无需用户显式说"记住"或"回忆"。

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

## 版本历史

| 版本 | 日期 | 里程碑 |
|------|------|--------|
| v1.0.0 | 2026-06-26 | 初始发布：记忆引擎 + 知识图谱 + SimHash 搜索 + 自检系统 |
| v2.0.0 | 2026-06-27 | SkillOpt 自我进化引擎 + 执行轨迹记录 |
| v2.1.0 | 2026-06-28 | 记忆双时间机制 + 动态阈值检索 |
| v3.0.0 | 2026-06-29 | 五层十六模块重构：八大新能力 |
| v3.0.1 | 2026-07-02 | 被动触发修复：自然语言触发词 + 场景映射表 |
| v3.1.0 | 2026-07-02 | 五大升级：反污染 + Obsidian 同步 + 冷启动 + 退场 + 会话生命周期 |
| v3.2.0 | 2026-07-02 | 子Agent编排器：4维评估 + 任务分解 + 6画像 + 预算熔断 |
| v3.2.1 | 2026-07-02 | 前置编配评估协议：隐含范围识别 + 域感知Token预估 |
| v3.2.2 | 2026-07-02 | 前置评估提升至 SOUL.md 始终在线 |

详见 [CHANGELOG.md](CHANGELOG.md)。

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
- 三进制哈希：超脑原创，受三值逻辑启发
- 设计灵感：认知科学中的"记忆层级模型"

---

**v3.0.1** · 2026-07-02 · 纯本地 · 零网络 · 零外部依赖 · 五层十六模块
