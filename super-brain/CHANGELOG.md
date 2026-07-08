# Changelog — Super Brain 超脑

## v3.7.2 (2026-07-09)

### Obsidian 本地知识库升级（Phase B：格式 / 安全 / 可视化）

基于 10 个 Obsidian 相关技能的调研（Phase A），对 `sb_obsidian.py` 做三块升级：

- **① 格式底座对齐（obsidian-markdown）**
  - 元数据从 `> **类型**:` 纯文本改为 Obsidian callout 块（`> [!note]`/`[!info]`/`[!tip]`/`[!warning]`/`[!todo]`/`[!question]`/`[!quote]`，按记忆类型分色）
  - 正文加 block reference `^sb-content`，为 Bases / 跨文件引用打底
  - `[[wikilink]]` 双向链接保留；导出全面符合 Obsidian 风味 Markdown
- **② 安全护栏（Vote 式安全文件 API）**
  - 新增 `safe_write_file(filepath, content, vault_root)` + `SafeWriteError`
  - 路径沙箱（仅限 `超脑记忆/` 导出目录）、拒绝 `..` 遍历、禁止写入 `.obsidian` 系统目录
  - 仅用 `open()` 直写（不调 shell），结构化异常不泄露系统路径
  - 替换 `export_to_obsidian` / `_INDEX.md` / `export_memory_as_card` 全部裸写
- **③ 图谱可视化（json-canvas）**
  - 新增 `export_graph_as_canvas(workspace, vault_path)`：读 `graph.json` → 生成 `超脑记忆/知识图谱.canvas`
  - 初版：节点 = 记忆（`file` 节点链对应 `.md`）/ 实体（`text` 节点），边 = 关联关系，环形布局（无外部依赖）
  - **增强（同版本内）**：修复「图谱偏素、看不懂」——实体节点改为 `text` 节点并按**类别上色**（person/project/organization/tool/concept→Obsidian 预设色）、按**关联数自适应大小**（枢纽放大）、**力导向布局**（相连聚拢、无关节点分离，替代空圈）、边显示**关系类型标签**（uses/created/part_of/…）、左上角附**标题 + 类别图例**；新增 `_force_directed_layout` / `_node_size_by_degree` / `_first_nonempty_graph` 辅助函数与空图回退
  - `superbrain.py` 新增 `obsidian canvas` 子命令

### 测试

- 新增 `test_obsidian.py`（7 项测试全过）：callout 渲染、block reference、安全写合法/拒绝遍历/拒绝越界、导出经安全写落盘、canvas 合法 JSON / 节点边数量一致 / 坐标范围 / 边引用存在节点。

---

## v3.7.1 (2026-07-08)

### 新增：先检索后入库·代码级强制（pre-commit 硬步骤）

把「对话即入库」从 SKILL.md 文档约定升级为 `superbrain.py` 的代码拦截。

- `superbrain.py` 新增 `enforce_hard_step_guard(force)` + `mark_search_done()`：
  - 状态文件 `DEFAULT_DATA_DIR/.hardstep.json` 记录 `last_search_ts` 与 `overrides[]`
  - `memory add` / `longterm ingest` / `memory auto-store` 三个写入命令入口接入校验
  - 窗口常量 `HARDSTEP_WINDOW_SECONDS = 30 * 60`（30 分钟任务窗口）
- 未满足「窗口内做过 `memory search`」则 `sys.exit(2)` 拦截，诊断区分"从未检索" / "窗口过期"
- 三命令各加 `--force`：跳过校验并打印告警，时间戳写入 `overrides[]` 审计数组（仅用于自动化 / 明确豁免）
- `memory search` 成功后写 `last_search_ts`，解锁后续写入
- 状态文件读写 best-effort，异常不影响正常入库

### 测试
- 三路径功能验证全过：① 无检索直接写入 → exit 2 拦截；② 检索后写入 → 正常；③ `--force` → 豁免 + 审计落盘
- 验证中自身入库命令被新校验拦下，先 search 再 add 通过——闭环确认生效

### 背景
- v3.7.0（2026-07-08）落地「对话即入库」文档级硬步骤约定；本版本将其升级为代码强制（用户拍板「需要强制」）

---

## v3.7.0 (2026-07-08)

### 变更：Karpathy 认知 OS 五条蒸馏全落地（详见发布级 CHANGELOG v3.7.0 条目）
- 尾部可靠性门控（自检 9→12 项，新增 3 个门控极端场景检查：salience 边界/demote 持久性/工作空间溢出保护）
- 幽灵标注（provenance 字段 + compute_provenance()，入库即标，get_context 输出带来源标签）
- 套装固化（sb_gating.py 审计日志 _audit_log()/rollback()/explain() + gating audit/rollback/explain CLI）
- 构建即理解校验（sb_longterm.py comprehension_check()，ingest 入库前独立复述校验）
- 能力感知路由（新建 sb_capability.py，8 项能力画像+能力检查+编排器集成，capability list/check/update CLI）
- 49/49 回归测试全通过

## v3.6.1 (2026-07-08)

### 变更：门控层自动接线（GWT 选择性原则落地 ingest 主干）
把 v3.6.0 建好的门控层从"可手动治理"升级为"入库即自动运转"。

- `sb_memory.py` 的 `add_memory` 写盘前调用 `compute_salience` + `is_promoted`：
  - 单点接入即覆盖 `memory add` / `auto_store` / `longterm ingest` 全部入口
  - 晋升（salience 跨阈值 → `workspace_promoted`）在**编码时发生**，而非查询时惰性重算
- 新增 `gating_override` 字段（promote / demote / None）：
  - 修复 v3.6.0 的 demote 失效——原 `get_active_workspace` 手动 demote 设的 `False`
    会被显著度重算覆盖（demote 形同虚设）
  - `promote` / `demote` 改为写入 `gating_override`，查询时优先于显著度重算
- 链式点燃仍委托 `get_active_workspace` 查询时统一做，避免每条入库全量扫

### 测试
- `test_v36.py` 扩展至 36 项（新增 11 项自动晋升 + demote 修复用例）
- 回归 `test_superbrain.py`：49/49 全通过

### 修复
- `get_active_workspace` 手动 demote 被显著度重算覆盖失效 —— 新增 `gating_override`
  区分手动与自动判定

---

## v3.6.0 (2026-07-08)

### 新增：全局工作空间门控层（Global Workspace Gating）
受 Anthropic《A Global Workspace in Language Models》(2026-07-06) 启发。
论文核心：语言模型的"可言语表征"构成一个全局工作空间——绝大多数处理在
特权子空间(J-space)之外自动进行，只有跨过"点燃(Ignition)"门槛的表征才
被广播进全局工作空间参与推理。超脑原本"对话即入库全量提升进工作空间"违背
该选择性原则，本次修复为两层架构。

- `sb_gating.py`（新建）：
  - `compute_salience(mem, ws)` — confidence / recency(半衰期30d) /
    access_count / entanglement / type 基线 五信号加权，映射到 [0,1]
  - `get_threshold` / `set_threshold` — 每 workspace 晋升阈值（默认 0.35）
  - `is_promoted` / `chain_ignite` — 链式点燃，推理链任一节点晋升→整链 Ignition
  - `get_active_workspace(ws, cap)` — 容量上限约束的"全局工作空间"子集
  - `promote` / `demote` — 单条记忆人工覆盖
  - `calibrate` — 报告各阈值晋升比例，调向 GWT 8-25% 区间
  - `get_status` — 诊断快照
- `sb_memory.py`：
  - 新增 `reasoning_intermediate` 记忆类型（scope=session, category=reasoning）
  - `add_memory` 记忆字典新增 `salience` / `chain_id` / `reasoning_role` /
    `workspace_promoted` 四字段
  - `get_context` 新增 `workspace_only` 参数（仅返回已晋升记忆），并透出
    `workspace_promoted` 标志
- `sb_reasoning.py`：
  - 新增 `capture_reasoning_chain(text, source_id, ws)` — 把文本推理链捕获为
    `reasoning_intermediate` 记忆，共享顶层 `chain_id` + 双向 `related_nodes`
- `superbrain.py` CLI：
  - 新增 `gating` 子命令（status/active/promote/demote/threshold/calibrate）
  - 新增 `reason capture` 子命令
  - `memory context` 新增 `--workspace-only` 开关

### 测试
- 新增 `test_v36.py`：25 项（salience 单调性 / chain_ignite / reasoning_intermediate
  落库 / 活跃工作空间子集与容量 / context 选择性 / 门控 CLI 可调用性）
- 回归 `test_superbrain.py`：49/49 全通过（workspace 隔离，不触碰 production）

### 修复
- `capture_reasoning_chain` 原本只把 `chain_id` 写进 attributes，导致顶层字段为空、
  `chain_ignite` 无法据 `chain_id` 整链点燃 —— 已改为写入记忆顶层 `chain_id`。
- `get_context` 的 `entry` 未透出 `workspace_promoted`，`--workspace-only` 结果不可验证
  —— 已透出该标志。

---

## v3.5.0 (2026-07-07)
Token ROI 仪表盘全面升级：`calc_token_roi_trend()` 30天趋势回溯、每条记忆
`recommendation` 可行动建议、`generate_dashboard_html()` 新增趋势折线图和负 ROI
诊断表、CLI 新增 `--dashboard` 和 `--trend-days`、Obsidian Dataview 看板同步。
修复 `test_superbrain.py` workspace 隔离。49/49 测试全通过。

## v3.4.3 (2026-07-06)
P0 数据安全修复：`read_json()` 解析失败打印 stderr 警告；`read_memories()` 在
文件损坏时自动备份再返回 []，防止 `memory add` 覆盖丢失全部记忆。

## v3.4.2 (2026-07-06)
扣子 Linux 云端测试修复（210/211 通过），5 项跨平台兼容性 Bug。

## v3.4.1 (2026-07-06)
T2 阶段感知自动触发（强制规则 #6 + 四类阶段转换信号）。

## v3.4.0 (2026-07-05)
物理层自检（9 项）+ Token ROI 量化模块。

## v3.3.0 (2026-06-29)
Goal Continuation 续跑机制（结构化评估 + SHA256 停滞检测 + 4 次续跑上限）。

## v3.2.x (2026-06-26 ~ 2026-07-03)
子 Agent 编排器、前置编配评估、SOUL.md 四问判断前移。

## v3.0.0 (2026-06-26)
三进制哈希字词网络、六通道融合搜索、分类管线、感知增强、推理引擎、纠缠场、
上下文记忆、本地长期记忆、错别字纠偏、表达习惯学习。

## v1.0.0 ~ v2.1.0 (2026-06-22 ~ 2026-06-25)
基础记忆引擎、SimHash 语义搜索、知识图谱、自检系统、SkillOpt、执行轨迹、
Obsidian 双向同步、工作空间隔离、会话生命周期协议、Token 优化。
