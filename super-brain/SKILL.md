---
name: super-brain
version: v3.6.1
released: 2026-07-08
author: A1m1ng777888
license: MIT
description: "Super Brain 超脑认知增强技能 v3.6.1。全局工作空间门控层（Global Workspace Gating）：受 Anthropic《A Global Workspace in Language Models》(2026-07-06) 启发，记忆分冷存储与活跃工作空间两层，按显著度(salience)晋升、容量上限(cap)约束、链式点燃(chain-ignite)实现 Ignition；新增 reasoning_intermediate 记忆类型与 reason capture 中间推理捕获。基础功能：Goal Continuation 续跑机制+前置编配评估始终在线+正式评估+分解+规格生成+Goal评估+续跑+执行+T2阶段感知自动触发。触发词：记住、记忆、回忆、推理、纠缠、感知、分类、入库、搜索知识、知识图谱、自检、Token ROI、工作空间、门控、自动晋升、reason、entangle、perceive"
---

# Super Brain (超脑) — 认知增强技能 v3.6.1

## 概述

超脑是一个认知增强系统，为 AI 提供**持久记忆、知识图谱、语义搜索、自动推理、关联挖掘、对话即入库、分类管线、感知增强、子Agent编排**等核心能力。它解决了 AI Agent 的先天缺陷：跨会话失忆、上下文断裂、搜索低效、知识孤岛、无法推理、表达不通、单Agent上下文污染。

**v3.5.0 升级：Token ROI 仪表盘全面升级（最终迭代）。** 三大新增——① **30天趋势图**（`calc_token_roi_trend()` 按日回溯快照，双 Y 轴折线图显示净节省+记忆数变化）；② **负 ROI 诊断**（每条记忆的 `recommendation` 字段——零访问建议归档、高存储成本建议精简、一般负收益建议主动引用）；③ **交互式 HTML 看板**（`SB token-roi --dashboard` 一键生成，含趋势折线图+分类柱状图+类型环形图+Top 节省排行+负 ROI 诊断表）。同时修复 `test_superbrain.py` workspace 隔离问题（不再清空 production workspace，测试后恢复原始 workspace）。49/49 测试全通过。

**v3.6.0 升级：全局工作空间门控层（Global Workspace Gating）。** 受 Anthropic《A Global Workspace in Language Models》(2026-07-06) 启发，把"对话即入库全量提升进工作空间"的反 GWT 选择性问题修复为两层架构：① **冷存储 / 活跃工作空间分离**——记忆默认躺在冷存储，只有显著度(salience)跨过晋升阈值(threshold)才进入参与推理、注入上下文的"全局工作空间"；② **显著度多信号加权**——confidence/recency/access_count/entanglement/type 基线，reasoning_intermediate 基线最冷(-0.25)以免淹没工作空间；③ **链式点燃(chain-ignite)**——推理链任一节点晋升→整条链 Ignition 晋升（对应论文 Ignition 的竞争性/突变/广播）；④ **容量上限(cap)** 约束工作空间规模，mirror GWT 有限容量；⑤ **reasoning_intermediate 记忆类型** + `reason capture` 中间推理捕获，把驱动结论的中间概念变成一等可检索记忆。新增 `gating` 子命令（status/active/promote/demote/threshold/calibrate）与 `memory context --workspace-only` 选择性过滤。25/25 v3.6 测试 + 49/49 回归全通过。

**v3.6.1 升级：门控层自动接线（GWT 选择性原则落地到 ingest 主干）。** 把 v3.6.0 建好的门控层从"可手动治理"升级为"入库即自动运转"：① **单点接入 `add_memory`**——`memory add` / `auto_store` / `longterm ingest` 全部入口在写盘前调用 `compute_salience` + `is_promoted`，让晋升（salience 跨阈值→`workspace_promoted`）在**编码时发生**，而非等查询时惰性重算；② **修复 demote 失效**：原 `get_active_workspace` 用手动 `demote` 设的 `False` 会被显著度重算覆盖（demote 形同虚设），新增 `gating_override` 字段（promote/demote/None）区分手动与自动判定；③ 链式点燃仍委托 `get_active_workspace` 查询时统一做，避免每条入库全量扫。36/36 v3.6 测试（含 11 项新增自动晋升用例）+ 49/49 回归全通过。

**v3.4.3 升级：P0 数据安全修复。** 修复 `read_json()` 在 JSON 解析失败时静默返回 None 的缺陷——这导致 `read_memories()` 返回空列表，进而 `memory add` 用仅含新记忆的列表覆盖整个文件，造成全部历史记忆丢失。修复方案：`read_json()` 解析失败时打印 stderr 警告；`read_memories()` 检测到文件存在但解析失败时，先自动备份损坏文件再返回空列表。同时修复 v3.4.2 未生效的版本号同步问题（sb_core.py 仍为 3.4.1）。

**v3.4.2 升级：扣子 Linux 云端测试修复。** 基于扣子 Agent Linux 云端测试报告（210/211 测试通过），修复 5 项跨平台兼容性 Bug：P0 新增 .gitattributes 解决 CRLF 换行符问题、P1 trace record JSON 解析添加异常捕获防崩溃、P2 sb_core.py 版本号同步至 3.4.2、P3 test_superbrain.py 自检断言更新(5→9)、P4 aliases 帮助文本添加格式示例。

**v3.4.1 升级：T2 阶段感知自动触发。** 修复会话生命周期 T2 协议的根本架构缺陷——触发不再靠 Agent 记忆，改为强制规则 #6 + 四类阶段转换信号（精力信号/话题转向/里程碑达成/自然断开）。Agent 自主判断阶段结束，不经用户催促执行收尾。

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

所有数据本地存储（默认 `~/.workbuddy/super-brain/`），不依赖任何外部服务或 API。

**⚠️ 重要：Obsidian 集成说明**

Super Brain v3.1.0+ 的 **Obsidian 双向同步**是深度集成的核心功能，不是"可选附件"。它负责将记忆以 `.md` + `[[wikilink]]` 格式导出到 Obsidian vault，实现本地知识库的图谱可视化、反向链接和跨文件关联。

## 本地知识库依赖与自主选择

### 为什么需要 Obsidian？

Super Brain 的 Obsidian 同步模块（v3.1.0+）提供：

| 能力 | 说明 |
|------|------|
| **记忆导出** | JSON 记忆 → `.md` 文件 + `[[wikilink]]` 双向链接 |
| **图谱可视化** | Obsidian 图谱视图，直观看到知识关联 |
| **反向同步** | 用户在 Obsidian 中修改 `.md` 文件 → 同步回 Super Brain |
| **永久归档** | 即使清空 Super Brain 数据，Obsidian 中的 `.md` 仍可阅读 |

### 没有 Obsidian 会怎样？

**核心记忆引擎不受影响**——记忆依然正常工作（存储/搜索/推理/纠缠场/分类管线等全部可用）。缺少的只是：
- ❌ 记忆的 `.md` 文件导出与图谱可视化
- ❌ 双向同步（在 Obsidian 中编辑后写回 Super Brain）
- ❌ 与本地知识库的深度关联

### 请自主选择

**选项 A：安装 Obsidian，获得完整体验**

1. 从 [obsidian.md](https://obsidian.md) 下载安装
2. 打开已有 vault 或创建新 vault
3. 运行 `SB obsidian export` 将记忆导出为 `.md`
4. 推荐 vault 路径：`本地知识库v1/`（Super Brain 默认写入 `本地知识库v1/超脑记忆/`）

**选项 B：不使用 Obsidian，用其他方式管理本地知识库**

可能的替代方案：
- **任何 Markdown 编辑器**（VS Code、Typora 等）：导出后的 `.md` 文件依然可读、可搜索
- **Notion / 飞书 / 语雀**：手动导入 `.md` 文件
- **自定义脚本**：用 Python 读取 `~/.workbuddy/super-brain/` 下的 JSON 数据，转换成你需要的格式
- **仅使用 Super Brain 内部存储**：所有数据在 `~/.workbuddy/super-brain/memory/` 中以 JSON 格式存储，不依赖任何外部工具即可使用全部核心功能

---

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
6. **T2 阶段感知自动触发（v3.4.1 新增）**：Agent 必须主动监测对话的阶段转换信号。当检测到以下任一信号时，**不经用户催促**，立即执行 T2 收尾协议（见下方）：

### T2 阶段感知自动触发协议（v3.4.1）

**问题**：v3.1.0 的 T2 协议依赖 Agent 记忆触发，存在"手册印了但警铃没接线"的架构缺陷。用户不说"晚安/拜拜"，Agent 必须自己判断阶段性结束。

**触发信号（Agent 自主监测，无需用户显式关键词）：**

| 信号类型 | 检测模式 | 示例 |
|---------|---------|------|
| **精力信号** | 用户表达疲劳/不想继续工程 | "有点累"、"先不做了"、"今天就到这"、"懒得弄了" |
| **话题转向** | 从任务执行突转为反思/闲聊，且带有收尾语气 | "其实也不止这些……"、"我们聊点别的吧" |
| **里程碑达成** | 一个明确项目结论后超过 2 轮无新任务推进 | Bug 修完→哲学讨论→无后续指令 |
| **自然断开** | 用户说"先这样"、"下次再"、"明天见"、"好的，" 后没有新话题 | |

**触发后执行（三步，必须全部完成）：**

```
1. SB selfcheck --fix          # 健康检查 + 自动修复
2. SB token-roi --quickline    # Token 节省简报
3. 追加 .workbuddy/memory/YYYY-MM-DD.md   # 写工作日志
```

**⚠️ 关键原则**：
- T2 的触发责任在 Agent，不在用户。宁可多跑一次也不漏掉收尾。
- 跑完 T2 后正常回复用户，不要用技术输出淹没对话——selfcheck 结果和 ROI 数字只写进日志，不在聊天里逐条报。
- 如果用户说"好的，明天见"等明确结束语，T2 跑完后回复简洁，不留新问题。

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

### v3.6.0 新增命令（全局工作空间门控层）

| 命令 | 用途 |
|------|------|
| `gating status` | 查看门控状态（阈值 / 容量 / 晋升比例） |
| `gating active [--limit N]` | 列出当前晋升进全局工作空间的记忆 |
| `gating promote --id ID` | 强制晋升单条记忆（覆盖显著度） |
| `gating demote --id ID` | 强制把单条记忆移出工作空间 |
| `gating threshold [--value 0-1]` | 读取或设置晋升显著度阈值（默认 0.35） |
| `gating calibrate [--threshold 0-1]` | 报告各阈值下的晋升比例，调向 GWT 8-25% 区间 |
| `reason capture --text "..."` | 把一段文本的推理链捕获为 `reasoning_intermediate` 记忆（共享 chain_id + 双向 related_nodes） |
| `memory context "query" --workspace-only` | 仅检索已晋升进全局工作空间的记忆（GWT 选择性广播） |

### v3.6.1 变更（门控层自动接线）

- **入库即晋升**：`memory add` / `longterm ingest`（`auto_ingest`）现在在写盘前自动计算 salience 并判定 `workspace_promoted`，无需手动 `gating promote` 或查询时惰性重算。
- **`gating_override` 字段**：`promote` / `demote` 写入 `gating_override=promote/demote`，查询时优先于显著度重算，修复 demote 被覆盖失效。
- **`reasoning_intermediate` 类型字段**：`salience` / `chain_id` / `reasoning_role` / `workspace_promoted` / `gating_override`（v3.6.0 起）。

### v3.4.0 新增命令

| 命令 | 用途 |
|------|------|
| `token-roi` | 量化 Token 节省 ROI（人类可读摘要） |
| `token-roi --json` | 输出完整的 JSON ROI 数据 |
| `token-roi --dashboard [PATH]` | 生成交互式 HTML 仪表盘（可指定输出路径） |
| `token-roi --dashboard --trend-days 14` | 指定趋势图天数（默认 30 天） |
| `token-roi --dashboard --days 7` | 仅统计最近 7 天的 ROI 仪表盘 |

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
| **v3.6.1** | **2026-07-08** | **门控层自动接线（GWT 选择性原则落地 ingest 主干）：** `sb_memory.py` 的 `add_memory` 写盘前调用 `compute_salience` + `is_promoted`，使 `memory add` / `auto_store` / `longterm ingest` 全部入口入库即按显著度自动晋升（salience→`workspace_promoted`）。修复 demote 失效：原 `get_active_workspace` 手动 demote 被显著度重算覆盖，新增 `gating_override` 字段（promote/demote/None）区分手动与自动。链式点燃仍委托查询时统一做。36/36 v3.6 测试（含 11 项自动晋升新增用例）+ 49/49 回归全通过。 |
| **v3.6.0** | **2026-07-08** | **全局工作空间门控层（Global Workspace Gating）：** 受 Anthropic《A Global Workspace in Language Models》(2026-07-06) 启发，把"对话即入库全量提升"的反 GWT 选择性问题修复为冷存储/活跃工作空间两层架构。新增 `sb_gating.py`（compute_salience 多信号显著度、get_threshold/set_threshold、is_promoted、chain_ignite 链式点燃、get_active_workspace 容量上限、promote/demote、calibrate、get_status）。`sb_memory.py` 新增 `reasoning_intermediate` 记忆类型与 salience/chain_id/reasoning_role/workspace_promoted 四字段；`get_context` 新增 `--workspace-only` 选择性过滤并透出 workspace_promoted 标志。`sb_reasoning.py` 新增 `capture_reasoning_chain` 中间推理捕获（共享顶层 chain_id + 双向 related_nodes）。CLI 新增 `gating` 子命令与 `reason capture`、`memory context --workspace-only`。25/25 v3.6 测试 + 49/49 回归全通过。 |
| **v3.5.0** | **2026-07-07** | **Token ROI 仪表盘全面升级：** `calc_token_roi_trend()` 30天趋势回溯、每条记忆 `recommendation` 可行动建议、`generate_dashboard_html()` 新增趋势折线图和负 ROI 诊断表、CLI 新增 `--dashboard` 和 `--trend-days` 标志、Obsidian Dataview 看板同步更新。修复 `test_superbrain.py` workspace 隔离（不再清空 production 数据）。49/49 测试全通过。 |
| **v3.4.3** | 2026-07-06 | P0 数据安全修复：`read_json()` JSON解析失败时从静默返回None改为打印stderr警告；`read_memories()` 在文件存在但解析失败时自动备份损坏文件再返回[]（而非直接返回[]导致write_memories覆盖丢失全部记忆）。修复sb_core.py版本号3.4.1→3.4.3（v3.4.2的P2修复未生效）。 |
| **v3.4.2** | 2026-07-05 | 扣子 Linux 云端测试修复(5项)：P0 新增 .gitattributes 跨平台换行符管理(*.py/*.sh 强制 LF)、P1 trace record JSON 解析添加 try/except 防崩溃、P2 sb_core.py 版本号 3.0.0→3.4.2、P3 test_superbrain.py 自检断言 5→9、P4 aliases 帮助文本添加格式示例。测试保持 211 项，核心功能无变更。 |
| **v3.4.1** | 2026-07-04 | T2 阶段感知自动触发协议：修复会话生命周期 T2 协议的架构缺陷——从依赖 Agent 记忆触发升级为强制规则 #6 + 四类阶段转换信号检测（精力信号/话题转向/里程碑达成/自然断开）。Agent 自主判断阶段结束，不经用户催促执行 T2 收尾（selfcheck + ROI + 日志）。 |
| **v3.4.0** | 2026-07-03 | 物理层自检升级(9项=3物理+6逻辑)：文件完整性+索引可重建性+备份时效，修复前自动备份(keep 5)。Token ROI 量化模块：净收益/分类节省/ROI比率/负ROI告警。新增 `sb_token_roi.py`，CLI 新增 `token-roi` 命令。91项测试全通过。Goal Continuation 续跑机制：结构化目标评估(`evaluate_goal_completion`)+四道闸门(达成/上限/abort/停滞)+SHA256停滞检测+A4次续跑上限、零LLM开销。新增CLI命令evaluate/continue/goal-status/continuation-reset。88项测试全通过。 |
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
