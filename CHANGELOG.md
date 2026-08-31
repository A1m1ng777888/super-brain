# Changelog — Super Brain 超脑

## v3.12.2 (2026-08-31) — 工作台全线（写通道+看板+C 端化）+ 阶段2 整合/时态 + 图谱消融

### 新增 — 本地工作台 C 端化改造（产品视角，下午增量）

- **三区信息架构**：状态横幅（hero，深色作品卡）→ 自动打理（组件=服务话术）→ 需要你决定（整理建议两步应用）→ 正在推进（项目+任务看板）；机制语言→结果语言全量替换（守护引擎→自动体检、整合提案→整理建议）
- **人话映射层**：`ISSUE_COPY`（11 类体检 issue → 标题+说明）、`_KIND_LABEL`（4 类建议分型）、`SERVICE_DISPLAY`（服务话术）；`api_state` 输出 `health_friendly`/`services`/`copy.ai_prompt`
- **两步应用通道（D1-B）**：整理建议从「复制命令行」升级为面板内「看看建议 → 确认应用」（`POST /api/consolidate/apply` 白名单固定脚本）；**两段式铁律不变**——永不自动 apply，显式确认=人工通道
- **真实路径注入**：「交给 AI 深入检查」提示词由后端注入 health_state.json + latest_report.json 真实路径，复制即贴即用（消灭 `<用户>` 占位符）
- **空状态引导**：never_ran → 「做第一次体检」单一 CTA（空状态三要素）
- **体检历史趋势（P3）**：`sb_healthlite._append_history`（每次运行追加摘要，cap 90 条，原子写，失败静默）+ 面板 trendSvg 微趋势（30 根竖条：颜色=结果、高度=提醒数、悬停详情）

### 新增 — 正在推进看板（对话即上板）

- 面板第四区：项目（状态徽章点击循环/图钉置顶/↑↓ 排序/✎ 编辑现状/▾ 展开项目内任务清单+内联回车添加）+ 任务清单（checkbox/可选截止日期/逾期与 7 天内到期「今天要处理」置顶高亮）+ 随手任务组
- **对话即上板**：Agent 收尾直接写 `~/.workbuddy/super-brain/workbench_board.json`（首次播种真实项目，原子写，损坏 .corrupt.bak 重播种）；面板每 5s 轻量轮询 `GET /api/board/poll`（只读 board 零子进程），`updated_at` 变化局部刷新——Agent 写文件 → 面板 ≤5s 反映，输入聚焦/编辑态自动跳过
- API：`POST /api/board` 单端点八 action（add/toggle/del_task、add/update/move_project/toggle_pin/del_project），输入校验（空标题拦截/非法日期置空/长度上限）

### UI — 白盒子画廊语言（对标 a1m1ng.cn v8 设计 token）

- 深色作品卡 hero（#1a1917 底暖白字琥珀 kicker）、mono 编号区块标题（01/02/03+朱砂红编号+细线）、衬线 900 标题（Noto Serif SC 栈）、卡片 16px 圆角+hover 抬升、徽章 mono 化
- 朱砂红 #b84525（源自 v8）作为决策/逾期强调色引入；超脑琥珀压深 #D98A1F 提对比；两色分工：琥珀=行动/进行中，朱砂=需要决策/逾期
- 零外部依赖不变：系统字体栈 fallback、内联 SVG 图标、断网可用

### 新增 — M3-A 健康看板迁入

- `sb_dashboard.py`（M1 看板生成器内嵌版，严格只读）+ 面板「打开健康看板」→ `GET /dashboard` 托管（首次访问现场生成 ≈1s，注入重新生成/返回工具条）+ `POST /api/dashboard/refresh`

### 修复

- **M2 过程缺陷**：sb_consolidate apply 后 proposal 文件不刷新 → 面板挂陈旧提案（apply 尾部自动重生成，26 用例回归全绿）
- v3.12.1 洞：schtasks 计划任务命令行缺 `--workspace`（触发时跑在 default 空库）——现从 registry 读 workspace 写死进任务

### 新增 — L1 后台整合引擎（sb_consolidate.py）

- **零 LLM、零 token** 的后台记忆整合（对标 Mem0 Dream / Zep 抽取管线 / LangMem Background / Letta sleep-time / A-Mem evolution 五家共性能力，阶段2「补差距」最高优先项）
- **proposal→apply 两段式铁律**：后台（healthlite `--consolidate`）只生成提案清单 `consolidation_proposals.json`，**永不自动 apply**；应用走 `sb_consolidate --apply` 人工确认通道
- 四档动作：A=general 实体词表唯一命中归一（黑名单实体/对话碎片/多实体歧义排除，绝不新建实体）；B=同实体近重复合并（simhash≥0.80，碎片不整合，内容拼接不丢信息）；C=冗长陈旧抽取式压缩（>200字 & >30天 & ≥4句 & 压缩比≤50%）；D=知识更新链（同句 mem_id 引用+更正标记 → superseded+replaced_by+valid_until 三件套，对齐原生 replaces 语义）
- 安全设计：前缀断言防索引错位、apply 前自动备份（**%H%M 防同日覆盖**）、审计日志 reversible=True、simhash/ternary 哈希随修改重算
- 保守正确行为：200-350 字短冗长记录抽 3 句压不到一半 → 主动放弃（「压不动不如不压」）

### 新增 — 时态建模启用（阶段2-B）

- `add_memory` 缺省锚定 `valid_from = 创建日期`（v2.1.0 的时态机器首次全线激活：同 entity+type 时间重叠检查真正生效；valid_from 单独存在零行为回归）
- 存量回填 `superbrain-bench/backfill_valid_from.py`（dry-run/apply/备份；生产 673 条已回填）
- D 档触发规则经生产校准：**同句 ID+更正语义**是唯一可信证据；「纯显式引用」（会话汇总/关联误报）与「同实体相似带+全文更正词」（精确率 ~7%，「修正权协议」误触发）两条路径实测证伪并删除
- D 档语义校准：初版「软失效」（active+valid_until 走 ×0.85 过期降权）被 selfcheck temporal_validity 打回——valid_until 本义是用户声明有效期，「被更正」应走 superseded 硬失效通道（与 --replaces 原生语义对齐）

### 新增 — automation_registry.json（工作台组件契约）

- `~/.workbuddy/super-brain/automation_registry.json`：daily_health_lite + background_consolidation 两组件，**默认全关**，schema 依《超脑自动化守护设计方案_20260831》

### 新增 — 本地工作台 M2 写通道（sb_workbench.py + Start-Workbench.bat）

- 方案 C 落地（调研否决 Electron 壳/云端发布）：纯标准库单文件 HTTP 服务，**只绑 127.0.0.1**，面板=组件开关（写 registry 意图+真装卸 schtasks）/立即检查/引擎状态灯/issues 展开/「让 AI 深入检查」剪贴板提示词/整合提案摘要（只读，永不自动 apply）
- `schedule_manager.py` 升级 registry 组件驱动（`--task <id>`，向后兼容）；**修复 v3.12.1 洞：计划任务命令行现带 `--workspace`**（此前 schtasks 触发会跑在 default 空库）
- registry 契约扩展：组件增 `enabled`（用户意图）与 `implementation.workspace` 字段
- 全链路实测：toggle ON→schtasks 真装（TR 含 --workspace，下次运行 2026/9/1 08:30）→立即检查 exit 0→toggle OFF→终态默认关

### 新增 — 图谱增益消融（阶段3 验证第一项）

- `superbrain-bench/graph_gain_ablation.py`（同进程 A/B 零写盘）：E1 检索消融——30/30 题 top-5 一致，**图谱检索增益=0（by design，BM25 单路时代图谱不在检索热路径）**；E2 门控消融——50 席晋升集 10 席由 entanglement 项驱动（重合率 0.8），带图集 ent 均值 4.92 vs 全库 3.88，核心主题簇（超脑/TencentDB/tabbit）被系统性推入工作空间
- 一阶段「到上游差三项」至此全部关闭（后台整合/时态建模/图谱增益消融）

### 变更 — 328 条无审计 gating override 清除（v3.12.0 遗留待办闭环）

- 全库 362 条 override 全为 demote 且 audit manual=0（不可溯源）；清除后候选池 225→563、晋升 8.9%（带内）、selfcheck 无新 issue
- 备份：`memories.json.bak_20260831_clear_override`；清单：`superbrain-bench/results/clear_overrides_20260831.json`

### 生产实测（workspace=本地知识库）

- A×1（求职）+ B×0 + C×20（6412 字压缩）+ D×2（v3.7.2 发布误记、unknowns 原稿误记 supersede 链）应用；图谱 140 节点/276 边、general 48、整合候选 71→55
- 30 题交付分：recall@5 **0.933 三连持平零回归** / mrr 0.808→0.792（仅「Skill 分档」单题 rank 1→2，仍命中）
- test_consolidate.py **26 用例全绿**（A/B/C/D 四档 + 只读保证/断言失败隔离/幂等性/截断 ID 解析/同句更正语义）

## v3.12.1 (2026-08-31) — 每日自检守护引擎（可选，默认关闭）+ 交叉审计修复收尾

### 新增 — L0 守护引擎（sb_healthlite.py）

- 每日自动 `graph build`（新记忆进工作空间的前提）+ selfcheck + 门控带内只读检查 → `health_state.json`，供 Agent 异常时感知
- **退出码分级**：正常/warn → 0、仅 error → 1（token 契约：守护引擎每月 0-2 次触发不烧 token，warn 不击穿）
- 状态文件**原子写**（`tmp.{pid}` + `os.replace`，崩溃只留 tmp 残留绝不损坏状态文件）
- 锁文件 30min TTL + 释放前 **pid 校验**（防误删他人新锁）
- report 治理：只读目录按 mtime 保留最近 N 份（135→31 清理示例）

### 新增 — 计划任务管理（schedule_manager.py）

- Windows：schtasks 用户级任务 install/uninstall/status（无需管理员）；POSIX 打印 cron 行
- `--time HH:MM` 格式校验（00:00~23:59）；uninstall 区分「任务不存在」（非 0 不误报）
- 中文 Windows schtasks 输出 GBK 码页容错（encoding=mbcs）

### 开关策略

- **默认全关**：install 必须显式执行；开关主通道=可视化工作台自动化组件面板（规划中），CLI 为开发者兜底
- Agent 侧：仅 `status=error` 触发 L1 介入；warn 仅面板提示（去重避免每日重复触发）

### 收尾（审计 C 交叉验证后）

- SKILL.md 新增 §10.1「可选：每日自检守护（默认关闭）」
- v3.12.0 CHANGELOG 段回流本地（发布时只入 clone-temp）
- 全链路实测：首跑 5.4s / graph build 幂等（backfilled 8 条）/ warn 正确分级 rc=0

---

## v3.12.0 (2026-08-31) — 检索层重建 + 图谱复活 + 相对门控（P0-A→M 十四轮）

### 新增 — 自动建图

- `sb_graph.build_from_memories` + CLI `graph build`（--dry-run / 幂等 / 跨进程写锁）：entity 节点、实体伪文档库级 IDF 余弦相似度、top-K+地板 scale-free 建边、`related_nodes` 回填（合并不覆盖推理链记忆 ID）、只为有边实体建节点
- 实测：图谱 14→139 节点 / 247 边复活，entanglement 信号恢复，`graph mermaid` 从演示化石变为真实知识地图

### 新增 — 相对门控（scale-free）

- `get_threshold` 双模式：meta 显式阈值=手动模式（persona=0.35 身份常驻）；默认自动=阈值取 salience 排名第 k 高（k=min(cap, round(候选池×0.15))），分布漂移免重标
- CLI `gating threshold --auto` 清除手动值回自动模式
- 排名制对 confidence 偏移量免疫——salience 公式的偏移量问题在门控层自动失效

### 新增 — 幂等写入开关（v3.11.2 并入）

- `memory add --dedupe`：命中同 entity + active + simhash≥0.95 的重复时不写入、复用已有记忆（默认关闭，既有行为不变；0.95 阈值有 0.23 安全余量标定）

### 修复 — 检索层重建（v3.11.2 并入）

- 六通道 RRF 砍成 BM25 单路：消融证明三路噪声拖垮融合（30 行零依赖 BM25 全指标胜出、快 140 倍）
- 新增 `_bm25_tokenize`（CJK bigram+trigram、unigram 降权 ×0.35）：修复停用词主导排序（「我们」idf=4.15 反直觉高 IDF）
- persona 与 project 合并单次检索修量纲污染：30 题真实中文问句 recall@1 0.200→0.700、persona 槽位占用 63%→5%
- 访问统计时点断裂修复（`access_tracking_cutoff_ts`）：forget_priority 均值 −35.6%

### 修复 — 门控治理与健壮（P0-H~M）

- `add_memory` 写入路径事件驱动容量执行：晋升洪水 137→50 根治（治理不再只挂查询路径）
- 门控四写函数（get_active_workspace/chain_ignite/promote/demote）+ set_threshold 全量跨进程上锁：并发丢写面封堵
- `get_active_workspace` 陈旧标志双向重评（只升不降导致 persona 库结构性死锁）
- persona 工作空间阈值独立标定 0.35（0.70 对无图谱库是数学上不可达门槛）
- calibrate / graph build post_build_promotion 统一候选池口径（328 条 override 不再污染诊断数字）
- 两轮对抗性审阅修复 6 处真 bug（P0-K/M）

### 测试

- 新增 test_graph_build.py（18 项）、test_relative_gating.py（15 项）
- 12 套件回归全绿；交付层评测 30 题真实中文问句 recall@5 0.933 / mrr 0.807

---

## v3.11.1 (2026-08-20) — 门控容量持久执行 + 自检索引格式兼容（DSH 审阅高位项）

来源：DSH（鲸砚）会话审阅 selfcheck CRITICAL 高位项 + 配套加固，随后补齐版本管理快照。

### 修复 1: gating_flood_protection（晋升洪水，95 > cap 50）

- 根因：get_active_workspace 的 cap 截断只截返回值、不回写降级，workspace_promoted 标志随调用只增不减；chain_ignite 独立调用路径完全不经过容量约束
- 修复：新增 sb_gating._cap_enforce 容量持久执行器——手动 promote 钉选优先；链为单位保留（整链能放入剩余容量则整链进，放不下按个体 salience 填满）；超容部分清标志 + 可逆审计（cap_demote）、不带 gating_override，下次按 salience 重评可自然回迁；get_active_workspace 与 chain_ignite 统一过闸（chain_ignite 返回新增 cap_demoted 字段）
- 数据修复：示例工作区A 95→50、示例工作区B 74→50；全 8 工作区复扫 over_cap=0

### 修复 2: file_integrity 索引格式假阳性

- 根因：check_file_integrity 只认旧键 ternary_buckets/word_network，v3.9.3+ build_index 实际输出 keyword_index/word_network_stats → 健康评分误报 INVALID
- 修复：检查器兼容两代键名（现行格式优先判定，旧键仅作兼容）；并重建滞后索引（378→428 条，44513 tokens）

### 并入 1: find_duplicates TF-IDF 预计算（v3.11.0 发布后 08-17 本地改动，未随包发布）

- 预建 IDF doc_freq 表 + 每篇 doc 的 tf Counter，消除热路径「每候选 × 每 term 全库扫 doc_freq」的 O(n²·terms·doc_len) 退化（n=382 实测 ~235s → 秒级）
- 语义与原 tf_idf_cosine_similarity 逐项等价（doc_freq 按每文档对 term 至多计 1，idf=log((N+1)/(df+1))+1 相同），结果 bit 级一致

### 并入 2: memory list CLI 输出补 Source 字段（同批 08-17 未发布改动）

### 并入 3: test_prepublish_strip 夹具脱敏（GitHub Phase 1 发布审查零命中）

- 测试夹具中的作者用户名改为通用 devuser——夹具本身也不得带真实用户名，发布审查的个人路径扫描零命中

### 回归验证

- 新增 test_v36 T8 容量回归 5 项：单链 60 节点 chain_ignite 不推过 DEFAULT_CAP / 链填满容量且无 override 残留 / 无链批量反复调用持久标志稳定在 cap 内（36→41 项）
- 全量回归零失败：test_superbrain 49 + test_v2 71 + test_v3 94 + test_v36 41 + test_obsidian 7 + test_prepublish_strip 8 + test_p1 15 + test_v38 35 + test_v310 16 + test_forgetting 23 = 359

## v3.11.0 (2026-08-13) — 遗忘治理引擎 + 检索增强

### 新增 1: `sb_forgetting` 遗忘治理模块（v1.0.0）

- 遗忘优先级 = 规模因子 S × (1 − 活跃度因子 A) × 记忆衰减因子 D，纯标准库、零新存储
- 项目三档（按最后访问中位数分档）：active（≤14 天）/ warm（15–45 天）/ dormant（>45 天）
- 软切降权：dormant 0.5 / warm 0.8 / active 1.0，身份/护栏记忆（砚/user/潜进/超脑等）永远豁免
- CLI：`forgetting status`（项目档位 + 豁免统计）、`scan`（dry-run 候选预览）、`apply`（dormant 批量 demote，幂等）
- 两天观察期验证：dormant 首次触发（RAG/Transformer 46 天滑过 45 天线）、降权不误伤强相关检索

### 新增 2: 检索 entity 精确命中 boost

- 查询词与记忆 entity 精确命中（大小写不敏感）时，排序阶段加 `ENTITY_HIT_BOOST=0.04`
- 修复实验 1「RAG与记忆」反例：entity 强相关但 content 词面不重叠的记忆，RRF 排名过低被 limit 截断（rank 51 → top3）
- 设计约束：boost 只在「过滤后排序」阶段生效，不参与 dynamic_threshold 计算，避免抬高阈值误滤其他记忆

### 修复 1: v3.10.0 发布遗漏

- `sb_forgetting.py` / `test_forgetting.py` 未随 v3.10.0 打包，致 `superbrain.py` import 时 `ModuleNotFoundError`，本次一并补上

### 回归验证

- 新增 `test_forgetting.py`（23 项）+ `test_v3.py` 两回归（entity boost、阈值污染防护）
- 全量回归零失败：test_superbrain 49 + test_v2 71 + test_v3 94 + test_v36 36 + test_obsidian 7 + test_prepublish_strip 8 + test_p1 15 + test_v38 35 + test_v310 16 + test_forgetting 23

## v3.10.0 (2026-08-12) — 评分体系重构（待办 D + Penguin 评测范式落地）

来源：PenguinHarness（企鹅驾驭师）深度研究（2026-08-12，源码级拆解）。借鉴其评测协议三行映射：① 硬/软指标分域 ② 有效性协议（评测失效不得分）③ 候选→验证→接受/回滚。对应工作记忆待办 D（v3.10.0 评分体系重构——软指标从扣分项改为报告项）。

### 升级 1: 硬/软指标分域（`sb_selfcheck.py` → `_hard_score_from_checks`）

- `get_health_score()` 重构：软指标（completeness / gating_flood / duplicates / consistency / timeliness / temporal_validity / orphans）**从扣分项改为报告项**，不再减总分
- 总分只基于「**物理完整性 + 时效性 + 真损坏**」：file_integrity / index_integrity（×15 高惩罚）、backup_freshness（>30 天 -5 / >90 天 -15）、gating_salience_bounds / gating_demote_integrity（门控数据一致性破坏）
- 抽出 `_hard_score_from_checks()` 单一真相源，供 `get_health_score` 与修复后验证共用，杜绝两处逻辑漂移

### 升级 2: 有效性协议（`run_full_check` 顶层状态位）

- report 顶层新增 `score_status`（`valid` / `invalid` / `degraded`）+ `invalid_reason`
- **物理完整性/索引损坏 → `score_status=invalid`**——评测失效不是低分，`get_health_score` 返回 0，对应 Penguin 的 `failure_code`（benchmark_invalid / evaluation_failed）语义
- 软指标或门控异常 → `degraded`（分数可算，但标记降级）
- 消灭「拿脏数据算分」的静默错误：分数与评测有效性正交

### 升级 3: 修复后验证（`--fix` 接受标准）

- `run_full_check(auto_fix=True)` 修复完成后自动重检：`fix_validation` 记录 `pre_score / post_score / accepted / backup_path`
- 硬分未提升 → 打印回滚提示（备份由 `backup_info` 指向）
- 对应 Penguin agent-optimization「候选→验证→接受/回滚」纪律：修完必须证明更好

### 升级 4: CLI 暴露

- `selfcheck` / `health` 命令显示 `Score Status`（+ `Invalid Reason` / `Fix Validation`）

### 回归验证
- test_v310.py: 16/16 ✅（新增）
- test_v38.py: 35/35 ✅
- test_p1.py: 15/15 ✅
- test_v36.py: 36/36 ✅
- test_superbrain.py: 49/49 ✅
- test_v2.py: 71/71 ✅
- test_v3.py: 92/92 ✅
- test_obsidian.py: 7/7 ✅
- test_prepublish_strip.py: 8/8 ✅
- **329/329 回归零失败**

## v3.9.8 (2026-08-06) — mattpocock 纪律库吸收

来源：[mattpocock/skills](https://github.com/mattpocock/skills) 调研（2026-08-06，用户要求评估"哪些可以抄一抄"）。选择**吸进超脑而非全套安装**：纪律长在既有执行路径里（编排器/访谈协议/审阅），而非旁边多一个孤立 skill。

### 升级 1: decompose 曳光弹切片规格（`sb_orchestrator.py`）
借鉴 to-tickets 的垂直切片硬约束——"Each slice is sized to fit in a single fresh context window"：
- `_build_subtask` 新增 `blocking_edges`（阻塞边声明，默认 `[]` = 可立即启动）
- `_build_subtask` 新增 `context_window_fit`（`_estimate_context_fit()` 估算：中文 ~1.5 chars/token、英文 ~0.25 chars/token，多独立要求判定超载 → 建议再拆）
- `decompose_task` 返回新增 `slices` 汇总（index/objective/blocked_by/context_window_fit）+ `wide_refactor`
- 新增 `detect_wide_refactor()`：改名/重命名、schema 重命名、类型替换、目录重组等**单点机械变更波及全库**的模式 → 返回 expand-contract 三步序列建议（不做曳光弹，因为"任何垂直切片都无法保持绿色"）

### 升级 2: frontier 拷问法升级反向采访（`SKILL.md` 未知发现协议）
借鉴 grilling 的设计树机制：
- 决策画成**设计树**，按 **rounds** 工作，**frontier** = 前置条件已 settled 现在就能问的决策
- 每轮把整片 frontier **一次问完**，每个问题编号 + **附推荐答案**（用户只需确认/推翻，成本极低）
- 关键纪律：**事实是 Agent 的活，决策是用户的活**——可从环境查的事实派子 agent 查，只有决策提交用户
- 终止条件：frontier 清空 = 设计树每个分支都访问过，**没有任何东西被静默假设**，用户确认共享理解前不动手

### 升级 3: domain 项目术语表（新模块 `sb_domain.py` + CLI）
借鉴 CONTEXT.md 共享语言模式——"It is a glossary and nothing else"：
- 术语只存**词汇定义**，严禁 spec/草稿/实现细节混入
- 术语一经确定**当刻即写**，不批量攒
- 歧义当场标记 + 消解记录（避免"backlog 既是工具又是工作量"）
- 可导出 CONTEXT.md（人读/agent 共享），也可按 workspace 隔离存储
- CLI：`domain add/get/list/remove/ambiguity/ambiguities/export/stats`

### 升级 4: 双轴 code-review 固化（新文档 `references/review-guide.md`）
借鉴 code-review 技能，把 2026-07-14~15 GLM-5.2 外部审阅实验固化为可复用资产：
- **双轴分离不合并**：Standards（符合仓库标准 + Fowler 坏味道）× Spec（忠实实现 issue/spec），并行子 agent 互不污染上下文
- **Fowler 12 坏味道基线全文**（Mysterious Name / Duplicated Code / Feature Envy / Data Clumps / Primitive Obsession / Repeated Switches / Shotgun Surgery / Divergent Change / Speculative Generality / Message Chains / Middle Man / Refused Bequest）——审阅 prompt 必须全文注入，子 agent 无其他访问途径
- 两条绑定规则：repo overrides 仓库标准覆盖基线；永远是判断不是硬违规
- 沉淀 GLM 审阅实验 6 种系统性缺陷模式（静默数据丢失/量纲错误/异常静默吞掉/写副作用进只读函数/文档与行为不一致/死代码）

### 回归验证
- test_v38.py: 35/35 ✅（新增）
- test_p1.py: 15/15 ✅
- test_v36.py: 36/36 ✅
- test_superbrain.py: 49/49 ✅
- test_v2.py: 71/71 ✅
- test_v3.py: 92/92 ✅
- test_obsidian.py: 7/7 ✅
- test_prepublish_strip.py: 8/8 ✅
- **总计: 313/313 — 零回归**

## v3.9.7 (2026-07-24) — 自动触发断裂链修复

### 修复 1: `write_json` 无返回值导致假警告（P0 回归）
`sb_core.py:write_json()` 缺少 `return` 语句，返回 `None`。`_hardstep_save()` 将 `None` 返回给 `mark_search_done()`，`not None == True` 条件始终成立，导致**每次 search 都打印假警告**：
```
⚠️ [HARD-STEP] mark_search_done 写入失败，后续写入可能被误拦截
```
实际写入成功，警告是假的。为 v3.9.5 裸 `json.dump` 改 `write_json` 时引入的回归。
- **修复**：`write_json` 末尾加 `return True`
- **影响**：仅 `_hardstep_save()` 一处下游使用返回值，其他 30+ 处 `write_json` 调用者忽略返回值——零风险

### 修复 2: 跨会话硬步骤死锁（P0 设计缺陷）
`enforce_hard_step_guard` 的 30 分钟窗口假设**仅适用于同会话**。跨会话时 `last_search_ts` 来自历史会话（远超 30 分钟），首个写入命令被 `exit 2` 拦截。Agent 未处理子进程 exit 2 → 自动入库静默丢失 → B/C/D 连锁断裂。
- **修复**：过期窗口 / 从未检索场景改为**自动重置计时器并放行**（而非 `exit 2`），保留警告提醒
- **保留**：`--force` 豁免路径不变、未来时间戳拒绝不变、窗口内相关性校验不变
- **测试**：`test_p1.py` T1b 用例从「预期 exit 2」更新为「预期自动重置放行」

### 回归验证
- test_p1.py: 15/15 ✅
- test_v36.py: 36/36 ✅
- test_superbrain.py: 49/49 ✅
- test_v2.py: 71/71 ✅
- test_v3.py: 92/92 ✅
- test_obsidian.py: 7/7 ✅
- **总计: 270/270 — 零回归**

### 问题背景
连续 3 次每周自检出现振荡模式：手动修复后评分回升，下次又掉下来。根因是自检把"知识库的天然使用模式"（任务在进行中、promotion 比例高、多次会话描述同一项目）当成"问题"来扣分。

### 阈值调整（`sb_selfcheck.py` + `sb_search.py`）
- **gating_flood ratio**：0.40 → 0.70。密集使用知识库时 promotion ratio 自然偏高，0.40 是给"链式点燃 bug"设计的阈值，不适合日常使用场景
- **duplicates simhash**：`sb_search.py:find_duplicates` similarity_threshold 0.75 → 0.85。多次会话描述同一项目时相似度在 0.75-0.85 是正常现象，不应标为重复
- **--fix 自动合并**：0.95 → 0.85。与检测阈值对齐，让自动修复覆盖更多真实重复

### 默认值补全（`sb_memory.py`）
- **task 类型默认 `task_status="active"`**：`TYPE_DEFAULTS["task"]` 新增 `task_status: "active"`。新录入的 task 类型记忆天然带有状态标识，不再触发 completeness 误报

### completeness 白名单扩展（`sb_selfcheck.py`）
- `check_completeness` 的排除列表从 `("done", "completed", "cancelled")` 扩展为 `("done", "completed", "cancelled", "active", "in_progress", "pending")`。进行中的任务不再被标记为"incomplete"

### 测试适配
- `test_superbrain.py` 近重复测试数据改用相同内容（原 "JS" vs "JavaScript" 在 0.85 阈值下不触发，属预期行为）

### 效果
- 评分从 40→100（12/12 全绿），177 项回归零失败（49+92+36）
- 自动化 `automation-1782993283473` 升级：从"只诊断不改"→"selfcheck --fix + 自动 demote + 自动归档"

## v3.9.5 (2026-07-17) — P1+P2 系统性修复（五维度审阅完整闭环）

### P1 修复
- **硬步骤门控加固**：`sb_gating.py`（从 `superbrain.py` 策略下沉）—— `_hardstep_save` 改原子写、未来时间戳拒绝、overrides 环形截断 200 条
- **并发写治理**：`sb_core.py write_json` tmp 名加 `os.getpid()`
- **token_roi XSS**：`sb_token_roi.py` `html.escape` 转义所有用户内容
- **关键路径补测**：新增 `test_p1.py`（15 项）——硬步骤 exit 2、损坏 JSON 恢复、persona 双层召回、RRF 融合、二进制 JSON 防护

### P2 修复
- **warmup 常量共享**：`WARMUP_MEMORY_THRESHOLD=15` / `WARMUP_SESSION_THRESHOLD=3` 移至 `sb_core.py`
- **读路径写副作用**：`sb_memory.search update_access_stats` 默认 `False`
- **分层依赖注释**：`sb_core.py` 诊断函数延迟 import 说明
- **发布面收尾**：SKILL.md 通用化、prepublish TARGET_FILES 扩展至 20 项、dashboard CDN 降级

### 测试
278 项回归零失败（49+71+92+36+7+8+15）

## v3.9.4 (2026-07-17) — P0 性能与安全修复（五维度审阅驱动）

### 审阅
砚（K3）主控 + 5 并行只读子代理，对 v3.9.3 做代码质量/架构/安全/性能/测试五维度横向审阅（与 GLM-5.2 纵向逐模块审阅互补），82 项发现（高 20/中 31/低 31），7 项高危人工抽查全属实，整体 5.9/10。详见 `super-brain-完整审阅报告.md`。

### P0 修复（3 项，263 项回归零失败）
- **搜索热路径 O(n²·terms) 退化**：`sb_search.py` 预建 IDF 文档频率表（`_tfidf_cosine_precomputed`）+ `fuzzy_match` 长度差预筛（编辑距离下界剪枝，放在 substring 快速路径之后不误杀）。n=500 实测：21s → 0.6s（35 倍）；n=174：2.8s → 0.19s（15 倍）。
- **零成本索引自动维护**：`sb_longterm.py` 新增 `_ensure_fresh_index()`——缺失/陈旧/计数不符时自动重建；`zero_cost_retrieve` 首次含重建 1.4s，后续 **10ms**（keyword_index 11,936 tokens 候选过滤）。修复前全部 14 个 workspace 零 index.json。
- **测试文件强制数据目录隔离**：`test_v2.py`/`test_v36.py` 在 `from sb_core import` 前强制 `os.environ["SUPERBRAIN_DATA_DIR"] = mkdtemp`（不用 setdefault 避免已有 env 时静默失效）；`sb_orchestrator.py:1727` 内嵌测试硬编码路径 → `get_workspace_dir("default")`。

### 附属修复（P1-4，收尾顺手修）
- **版本号单一来源**：`sb_core.py` 新增 `VERSION = "3.9.4"` 模块常量；`DEFAULT_CONFIG["version"]` 引用 VERSION；`superbrain.py` 三处版本兜底（`'1.0.0'`/`'1.0.0'`/`'3.2.2'`）统一改为 `config.get('version', sb_core.VERSION)`。

## v3.9.3 (2026-07-15) — GLM-5.2 外部审阅终结版

### GLM-5.2 外部审阅里程碑
累计审阅 15 个核心模块（~6,150 行），发现并修复 40+ 真实缺陷，发布 11 个版本（v3.8.3–v3.9.3）。
审阅终止条件达成：连续两模块零 P0、P1 密度 < 1/364 行、零新静默数据丢失。

### 本轮修复（Top 5 + 扩充，pack-13~19）
**sb_core.py** — 基础设施 8 项：read_graph 损坏备份、load_config deepcopy + 备份、双写 try/except、session_start 工作空间一致、health_dir 返回值、ensure_workspace name、switch_workspace 校验
**sb_graph.py** — 图谱 2 项：source_memory 单复数 schema 统一、delete_node 返回 node_id
**sb_pipeline.py** — 管线 2 项：定义正则加词边界、cleanup backup abort
**sb_perception.py** — 感知 1 项：action_patterns 否定极性
**sb_context.py** — 上下文 2 项：best_sim 初始化 + tf_idf 传参 + ternary 外移
**sb_longterm.py** — 长期记忆 4 项：索引接线路径/结构双重对齐、infer_memory_type 补 factual、decision 标签修正

### 搁置
6 个低风险模块（superbrain/selfcheck/skillopt/token_roi/trace/capability）永久搁置——失败模式为直接报错，非静默损坏。
sb_orchestrator.py 审阅零修复——终止条件达成点。

## v3.8.8 (2026-07-14)

### 修复 — 模糊纠正 + 反污染加固（pack-08 GLM-5.2 审阅）
- `fuzzy_correct_query` 补 token 纠正 type 键（P1-1 KeyError 崩溃）
- token 纠正重建改用 `corrected_tokens` 拼接替代 replace（P1-2 全量替换）  
- 返回 `original_query` 而非被覆写值（P1-3）+ expression 循环用 working_query（P1-4）
- `RESOLVED_ERROR_PATTERNS` 补已解决/已修复/已处理（P1-5）+ variant.lower()（P2-6）
262 回归全过，零回归。

## v3.8.7 (2026-07-14)

### 修复 — 记忆引擎加固（pack-07 GLM-5.2 审阅）
- `add_memory` 冲突检测 dead variable 复活：记录 conflict_score/conflict_target 供诊断
- `merge_memories` related_nodes 落盘丢失：不走 update_memory 重读磁盘，直接在 memories 引用上操作后单次落盘 + audit log
- `search` vs `get_context`/`get_stats` 时区统一为本地时间
- `search` 去冗余二次 read_memories，复用第一次引用
- `update_memory` 补 ternary_hash 更新 + simhash_bits 一致性
- `add_memory` except 收窄(ImportError/TypeError/ValueError)
- `query_entanglement` 冷启动 warmup 守卫防 KeyError
262 项回归全过，零回归。

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
