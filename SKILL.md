---
name: super-brain
version: v3.12.3
released: 2026-08-31
author: A1m1ng777888
license: MIT
description: "Super Brain 超脑认知增强技能 v3.11.1。v3.8 系列：双层 Workspace 架构（persona + project）、RRF 秩融合检索、知识图谱 Mermaid 导出、GWT 门控层、Karpathy 认知 OS 蒸馏。v3.9 系列（GLM-5.2 外部审阅里程碑）：跨 15 个核心模块发现并修复 40+ 真实缺陷。v3.9.4（P0 性能修复）：搜索 15-35 倍提速、零成本索引自动维护、测试隔离。v3.9.5（P1+P2 系统性修复）：硬步骤门控原子写+未来时间拒绝+策略下沉、并发写 tmp.pid、read_json 二进制防护、token_roi XSS 转义、warmup 常量共享、读路径写副作用默认关、分层依赖注释、发布面脱敏扩大。v3.9.6（自检评分优化）：gating_flood ratio 阈值 0.40→0.70、duplicates simhash 0.75→0.85、--fix 自动合并 0.95→0.85、task 默认 task_status=active、completeness 白名单扩展。v3.9.7（自动触发断裂链修复）：write_json 返回值补全消假警告、跨会话硬步骤死锁修复。v3.9.8（mattpocock 纪律库吸收）：decompose 曳光弹切片规格、frontier 拷问法、domain 项目术语表、双轴 code-review。v3.10.0（评分体系重构，Penguin 评测范式）：① 硬/软指标分域——软指标从扣分项改为报告项，总分只基于物理完整性+时效性+真损坏 ② 有效性协议——score_status 与分数正交 ③ 修复后验证——--fix 后硬分未提升则提示回滚。v3.11.0（遗忘治理引擎 + 检索增强）：① 新增 sb_forgetting 遗忘治理模块（规模×活跃度二维，active/warm/dormant 三档软切降权，dormant 0.5/warm 0.8/active 1.0，身份记忆豁免，forgetting status/scan/apply CLI）② 检索 entity 精确命中 boost——查询词命中记忆 entity 时优先召回，修复词面不重叠导致的漏召回 ③ 修复 v3.10.0 发布遗漏（sb_forgetting.py 未随包发布致 superbrain ImportError）。v3.11.1（DSH 审阅高位项修复）：① 门控容量持久执行——新增 _cap_enforce 执行器统一 get_active_workspace 与 chain_ignite 两条晋升路径，超容部分持久降级（可逆审计、无 override 残留），晋升洪水（95>cap50）根治 ② 自检索引格式兼容——check_file_integrity 兼容 v3.9.3+ 现行索引键（keyword_index/word_network_stats），file_integrity 假阳性消除 ③ find_duplicates TF-IDF 预计算——IDF doc_freq 表 + doc Counter 消除 O(n²·terms·doc_len) 退化（n=382 实测 ~235s→秒级，结果 bit 级一致）。v3.11.2（检索层重建，内部轮）：六通道 RRF 依据消融证据砍成 BM25 单路、_bm25_tokenize 修复 CJK 停用词主导、persona 合并单次检索（recall@1 0.200→0.700）、访问统计时点断裂修复、--dedupe 幂等写入开关。v3.12.0（P0-A→M 十四轮对抗性开发）：新增自动建图（graph build，entity 节点 + top-K scale-free 建边 + related_nodes 回填）、相对门控（get_threshold 双模式：meta 手动 / 默认自动=排名百分位，分布漂移免重标）、门控治理与写路径全量上锁、实体归一化、两轮对抗审阅修 6 处真 bug；实测检索 recall@1 0.200→0.700、门控洪水 137→50 根治、图谱 14→139 节点复活。v3.12.1（每日自检守护引擎，默认关闭）：新增 sb_healthlite.py L0 守护（graph build + selfcheck + 门控带内检查 → health_state.json，退出码分级 warn→0 / error→1、原子写 + 锁 pid 校验）+ schedule_manager.py（schtasks 用户级计划任务 install/uninstall/status，--time HH:MM 校验）；纯本地零 token 零联网，开关主通道=可视化工作台自动化组件面板（规划中，默认全关）。v3.12.2（工作台全线+阶段2 收官）：sb_consolidate.py 零 LLM 后台整合（A 归一/B 合并/C 压缩/D 知识更新链，proposal→apply 两段式永不自动 apply）、时态建模启用（valid_from 锚定+存量回填）、sb_workbench.py 本地工作台（C 端化三区 IA+正在推进看板对话即上板+健康看板迁入双 Tab）、图谱增益消融（一阶段「差三项」全关闭）。v3.12.3（工作台体验五连升级）：R1 节奏条（完成率环+体检 streak 渐变式不归零+42 天热力图+项目进度条）、R2 看板导出 JSON/导入恢复（消毒+自动备份）、R3 暗色模式（CSS 变量+防闪白+?theme= 调试通道）、R4 移动端+iframe 高度自适应+局域网模式（--host 0.0.0.0 opt-in+_lan_ip 探测+Start-Workbench-LAN.bat）、R5 微交互基线（环动画/勾选 pop/spring 开关/键盘可达/prefers-reduced-motion）。纯标准库零依赖。"
---

# Super Brain (超脑) — 认知增强技能 v3.12.3

## 概述

超脑是一个认知增强系统，为 AI 提供**持久记忆、知识图谱、语义搜索、自动推理、关联挖掘、对话即入库、分类管线、感知增强、子Agent编排**等核心能力。它解决了 AI Agent 的先天缺陷：跨会话失忆、上下文断裂、搜索低效、知识孤岛、无法推理、表达不通、单Agent上下文污染。

**v3.7.0 升级：Karpathy 认知 OS 五条蒸馏全落地。** 五路并行——① 尾部可靠性门控（自检 9→12 项，新增 3 个门控极端场景检查：salience 边界/demote 持久性/工作空间溢出保护）；② 幽灵标注（provenance 字段 + `compute_provenance()` 入库即标，`get_context()` 输出带标签：✅已验证/🧠推断/🔗推理步骤/❓未标注）；③ 套装固化（`sb_gating.py` 新增审计日志 `_audit_log()` + `rollback()` 回滚 + `explain()` 解释，`gating audit/rollback/explain` CLI）；④ 构建即理解校验（`sb_longterm.py` 新增 `comprehension_check()`，ingest 管�线入库前独立复述校验，未通过→降置信度+标待验证）；⑤ 能力感知路由（新建 `sb_capability.py`，8 项能力画像+能力检查+编排器集成，`capability list/check/update` CLI）。49/49 回归测试全通过。

**v3.7.1 升级：先检索后入库·代码级强制。** 把「对话即入库」从文档约定升级为 `superbrain.py` 的代码拦截——`memory add` / `longterm ingest` / `memory auto-store` 三个写入命令执行前校验「30 分钟窗口内是否做过 `memory search`」，未满足则 `exit 2` 拦截；`--force` 可显式豁免并写入 `.hardstep.json` 审计。详见「命令参考 > v3.7.1 变更」。

**v3.8.2 升级：检索融合 RRF 化 + 图谱 Mermaid 化。** ① 检索融合从 6 路手调权重求和改为 **RRF（Reciprocal Rank Fusion）**——Σ 1/(K+rank)（K=60），收割 TencentDB-Agent-Memory 的符号化范式，动态阈值按 RRF 量纲自适应；② 新增 `SB graph mermaid` 命令（`sb_mermaid.py`），把 `graph.json` 知识图谱导出为 Mermaid 图（节点按类别/type 上色、关系标签），是 TencentDB「符号化卸载」的轻量落地——让图谱可被任意 Markdown/渲染器消费。详见「命令参考 > v3.8.2 新增命令」。254/254 测试全过。

**v3.8.3 升级：图谱导出加固（surgical 修补）。** 由 Tabbit Pro 的 GLM-5.2 外部代码审阅发现并验证：`sb_mermaid.py` 的 node id 直接作为 Mermaid 标识符未净化（特殊字符 id 静默产出非法图）、`read_graph` 返回 None/畸形值缺乏守卫。修复：① 引入 `_safe_nid()` + `orig_to_safe` 映射，节点与边共用保证引用一致；② `read_graph` 返回非 dict/结构异常时走占位图而非崩溃；③ 方向非法值兜底 LR、`_sanitize` 处理换行与 `]`、悬空边附注释、去掉 `eid` 死代码。**零依赖、不改默认输出、不影响合法输入行为**。详见「命令参考 > v3.8.3 变更」。254/254 + 11 项回归全过。

**v3.8.4 升级：检索融合加固（surgical 修补）。** 由 Tabbit Pro 的 GLM-5.2 外部算法逻辑审阅发现并验证：`sb_search.py` 的 `expanded_score` 判定 `len(expanded_tokens) > len(query_tokens)` 把「去重后的 set 长度」与「含重复的 list 长度」比较——query 含重复 token 时两长度被拉平，即使词网真扩展了新 token，条件也为 False，第六路信号（词网扩展匹配）被静默关闭，整条查询召回失真。修复：记录 `base_token_count`（去重后基数），改以 `len(expanded_tokens) > base_token_count`（set-vs-set）判断扩展是否发生。**纯标准库、零依赖、不改默认输出**。新增确定性回归测试（重复 token 查询 + 仅含扩展 token 的记忆，旧逻辑漏召回、修复后召回）。详见「命令参考 > v3.8.4 变更」。254/254 + 1 项回归全过。

**v3.8.5 升级：脱敏脚本加固（surgical 修补）。** 由 Tabbit Pro 的 GLM-5.2 外部安全审阅发现并实跑验证：`prepublish_strip_local_paths.py` 的 `VAULT_ASSIGN_RE` 行尾 `$` 锚在赋值行带尾部注释时静默失配，fall-through 到 `DRIVE_PATH_RE`，脱敏结果从标准 `os.path.expanduser("~/ObsidianVault")` 降级为裸串 `"~/ObsidianVault"`（Windows 上 `~` 不展开 = 路径失效）；`DRIVE_PATH_RE` 仅覆盖 Windows 盘符路径，漏掉注释/帮助文本中的 Unix 主目录路径（`/home/xxx`、`/Users/xxx`、`/root/xxx`）；`file:///E:/` 中的盘符路径被误伤为 `file:///~/ObsidianVault`。修复：`VAULT_ASSIGN_RE` 允许可选尾注释且替换时保留原始缩进；`DRIVE_PATH_RE` 负向后行断言追加排除 `/`（`file:///` 不再误伤）；新增 `UNIX_HOME_RE` 覆盖 Unix 主目录路径。**纯标准库、零依赖、不改默认行为**。新增 `test_prepublish_strip.py` 8 项 unittest 回归（尾注释/缩进/Unix/https/file:// 控制组），全过。详见「命令参考 > v3.8.5 变更」。

所有数据本地存储（默认 `~/.workbuddy/super-brain/`），不依赖任何外部服务或 API。

**⚠️ 重要：Obsidian 集成说明**

Super Brain v3.7.2 的 **Obsidian 双向同步**是深度集成的核心功能，不是"可选附件"。它负责将记忆以 `.md` + `[[wikilink]]` 格式导出到 Obsidian vault，实现本地知识库的图谱可视化、反向链接和跨文件关联。

## 本地知识库依赖与自主选择

### 为什么需要 Obsidian？

Super Brain 的 Obsidian 同步模块（v3.7.2）提供：

| 能力 | 说明 |
|------|------|
| **记忆导出** | JSON 记忆 → `.md` 文件 + `[[wikilink]]` 双向链接 |
| **图谱可视化** | `SB obsidian canvas` 导出 `知识图谱.canvas`（json-canvas，按类别上色 + 力导向布局 + 关系标签 + 图例），在 Obsidian 中可视化知识网络 |
| **反向同步** | 用户在 Obsidian 中修改 `.md` 文件 → 同步回 Super Brain |
| **永久归档** | 即使清空 Super Brain 数据，Obsidian 中的 `.md` 仍可阅读 |

### Obsidian 导出格式（v3.7.2 升级）

- **格式底座对齐 obsidian-markdown**：元数据用 callout 块（`> [!note]` 等按类型分色），正文带 block reference（`^sb-content`）供 Bases / 跨文件引用；`[[wikilink]]` 双向链接保留。导出全面符合 Obsidian 风味 Markdown，可被 Obsidian 原生渲染、被其他 agent 复用。
- **安全护栏（Vote 式安全文件 API）**：所有写入 vault 的操作走 `safe_write_file` 受控封装——路径沙箱（仅限 `超脑记忆/` 导出目录）、拒绝 `..` 遍历、禁止写入 `.obsidian` 系统目录，仅用 `open()` 直写（不调 shell）。结构化异常不泄露系统路径。
- **图谱可视化（json-canvas，v3.7.2 记忆级增强）**：`SB obsidian canvas` 将 `graph.json` + 全部记忆导出为 `超脑记忆/知识图谱.canvas`，**三类节点共存**：① 实体节点（`graph.json`，按类别上色 + 按关联数定大小）；② 主题节点（记忆 `entity` 去重，每个主题一个绿色文本节点）；③ **记忆节点（每条记忆一个 `file` 节点，链对应 `.md`，按记忆 type 上色）**。边含实体间关系（uses/created/part_of…，显示标签）+ 记忆→主题归属边（同 `entity` 的记忆聚成星系环绕主题节点）。双组件力导向布局（实体组件与记忆组件各自收敛后并排），无依赖纯算法生成。左上角附标题 + 图例。

### 没有 Obsidian 会怎样？

**核心记忆引擎不受影响**——记忆依然正常工作（存储/搜索/推理/纠缠场/分类管线等全部可用）。缺少的只是：
- ❌ 记忆的 `.md` 文件导出与图谱可视化
- ❌ 双向同步（在 Obsidian 中编辑后写回 Super Brain）
- ❌ 与本地知识库的深度关联

**超脑语义层 × 本地知识库 = 互补分层（设计特征，非单一真相源）**
超脑（`~/.workbuddy/super-brain/` 的 JSON 记忆）负责机器可检索的语义层；本地知识库（Obsidian Vault / 工作区 `MEMORY.md` / 用户级 `~/.workbuddy/MEMORY.md`）负责人可读速查层。两者**冗余并存是设计特征**，不视为冲突。
硬步骤约定确保二者同步而非二选一：涉及技术/项目/偏好的任务，先 `SB memory search` 召回、再 `SB longterm ingest` / `memory add` 入库，本地 `MEMORY.md` 仅作冗余备份，不可当替身。（2026-07-08 升级为 pre-commit 级，详见上文「核心工作流 > 1. 对话即入库」）

### 通用版首次配置向导（Onboarding）

> 仅通用版（GitHub clone）需要此向导。本地版（作者环境）已硬编码主库路径，自动跳过本向导。

通用版**不假设任何 vault 路径**。使用者首次使用 Obsidian 同步时，必须在**一次对话**内完成以下两步：

**第 1 步 — 询问（必做）**
用 `AskUserQuestion` 或对话询问两个信息：
1. **Obsidian 安装情况与位置**：是否安装？装在哪？（未安装则进入「先给模板、装好再配」分支）
2. **主仓库（vault）路径**：使用者的知识库根目录在哪？（记忆导出目标，不能写死）

**第 2 步 — 提供搭建模板**
询问完成后，向使用者提供 `references/obsidian-vault-template.md`（路径无关的本地知识库搭建模板），并按使用者的 vault 路径定制示例中的 `<VAULT>` 占位符。

**分支处理**
- **尚未安装 Obsidian**：先给模板与目录约定，说明「装好 Obsidian 并确定 vault 后，设 `OBSIDIAN_VAULT_PATH` 或 `--vault-path` 再跑 `obsidian export`」，暂不强制配置。
- **已装且给出 vault**：引导其设 `OBSIDIAN_VAULT_PATH`（或记 `--vault-path`），立即跑一次 `obsidian export` 验证导出落盘正确。

**关键约束**
- 通用版代码里的 `DEFAULT_VAULT_PATH` 必须是**通用回退值**（如 `~/ObsidianVault`），**严禁硬编码作者机器路径**——否则 Phase 1 安全审查会判定为个人路径泄露并拦截发布。
- 路径决策权完全交给使用者；AI 只问、只提供模板，不替使用者定路径。
- 发布前脱敏（已固化）：本地活代码保留硬编码主库以获得开箱即用便利；发布到 GitHub 前，对 clone-temp 副本运行 `scripts/prepublish_strip_local_paths.py --target-dir <clone-temp根目录> --apply`，自动将硬编码 vault 路径还原为 `~/ObsidianVault`（脚本路径无关、自身过 Phase 1，只改发布副本、不动本地）。推荐顺序：Phase 3 同步 → 跑此脚本 → Phase 1 审查 → 推送。

### Persona Workspace 首次配置向导（v3.8.0+）

> 通用版（GitHub clone）首次使用 `--persona` 或发现 `persona_workspace_path` 未配置时触发。本地版（作者环境）已硬编码路径，自动跳过。

Persona workspace 是 AI 助手的**常驻身份记忆层**——跨项目始终加载，不随 cwd 切换。通用版**不假设任何路径**，由使用者选择。

**第 1 步 — 询问（必做）**

用 `AskUserQuestion` 或对话询问一个信息：

> **你想把 AI 助手的身份记忆（偏好/决策/身份等跨项目记忆）存在哪？**
>
> 1. **个人本地知识库下**（推荐）— 在你的知识库根目录下创建 `super-brain-persona/` 子目录，记忆与知识库放一起，便于备份和迁移
> 2. **Super Brain 默认位置** — `~/.workbuddy/super-brain/workspaces/persona/`，与超脑其他数据放一起
> 3. **自定义路径** — 你指定一个绝对路径

**默认行为**：用户不做指示 → 走选项 1（个人本地知识库下）。若用户尚未配置 Obsidian vault 路径，则 fallback 到选项 2。

**第 2 步 — 执行配置**

根据用户选择执行：
- **选项 1**：`SB workspace persona --path "<vault>/super-brain-persona"`（vault 路径取 Obsidian onboarding 已配置的 `OBSIDIAN_VAULT_PATH`，若未配置则问用户知识库根目录）
- **选项 2**：不执行任何命令，`persona_workspace_path` 留 `None`，`get_persona_workspace_dir()` 自动 fallback 到默认路径
- **选项 3**：`SB workspace persona --path "<用户指定路径>"`

**第 3 步 — 验证**

配置后跑 `SB workspace persona --show` 确认路径和记忆数（首次应为 0）。

**关键约束**
- 通用版代码里的 `DEFAULT_CONFIG["persona_workspace_path"]` 必须是 `None`（意为"未配置，用默认 fallback"），**严禁硬编码作者机器路径**——否则 Phase 1 安全审查会判定为个人路径泄露并拦截发布。
- 路径决策权完全交给使用者；AI 只问、只执行，不替使用者定路径。
- 本地版（作者环境）保留硬编码路径以获得开箱即用便利；发布前由 `prepublish_strip_local_paths.py` 自动还原。

**选项 A：安装 Obsidian，获得完整体验**

1. 从 [obsidian.md](https://obsidian.md) 下载安装
2. 打开已有 vault 或创建新 vault
3. 运行 `SB obsidian export` 将记忆导出为 `.md`
4. 推荐 vault 路径：任意你习惯的目录（如 `~/MyVault`）；Super Brain 默认写入 `<vault>/超脑记忆/`，可用 `OBSIDIAN_VAULT_PATH` 环境变量或 `--vault-path` 覆盖

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

## 未知发现协议 (Unknowns Discovery Protocol)（v3.7.4 新增）

> **⚠️ 实现说明 (B1 修复 2026-07-10)**：本协议是 **Agent 行为指导**（类似 v3.2.2 前置编配评估提升到 SOUL.md 的处理），映射到已有命令组合——`SB memory search` + `SB entangle mine`（Blindspot Pass）、`SB selfcheck`（Quiz 后置测验）、对话内偏离说明（Deviation Log）。**无独立 CLI 命令**，不违反 v3.7.1 代码强制哲学（协议的"动作"是 Agent 在对话中执行，而非 skill 代码调用）。若未来需独立落地，可新增 `sb_unknowns.py` + `unknowns blindspot/quiz` CLI。

> 借鉴 Anthropic Thariq Shihipar《A Field Guide to Fable: Finding Your Unknowns》(2026-07-03)。核心隐喻：**prompt 是地图，真实疆域（代码库 / 项目上下文 / 你的隐性标准）才是地形，地图永远 ≠ 地形，二者之间的 gap 叫 unknowns（未知）；AI 每遇一个 unknown 就只能猜，猜错的累积是长任务跑偏的根因。**

**四类未知（Rumsfeld 四象限，按危险度排序）：**

| 类型 | 含义 | 超脑对应动作 |
|------|------|------|
| Known Knowns 已知熟知 | 已写进 prompt 的明确需求 | 已在地图内，无需处理 |
| Known Unknowns 已知未知 | 你意识到没想好、要探索的部分 | `orchestrate assess` 显式标为待探索 |
| **Unknown Knowns 未知熟知（最危险）** | 你太理所当然、不会写进 prompt，但 AI 不知道的隐性业务逻辑 / 编码习惯 / 审美标准 | 纠缠场拉取历史同类记忆作 anchor；主动反问「这里有没有你默认但没说的标准？」 |
| Unknown Unknowns 未知未知 | 你和 AI 都没想到的盲点 / 潜藏 bug / 更好架构 | Blindspot Pass（见下）主动暴露 |

**三阶段技术（与超脑能力映射）：**

1. **Pre-implementation 动手前**
   - **Blindspot Pass 盲点审查**：接到非平凡新任务时，先 `SB memory search` + `SB entangle mine` 扫描 brief 与已知上下文的落差，主动列出「我可能忽略的未知未知」，再问用户「接下来怎么更好提问」。
   - **Reverse Interview 反向采访（v3.9.8 升级为 frontier 拷问法）**：动手前就计划/设计展开**拷问式访谈**（借鉴 mattpocock/skills `grilling` 技能），把决策画成一棵**设计树**——每个决策分支挂出依赖它的子决策。按 **rounds（轮）** 工作：**frontier = 所有前置条件已settled、现在就能问的决策**。每轮把整片 frontier 一次问完，每个问题编号 + **附上我的推荐答案**（用户只需确认/推翻，成本极低）；等用户答完再算下一轮 frontier。关键纪律：
     - **事实是 Agent 的活，决策是用户的活**——frontier 问题里凡是能从环境查的事实（文件系统/工具/记忆库），派子 agent 查，绝不问用户能自己查到的东西；只有决策才提交给用户。
     - **一次只问一个**架构级关键问题（一旦答案变了就改变底层方案的问题）仍适用于"独立决策"，但 frontier 内**并行编号多问**（它们互不依赖）；依赖未决问题的问题归入更晚的 round，不在本轮问。
     - **终止条件**：设计树 frontier 清空——每个分支都访问过、没有任何东西被静默假设。在用户确认达成共享理解前，不动手执行。
     - 问题格式：`❓ Q1 - <标题>: <正文含多个选项>` + `➡️ 推荐答案`。
   - **References 参照锚点**：引用用户历史同类项目 / 记忆作为约束 anchor，把「说不清的品味」具象化。

2. **During implementation 执行中**
   - **Deviation Log 偏离说明**：执行中每遇边缘 case 逼我偏离原方案，选最保守备选，把改动记进 `implementation_notes`（或对话里的「偏离说明」栏）再继续——让猜测可见，不偷偷魔改。

3. **Post-implementation 收尾**
   - **Quiz 后置测验**：任务完成前，生成「本次到底改了什么 / 关键决策为何」的 explainer，并复用 `sb_selfcheck` 自检；若无法向用户清晰解释某改动，说明那里藏着一个未被发现的 unknown，回到 Pre 补全。

**触发分档（细化一档，与 Simplicity First 护栏一致）：** 按任务体量 / 边界清晰度分三档，避免仪式拖死效率——

| 档位 | 触发条件 | 启用动作 | 跳过动作 |
|------|----------|----------|----------|
| **A 全仪式** | 开新项目 / 陌生代码库 / 跨多文件大改动 / 设计审美类任务（隐性标准多） | Pre 全开（盲点审查 + 反向采访 + 参照锚点）+ During（偏离说明）+ Post（后置测验） | 无 |
| **B 仅 Pre** | 中等任务、框架已知、需求基本清楚（如已知栈内的功能实现） | 仅 Pre：盲点审查 + 一次反向采访关键问题 | 跳过偏离说明 / 后置测验（除非执行中真撞偏离，临时开 During） |
| **C 跳过** | trivial 改动：typo / 翻译 / 单文件小修 / 明确查询 | 仅常规入库，不跑协议 | 全跳过 |

- **决策责任**：档位由 Agent 在任务开头用「前置编配评估」四问粗判；拿不准时**优先升档**（宁可多跑一次盲点审查，也不漏掉 Unknown Knowns）。
- **用户覆盖**：用户可随时口头要求「这次走全仪式 / 这次跳过」，覆盖 Agent 的档位判定。

**与前置编配评估协议的关系：** 本协议的 Pre 阶段是「前置编配评估协议」的**补充**而非替代——编配评估解决「要不要拆并行」，未知发现解决「需求边界清不清」。两者在新任务开头串联：先未知发现（澄清边界），再编配评估（决定执行形态）。

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

> **⚠️ pre-commit 级硬步骤（2026-07-08 用户拍板升级）**
> 上述入库不是「可选动作」，而是**非写不可的硬步骤**，且须前置检索：
> - **动手前**必跑 `SB memory search` 召回相关记忆（确认是否新主题、与既有知识如 dive-into-llms / 本地部署决策建关联）
> - **过程/收尾**必跑 `SB longterm ingest` 或 `SB memory add --type` 对话即入库
> - 本地 `MEMORY.md`（工作区 / 用户级）仅作**冗余速查备份**，**不可作为超脑语义层的替身**——两者是独立路径，禁止只写本地而漏掉超脑
> - 触发范围：技术调研、模型/工具学习、项目决策、用户偏好分享等
> - **已由 superbrain.py 代码强制**：`memory add` / `longterm ingest` / `auto-store` 三个写入命令在执行时会校验「近期（30 分钟窗口内）是否做过 memory search」；未满足则拦截（exit 2，打印诊断）。需要显式豁免时在原命令后加 `--force`（会被写入审计，仅用于自动化 / 明确豁免场景）。检索状态存于 `DEFAULT_DATA_DIR/.hardstep.json`。

> **🚨 会话开场待办检查（v3.12.2 M3-C，与硬步骤同级）**
> 完成 `SB memory search` 召回后，检查 `~/.workbuddy/super-brain/pending_ai_review.md` 是否存在且修改时间在 48 小时内：
> - **存在** → 主动读取，按其中 error 项逐项归因并给出修复方案（这是守护引擎 error 时自动落下的待办，用户无需转述）；
> - **不存在或过期** → 跳过，零开销。
> 该文件由 `sb_healthlite` 在体检 status=error 时原子写入、恢复 ok/warn 后自动清除——**不存在陈旧警报问题**，看到即处理。

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

### 10.1 可选：每日自检守护（v3.12.1 增量，**默认关闭**）

纯本地的定时守护引擎：每日自动 `graph build`（新记忆进工作空间的前提）+ 健康自检 + 门控带内检查，写入 `health_state.json` 供 Agent 异常时感知。**零 AI 用量、零联网、零遥测**——由系统计划任务直接运行，AI 不参与。

```bash
python schedule_manager.py status       # 查看安装与运行状态
python schedule_manager.py install --time 08:30   # 显式开启（默认关闭）
python schedule_manager.py uninstall    # 随时关闭
```

- 开关主入口是**可视化工作台的自动化组件面板**（规划中，组件将全部默认关闭）；命令行是开发者兜底通道
- Agent 侧：会话开场可读 `~/.workbuddy/super-brain/health_state.json`，**只有 `status=error` 才触发 L1 介入展开处理**；`warn` 只是面板提示，**不触发 L1**（token 契约：守护引擎对 warn 返回退出码 0，仅 error 返回 1）。同一 error issue 介入后应去重，避免每日重复触发

### 10.2 L1 后台整合引擎（v3.12.2，**proposal→apply 两段式**）

对标 Mem0 Dream / Zep 抽取管线 / LangMem Background / Letta sleep-time / A-Mem evolution 的**零 LLM 实现**（`sb_consolidate.py`）：三档规则式整合动作，后台只生成提案，**应用必须人工确认**。

```bash
python sb_consolidate.py --workspace X          # 生成 proposal（只读，dry-run）
python sb_consolidate.py --workspace X --apply  # 人工确认后应用（自动备份+审计+哈希重算）
python sb_healthlite.py --consolidate           # 每日守护时顺带出提案（永不自动 apply）
```

四档动作与铁律：

| 档 | 动作 | 门槛 | 铁律 |
|----|------|------|------|
| A | general 实体归一 | 词表唯一命中（既有实体，频次≥3） | 黑名单实体/对话碎片/多实体歧义不提案；绝不新建实体 |
| B | 同实体近重复合并 | simhash ≥ 0.80 | 碎片不整合；内容拼接不丢信息；被并方归档+replaced_by |
| C | 冗长陈旧压缩 | >200字 & >30天 & ≥4句 & 压缩比≤50% | 抽取式确定性抽句（实体/数字/结论句优先）；原文在备份可回滚 |
| D | 知识更新链（阶段2-B 时态） | 同句 mem_id 引用 + 更正标记词（更正/有误/supersedes…） | 三件套 superseded+replaced_by+valid_until（对齐原生 replaces）；纯引用/远处修正/相似带全部证伪排除 |

- 设计依据：2026-08-30 整合负结果（碎片整合与纯去重零收益）——引擎四档全部避开证伪路径；「整合的收益在长期库卫生（防冗长累积/防 general 回潮），不在一次性召回提升」
- D 档证伪记录（2026-08-31 生产 54 条提案实测）：「纯显式引用」把会话汇总/关联条全误报；「同实体 sim∈[0.45,0.80) + 全文任意更正词」精确率 ~7%（「修正权协议」的「修正」二字触发更正）。唯一可信证据=同句 ID+更正语义
- 时态启用（阶段2-B）：add_memory 缺省锚定 valid_from=创建日期（零行为回归）；存量回填走 `superbrain-bench/backfill_valid_from.py`（生产 673 条已回填）
- 组件注册：`~/.workbuddy/super-brain/automation_registry.json`（`background_consolidation` 组件，默认关闭，工作台面板契约）
- 保守正确行为：200-350 字短冗长记录抽 3 句压不到一半，引擎主动放弃（「压不动不如不压」），卫生审计的「整合候选」数 ≠ 可压数

### 10.3 本地工作台（M2 写通道 + C 端化，v3.12.2）

`sb_workbench.py`——纯标准库单文件 HTTP 服务，把静态看板升级为**本地控制面**（方案 C；调研否决 Electron 壳「本机 9 类坑」与「发布为应用」云端沙箱碰不到本地文件）。**只绑 127.0.0.1**，零外部依赖。

```bash
python sb_workbench.py            # 127.0.0.1:8917，自动开浏览器
python sb_workbench.py --host 0.0.0.0   # 局域网模式：手机同 Wi-Fi 访问（无鉴权，可信网络用完即关）
双击 Start-Workbench.bat          # 无代码用户入口（ASCII+CRLF 防码页坑）
双击 Start-Workbench-LAN.bat      # 无代码用户的局域网入口（R4）
```

- **面板能力（C 端化改造，2026-08-31）**：三区 IA——①状态横幅（hero：一切正常/N 项提醒/还没体检过引导，含每条 issue 的人话解释与「立即体检」「打开健康看板」「交给 AI 深入检查」CTA）②自动打理（组件=服务话术，如「记忆库自动体检」；开关+下次时间+立即体检）③需要你决定（整理建议：看看建议明细 → 确认应用两步按钮；空态显示干净）。**两段式铁律升级**：apply 从「复制命令行」改为面板内显式二次确认（`POST /api/consolidate/apply`，白名单固定脚本，永不自动 apply）；「交给 AI」提示词由后端注入真实路径（health_state.json + latest_report.json），复制即用零占位符。机制语言→结果语言全量替换（守护引擎→自动体检、整合提案→整理建议）
- **M3-A→v3 健康看板融合（双 Tab）**：`sb_dashboard.py`（M1 看板生成器内嵌版，严格只读）不再开新标签——工作台改双 Tab（`A 管家` / `B 记忆图谱`），图谱 Tab 以 `iframe /dashboard?embed=1` 隔离嵌入（懒加载，首次进入才请求；`?embed=1` 不注入工具条避免与宿主重复）+「↻ 重新生成数据」按钮（`POST /api/dashboard/refresh` 后强制重载快照）；独立访问 `/dashboard` 仍带工具条。产物落 `~/.workbuddy/super-brain/dashboard.html`
- **R1 激励层（v3.12.3-dev，2026-08-31）**：hero 下新增「节奏条」——①任务**完成率环**（SVG 手写，全局 done/total，数据 `api_state.board_stats`）②体检 **streak 大数字**（渐变式不归零语义，学 Loop：中断显示「上次连续 N 天 · 已中断 M 天 · 历史最高 K 天」，跑一次就续上；数据 `_health_pulse(health_history)`）③**42 天月历热力图**（灰=无记录/浅琥珀=1 次/琥珀=2+ 次/红=当天有 error，今日格朱砂描边，hover 出详情）。项目行加**细进度条**（琥珀，done/total 徽章替代原「N 待办」）。poll 轮询到 board 变化时本地重算 stats（`localBoardStats`，与服务端同口径），完成率环即时反映对话改动
- **R2 看板导出/导入（v3.12.3-dev，铁律 2 补课）**：「正在推进」区头新增**导出 JSON**（前端 Blob 下载 `workbench-board-YYYY-MM-DD.json`）与**导入恢复**（file input → 前端 confirm 二次确认 → `POST /api/board action=import_board`）；服务端 `_validate_import` 消毒校验（结构校验+字段净化+id 去重重生成+先过滤后截断 200 条/2000 条护栏），旧文件落盘前自动备份 `.pre-import.bak`；POST 长度上限 2KB→256KB（导入文件可达数十 KB）。数据 ≥30 条时区头温和提示备份（铁律 2 第 5 条落地）
- **R3 暗色模式（v3.12.3-dev，2026-08-31）**：CSS 变量方案——`:root[data-theme="dark"]` 重定义全量 token（琥珀/朱砂/ok/err 提亮一档保对比；**--amber-deep 语义反转**：亮色=深琥珀字、暗色=亮琥珀字；`color-scheme:dark` 让 checkbox/date/滚动条跟随）；新增 `--surface`/`--due-ink` 变量并替换全部硬编码 `#fff` 背景与 duebox 深红字；ringSvg 色 CSS 变量化（SVG style 属性）。**开关=sub 行右侧小圆钮**（月亮/太阳 SVG），偏好存 localStorage（key `wb_workbench_theme`），首次跟随 `prefers-color-scheme`；head 内联防闪脚本（URL `?theme=dark|light` > localStorage > 系统）消灭暗色用户首屏闪白；do_GET 路由剥 query 后匹配（`/?theme=` 修复）。`B 记忆图谱` Tab 的 iframe dashboard 暂保持亮色（独立产物，后续迭代）
- **R4 移动端 + iframe 自适应 + 局域网通道（v3.12.3-dev，2026-08-31）**：①`#graph-frame` 由固定 `78vh` 改**内容自适应**——同源 iframe 用 `contentDocument.scrollHeight` 量高（+24px 余量，load 事件 + 350ms 二次校准，跨域/异常保持 78vh 内滚兜底），看板随宿主页面自然滚动，移动端无嵌套滚动陷阱；②`?tab=graph` 直达通道（对称 `?theme=`，调试/截图用），配套 `renderGraphBar` null 防护（直达时 STATE 尚未加载不崩）；③**局域网模式可用化**：`--host 0.0.0.0` 显式 opt-in（默认仍只绑回环），`_lan_ip()` UDP 选路探测（连接不发包）自动打印手机可访问的 `http://<局域网IP>:8917/`，浏览器打开地址与绑定地址解耦，新增 `Start-Workbench-LAN.bat` 无代码入口（ASCII+CRLF，注明无鉴权仅限可信网络）；④移动端媒体查询补 `env(safe-area-inset-bottom)` 底部安全区。验证：Playwright（`channel:"msedge"` 驱动系统 Edge）fullPage 四连截——桌面图谱全高嵌入 / 移动 375px 单列无溢出 / 移动图谱可读 / 桌面首页零回归。**坑：Edge 裸 `--headless --screenshot` 在本机静默失败**（profile 正常创建但不落图，新旧 headless 均如此），截图一律走 Playwright
- **R5 微交互基线（v3.12.3-dev，2026-08-31，纯 CSS 零架构改动）**：六件套——①完成率环 `@keyframes ringfill`（stroke-dashoffset 157.1→目标，勾任务→poll 重绘→动画重放=完成反馈）②勾选 pop（checkbox `:checked` scale 1→1.3→1）③任务划线颜色渐变（`transition:color .3s`）④开关 spring（`cubic-bezier(.34,1.56,.64,1)` overshoot 回弹）⑤`:active` 按压 + `:focus-visible` 键盘可达（outline 琥珀）⑥`prefers-reduced-motion: reduce` 一刀切禁用（`*{animation:none!important;transition:none!important}`）。ringSvg 第二圆 style 加 `animation:ringfill .9s cubic-bezier(.2,.8,.2,1)`。**范围判定**：项目展开动画不可行——`toggleExpand→renderBoard()` innerHTML 全量重绘，新元素无过渡起点，做动画需改渲染架构，超出「微交互基线·小」记遗留。验证：13 断言全绿 + Playwright 环动画中间态（350ms 弧未画满）与终态收敛对照 + `reducedMotion:'reduce'` 上下文零 pageerror + 桌面/移动零回归

### 10.4 正在推进看板（对话即上板，v3.12.2）

面板第四区「正在推进」= 项目（状态徽章：进行中/待拍板/规划中/暂停/已完成，点击切换；**图钉置顶**；**↑↓ 排序**；**✎ 编辑现状 note**；**▾ 展开项目内任务清单**——含项目内联回车添加）+ 任务清单（checkbox、可选截止日期、逾期/7 天内到期置顶「今天要处理」高亮；无项目任务归「随手任务」组，已完成统一沉底）。数据落 `~/.workbuddy/super-brain/workbench_board.json`（首次读取自动播种真实项目；原子写；损坏自动 .corrupt.bak 备份后重播种）。

**实时同步**：面板每 5s 轻量轮询 `GET /api/board/poll`（只读 board、零子进程），`updated_at` 变化即局部刷新看板区——Agent 写文件 → 面板 ≤5s 反映；输入聚焦/编辑态自动跳过本轮应用，不打断操作。

**对话即上板（Agent 侧约定）**：对话中用户提到新任务、项目状态变化、截止日期 → 收尾时直接更新 `workbench_board.json`（schema：`{version, updated_at, projects:[{id,name,status,note,pinned,updated_at}], tasks:[{id,title,project,done,due}]}`；id 用 `t_`/`p_`+8 位 hex；due 仅 `YYYY-MM-DD` 或 null；保持原子写与字段长度：title≤120/name≤40/note≤200）。面板 CRUD 走 `POST /api/board`（action: add_task/toggle_task/del_task/add_project/update_project/del_project/move_project/toggle_pin/import_board，单端点分发，写动作仅限 board 文件）。

```bash
python sb_workbench.py            # 127.0.0.1:8917，自动开浏览器
双击 Start-Workbench.bat          # 无代码用户入口（ASCII+CRLF 防码页坑）
```
- **意图/现实分离**：开关写 automation_registry.json（意图权威源），schtask/health_state 只读展示
- `schedule_manager.py` 同步升级 registry 组件驱动：`--task <component_id>` 装卸任意组件；任务命令行**带 `--workspace`**（修复 v3.12.1 洞：schtasks 触发时无环境变量，healthlite 会跑在 default 空库）
- 全链路已实测：toggle ON → schtasks 真装（TR 含 --workspace）→ run-now exit 0 → toggle OFF → 终态默认关

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

## 命令输入契约（声明式 input_schema）

> 借鉴 DeerFlow 的 `input_schema` 设计：把"命令该填什么"从散文说明升级为结构化契约。
> 目的：① 让 AI/使用者一眼看清必填与可选；② 漏填/填错类型在调用前即可被发现（文档级契约；代码级强制校验见末尾说明）。
> 本部分为文档补丁，不单独 bump 版本号，随下次功能发布一并走版本。

### `SB memory add` — 输入契约

```yaml
input_schema:
  required:
    - name: type
      type: enum
      values: [preference, decision, task, event, fact]
      note: 记忆意图类型，决定分类与召回权重（优先级 preference>decision>task>event>fact）
    - name: content
      type: string
      note: 记忆正文，一句话到一段
  optional:
    - name: entity
      type: string
      note: 关联实体（项目/人物/工具名），用于知识图谱
    - name: confidence
      type: float
      range: [0.0, 1.0]
      default: 0.9
    - name: persona
      type: flag
      note: 写入 persona 层而非 project 层
    - name: force
      type: flag
      note: 豁免硬步骤门控（写入 .hardstep.json 审计）
```

### `SB reason decide` — 输入契约

```yaml
input_schema:
  required:
    - name: options
      type: json-array
      note: 候选方案列表，必须为 JSON 数组字符串，如 '["方案A","方案B"]'
  optional:
    - name: context
      type: string
      note: 决策背景，提升推理质量（可选但建议填）
```

> **代码级校验说明**：当前契约为文档级，提升清晰度与 AI 调用确定性。若要升级为"程序强制拦截漏填/错类型"，需另写 validator 解析此 schema（类似 `enforce_hard_step_guard` 的扩展）。非紧急，按需再上。

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

### v3.7.0 新增命令（Karpathy 蒸馏）

| 命令 | 用途 |
|------|------|
| `gating audit [--limit N]` | 查看最近门控审计记录（自动/手动晋升降级轨迹） |
| `gating rollback [--n N]` | 回滚最近 N 条可逆自动操作 |
| `gating explain --mem-id ID` | 解释一条记忆的门控状态（salience 分解+审计轨迹） |
| `capability list` | 列出所有能力画像及可靠性评分 |
| `capability check <cap_id>` | 查询单项能力的可靠性+降级策略 |
| `capability update <cap_id> --score 0.X` | 更新能力评分或证据引用 |

### v3.8.2 新增命令（RRF 检索融合 + graph mermaid）

| 命令 | 用途 |
|------|------|
| `graph mermaid [--workspace NAME] [--direction LR\|TB]` | 把知识图谱导出为 Mermaid 图（节点按类别/type 上色、关系标签），可被任意 Markdown/渲染器消费（TencentDB 符号化卸载轻量版） |

- **检索融合 RRF 化**：`search_memories()` 内部从 6 路手调权重求和改为 RRF（Σ1/(K+rank)，K=60），收割 TencentDB-Agent-Memory 的符号化范式；新增 `_signal_relevant()` 粗筛跳过纯噪声，动态阈值按 RRF 量纲自适应。召回质量对权重敏感度的依赖显著降低。

### v3.8.5 变更（脱敏脚本加固 · surgical 修补）

- **VAULT_ASSIGN_RE 尾部注释失配修复**：`prepublish_strip_local_paths.py` 的 `VAULT_ASSIGN_RE` 原以 `\)\s*$` 收尾，要求 `)` 后直接到行尾。当 `DEFAULT_VAULT_PATH` 赋值行带行内注释（如 `  # 默认库`），正则无法匹配，该行 fall-through 到 `DRIVE_PATH_RE`，脱敏结果从标准 `os.path.expanduser("~/ObsidianVault")` 降级为裸串 `"~/ObsidianVault"`——Windows 上 `~` 不展开，发布副本的 vault 路径解析被破坏。
- **修复方式**：正则收尾改为 `\)\s*(?:#.*)?$`，允许可选尾注释；替换逻辑提取并保留原始缩进（不再硬编码无缩进）。赋值行无论是否带注释，均走 VAULT 分支产出正确的 `expanduser` 包装。
- **Unix 路径覆盖 + URL 误伤修复**：
  - 新增 `UNIX_HOME_RE`（`(?<!\w)/(?:home|Users|root)/[\u4e00-\u9fffa-zA-Z0-9_./-]+`），覆盖注释/帮助文本中残留的 Unix 主目录绝对路径，避免泄露开发者主目录。
  - `DRIVE_PATH_RE` 负向后行断言由 `(?<![A-Za-z])` 扩展为 `(?<![A-Za-z/])`，排除 `file:///E:/` 中的盘符路径被误伤（`file:///E:/foo` 不再被破坏为 `file:///~/ObsidianVault`）。
- **回归测试**：新增 `test_prepublish_strip.py`（纯标准库 `unittest`，零依赖）8 项用例——无注释赋值、带尾注释赋值（P0-1）、缩进赋值（P0-2）、已通用值不改、注释中 Windows 路径、Unix 路径脱敏（P1-1）、`file://` 不误伤（P2-1）、`https://` 不误伤。全过。

### v3.8.4 变更（检索融合加固 · surgical 修补）

- **扩展信号判定修复**：`search_memories()` 的 `expanded_score` 原判定 `len(expanded_tokens) > len(query_tokens)`——`expanded_tokens` 是去重后的 `set`、`query_tokens` 是含重复的 `list`。当 query 含重复 token（如 `"python python code"`），两长度被拉平为相等，即使词网真扩展了新 token，条件也为 `False`，`expanded_score` 被静默置 0，第六路信号（词网扩展匹配）整条查询失效。
- **修复方式**：在构建 `expanded_tokens` 后记录 `base_token_count = len(expanded_tokens)`（去重后基数），循环中改用 `has_expansion = len(expanded_tokens) > base_token_count`（set-vs-set）判断扩展是否真发生。仅在确有新 token 加入时才点亮第六路，不受重复 token 干扰。
- **回归测试**：`test_v3.py` 新增确定性用例——`get_word_network` 注入返回 `["programming"]` 的假词网，query=`"python python"`（含重复），记忆内容仅含扩展 token `"programming"`。修复前 `expanded_score=0` 且无其他信号达标 → 漏召回；修复后 `has_expansion=True` → 召回。该测试精确区分新旧行为。
- **约束守住**：纯标准库零依赖、不改默认输出、不影响合法输入（无重复 token 时行为不变）、不动存储核心；未采纳审阅中 `wn` 的 None 防御（经验证 `get_word_network` 为保返回工厂，永不返回 `None`，属误报，加防御违反 Surgical Changes）。

### v3.8.3 变更（图谱导出加固 · surgical 修补）

- **node id 标识符净化**：`graph_to_mermaid()` 原把 `graph.json` 的 node id 直接塞进 Mermaid 标识符位置（如 `my node / A [x]`），含空格/中文/方括号时静默产出非法语法。新增 `_safe_nid()`（正则 `[^A-Za-z0-9_]` 替换，纯标准库）与 `orig_to_safe` 映射，节点与边共用保证两端引用一致。
- **读取守卫**：`read_graph` 返回 `None`/非 dict，或 nodes/edges 值非 dict 时，返回带 `%%` 注释的占位图而非抛 `AttributeError`。
- **健壮性微调**：`--direction` 非法值兜底为 `LR`（CLI `choices` 显式报错）；`_sanitize` 增加换行与 `]` 处理；悬空边附 `%% N 条悬空边已忽略` 注释；去除 `eid` 循环死变量。
- **约束守住**：纯标准库零依赖、不改默认输出、不影响合法 slug id 的输入行为。

### v3.8.1 变更（Persona onboarding 代码级兜底）

- **首次使用检测**：`workspace persona --show`（或无参数运行）时，`_persona_onboarding_hint()` 检测 `persona_workspace_path is None` 且 persona memories 为空，打印 onboarding 提示（三选项 + 指向 SKILL.md 向导章节）。
- **触发条件**：仅首次使用时触发——一旦配置了路径或写入了 persona 记忆，提示自动消失。
- **哲学**：与 v3.7.1 硬步骤同——用代码兜底而非靠 AI 自觉读文档。

### v3.8.0 新增命令（双层 Workspace）

| 命令 | 用途 |
|------|------|
| `workspace persona --path PATH` | 设置 persona workspace 路径（常驻身份记忆层） |
| `workspace persona --show` | 查看当前 persona 配置与记忆数 |
| `memory add ... --persona` | 写入 persona workspace 而非 project workspace |

### v3.8.0 变更（双层 Workspace 架构）

- **persona 层（常驻身份记忆）**：新增 `get_persona_workspace_dir()` / `read_persona_memories()` / `write_persona_memories()`。persona workspace 路径由 `config.persona_workspace_path` 指定（默认 `~/.workbuddy/super-brain/workspaces/persona/`）。
- **cwd 自动绑定**：新增 `resolve_workspace()`，从 `os.getcwd()` 向上找 `.workbuddy` 标记，取父目录名当 workspace 名，自动 `ensure_workspace`。`get_workspace_dir(None)` 从回退 `config.current_workspace` 改为先试 cwd 解析。
- **双层召回**：`search()` 在搜 project workspace 后，追加搜 persona workspace，persona 结果 ×1.1 boost，去重合并。
- **`--persona` flag**：`memory add --persona` 写入 persona workspace。`add_memory()` 新增 `persona=False` 参数。
- **向后兼容**：显式 `--workspace` 参数路径完全不变；`config.current_workspace` 降级为 cwd 解析不到时的 fallback。

### v3.7.1 变更（先检索后入库·代码强制）

- **硬步骤代码强制**：`memory add` / `longterm ingest` / `memory auto-store` 三个写入命令执行前调用 `enforce_hard_step_guard()`，校验 `.hardstep.json` 的 `last_search_ts` 是否在 30 分钟窗口内；未满足则 `exit 2` 拦截并打印诊断（区分"从未检索" / "窗口过期"）。
- **`--force` 显式豁免**：三命令各加 `--force`，跳过校验时打印告警并写入 `.hardstep.json` 的 `overrides[]` 审计数组（仅用于自动化 / 明确豁免场景）。
- **`memory search` 打戳**：成功后写 `last_search_ts`，解锁后续写入。
- 状态文件：`DEFAULT_DATA_DIR/.hardstep.json`（best-effort，读写失败不影响正常入库）。

### v3.6.1 变更（门控层自动接线）

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
7. **六通道信号 + RRF 秩融合**：TF-IDF + 关键词 + SimHash + 三进制 + 模糊 + 扩展 六路信号，按 Reciprocal Rank Fusion（Σ1/(K+rank)）融合，替代手调权重
8. **向后兼容**：v1.0-v2.1 功能全部保留，旧记忆可搜索

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| **v3.12.3** | **2026-08-31** | **工作台体验五连升级（R1-R5，审阅整改落地）：** ① **R1 节奏条**——任务完成率环（SVG 手写，对话勾任务即时反映）+ 体检 streak 大数字（渐变式不归零：中断显示「上次连续 N 天 · 已中断 M 天 · 历史最高 K 天」）+ 42 天月历热力图（灰/浅琥珀/琥珀/红=error，今日朱砂描边）+ 项目行细进度条；② **R2 看板导出/导入**——导出 JSON（`workbench-board-YYYY-MM-DD.json`）+ 导入恢复（服务端 `_validate_import` 消毒：结构校验+字段净化+id 去重重生成+200/2000 护栏，旧文件 `.pre-import.bak` 自动备份，POST 上限 2KB→256KB，≥30 条温和提示备份）；③ **R3 暗色模式**——`:root[data-theme="dark"]` 全量 token 重定义（--amber-deep 语义反转、color-scheme:dark 控件跟随），开关=小圆钮月亮/太阳，偏好 localStorage，head 防闪白脚本（URL `?theme=` > localStorage > 系统），修复 `/?theme=` 404（query 剥离）；④ **R4 移动端+iframe 自适应+局域网通道**——`#graph-frame` 78vh→内容自适应（同源 scrollHeight 量高+24px、load+350ms 双校准、异常兜底），`?tab=graph` 直达+null 防护，`--host 0.0.0.0` 显式 opt-in（默认仍回环）+ `_lan_ip()` UDP 选路探测自动打印手机 URL + `Start-Workbench-LAN.bat`，移动端 safe-area；⑤ **R5 微交互基线**（纯 CSS 零架构改动）——完成率环 `@keyframes ringfill` 动画（勾任务→重绘→重放=完成反馈）、勾选 pop（scale 1→1.3→1）、划线颜色渐变、开关 spring（overshoot 回弹）、`:active` 按压+`:focus-visible` 键盘可达、`prefers-reduced-motion` 一刀切禁用。**验证**：R4 26 断言+R5 13 断言全绿（含铁律 9 DAG 六渲染函数零互调）、Playwright（`channel:"msedge"`）多轮截图（环动画中间态/终态、减动效模式、移动 375 单列、双主题零回归）。
| **v3.12.2** | **2026-08-31** | **工作台全线（写通道+看板+C 端化）+ 阶段2 整合/时态 + 图谱消融：** ① **新增 `sb_consolidate.py`**——零 LLM 后台整合（对标 Mem0 Dream / Zep / LangMem / Letta / A-Mem 五家共性能力）：A 档 general 实体词表唯一命中归一（黑名单+碎片+歧义排除，绝不新建实体）、B 档同实体近重复合并（sim≥0.80，碎片不整合）、C 档冗长陈旧抽取式压缩（>200字&>30天&压缩比≤50%，压不动不如不压）、D 档知识更新链（同句 mem_id 引用+更正标记→superseded 三件套，对齐原生 replaces 语义）；后台只出 proposal **永不自动 apply**；apply 前缀断言+备份（%H%M 防同日覆盖）+审计+哈希重算。② **阶段2-B 时态启用**——add_memory 缺省锚定 valid_from=创建日期；存量回填 `backfill_valid_from.py`（生产 673 条）；D 档实测：54→2 条真更正链落地（v3.7.2 发布误记、unknowns 原稿误记），软失效设计被 selfcheck temporal_validity 打回后改对齐原生语义。③ **新增 `sb_workbench.py` 本地工作台**（方案 C：纯标准库 HTTP 服务只绑 127.0.0.1）——**C 端化三区 IA**（深色 hero 横幅+人话体检解释+服务话术卡+整理建议两步应用 `/api/consolidate/apply`+AI 提示词真实路径注入）、**正在推进看板**（对话即上板：`workbench_board.json`+`/api/board` 八 action+图钉置顶/↑↓排序/项目内展开任务/编辑现状/5s 轻量轮询实时同步）、**体检历史趋势**（`_append_history` cap 90 条+trendSvg）、**M3-A 健康看板迁入**（`sb_dashboard.py` 只读内嵌+`/dashboard` 托管）、**M3-C AI 待办自动化**（error 自动落 `pending_ai_review.md`、恢复自动清除，会话开场检查约定）；UI 对标 a1m1ng.cn v8 白盒子画廊语言（mono 编号/衬线标题/深色卡/朱砂红强调）。④ **图谱增益消融**——E1 检索增益 0（by design）/E2 门控 10 席 entanglement 驱动，一阶段「差三项」全关闭。⑤ **328 条无审计 override 已清除**（候选池 225→563，晋升 8.9% 带内）。⑥ **生产实测**——A×1+C×20+D×2；30 题 recall@5 0.933 持平零回归；test_consolidate 26 用例全绿；工作台全链路（toggle/体检/apply/看板 CRUD/置顶排序/轮询）实测通过。 |
| **v3.12.1** | **2026-08-31** | **每日自检守护引擎（可选，默认关闭）+ 交叉审计修复收尾：** ① **新增 L0 守护**——`sb_healthlite.py`（graph build + selfcheck + 门控带内只读检查 → `health_state.json`；退出码分级 warn→0 / error→1 保 token 契约；状态文件原子写 `tmp.{pid}`+`os.replace`；锁文件 30min TTL + 释放前 pid 校验防误删；--time/--keep 校验；report 治理只读目录）。② **新增计划任务管理**——`schedule_manager.py`（Windows schtasks 用户级任务 install/uninstall/status，--time HH:MM 校验、uninstall 区分「任务不存在」、GBK 码页容错；POSIX 打印 cron 行）。③ **开关策略**——默认全关，主通道=可视化工作台自动化组件面板（规划中），CLI 为开发者兜底；Agent 仅 `status=error` 触发 L1 介入，warn 仅面板提示。④ **质量过程**——切换模型三代理并行对抗性审计（审计 C）发现 P0×2+P1×5 全部修复并独立验证；全链路实测（首跑 5.4s / build 幂等 / warn 正确分级）。纯标准库零依赖。 |
| **v3.12.0** | **2026-08-31** | **检索层重建 + 图谱复活 + 相对门控（P0-A→M 十四轮对抗性开发）：** ① **检索层重建（v3.11.2 内部轮并入）**——消融证明六通道 RRF 被三路噪声拖垮（simhash/ternary ≈ 随机基线），砍成 BM25 单路；新增 `_bm25_tokenize`（CJK bigram+trigram、unigram 降权 ×0.35）修复停用词主导排序；persona 与 project 合并单次检索修量纲污染（30 题 recall@1 0.200→0.700）；访问统计时点断裂修复（`access_tracking_cutoff_ts`）；`--dedupe` 幂等写入开关（0.95 阈值标定，默认关）。② **新增自动建图**——`sb_graph.build_from_memories` + CLI `graph build`（--dry-run/幂等/写锁）：entity 节点、实体伪文档库级 IDF 余弦、top-K+地板 scale-free 建边、related_nodes 回填（合并不覆盖推理链记忆 ID）、只为有边实体建节点；图谱 14→139 节点复活，entanglement 信号恢复。③ **相对门控（scale-free）**——`get_threshold` 双模式：meta 显式=手动（persona=0.35 身份常驻），默认自动=阈值取 salience 排名第 k 高（k=min(cap, round(候选池×0.15))），分布漂移免重标（终结一天三标）；CLI `gating threshold --auto`；排名制对 confidence 偏移量免疫。④ **治理与健壮**——add_memory 写入路径事件驱动容量执行（晋升洪水 137→50 根治）、门控四写函数全量上锁（并发丢写面封堵）、实体归一化工具（general 16.9%→8.9%）、calibrate/post_build_promotion 候选池口径统一。⑤ **质量过程**——两轮对抗性审阅（P0-K/M）修 6 处真 bug（persona 结构性死锁、无锁建图、陈旧标志、门控零锁、诊断口径）；新增 test_graph_build(18)/test_relative_gating(15)；12 套件回归全绿，交付层评测 recall@5 0.933/mrr 0.807 基线持平。注：328 条无审计历史 demote override 的清除待用户拍板（不影响发布）。 |
| **v3.11.1** | **2026-08-20** | **门控容量持久执行 + 自检索引格式兼容（DSH 审阅高位项）：** ① 新增 sb_gating._cap_enforce 容量执行器，get_active_workspace 与 chain_ignite 统一过闸——旧版 cap 截断只截返回值不回写，workspace_promoted 标志只增不减（95>50）致 gating_flood_protection 持续 CRITICAL；现在超容部分持久降级（可逆审计、无 override、链为单位保留）。② check_file_integrity 兼容 v3.9.3+ 现行索引键（keyword_index/word_network_stats），消除 file_integrity 假阳性（Score Status 误报 INVALID）。③ 并入 v3.11.0 发布后未打包的 find_duplicates TF-IDF 预计算性能修复（~235s→秒级）④ test_prepublish_strip 夹具脱敏（GitHub Phase 1 发布审查零命中）。回归：test_v36 新增 T8 容量回归 5 项（36→41）。 |
| **v3.11.0** | **2026-08-13** | **遗忘治理引擎 + 检索增强：** ① **新增 `sb_forgetting` 遗忘治理模块**（v1.0.0）——遗忘优先级 = 规模因子 × (1-活跃度) × 记忆衰减因子；项目三档（active/warm/dormant）按最后访问中位数分档（≤14/15-45/>45 天），软切降权 dormant 0.5 / warm 0.8 / active 1.0，身份/护栏记忆豁免；CLI `forgetting status/scan/apply`。两天观察期验证：dormant 首次触发（RAG/Transformer 46 天）、降权不误伤强相关检索。② **检索 entity 精确命中 boost**——查询词与记忆 entity 精确命中时（大小写不敏感）在排序阶段加 `ENTITY_HIT_BOOST=0.04`，修复实验 1「RAG与记忆」反例（entity 强相关但 content 词面不重叠，排名过低被 limit 截断，rank 51→top3）。③ **修复 v3.10.0 发布遗漏**——`sb_forgetting.py`/`test_forgetting.py` 未随 v3.10.0 打包，致 superbrain `ImportError`。新增 `test_forgetting.py`(23 项) + test_v3 两回归。回归零失败（49+71+94+36+7+8+15+35+16+23）。 |
| **v3.10.0** | **2026-08-12** | **评分体系重构（待办 D + Penguin 评测范式落地）：** ① **硬/软指标分域**——`sb_selfcheck.py` 重构 `get_health_score()`，软指标（completeness/gating_flood/duplicates/consistency/timeliness/temporal_validity/orphans）从扣分项改为报告项，总分只基于「物理完整性+时效性+真损坏」；抽 `_hard_score_from_checks()` 单一真相源。② **有效性协议**——`run_full_check` 顶层新增 `score_status`（valid/invalid/degraded）+ `invalid_reason`：物理损坏 = 评测无效（score 返回 0），不是低分；与分数正交。③ **修复后验证**——`--fix` 后自动重检，`fix_validation` 记录 pre/post 硬分与 accepted，未提升则提示回滚（快照已由 backup_info 提供）。④ CLI `selfcheck`/`health` 暴露 score_status。新增 `test_v310.py`（16 项）。329 项回归零失败（49+71+92+36+7+8+15+35+16）。 |
| **v3.9.8** | **2026-08-06** | **mattpocock 纪律库吸收（四项升级）：** ① **decompose 曳光弹切片规格**（借鉴 to-tickets）——`_build_subtask` 新增 `blocking_edges`（阻塞边声明，默认空=可立即启动）+ `context_window_fit`（`_estimate_context_fit` 估算切片是否单个全新上下文窗口装下，超预算/含多独立要求→建议再拆）；`decompose_task` 新增 `slices` 汇总 + `wide_refactor` 检测（`detect_wide_refactor`——改名/类型替换/目录重组等波及全库的机械变更→expand-contract 三步序列，不做曳光弹）。② **frontier 拷问法升级反向采访**（借鉴 grilling）——设计树按 rounds 工作、每轮问整片 frontier、每问编号+附推荐答案、事实是 Agent 的活决策是用户的活、frontier 清空才动手。③ **新增 domain 项目术语表**（借鉴 CONTEXT.md 共享语言）——新模块 `sb_domain.py`，术语只存词汇定义零实现细节、当刻即写、歧义标记消解、可导出 CONTEXT.md；CLI：`domain add/get/list/remove/ambiguity/ambiguities/export/stats`。④ **双轴 code-review 固化**（借鉴 code-review）——新增 `references/review-guide.md`：Standards×Spec 并行子 agent 不合并、Fowler 12 坏味道基线全文（供注入 prompt）、repo overrides 规则、GLM-5.2 审阅实验 6 种系统性缺陷模式沉淀。新增 `test_v38.py`(35 项)。313 项回归零失败（49+71+92+36+7+8+15+35）。 |
| **v3.9.7** | **2026-07-24** | **自动触发断裂链修复：** ① 修复 `write_json` 无返回值 → `mark_search_done` 每次打印假"写入失败"警告（v3.9.5 回归）② 修复跨会话硬步骤死锁——过期窗口 / 从未检索场景改为自动重置计时器并放行，而非 `exit 2` 拦截，消除跨会话自动入库静默丢失。270 项回归零失败（15+36+49+71+92+7）。|
| **v3.9.6** | **2026-07-20** | **自检评分优化（消除振荡式扣分）：** ① 阈值调整：gating_flood ratio 0.40→0.70（密集使用场景不再误报）、duplicates simhash 0.75→0.85（跨会话项目描述不再误标）、--fix 自动合并 0.95→0.85（与检测阈值对齐）② 默认值补全：TYPE_DEFAULTS["task"] 新增 task_status="active"，新 task 天然不触发 completeness 误报 ③ completeness 白名单扩展：排除列表 +active/in_progress/pending ④ VERSION 3.9.5→3.9.6 ⑤ 自动化升级：skip 旧 maintenance/cleanup 脚本路径，改为 selfcheck --fix + 自动 demote + 自动归档 ⑥ 测试适配：177 项回归零失败（49+92+36）。|
| **v3.9.5** | **2026-07-17** | **P1+P2 系统性修复（五维度审阅完整闭环）：** ① P1-5 硬步骤门控加固：`_hardstep_save` 改 `write_json` 原子写 + 未来时间戳拒绝 + overrides 环形截断(200 条) ② P2-10 策略下沉：`enforce_hard_step_guard`/`mark_search_done` 从 `superbrain.py` 移到 `sb_gating.py`（门控策略归领域层） ③ P1-6 并发写治理：`write_json` tmp 名加 `os.getpid()` ④ P1-7 token_roi XSS：`html.escape` 转义 `content_preview`/`category`/`recommendation` ⑤ P2-9 warmup 常量共享：`WARMUP_MEMORY_THRESHOLD=15/WARMUP_SESSION_THRESHOLD=3` 移至 `sb_core.py`，`sb_reasoning`/`sb_entanglement` 统一 import ⑥ P2-11 读路径写副作用：`sb_memory.search update_access_stats` 默认 `False` ⑦ P1-8 关键路径补测：新增 `test_p1.py`(15 项)——硬步骤 exit 2/损坏 JSON 恢复/persona 双层/RRF 融合/二进制防护 ⑧ P2-12 分层依赖注释 ⑨ P2-13 发布面收尾：SKILL.md「本地知识库v1」→ 通用值、`prepublish TARGET_FILES 20` 项、dashboard CDN 降级。278 项回归零失败（49+71+92+36+7+8+15）。 |
| **v3.9.4** | **2026-07-17** | **P0 性能与安全修复（五维度审阅驱动）：** ① 搜索热路径 O(n²·terms) 退化修复：`sb_search.py` 预建 IDF 文档频率表（`_tfidf_cosine_precomputed`）+ `fuzzy_match` 长度差预筛（编辑距离下界剪枝，放在 substring 快速路径之后不误杀）。n=500 实测从 21s 降至 0.6s（35 倍），n=174 从 2.8s 降至 0.19s（15 倍）。② 零成本索引自动维护：`sb_longterm.py` 新增 `_ensure_fresh_index()`——缺失/陈旧/计数不符时自动重建；`zero_cost_retrieve` 首次含重建 1.4s，后续 **10ms**（含 keyword_index 11936 tokens 候选过滤）。③ 测试文件强制数据目录隔离：`test_v2.py`/`test_v36.py` 在 `from sb_core import` 前强制 `os.environ["SUPERBRAIN_DATA_DIR"] = mkdtemp`；`sb_orchestrator.py:1727` 内嵌测试硬编码路径→`get_workspace_dir`。④ P1-4 版本号单一来源：`sb_core.py` 新增 `VERSION` 常量，`superbrain.py` 三处兜底统一引用。263 项回归零失败（49+71+92+36+7+8）。 |
| **v3.8.5** | **2026-07-14** | **脱敏脚本加固（surgical 修补）：** 由 Tabbit Pro GLM-5.2 外部安全审阅发现并实跑验证 `prepublish_strip_local_paths.py` 的 `VAULT_ASSIGN_RE` 行尾 `$` 锚在尾部注释场景静默失配、fall-through 到 `DRIVE_PATH_RE` 降级为裸串 `~/ObsidianVault`（丢 `os.path.expanduser`，Windows 上 `~` 不展开）；`DRIVE_PATH_RE` 仅覆盖 Windows 盘符、漏 Unix 主目录路径（`/home/xxx` 等）；`file:///E:/` 盘符被误伤。修复：`VAULT_ASSIGN_RE` 允许可选尾注释 + 替换保留缩进；`DRIVE_PATH_RE` 负向后行断言排除 `/`；新增 `UNIX_HOME_RE` 覆盖 Unix 路径。新增 `test_prepublish_strip.py` 8 项 unittest 回归。纯标准库零依赖、不改默认行为。strip 8/8 回归全过，核心套件 4/5 通过（test_superbrain 的 `total==5` 为与实时记忆数耦合的既有脆弱断言、与本补丁无关）。 |
| **v3.8.4** | **2026-07-14** | **检索融合加固（surgical 修补）：** 由 Tabbit Pro GLM-5.2 外部算法逻辑审阅发现 `sb_search.py` 的 `expanded_score` 用 `len(expanded_tokens) > len(query_tokens)`（set-vs-list）误判「扩展是否发生」——query 含重复 token 时两长度拉平，即使词网真扩展新 token，条件也为 False，第六路信号静默关闭。修复：记录 `base_token_count`（去重基数），改以 `len(expanded_tokens) > base_token_count`（set-vs-set）判断。新增确定性回归测试（重复 token 查询 + 仅含扩展 token 的记忆，旧逻辑漏召回/修复后召回）。纯标准库零依赖、不改默认输出。254/254 + 1 项回归全过，零回归。 |
| **v3.8.3** | **2026-07-14** | **图谱导出加固（surgical 修补）：** 由 Tabbit Pro GLM-5.2 外部审阅发现 `sb_mermaid.py` 的 node id 未净化（特殊字符 id 静默产出非法 Mermaid 图）、`read_graph` 缺守卫。修复：引入 `_safe_nid()` + `orig_to_safe` 映射净化标识符；`read_graph` 返 None/非 dict 走占位图；方向非法兜底 LR、`_sanitize` 处理换行/`]`、悬空边注释、去 `eid` 死代码。零依赖、不改默认输出、不影响合法输入。254/254 + 11 项回归全过，零回归。 |
| **v3.8.2** | **2026-07-14** | **检索融合 RRF 化 + 图谱 Mermaid 化：** ① 检索融合重构——弃用 6 路手调权重求和，改为 RRF（Reciprocal Rank Fusion，Σ1/(K+rank)，K=60），收割 TencentDB-Agent-Memory 符号化范式；新增 `_signal_relevant()` 粗筛（任一路信号达最低阈值才入候选）跳过纯噪声，动态阈值按 RRF 量纲自适应。② 新增 `graph mermaid` 命令（`sb_mermaid.py`）：把 `graph.json` 知识图谱导出为 Mermaid 图（实体/记忆节点按类别/type 上色、关系标签、方向可选 LR/TB），是 TencentDB「符号化卸载」的轻量落地。`SB graph mermaid [--workspace NAME] [--direction LR|TB]`。③ SKILL.md 新增「命令输入契约」声明式 input_schema 段。254/254 测试全过，零回归。 |
| **v3.8.1** | **2026-07-11** | **Persona onboarding 代码级兜底：** `superbrain.py` 新增 `_persona_onboarding_hint()`——`workspace persona --show`（或无参数运行）时，检测 `persona_workspace_path is None` 且 persona memories 为空，则打印 onboarding 提示（三选项 + 指向 SKILL.md 向导章节）。将 persona onboarding 从纯文档约定升级为代码级提示，与 v3.7.1 硬步骤同哲学：用代码兜底而非靠纪律。 |
| **v3.8.0** | **2026-07-11** | **双层 Workspace 架构（persona × project 分离）：** 新增 persona workspace（常驻身份记忆层）——砚的身份记忆（偏好/决策/身份/跨项目事实）独立存储，不随 cwd 切换。对应 Freehold L1（始终自有数据主权）vs L2/L3（项目能力层可换）。① `sb_core.py` 新增 `resolve_workspace()`（cwd→.workbuddy 自动绑定，替代全局单激活开关）、`get_persona_workspace_dir()`、`read_persona_memories()`、`write_persona_memories()`；`get_workspace_dir()` 回退逻辑改为先试 cwd 解析；DEFAULT_CONFIG 新增 `persona_workspace_path` 字段。② `sb_memory.py` `search()` 双层合并召回（persona 结果 ×1.1 boost，去重）；`add_memory()` 新增 `persona=False` 参数，`persona=True` 时写入 persona workspace。③ `superbrain.py` 新增 `workspace persona --path/--show` CLI 子命令；`memory add` 新增 `--persona` flag。④ 通用版首次使用时通过 `workspace persona --path` 配置路径，默认 fallback 到 `~/.workbuddy/super-brain/workspaces/persona/`。49/49 回归全通过，零回归。 |
| **v3.7.5** | **2026-07-10** | **审计驱动修复：** 运行级深度审计发现 6 确认 Bug + 16 疑似风险 + 13 未知盲区。22 项修复覆盖 9 文件：原子写入(B6)、测试隔离(B2)、空 content 检查(B3)、硬步骤相关性校验(B4/R1)与 save 报错(R2)与 force 审计增强(R3)、search 写副作用参数化(R4)、过期格式校验(R5)、replaces 时序修复(R10)、SimHash 冲突检测增强(R11)、dedup 失败记录(R13)、domain_floor 取最大值(B5)、capability 日志增强(R6)、profile 缓存(R9) 、comprehension_check 局限性注释(R7/R8)、selfcheck 索引失败记录(R12)、Obsidian frontmatter 解析增强(R14/R15)。SKILL.md 未知发现协议标注澄清(B1)。254/254 测试全过，零回归。 |
| **v3.7.4** | **2026-07-09** | **未知发现协议（Unknowns Discovery Protocol）：** 借鉴 Anthropic Thariq Shihipar《A Field Guide to Fable: Finding Your Unknowns》，新增独立章节把「需求澄清」系统化接入超脑。覆盖四类未知（Rumsfeld 四象限）与三阶段技术——Pre(Blindspot Pass 盲点审查 + Reverse Interview 反向采访 + References 参照锚点，映射 `memory search`/`entangle`)、During(Deviation Log 偏离说明，让猜测可见)、Post(Quiz 后置测验，复用 `sb_selfcheck`)。与「前置编配评估协议」互补：先未知发现澄清边界，再编配评估决定执行形态。仅对非平凡任务启用，trivial 改动按 Simplicity First 跳过。触发条件于 2026-07-09 用户要求细化为一档三档：A 全仪式（新项目/陌生库/大改动/设计审美类）/ B 仅 Pre（中等已知框架任务）/ C 跳过（trivial），拿不准优先升档，用户可口头覆盖。 |
| **v3.7.2** | **2026-07-09** | **Obsidian 本地知识库升级（Phase B）：** ① 格式底座对齐 obsidian-markdown——元数据改为 callout 块（按类型分色）、正文加 `^sb-content` block reference，导出全面符合 Obsidian 风味 Markdown；② 安全护栏——新增 `safe_write_file` 受控封装（路径沙箱 + 拒绝 `..` 遍历 + 禁止写入 `.obsidian` 系统目录，仅 `open()` 直写不调 shell），替换全部裸写；③ 图谱可视化——新增 `export_graph_as_canvas` + `SB obsidian canvas` 子命令，将 `graph.json` 导出为 `知识图谱.canvas`（json-canvas），节点链对应 `.md`、边为关联。新增 `test_obsidian.py`（7 项测试全过）。 |
| **v3.7.1** | **2026-07-08** | **先检索后入库·代码级强制：** `superbrain.py` 新增 `enforce_hard_step_guard()` + `mark_search_done()`，对 `memory add` / `longterm ingest` / `memory auto-store` 三个写入命令做拦截——未检测到「30 分钟窗口内做过 `memory search`」则 `exit 2` 拦截并打印诊断；三命令各加 `--force` 显式豁免（写入 `.hardstep.json` 的 `overrides[]` 审计）；`memory search` 成功后写 `last_search_ts`。状态文件 `DEFAULT_DATA_DIR/.hardstep.json`（best-effort）。功能验证拦截/放行/豁免三路径全过。 |
| **v3.7.0** | **2026-07-08** | **Karpathy 认知 OS 五条蒸馏全落地：** ① 尾部可靠性门控——`sb_selfcheck.py` 新增 3 个门控极端场景自检项（salience_bounds/demote_integrity/flood_protection），自检总数 9→12，health_score 更新；② 幽灵标注——`sb_memory.py` 新增 PROVENANCE_LABELS + `compute_provenance()`，`add_memory` 入库即标，`get_context` 输出带来源标签（✅已验证/🧠推断/🔗推理步骤/❓未标注）；③ 套装固化——`sb_gating.py` 新增审计日志 `_audit_log()` / `rollback()` / `explain()` + `audit_log.json`，`gating audit/rollback/explain` CLI；④ 构建即理解校验——`sb_longterm.py` 新增 `comprehension_check()`，ingest 管�线入库前独立复述校验；⑤ 能力感知路由——新建 `sb_capability.py`（8 项能力画像+能力检查+编排器集成），`capability list/check/update` CLI。修复 `get_health_score` 重复循环 bug。49/49 回归全通过。 |
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
| **v3.1.0** | 2026-07-02 | 五大升级：反污染规则(P0)低置信度决策+未解决错误+SimHash去重、Obsidian双向同步(P1)JSON→.md+[[wikilink]]导出写入 Obsidian vault/超脑记忆、冷启动门控(P1)memory<15+sessions<3→仅感知存储、退场生命周期(P2)硬删除线+自动备份、会话生命周期协议(P2)T1启动+T2收尾+T3健康扫描。61项测试全通过。 |
| **v3.0.1** | 2026-07-02 | 被动触发修复：SKILL.md 新增自然语言触发场景表（8种场景→命令映射）；USER.md 注入超脑使用约定（每会话硬注入）；SOUL.md Continuity 节增加超脑主动使用指令。三层冗余确保每会话感知。 |
| **v3.0.0** | 2026-06-29 | 八大升级：三进制哈希字词网络（3^64状态）、分类管线（定义/闲聊差异化衰减）、感知增强（学/查自动判断）、推理引擎（关键点提取+逻辑分析+结论推导）、纠缠场（三通道关联挖掘）、上下文记忆（主题聚类+跨会话追踪）、本地长期记忆（对话即入库+零成本检索）、记忆引擎升级（自动存储+错别字纠偏+表达学习）。61项测试全通过。 |
| v2.1.0 | 2026-06-28 | 记忆双时间机制、动态阈值检索、自检时间有效性指标 |
| v2.0.0 | 2026-06-27 | SkillOpt 自我进化引擎、执行轨迹记录、验证门控 |
| v1.0.0 | 2026-06-26 | 初始版本：六模块、SimHash+TF-IDF 检索、Workspace 隔离 |

## 参考文档

- `references/architecture.md` — 完整架构、数据流、模块交互
- `references/data-schema.md` — 记忆、图谱、配置的数据模式
- `references/token-optimization.md` — Token 优化策略与量化指标
- `references/review-guide.md` — 双轴代码审阅规范（v3.9.8）：Standards×Spec 并行子 agent、Fowler 12 坏味道基线全文（供注入审阅 prompt）、repo 覆盖规则、审阅流程。GLM-5.2 外部审阅实验的纪律固化。

## 项目术语表（v3.9.8，借鉴 mattpocock CONTEXT.md 共享语言）

**问题**：项目讨论中"说不清的品味"和行话漂移是 Unknown Knowns 的高发区——你默认懂了、AI 默认猜了，两端对不上。术语表提供**人机共享的词汇共识**。

**核心纪律**（源自 mattpocock/skills 的 CONTEXT.md）：
- 术语表**只存词汇定义**——"It is a glossary and nothing else"。严禁 spec、草稿、实现细节混入。
- 术语一经确定**当刻即写**（capture as they happen），不批量攒。
- 歧义当场标记并记录消解方案（`SB domain ambiguity`），避免"backlog 既是工具又是工作量"这类二义残留。
- 项目语境切换时先 `SB domain list` 召回术语，agent 用词与项目一致 → 思考 token 下降、沟通误差减半。

**命令**（v3.9.8 新增）：

| 命令 | 用途 |
|------|------|
| `domain add <term> <definition> [--status proposed\|accepted\|deprecated] [--avoid 同义词,...]` | 新增/更新术语（当刻即写） |
| `domain get <term>` | 查询单个术语 |
| `domain list [--status ...]` | 列出术语 |
| `domain remove <term>` | 删除术语 |
| `domain ambiguity <term> --conflict "..." --resolution "..."` | 标记术语歧义与消解 |
| `domain ambiguities` | 列出歧义记录 |
| `domain export [--path ...]` | 导出 CONTEXT.md（人读/agent 共享格式） |
| `domain stats` | 术语表统计 |

**与超脑记忆的关系**：术语表是**显式约定层**（agent 行为约束），记忆是**隐式检索层**（语义召回）。同一术语可同时存在于两者，不冲突——术语表负责"该怎么说"，记忆负责"之前聊过什么"。
