---
name: super-brain
version: v3.0.1
released: 2026-07-02
description: "Super Brain 超脑认知增强技能 v3.0.0。八层十六模块架构：三进制哈希字词网络、分类管线、感知增强、推理引擎、纠缠场、上下文记忆、本地长期记忆、记忆引擎升级。为 AI 提供跨会话持久记忆、知识图谱、语义搜索、自动推理、关联挖掘、对话即入库等能力。触发词：记住、记忆、回忆、推理、纠缠、感知、分类、入库、搜索知识、知识图谱、自检、remember、recall、reason、entangle、perceive、之前、上次、那个、我们聊过、你之前说、别忘了、还有没有、相关的内容、帮我回忆、继续上次"
---

# Super Brain (超脑) — 认知增强技能 v3.0.0

## 概述

超脑是一个认知增强系统，为 AI 提供**持久记忆、知识图谱、语义搜索、自动推理、关联挖掘、对话即入库、分类管线、感知增强**等核心能力。它解决了 AI Agent 的先天缺陷：跨会话失忆、上下文断裂、搜索低效、知识孤岛、无法推理、表达不通。

**v3.0.0 八大升级：**

| 模块 | 能力 | 核心技术 |
|------|------|----------|
| **记忆引擎** | 自动存储、跨对话关联、错别字纠偏、学习用户表达 | Levenshtein + 表达档案 |
| **推理引擎** | 提炼数据重点、梳理逻辑、推导结论 | 因果分析 + 关键点提取 |
| **纠缠场** | 挖掘未明说关联、强化词词联系 | 三通道融合（哈希+共现+图谱） |
| **上下文记忆** | 同主题归拢、跨窗口跨日期追溯 | 凝聚聚类 + 线程追踪 |
| **感知增强** | 自动判断"学"还是"查" | 新颖性检测 + 信息价值评估 |
| **分类管线** | 定义类/闲聊类区分、差异化衰减 | 模式匹配 + 指数衰减 |
| **三进制哈希** | 3^64 状态、字词网络 | 三进制哈希 (-1/0/+1) |
| **本地长期记忆** | 跨会话关联、零成本检索、对话即入库 | 预计算索引 + 倒排表 |

所有数据本地存储（默认 `~/.workbuddy/super-brain/`），不依赖任何外部服务或 API。

## 被动触发场景（v3.0.1 新增）

除了显式触发词外，以下自然语言场景应自动加载超脑并执行对应操作：

| 用户说了什么 | 自动执行 | 命令 |
|-------------|---------|------|
| "之前/上次/那个…" | 搜索相关记忆 | `SB memory search --text "..."` |
| "我们聊过…/你之前说…" | 搜索+上下文追溯 | `SB context-mem recall --query "..."` |
| "别忘了…/记住这个…" | 自动存储 | `SB memory auto-store --text "..."` |
| "还有没有相关的…" | 纠缠场挖掘 | `SB entangle mine --concept "..."` |
| "帮我总结一下…" | 推理引擎提炼 | `SB reason extract --text "..."` |
| "该怎么办/选哪个…" | 推理引擎决策 | `SB reason decide --options "..."` |
| 用户分享个人信息/偏好/目标 | 对话即入库 | `SB longterm ingest --text "..."` |
| "继续上次…" | 上下文线程追踪 | `SB context-mem trace --topic "..."` |

**判断原则：** 不需要用户说"记住"或"回忆"——agent 应主动判断是否需要查记忆、存记忆。

## 架构

**五层十六模块：**

- **感知层**：感知增强（学/查判断）、分类管线（定义/闲聊区分）
- **认知层**：记忆引擎（v3.0 自动存储+纠偏+表达学习）、推理引擎（v3.0）、上下文记忆（v3.0）、本地长期记忆（v3.0）
- **关联层**：知识图谱、纠缠场（v3.0）、语义搜索（v3.0 三进制哈希+模糊匹配+字词网络）
- **自愈层**：自检系统（v2.1 六项指标）、SkillOpt 自我进化、执行轨迹记录
- **存储层**：Workspace 隔离、三进制哈希索引、JSON 文件存储、倒排索引

## 初始化

```bash
python superbrain.py init
```

## 核心工作流

### 1. 对话即入库（v3.0.0 新增）

自动从对话文本中提取、分类、存储知识：

```bash
# 自动感知+提取+存储
SB longterm ingest --text "配置API网关需要设置超时时间30秒，这是生产环境必须配置。"

# 自动存储（记忆引擎入口）
SB memory auto-store --text "用户偏好使用TypeScript进行开发"
```

系统自动完成：感知判断 → 信息价值评估 → 分类（定义/闲聊）→ 关键点提取 → 存储入记忆库 → 更新索引。

### 2. 零成本检索（v3.0.0 新增）

使用预计算的三进制哈希索引进行检索，无需全量扫描：

```bash
SB longterm retrieve "Docker部署配置" --limit 5
```

### 3. 错别字纠偏搜索（v3.0.0 新增）

自动纠正查询中的错别字和用词偏差：

```bash
# 学习用户表达习惯
SB memory learn-expr --input "TS" --standard "TypeScript"

# 纠偏搜索
SB memory search-corrected "TScript开发偏好"
```

### 4. 推理引擎（v3.0.0 新增）

```bash
# 提炼关键信息
SB reason extract --text "React 18引入并发渲染。因为并发渲染提高性能，所以大型应用受益最大。"

# 分析逻辑结构
SB reason analyze --text "由于网络延迟导致请求超时，因此需要增加重试机制。"

# 从记忆推导结论
SB reason conclude "项目架构决策"

# 辅助决策
SB reason decide --options '["方案A", "方案B", "方案C"]'
```

### 5. 纠缠场（v3.0.0 新增）

```bash
# 挖掘概念关联
SB entangle mine "超脑"

# 构建纠缠场
SB entangle build

# 查询纠缠（发现隐藏关联）
SB entangle query "哈希搜索"

# 强化词词连接
SB entangle reinforce --token1 "记忆" --token2 "搜索" --strength 0.2
```

### 6. 上下文记忆（v3.0.0 新增）

```bash
# 主题聚类
SB context-mem cluster

# 追踪对话线程
SB context-mem trace "超脑架构"

# 跨会话召回
SB context-mem recall "TypeScript" --days-back 30

# 获取主题上下文
SB context-mem topic "项目架构"
```

### 7. 感知增强（v3.0.0 新增）

```bash
# 判断学还是查
SB perceive check --text "用户喜欢用暗色主题"

# 批量感知
SB perceive batch --messages '["你好", "配置需要设置超时", "哈哈好的"]'
```

### 8. 分类管线（v3.0.0 新增）

```bash
# 分类内容
SB pipeline classify --text "React是Facebook开发的JavaScript库"

# 管线统计
SB pipeline stats
```

### 9. 记忆引擎（v2.1 继承 + v3.0 增强）

```bash
# 存储记忆（v2.1 时间机制 + v3.0 三进制哈希）
SB memory add --type fact --content "项目使用React 18" --entity "项目" --confidence 0.9

# 语义搜索（v3.0 六通道融合）
SB memory search "前端框架" --limit 5

# 上下文注入
SB memory context "项目架构" --limit 5
```

### 10. 知识图谱 / 自检 / SkillOpt（v2.0 继承）

```bash
SB graph add-node --name "React" --type tool
SB graph add-edge --source "项目" --target "React" --type uses
SB selfcheck --fix
SB skillopt self-evolve --epochs 3
```

## v3.0.0 技术细节

### 三进制哈希字词网络

传统 SimHash 使用二进制（0/1），v3.0.0 升级为三进制（-1/0/+1）：

| 特性 | 二进制 SimHash | 三进制 Ternary Hash |
|------|---------------|-------------------|
| 状态数 | 2^64 ≈ 1.8×10^19 | 3^64 ≈ 3.4×10^30 |
| 中性位 | 无 | 有（0 = 不影响） |
| 区分力 | 基准 | ~19万倍提升 |
| 模糊容错 | 弱 | 强（中性位提供缓冲） |

字词网络基于三进制哈希构建，每个 token 获得独立的哈希指纹，相似 token 自动"纠缠"。

### 分类管线衰减策略

| 类别 | 半衰期 | 自动归档 | 示例 |
|------|--------|---------|------|
| 定义类 | 365 天 | 730 天 | "React是JavaScript库" |
| 闲聊类 | 7 天 | 30 天 | "哈哈好的谢谢" |
| 混合类 | 90 天 | 180 天 | "用React但需注意兼容性" |

### 六通道搜索融合

v3.0.0 搜索引擎融合六个信号通道：

| 通道 | 权重 | 功能 |
|------|------|------|
| TF-IDF | 0.35 | 精确语义匹配 |
| 关键词 | 0.20 | 精确命中提升 |
| SimHash | 0.15 | 快速粗筛 |
| 三进制哈希 | 0.12 | 增强区分 |
| 模糊匹配 | 0.10 | 错别字容错 |
| 字词网络扩展 | 0.08 | 关联词发现 |

## 命令参考

### v3.0.0 新增命令

| 命令 | 用途 |
|------|------|
| `memory auto-store` | 自动提取存储重要信息 |
| `memory correct` | 错别字/用词纠偏 |
| `memory learn-expr` | 学习用户表达习惯 |
| `memory search-corrected` | 纠偏搜索 |
| `perceive check` | 感知判断（学/查/跳过） |
| `perceive batch` | 批量感知分析 |
| `perceive stats` | 感知统计 |
| `pipeline classify` | 内容分类 |
| `pipeline stats` | 管线统计 |
| `reason extract` | 提取关键信息 |
| `reason analyze` | 逻辑分析 |
| `reason conclude` | 推导结论 |
| `reason decide` | 辅助决策 |
| `entangle mine` | 挖掘概念纠缠 |
| `entangle build` | 构建纠缠场 |
| `entangle query` | 查询纠缠关联 |
| `entangle reinforce` | 强化词词连接 |
| `entangle stats` | 纠缠场统计 |
| `context-mem cluster` | 主题聚类 |
| `context-mem trace` | 追踪对话线程 |
| `context-mem recall` | 跨会话召回 |
| `context-mem topic` | 获取主题上下文 |
| `context-mem stats` | 上下文统计 |
| `longterm ingest` | 对话即入库 |
| `longterm index` | 构建检索索引 |
| `longterm retrieve` | 零成本检索 |
| `longterm associate` | 跨会话关联 |
| `longterm stats` | 长期记忆统计 |

### 继承命令（v1.0-v2.1）

`init`, `memory add/list/get/search/update/delete/merge/context/stats`, `graph add-node/add-edge/query/list/delete/stats`, `selfcheck`, `health`, `workspace list/create/switch`, `stats`, `skillopt status/self-evolve/optimize/history/rejected/rollback`, `trace record/feedback/list/stats/export`

## 设计原则

1. **本地优先**：所有数据本地存储，无云依赖
2. **渐进增强**：只增强不削弱 AI 默认能力
3. **三进制优势**：3^64 状态空间，19万倍区分力提升
4. **差异化衰减**：定义类长留，闲聊类快清，节省存储
5. **对话即入库**：自动感知+提取+存储，零人工干预
6. **零成本检索**：预计算索引，O(1) 查找，Token 节约
7. **六通道融合**：TF-IDF + 关键词 + SimHash + 三进制 + 模糊 + 扩展
8. **向后兼容**：v1.0-v2.1 功能全部保留，旧记忆可搜索

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| **v3.0.1** | 2026-07-02 | 被动触发修复：SKILL.md 新增自然语言触发场景表（8种场景→命令映射）；USER.md 注入超脑使用约定（每会话硬注入）；SOUL.md Continuity 节增加超脑主动使用指令。三层冗余确保每会话感知。 |
| **v3.0.0** | 2026-06-29 | 八大升级：三进制哈希字词网络（3^64状态）、分类管线（定义/闲聊差异化衰减）、感知增强（学/查自动判断）、推理引擎（关键点提取+逻辑分析+结论推导）、纠缠场（三通道关联挖掘）、上下文记忆（主题聚类+跨会话追踪）、本地长期记忆（对话即入库+零成本检索）、记忆引擎升级（自动存储+错别字纠偏+表达学习）。61项测试全通过。 |
| v2.1.0 | 2026-06-28 | 记忆双时间机制、动态阈值检索、自检时间有效性指标 |
| v2.0.0 | 2026-06-27 | SkillOpt 自我进化引擎、执行轨迹记录、验证门控 |
| v1.0.0 | 2026-06-26 | 初始版本：六模块、SimHash+TF-IDF 检索、Workspace 隔离 |

## 参考文档

- `references/architecture.md` — 完整架构、数据流、模块交互
- `references/data-schema.md` — 记忆、图谱、配置的数据模式
- `references/token-optimization.md` — Token 优化策略与量化指标
