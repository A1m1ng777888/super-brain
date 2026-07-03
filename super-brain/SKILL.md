---
name: super-brain
version: v3.4.0
released: 2026-07-03
author: A1m1ng777888
license: MIT
description: "Super Brain 超脑认知增强技能 v3.4.0。物理层自检(文件完整性+索引可重建性+备份时效)→修复前自动备份 + Token ROI 量化(净收益/分类节省/ROI比率)。基础功能：Goal Continuation 续跑机制+前置编配评估始终在线+正式评估+分解+规格生成+Goal评估+续跑+执行。触发词：记住、记忆、回忆、推理、纠缠、感知、分类、入库、搜索知识、知识图谱、自检、Token ROI、remember、recall、reason、entangle、perceive"
---

# Super Brain (超脑) — 认知增强技能 v3.4.0

## 概述

超脑是一个认知增强系统，为 AI 提供**持久记忆、知识图谱、语义搜索、自动推理、关联挖掘、对话即入库、分类管线、感知增强、子Agent编排**等核心能力。它解决了 AI Agent 的先天缺陷：跨会话失忆、上下文断裂、搜索低效、知识孤岛、无法推理、表达不通、单Agent上下文污染。

**v3.4.0 升级：物理层自检 + Token ROI 量化。** 自检从 6 项逻辑检查升级为 9 项（新增文件完整性/索引可重建性/备份时效），修复前自动备份。Token ROI 量化模块——用现有统计数据计算每条记忆的 token 节省量，输出净收益和 ROI 比率。

**v3.3.0 升级：Goal Continuation 续跑机制。** 编排器在任务未完成时自动继续执行——不靠 LLM 自由文本判断，靠结构化数据 + SHA256 签名比较，零额外模型调用。

**v3.2.2 升级：前置评估提升至 SOUL.md。** 四问判断逻辑移至 SOUL.md Continuity 层，Agent 无需加载本 skill 即可自主判断任务复杂度。判断为需要编排时再加载本 skill 执行正式评估和分解。

**v3.2.1 升级：前置编配评估协议**

核心改进——用户不再需要显式说"帮我拆成子任务"。编排器现在能自主判断单句大任务。

| 改进 | 说明 |
|------|------|
| **隐含范围识别** | "搭建完整电商网站" → 自动识别为 code+design+docs 多域任务 |
| **域感知 Token 预估** | "完整网站" → 最低 15000 tokens，而非按字数算的 50 |
| **前置检查协议** | SKILL.md 强制规则 #5：收到非简单任务 → 先跑 `orchestrate assess` |
| **隐含子任务发现** | 单句无编号任务 → `_discover_implicit_subtasks()` 自动展开 |
| **Token 量级加分** | est≥15000 → independence +0.12（大量工作 = 并行潜力） |

**v3.2.0 新增：子Agent编排器**

| 功能 | 说明 |
|------|------|
| **复杂度评估** | 4维度打分（上下文隔离度/任务独立性/工具差异/Token风险） |
| **反编配门控** | 简单任务直接拒绝、强顺序任务硬挡、熔断器级联保护 |
| **任务分解** | 四要素输出（目标+输出格式+工具+边界），独立性校验 |
| **工具画像** | 6套预设（research/code/design/data/docs/general），最小工具集选择 |
| **预算熔断** | 50000 token上限 + 会话级失败计数熔断（3次触发） |
| **失败隔离** | 单子任务失败不影响全局，熔断后手动重置 |

**v3.1.0 五模块升级：**

| 模块 | 优先级 | 核心能力 |
|------|--------|----------|
| **反污染规则** | P0 | 低置信度决策不过库、未解决错误不过库、SimHash 去重递增计数 |
| **Obsidian 双向同步** | P1 | JSON → .md + [[wikilink]] 导出、Obsidian vault 图谱可视化、反向同步 |
| **冷启动门控** | P1 | memory<15 AND sessions<3 → 仅感知+存储，达标后自动激活推理+纠缠 |
| **退场生命周期** | P2 | 硬删除线（定义类 0.05/闲聊类 0.10/混合类 0.08）、自动备份 |
| **会话生命周期协议** | P2 | T1 启动(搜索+简报)、T2 收尾(反污染+入库)、T3 定期(7维健康扫描) |

所有数据本地存储（默认 `~/.workbuddy/super-brain/`），不依赖任何外部服务或 API。Obsidian 为可选可视化工具。

## 被动触发场景（v3.0.1 新增）

**⚠️ 强制执行规则 ⚠️**

除了显式触发词外，以下自然语言场景应**必须**加载超脑并执行对应操作：

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
| "这个任务太复杂/帮我同时做…" | 子Agent编配评估 | `SB orchestrate assess TASK --context-size N` |
| "拆成几个子任务/并行处理" | 任务分解 | `SB orchestrate decompose TASK` |
| "帮我同时做A、B、C…" (≥3项) | 全链路编配 | `SB orchestrate spec TASK --context-size N` |
| "项目告一段落/阶段性总结/看看省了多少…" | Token ROI 量化 | `SB token-roi --quickline` |
| 对话收尾/项目结束 | 自动 Token ROI 简报 | `SB token-roi --quickline --days 7` |

**强制规则：**
1. **每次对话开始**：自动搜索与当前话题相关的历史记忆
2. **每次对话结束**：主动将对话中的重要信息入库 + **自动追加 Token ROI 简报**
3. **用户提到项目/技术/偏好**：立即搜索+入库
4. **检测到知识缺口**：主动纠缠场挖掘相关概念
5. **每次收到任务时（v3.2.1 新增）**：前置编配评估 → **已提升至 SOUL.md Continuity 层，始终在线，不需加载本 skill**

### 前置编配评估协议 (Pre-Execution Assessment Protocol)

**⚠️ 强制规则 #5 已提升至 SOUL.md Continuity 层（v3.2.2 起始终在线）。**

四问判断逻辑（上下文量/并行度/能力差异/隐含范围）**始终在 Agent 身份中生效**，不依赖加载本 skill。Agent 自己完成快速判断后：
- ≥3 个"是" → 加载本 skill，运行 `orchestrate assess` 做正式评估
- 全"否" → 单 Agent 直接执行
- 不确定 → 宁可评估也不错失

以下为正式评估后的详细流程（需本 skill 加载后执行）：

```
1. 收到任务 → 跳过简单判断（翻译/查时间/简单定义 → 直接执行）
2. 预估当前上下文大小（大致 token 数）
3. 运行: SB orchestrate assess "完整任务描述" --context-size N
4. 如果 should_spawn = true:
   a. 运行: SB orchestrate spec "完整任务描述" --context-size N
   b. 向用户展示分解计划（子任务数 + 画像 + 预估节省 tokens）
   c. 用户确认 → 并行 spawn 子Agent执行
   d. 用户拒绝 → 单Agent执行（注意token限制）
5. 如果 should_spawn = false → 单Agent执行
```

**自主判断维度（编排器自动完成，无须用户显式指定）：**

| 维度 | 检测方式 |
|------|----------|
| 隐含范围 | 单句"搭建完整电商网站" → 自动识别为 code+design+docs 多域大任务 |
| Token 预估 | "完整网站" → 域感知最低 15000 tokens，而非按字数算的 50 tokens |
| 画像数量 | 多画像 = 可并行 → 自动拆分 |
| 上下文污染 | 当前对话越长 → 隔离需求越高 |

**典型自主触发场景：**

| 用户说什么 | 编排器自主判断 |
|-----------|---------------|
| "帮我搭建一个完整的电商网站" | 单句但隐含4个并行子任务（前端/后端/设计/文档）→ 建议编配 |
| "帮我分析这个项目的代码质量" | 隐含多维度（结构/安全/性能/风格）→ 建议编配 |
| "帮我整理知识库" | 多文件操作 + 索引更新 + 报告生成 → 评估后决定 |
| "搜索Python最佳实践" | 简单搜索 → 单Agent直接执行 |
| "翻译这段文字" | 简单任务 → 跳过评估 |

**编配后汇总规则：**
- 所有子Agent并行执行，各自独立上下文
- 完成后由主Agent收集各子Agent的精简结论
- 汇总为最终答案，中间过程不展示

## 架构

**五层十七模块：**

- **感知层**：感知增强（学/查判断）、分类管线（定义/闲聊区分）
- **认知层**：记忆引擎（v3.0 自动存储+纠偏+表达学习）、推理引擎（v3.0）、上下文记忆（v3.0）、本地长期记忆（v3.0）
- **关联层**：知识图谱、纠缠场（v3.0）、语义搜索（v3.0 三进制哈希+模糊匹配+字词网络）
- **编排层**（v3.2 新增，v3.3 增强）：子Agent编排器（复杂度评估→任务分解→规格生成→Goal Continuation 续跑→生命周期追踪）
- **自愈层**：自检系统（v3.4.0 9项指标：3项物理+6项逻辑，修复前自动备份）、SkillOpt 自我进化、执行轨迹记录
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

### v3.4.0 新增命令

| 命令 | 用途 |
|------|------|
| `token-roi` | 量化 Token 节省 ROI（人类可读摘要） |
| `token-roi --json` | 输出完整的 JSON ROI 数据 |

### v3.3.0 新增命令

| 命令 | 用途 |
|------|------|
| `orchestrate evaluate` | 结构化评估目标完成度 |
| `orchestrate continue` | 自动续跑（基于评估结果） |
| `orchestrate goal-status` | 查看目标当前状态 |
| `orchestrate continuation-reset` | 重置续跑计数器 |

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
| **v3.4.0** | 2026-07-03 | 物理层自检升级(9项=3物理+6逻辑)：文件完整性+索引可重建性+备份时效，修复前自动备份(keep 5)。Token ROI 量化模块：净收益/分类节省/ROI比率/负ROI告警。新增 `sb_token_roi.py`，CLI 新增 `token-roi` 命令。91项测试全通过。 |
| **v3.3.0** | 2026-07-03 | Goal Continuation 续跑机制：结构化目标评估(`evaluate_goal_completion`)+四道闸门(达成/上限/abort/停滞)+SHA256停滞检测+A4次续跑上限、零LLM开销。新增CLI命令evaluate/continue/goal-status/continuation-reset。88项测试全通过。 |
| **v3.2.2** | 2026-07-02 | 前置编配评估提升至 SOUL.md Continuity 层：四问判断逻辑（上下文量/并行度/能力差异/隐含范围）始终在线，不依赖 skill 加载。Agent 自主快速判断→需要时才加载本 skill 执行 orchestrate 正式评估。 |
| **v3.2.1** | 2026-07-02 | 前置编配评估协议：隐含范围识别（单句"搭建完整电商网站"→多域大任务）、域感知Token预估（15000+而非50）、Token量级加分、隐含子任务发现(_discover_implicit_subtasks)、SKILL.md强制规则#5(收到非简单任务→自动评估)。29项测试全通过。 |
| **v3.2.0** | 2026-07-02 | 子Agent编排器：4维度复杂度评估+反编配门控(简单/顺序/熔断)、任务分解引擎(目标+输出+工具+边界+独立性校验)、6套工具画像、预算熔断(50000上限+3次级联)+失败隔离、生命周期追踪。新增 sb_orchestrator.py(~500行)，CLI新增 orchestrate 命令组(assess/decompose/spec/spawn/complete/stats/reset/profiles)。76项测试全通过。 |
| **v3.1.0** | 2026-07-02 | 五大升级：反污染规则(P0)低置信度决策+未解决错误+SimHash去重、Obsidian双向同步(P1)JSON→.md+[[wikilink]]导出写入本地知识库v1/超脑记忆、冷启动门控(P1)memory<15+sessions<3→仅感知存储、退场生命周期(P2)硬删除线+自动备份、会话生命周期协议(P2)T1启动+T2收尾+T3健康扫描。61项测试全通过。 |
| **v3.0.1** | 2026-07-02 | 被动触发修复：SKILL.md 新增自然语言触发场景表（8种场景→命令映射）；USER.md 注入超脑使用约定（每会话硬注入）；SOUL.md Continuity 节增加超脑主动使用指令。三层冗余确保每会话感知。 |
| **v3.0.0** | 2026-06-29 | 八大升级：三进制哈希字词网络（3^64状态）、分类管线（定义/闲聊差异化衰减）、感知增强（学/查自动判断）、推理引擎（关键点提取+逻辑分析+结论推导）、纠缠场（三通道关联挖掘）、上下文记忆（主题聚类+跨会话追踪）、本地长期记忆（对话即入库+零成本检索）、记忆引擎升级（自动存储+错别字纠偏+表达学习）。61项测试全通过。 |
| v2.1.0 | 2026-06-28 | 记忆双时间机制、动态阈值检索、自检时间有效性指标 |
| v2.0.0 | 2026-06-27 | SkillOpt 自我进化引擎、执行轨迹记录、验证门控 |
| v1.0.0 | 2026-06-26 | 初始版本：六模块、SimHash+TF-IDF 检索、Workspace 隔离 |

## 参考文档

- `references/architecture.md` — 完整架构、数据流、模块交互
- `references/data-schema.md` — 记忆、图谱、配置的数据模式
- `references/token-optimization.md` — Token 优化策略与量化指标
