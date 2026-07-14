# Changelog — Super Brain 超脑

## v3.8.6 (2026-07-14)

### 修复 — 门控与纠缠加固（surgical 修补，由 Tabbit GLM-5.2 外部审阅发现并实跑验证）

**sb_gating.py:**
- rollback 先写 memory 再写 audit log → 崩溃窗口导致重复回滚；改为先标记 audit 再恢复 memory（2行调序）
- `get_active_workspace` 函数名 `get_` 暗示只读但实际写盘；docstring 首行显式标注 "Persists promoted state to disk" + 并发声明

**sb_entanglement.py:**
- `reinforce_links` 的 `int(strength * 10)` 向零截断，`strength < 0.1` 静默丢弃；改为 `max(1, int(round(strength * 10)))`（2行）
- graph 通道权重无归一化守卫（未来若产生 weight > 1.0 会主导 combined 排名）；增 `min(1.0, weight)`（1行）
- `query_entanglement` 聚和用无归一化加和，偏向「广覆盖弱关联」；改为 `max()` 取峰值（1行）

5 处 surgical 修改，纯标准库零依赖，262 项回归全过。

## v3.8.5 (2026-07-14)

### 修复 — 脱敏脚本加固（surgical 修补，由 Tabbit GLM-5.2 外部安全审阅发现并实跑验证）
- `prepublish_strip_local_paths.py` 的 `VAULT_ASSIGN_RE` 行尾 `$` 锚在 `DEFAULT_VAULT_PATH` 赋值行带尾部注释时静默失配，fall-through 到 `DRIVE_PATH_RE`，脱敏结果从标准 `os.path.expanduser("~/ObsidianVault")` 降级为裸串 `"~/ObsidianVault"`（Windows 上 `~` 不展开 = 路径失效）
- `DRIVE_PATH_RE` 仅覆盖 Windows 盘符路径，漏掉注释/帮助文本中的 Unix 主目录路径（`/home/xxx`、`/Users/xxx`、`/root/xxx`）
- `file:///E:/` 中的盘符路径被误伤为 `file:///~/ObsidianVault`
- 修复：`VAULT_ASSIGN_RE` 收尾改为 `\)\s*(?:#.*)?$`（允许可选尾注释），替换时提取并保留原始缩进；`DRIVE_PATH_RE` 负向后行断言由 `(?<![A-Za-z])` 扩展为 `(?<![A-Za-z/])`（排除 `file:///`）；新增 `UNIX_HOME_RE` 覆盖 Unix 主目录路径
- 新增 `test_prepublish_strip.py`（纯标准库 `unittest`，零依赖）8 项回归测试：无注释赋值、带尾注释赋值、缩进赋值、已通用值不改、Windows 路径、Unix 路径脱敏、`file://` 不误伤、`https://` 不误伤——全过
- 纯标准库、零依赖、不改默认行为

## v3.8.4 (2026-07-14)

### 修复 — 检索融合加固（surgical 修补，由 Tabbit GLM-5.2 外部算法逻辑审阅发现并验证）
- `sb_search.py` 的 `expanded_score` 判定 `len(expanded_tokens) > len(query_tokens)` 把「去重后的 set 长度」与「含重复的 list 长度」比较——query 含重复 token（如 `"python python code"`）时两长度被拉平，即使词网真扩展了新 token，条件也为 `False`，第六路信号（词网扩展匹配）被静默关闭，整条查询召回失真
- 修复：构建 `expanded_tokens` 后记录 `base_token_count = len(expanded_tokens)`（去重后基数），循环中改以 `has_expansion = len(expanded_tokens) > base_token_count`（set-vs-set）判断扩展是否真发生；仅在确有新 token 加入时才点亮第六路
- `test_v3.py` 新增确定性回归测试（`get_word_network` 注入返回 `["programming"]` 的假词网，query=`"python python"` 含重复，记忆内容仅含扩展 token `"programming"`）：修复前 `expanded_score=0` 且无其他信号达标 → 漏召回；修复后 `has_expansion=True` → 召回。精确区分新旧行为
- 约束守住：纯标准库零依赖、不改默认输出、不影响合法输入（无重复 token 时行为不变）、不动存储核心；审阅中 `wn` 的 None 防御经核实为误报（`get_word_network` 为保返回工厂，永不返回 `None`），未采纳以免违反 Surgical Changes
- 254/254 + 1 项回归全过，零回归

## v3.8.3 (2026-07-14)

### 修复 — 图谱导出加固（surgical 修补，由 Tabbit GLM-5.2 外部审阅发现）
- `sb_mermaid.py` 的 node id 直接作为 Mermaid 标识符未净化（特殊字符 id 如 `my node / A [x]` 静默产出非法图）——新增 `_safe_nid()`（正则 `[^A-Za-z0-9_]` 替换，纯标准库）+ `orig_to_safe` 映射，节点与边共用保证引用一致
- `read_graph` 返回 `None`/非 dict 或 nodes/edges 值非 dict 时缺守卫（抛 `AttributeError`）——改为返回带 `%%` 注释的占位图
- `--direction` 非法值兜底为 `LR`（CLI `choices` 显式报错）；`_sanitize` 增加换行与 `]` 处理；悬空边附 `%% N 条悬空边已忽略` 注释；去除 `eid` 循环死变量
- 约束守住：纯标准库零依赖、不改默认输出、不影响合法 slug id 的输入行为
- 254/254 + 11 项回归全过，零回归

## v3.8.2 (2026-07-14)

### 升级 — 检索融合 RRF 化 + 图谱 Mermaid 化
- 检索融合重构：弃用 6 路手调权重求和，改为 **RRF（Reciprocal Rank Fusion，Σ1/(K+rank)，K=60）**，收割 TencentDB-Agent-Memory 的符号化范式；新增 `_signal_relevant()` 粗筛（任一路信号达最低阈值才入候选）跳过纯噪声，动态阈值按 RRF 量纲自适应
- 新增 `graph mermaid` 命令（`sb_mermaid.py`）：把 `graph.json` 知识图谱导出为 Mermaid 图（实体/记忆节点按类别/type 上色、关系标签、方向可选 LR/TB），是 TencentDB「符号化卸载」的轻量落地——图谱可被任意 Markdown/渲染器消费
- `SKILL.md` 新增「命令输入契约」声明式 input_schema 段（`memory add` / `reason decide` 等），提升 AI 调用确定性
- 254/254 测试全过，零回归

## v3.8.1 (2026-07-11)

### 新增 — Persona onboarding 代码级兜底
- `superbrain.py` 新增 `_persona_onboarding_hint()`：`workspace persona --show`（或无参数运行）时，检测 `persona_workspace_path is None` 且 persona memories 为空，则打印 onboarding 提示（三选项 + 指向 SKILL.md 向导章节）
- 将 persona onboarding 从纯文档约定升级为代码级提示，与 v3.7.1 硬步骤同哲学：用代码兜底而非靠纪律

## v3.8.0 (2026-07-11)

### 新增 — 双层 Workspace 架构（persona × project 分离）
- 新增 persona workspace（常驻身份记忆层）：AI 助手的身份记忆（偏好/决策/身份/跨项目事实）独立存储，不随 cwd 切换；对应 Freehold L1（始终自有数据主权）vs L2/L3（项目能力层可换）
- `sb_core.py` 新增 `resolve_workspace()`（cwd→.workbuddy 自动绑定）、`get_persona_workspace_dir()` / `read_persona_memories()` / `write_persona_memories()`；`sb_memory.py` `search()` 双层合并召回（persona 结果 ×1.1 boost，去重）
- `superbrain.py` 新增 `workspace persona --path/--show` CLI；`memory add` 新增 `--persona` flag
- 49/49 回归全通过，零回归

## v3.7.5 (2026-07-10)

### 修复 — 审计驱动修复（22 项）
- 运行级深度审计发现 6 确认 Bug + 16 疑似风险 + 13 未知盲区，22 项修复覆盖 9 文件：原子写入、测试隔离、空 content 检查、硬步骤相关性校验与 save 报错/force 审计增强、search 写副作用参数化、过期格式校验、replaces 时序修复、SimHash 冲突检测增强、dedup 失败记录、domain_floor 取最大值、capability 日志增强、profile 缓存、comprehension_check 局限性注释、selfcheck 索引失败记录、Obsidian frontmatter 解析增强
- SKILL.md 未知发现协议标注澄清
- 254/254 测试全过，零回归

## v3.7.4 (2026-07-09)

### 新增 — 未知发现协议（Unknowns Discovery Protocol）
- 借鉴 Anthropic Thariq Shihipar《A Field Guide to Fable: Finding Your Unknowns》，新增独立章节把「需求澄清」系统化接入超脑
- 覆盖四类未知（Rumsfeld 四象限）与三阶段技术——Pre（Blindspot Pass / Reverse Interview / References）、During（Deviation Log）、Post（Quiz 后置测验，复用 `sb_selfcheck`）
- 与「前置编配评估协议」互补：先未知发现澄清边界，再编配评估决定执行形态；仅对非平凡任务启用，trivial 改动按 Simplicity First 跳过

## v3.7.3 (2026-07-09)

### 修复 / 安全 — 发布前路径脱敏固化
- 新增 `scripts/prepublish_strip_local_paths.py`：路径无关（自身不含任何个人路径），发布前将硬编码 vault 路径还原为通用回退值 `~/ObsidianVault`；默认 dry-run 预览，`--apply` 才改写；只改 clone-temp 发布副本，绝不碰本地活代码
- 本地版与通用版（GitHub clone）边界彻底分清：本地版保留硬编码主库以获得开箱即用便利；通用版经脱敏脚本处理后发布，可过 Phase 1 安全审查（个人路径泄露拦截）

### 新增 — 通用版首次配置向导 + 路径无关搭建模板
- `SKILL.md` 新增「通用版首次配置向导」：使用者首次使用 Obsidian 同步时，一次对话内先问 Obsidian 安装位置 + 主仓库(vault)路径，再给 `references/obsidian-vault-template.md`
- vault 路径决策权完全交给使用者；AI 只问、只提供模板，不替使用者定路径

### 增强 — 记忆级知识图谱（v3.7.2 补强，随本版正式发布）
- `export_graph_as_canvas` 重写为三类节点（实体 text / 主题 text / 记忆 file）+ 双组件力导向；主库实测 258 节点 / 194 边
- 承接 v3.7.2 的 callout 格式、block reference、safe_write_file 安全护栏

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
  - **记忆级图谱（补强）**：全部记忆也画进画布——每条记忆一个 `file` 节点（链对应 `.md`，按记忆 type 上色），按 `entity` 去重生成绿色主题节点，记忆→主题归属边使同主题记忆聚成「星系」环绕主题节点；双组件力导向（实体组件与记忆组件各自收敛后并排）。主库实测：258 节点（29 实体 + 52 主题 + 169 记忆 + 8 图例）/ 194 边（25 实体关系 + 169 记忆归属）

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
