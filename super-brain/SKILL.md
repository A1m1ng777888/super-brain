---
name: super-brain
version: v2.0.0
released: 2026-06-27
description: "Super Brain 超脑认知增强技能 v2。融合 Microsoft SkillOpt 自我进化引擎，为 AI 提供跨会话持久记忆、知识图谱、SimHash 语义搜索、知识自检修复、SkillOpt 自我进化、执行轨迹记录等能力。触发词：记住、记忆、回忆、自我进化、优化技能、记录轨迹、搜索知识、知识图谱、自检、remember、recall、self-evolve、skillopt、trace"
---

# Super Brain (超脑) — 认知增强技能 v2.0.0

## 概述

超脑是一个认知增强系统，为 AI 提供**持久记忆、知识图谱、语义搜索、自检修复、SkillOpt 自我进化、执行轨迹记录**六大核心能力。它解决了 AI Agent 的八大先天缺陷：跨会话失忆、上下文断裂、被动响应、搜索低效、知识孤岛、错误固化、缺乏自愈、无法自我进化。

**v2.0.0 新特性：**
- 融合 Microsoft SkillOpt 自我进化引擎（微软 × 上海交大 × 同济 × 复旦联合研究）
- 执行轨迹记录（三信号源：显式反馈 > 隐式信号 > 验证集评分）
- 技能自动优化（支持优化任意 SKILL.md 或超脑自我进化）
- 验证门控机制（只有分数提升才接受编辑）

所有数据本地存储（默认 `~/.workbuddy/super-brain/`，可通过环境变量 `SUPERBRAIN_DATA_DIR` 自定义），不依赖任何外部服务或 API。

## 架构

四层十二模块：

- **核心认知层**：记忆引擎、知识图谱、语义搜索、智能纠错、自检系统
- **自我进化层**（v2 新增）：SkillOpt 引擎、执行轨迹记录、验证门控
- **存储层**：Workspace 隔离、基于文件的 JSON 存储、轨迹存储
- **Token 优化层**：上下文压缩、结构化注入、按需加载

详见 `references/architecture.md`。

## 初始化

首次使用前运行一次（创建数据目录和默认 Workspace）：

```bash
# 方式一：直接运行（使用默认数据目录）
python super-brain/scripts/superbrain.py init

# 方式二：自定义数据目录
export SUPERBRAIN_DATA_DIR=~/.super-brain
python super-brain/scripts/superbrain.py init
```

## 何时使用

### 自动触发（主动执行，无需用户明确要求）

**1. 记忆抽取** — 对话中用户分享了以下信息时，主动提取存储：
- 个人偏好（UI 风格、工作流、编码习惯、工具选择）
- 项目事实（技术栈、架构决策、截止时间）
- 重要决策及其理由
- 任务分配或承诺事项
- 人物/项目/概念之间的关联

使用 `memory add` 存储为结构化记忆。

**2. 上下文召回** — 新会话开始时，或用户查询涉及过往话题时，用 `memory search` 或 `memory context` 检索相关记忆，注入当前上下文。

**3. 图谱构建** — 对话中出现实体（人物、项目、工具、概念）及其关系时，用 `graph add-node` 和 `graph add-edge` 更新知识图谱。

**4. 冲突检测** — 当新信息与已存储的记忆矛盾时，标记冲突并向用户确认。

**5. 执行轨迹记录**（v2 新增）— 每次执行超脑命令后，自动记录执行轨迹：
- 命令执行成功 → 隐式信号（completed=true, weight=0.3）
- 命令执行出错 → 隐式信号（error=true, weight=-1.0）
- 用户明确表示满意/不满意 → 显式信号（weight=1.0，最高优先级）
- 验证集任务 → 验证信号（weight=0.5）

**6. 自我进化触发**（v2 新增）— 满足以下条件时，建议运行自我进化：
- 执行轨迹超过 20 条
- 用户显式反馈超过 5 条
- 检测到重复的失败模式
- 用户明确要求"优化技能" / "自我进化" / "self-evolve"

### 用户触发

- 用户明确说"记住这个" / "remember this"
- 用户问"你记不记得..." / "do you remember..."
- 用户要求搜索已积累的知识
- 用户要求知识健康检查
- 用户需要管理 Workspace
- 用户要求"优化这个技能" / "optimize this skill"
- 用户要求"自我进化" / "self-evolve"
- 用户要求查看执行轨迹或优化历史

## 核心工作流

### 1. 记忆抽取（存储）

检测到值得记忆的信息后，提取为结构化记忆：

```bash
SB memory add \
  --type <fact|preference|event|relationship|task|decision|context> \
  --content "记忆的简洁陈述" \
  --entity "关联的实体名称" \
  --confidence <0.0-1.0> \
  --source "会话或对话标识" \
  --tags "逗号,分隔,标签"
```

**抽取指南：**
- 用一句话概括核心信息，不要存整段对话
- 置信度设置：用户明确陈述 → 0.95+，推断 → 0.8，不确定 → 0.6
- 实体名称尽量具体（如 "用户"、"项目-X"、"技能系统"）
- 类型说明：
  - `fact`：客观事实
  - `preference`：用户偏好（喜欢/不喜欢）
  - `event`：发生的事件
  - `relationship`：A 与 B 的关联
  - `task`：待办事项
  - `decision`：已做出的决策
  - `context`：背景信息

**批量抽取**（一次丰富的对话后，可提取多条）：

```bash
SB memory add --type preference --content "用户偏好简洁回复" --entity "用户" --confidence 0.95
SB memory add --type fact --content "项目使用 React 18 + TypeScript" --entity "项目-X" --confidence 0.9
SB memory add --type decision --content "选择 SimHash 而非全量向量数据库以简化实现" --entity "超脑" --confidence 0.85
```

### 2. 上下文召回（检索）

回复用户之前，先检查是否存在相关记忆：

**快速搜索**（返回匹配记忆及相似度评分）：

```bash
SB memory search "用户的编码偏好" --limit 5
```

**Token 优化上下文**（返回压缩 JSON，适合直接注入上下文）：

```bash
SB memory context "当前项目架构" --limit 5
```

`context` 命令返回 Token 优化的 JSON 结构，仅包含必要字段（id、type、entity、content、confidence、score），相比全量加载节省约 75% Token。

### 3. 知识图谱（关联）

当对话中出现实体及其关系时，构建图谱：

```bash
# 添加实体节点
SB graph add-node --name "项目 Alpha" --type project --aliases "alpha,proj-a"
SB graph add-node --name "React" --type tool
SB graph add-node --name "张三" --type person

# 用有向边连接实体
SB graph add-edge --source "项目 Alpha" --target "React" --type uses
SB graph add-edge --source "张三" --target "项目 Alpha" --type participates_in
```

**查询图谱**（发现关联关系）：

```bash
SB graph query "项目 Alpha" --depth 2
```

### 4. 自检系统（维护）

周期性运行诊断（建议每 7 天一次，或用户主动触发）：

```bash
# 仅检查
SB selfcheck

# 检查并自动修复安全项（归档过时低置信度记忆、合并疑似重复）
SB selfcheck --fix
```

**查看健康评分：**

```bash
SB health
```

自检扫描五项指标：
- **一致性**：同一实体的记忆是否存在语义矛盾
- **时效性**：陈旧、低频访问、低置信度记忆
- **完整性**：未标记完成状态的任务
- **孤立节点**：知识图谱中无任何连接边的节点
- **重复数据**：SimHash 相似度 > 85% 的记忆对

### 5. Workspace 管理（隔离）

不同项目/领域拥有独立的知识空间：

```bash
SB workspace create --name "项目-Alpha"
SB workspace switch --name "项目-Alpha"
SB workspace list
```

每个 Workspace 拥有独立的记忆库、知识图谱和元数据。处理不同项目知识前先切换到对应 Workspace。

### 6. 错误纠正（合并/解决）

自检标记重复或矛盾后：

```bash
# 合并两条重复记忆（高置信度吸收低置信度）
SB memory merge --id1 mem_20260626_001 --id2 mem_20260626_002

# 更新记忆内容或置信度
SB memory update --id mem_20260626_001 --content "更新后的内容" --confidence 0.95

# 归档过时记忆
SB memory update --id mem_20260626_001 --status archived

# 永久删除
SB memory delete --id mem_20260626_001
```

## Token 优化策略

超脑的设计目标是在增强能力的同时**降低** Token 消耗：

1. **结构化注入**：用 `memory context`（压缩 JSON）替代全量记忆 dump，仅包含必要字段。

2. **按需加载**：仅检索与当前查询相关的记忆，而非全量加载。用 `--limit` 控制上限（默认 5-10 条）。

3. **置信度加权检索**：高置信度记忆优先返回，减少噪音信息消耗 Token。

4. **上下文压缩**：将历史对话压缩为单句记忆，而非存储完整对话记录。

5. **图谱惰性加载**：按实体名称按需查询，不加载全量知识图谱。

**核心原则**：每条记忆操作必须带来大于其 Token 消耗的价值。如果搜索无结果或不相关，不注入空上下文——直接忽略即可。

## 感知增强（主动浮出）

超脑支持超越被动问答的主动行为：

1. **相关知识浮出**：回复用户时，检查是否存在相关的历史决策或背景信息。如有，自然提及："顺便一提，你之前在这个话题上决定过 X。"

2. **重复检测**：如果用户问的问题在历史对话中已解决，优先浮出历史方案，而非重新解决。

3. **矛盾提醒**：如果用户当前表述与已存储记忆矛盾，温和提醒："我记得你之前提到的是 X，这个情况有变化吗？"

4. **图谱推荐**：利用知识图谱的关联关系，推荐用户可能尚未考虑的相关话题或连接点。

## 命令参考

| 命令 | 用途 |
|------|------|
| `init` | 初始化数据目录 |
| `memory add` | 存储新记忆 |
| `memory list` | 按条件筛选记忆列表 |
| `memory get` | 按 ID 获取单条记忆 |
| `memory search` | 语义搜索记忆 |
| `memory context` | Token 优化的上下文检索 |
| `memory update` | 更新记忆字段 |
| `memory delete` | 删除记忆 |
| `memory merge` | 合并两条重复记忆 |
| `memory stats` | 记忆统计 |
| `graph add-node` | 添加知识图谱节点 |
| `graph add-edge` | 添加知识图谱边 |
| `graph query` | 从某节点查询图谱 |
| `graph list` | 列出节点或边 |
| `graph delete` | 删除节点 |
| `graph stats` | 图谱统计 |
| `selfcheck` | 运行诊断 |
| `selfcheck --fix` | 运行诊断并自动修复 |
| `health` | 显示健康评分 |
| `workspace list` | 列出 Workspace |
| `workspace create` | 创建 Workspace |
| `workspace switch` | 切换 Workspace |
| `stats` | 总体统计 |
| `skillopt status` | 查看 SkillOpt 状态 |
| `skillopt self-evolve` | 超脑自我进化 |
| `skillopt optimize` | 优化指定技能 |
| `skillopt history` | 查看优化历史 |
| `skillopt rejected` | 查看被拒编辑 |
| `skillopt rollback` | 回滚到指定 epoch |
| `trace record` | 记录执行轨迹 |
| `trace feedback` | 添加显式反馈 |
| `trace list` | 列出执行轨迹 |
| `trace stats` | 查看轨迹统计 |
| `trace export` | 导出轨迹用于优化 |

## SkillOpt 自我进化（v2 新增）

超脑 v2 融合 Microsoft SkillOpt 引擎，支持技能自动优化和自我进化。

### 核心概念

**SkillOpt 优化循环：**
```
执行轨迹记录 → 反思分析 → 生成编辑 → 验证门控 → 接受/拒绝
```

**三信号源融合（信号权重）：**
- 显式反馈（用户满意/不满意）：weight = 1.0（最高优先级）
- 隐式信号（完成/报错/超时）：weight = 0.3
- 验证集评分（标准任务得分）：weight = 0.5

**文本学习率（编辑预算）：**
- 每个 epoch 最多编辑 4 处（防止覆写有用规则）
- 随着 epoch 增加，编辑预算递减（类似学习率衰减）

### 使用方式

**方式一：超脑自我进化**

优化超脑自己的 SKILL.md：

```bash
# 查看当前状态
SB skillopt status

# 运行自我进化（默认 3 个 epoch）
SB skillopt self-evolve --epochs 3

# 指定验证任务集
SB skillopt self-evolve --epochs 3 --validation-tasks my_tasks.json
```

**方式二：优化任意 Skill**

优化其他 SKILL.md：

```bash
SB skillopt optimize --skill-path /path/to/SKILL.md --epochs 3
```

**查看优化历史：**

```bash
# 查看接受的优化
SB skillopt history

# 查看被拒绝的编辑（负反馈缓冲）
SB skillopt rejected
```

**回滚到上一版本：**

```bash
SB skillopt rollback --epoch 2
```

### 验证任务集格式

```json
[
  {
    "name": "记忆写入与召回",
    "command": "memory add",
    "input": {"content": "测试记忆", "type": "fact"},
    "expected_output": {"id": true},
    "score_weight": 1.0
  }
]
```

### 默认验证任务

超脑内置 4 个默认验证任务（记忆写入、语义搜索、图谱添加、自检）。可通过 `--validation-tasks` 自定义。

## 执行轨迹记录（v2 新增）

记录每次执行轨迹，用于自我进化分析。

### 自动记录

每次执行超脑命令后，自动调用：

```bash
SB trace record \
  --command "memory add" \
  --input '{"content": "...", "type": "fact"}' \
  --output '{"id": "mem_xxx", "status": "success"}'
```

### 添加显式反馈

用户可事后提供反馈：

```bash
SB trace feedback --trace-id tr_20260627_xxx --rating satisfied
SB trace feedback --trace-id tr_20260627_xxx --rating dissatisfied
```

### 查看轨迹统计

```bash
SB trace stats
SB trace list --limit 20
```

### 导出用于优化

```bash
SB trace export --output traces_for_optimization.json
```

### 信号权重计算

```python
加权分数 = 显式信号 × 1.0 + 隐式信号 × 0.3 + 验证评分 × 0.5

# 示例
满意 + 完成 = +2.0 × 1.0 + 0.5 × 0.3 = +2.15
不满意 + 报错 = -2.0 × 1.0 + (-1.0) × 0.3 = -2.30
```

## 设计原则

1. **本地优先**：所有数据本地存储，无云依赖
2. **渐进增强**：只增强不削弱 AI 默认能力，失败时优雅降级
3. **透明可控**：用户可随时通过 CLI 查看、编辑、删除任意记忆
4. **Token 正向收益**：每个新增功能必须证明"节省的 Token > 消耗的 Token"
5. **模块独立**：各子系统互相独立，可单独使用（只记不查、只查不检等）
6. **信号优先级**（v2 新增）：显式反馈 > 隐式信号 > 验证集评分
7. **验证门控**（v2 新增）：只有分数提升才接受编辑，防止退化

## 参考文档

- `references/architecture.md` — 完整架构、数据流、模块交互
- `references/data-schema.md` — 记忆、图谱、配置的数据模式
- `references/token-optimization.md` — Token 优化策略与量化指标

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| **v2.0.0** | 2026-06-27 | 融合 Microsoft SkillOpt 自我进化引擎；新增执行轨迹记录（三信号源）；新增 skillopt 和 trace 子命令；架构升级为四层十二模块 |
| **v1.0.0** | 2026-06-26 | 初始版本：六模块完整实现、49 项测试全通过、SimHash+TF-IDF 混合检索、Workspace 隔离、五项自检系统 |

> 迭代路线参考：`项目档案/超脑Skill.md` 中的更新路线图。
