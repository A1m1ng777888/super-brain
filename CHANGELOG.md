# Changelog

## [3.4.0] — 2026-07-03

### 新增 — 物理层自检 + Token ROI 量化

基于与左脑 Skill 的对比测试反思，补上自检系统的物理存储层视角，并新增 Token 节省量化能力。

- **自检 6→9 项**：新增 `check_file_integrity`（文件完整性）、`check_index_integrity`（索引可重建性）、`check_backup_freshness`（备份时效）三项物理层检查
- **修复前自动备份**：`_create_backup()` 在 `--fix` 执行前自动备份全量数据（保留最近 5 次）
- **Token ROI 量化**：新增 `sb_token_roi.py` 模块，用现有统计数据（access_count × 内容大小 × 压缩率）自动计算净收益和 ROI 比率
- **CLI 新增**：`token-roi` / `token-roi --json` / `token-roi --days N` / `token-roi --quickline`（对话注入用）
- **对话集成**：SKILL.md 对话收尾协议自动附带 Token ROI 简报
- **测试**：91/91 全通过（76 原测试 + 9 自检 + 6 Token ROI）

### 背景 — 2026-07-03 对比测试

- 完成 24 项统一对比测试，超脑 20/24 vs 左脑 21/24
- 核心能力（记忆/推理/摘要/因果/模糊查询/去重）双方均通过
- 生成《超脑 vs 左脑 技术对比白皮书》作为法律防御材料
- 本次升级的两项改进直接来自对比反思

## [3.3.0] — 2026-07-03

### 新增 — Goal Continuation 续跑机制

让编排器在任务未完成时自动继续——不靠 LLM 自由文本判断，靠结构化数据 + SHA256 签名比较。

- **结构化目标评估**：`evaluate_goal_completion()` 基于 sub_results 的 status 字段判断，不消耗额外 LLM 调用
- **四道闸门**：`should_continue_goal()` 目标达成→停止 / 最大续跑(4次)→停止 / abort 标记→停止 / SHA256 停滞检测→停止
- **停滞检测**：`_hash_results()` 对子任务结果做 SHA256 签名，与前一轮比较，完全相同 = 停滞
- **零 LLM 开销**：整个续跑判断链只用已有结构化字段 + 微秒级哈希比较，不需要额外模型调用
- **CLI 新增**：`orchestrate evaluate / continue / goal-status / continuation-reset`
- **测试**：12 项新测试，累计 88 项全部通过

### 修复 — 安全与隐私

- `sb_obsidian.py`：移除硬编码的本地 Obsidian vault 路径，改为 `OBSIDIAN_VAULT_PATH` 环境变量
- `superbrain.py`：CLI 帮助文本同步更新
- `LICENSE`：署名从模糊的"Super Brain Contributors"改为 `A1m1ng777888`
- 全部 19 个 Python 文件：添加 `Copyright (c) 2026 A1m1ng777888` + `Author` 署名
- `SKILL.md`：frontmatter 新增 `author` 和 `license` 字段

## [3.2.2] — 2026-07-02

### 升级 — 前置评估 Ambient

- **SOUL.md**：新增「前置编配评估」四问判断逻辑（上下文量/并行度/能力差异/隐含范围），始终在线，不依赖 skill 加载
- **SKILL.md**：规则 #5 标注已提升至 SOUL.md，前置编配评估协议部分追加引用说明
- **架构**：前置评估从 skill-gated → identity-gated，Agent 收到任何任务时自主判断，需要编排时才加载 skill

## [3.2.1] — 2026-07-02

### 升级 — 前置编配评估协议

- **隐含范围识别**：`_assess_independence()` 加入多画像自动加分、范围关键词、Token 量级加分
- **域感知 Token 预估**：`_estimate_task_tokens()` 域感知 floor（"完整网站"→最低 15000 tokens）
- **隐含子任务发现**：`_discover_implicit_subtasks()` 自动将单句大任务展开为多个并行子任务
- **画像检测补全**：前端/后端/数据库/部署 → code 画像，网站/网页 → design 画像
- **SKILL.md 强制规则 #5**：收到非简单任务时先跑 `orchestrate assess`

## [3.2.0] — 2026-07-02

### 新增 — 子 Agent 编排器

- **sb_orchestrator.py**（~650 行）：子 Agent 编排引擎
- **4 维度复杂度评估**：context_isolation / task_independence / tool_divergence / token_risk
- **反编配门控**：TRIVIAL_PATTERNS 硬拒、SEQUENTIAL_PATTERNS 硬挡（≥2 匹配）、CIRCUIT_BREAKER 熔断（3 次级联）
- **任务分解引擎**：四要素（objective + output_format + tools + boundary）+ 独立性校验
- **6 套工具画像**：research / code / design / data / docs / general
- **预算熔断**：50000 token 上限 + 3 次失败触发会话级熔断
- **生命周期追踪**：spawn/complete/fail 记录 + 画像使用频率统计
- **CLI**：orchestrate 命令组（assess/decompose/spec/spawn/complete/stats/reset/profiles）
- **测试**：76 项全通过（61 + 3 CLI + 12 orchestrator）

## [3.1.0] — 2026-07-02

### 新增 — 五大模块升级

#### 反污染规则 (`sb_memory.py` — P0)

- confidence < 0.7 的决策不入库
- 未解决错误不入库
- SimHash ≥ 0.92 时递增计数器不新建记录
- 死胡同探索模式不入库

#### Obsidian 双向同步 (`sb_obsidian.py` — P1，全新 ~330 行)

- JSON → .md + [[wikilinks]] 导出至 Obsidian vault
- YAML frontmatter（tags/type/entity/confidence/status）
- 反向同步（.md 编辑回写 JSON）
- 自动链接已有 vault 笔记

#### 冷启动门控 (`sb_reasoning.py` / `sb_entanglement.py` — P1)

- memory < 15 AND session < 3 → 仅感知+存储，关闭推理引擎和纠缠场
- 达标后自动切换为 active 模式

#### 退场生命周期 (`sb_pipeline.py` — P2)

- 两阶段清理：标记弃用 → 硬删除，自动备份
- 新增硬删除线和弃用缓冲期

#### 会话生命周期协议 (`sb_core.py` — P2)

- T1 启动：搜索 + 简报 + session 计数
- T2 收尾：反污染 + 入库 + 图谱更新
- T3 定期：7 维健康扫描

### 测试

- 61 项全通过

---

## [3.0.1] — 2026-07-02

### 修复 — 被动触发

- **SKILL.md**：新增 12 个自然语言触发词（之前、上次、那个、我们聊过、你之前说、别忘了、还有没有、相关的内容、帮我回忆、继续上次、记住这个、search knowledge）
- **SKILL.md**：新增 8 种场景→命令映射表（用户说了什么 → 自动执行 → 对应命令）
- **USER.md**：注入超脑使用约定（每会话硬注入兜底，确保 agent 主动使用超脑）
- **SOUL.md**：Continuity 节增加超脑主动使用指令

### 设计原则

- 不需要用户说"记住"或"回忆"——agent 应主动判断是否需要查记忆、存记忆
- 对话中出现值得长期记住的知识 → `SB longterm ingest` 对话即入库

---

## [3.0.0] — 2026-06-29

### 新增 — 八大能力

#### 1. 三进制哈希字词网络 (`sb_search.py` 升级)

- 三进制哈希（-1/0/+1），状态空间 3^64（~1.9 万倍区分力提升）
- 字词网络：共现频率图，记录词与词之间的关联强度
- 六通道融合搜索：TF-IDF(0.35) + 关键词(0.20) + SimHash(0.15) + 三进制(0.12) + 模糊(0.10) + 字词网络(0.08)

#### 2. 分类管线 (`sb_pipeline.py` — v3 新增)

- 定义类（365 天半衰期）/ 闲聊类（7 天）/ 混合类（90 天）差异化衰减
- 衰减公式：`retention = 0.5^(age/half_life) × access_boost × confidence_boost`
- 自动归档过期记忆

#### 3. 感知增强 (`sb_perception.py` — v3 新增)

- 信息价值评估（分类、密度、特异性、可行动性、长度惩罚）
- 新颖性检测（与现有记忆相似度对比）
- 决策输出：learn / query / both / skip

#### 4. 推理引擎 (`sb_reasoning.py` — v3 新增)

- 关键点提取（从长文本提炼核心信息）
- 因果分析（因果/条件/对比三种逻辑链）
- 结论推导（从观察数据推导结论）
- 决策支持（多选项加权评估）

#### 5. 纠缠场 (`sb_entanglement.py` — v3 新增)

- 三通道融合：哈希相似度 + 共现频率 + 图谱拓扑
- 挖掘未明说的隐含关联
- 强化词词联系网络

#### 6. 上下文记忆 (`sb_context.py` — v3 新增)

- 凝聚聚类：同主题记忆自动归拢
- 跨会话线程追踪：trace 命令追溯历史对话线程
- 按日期召回：recall 按时间范围召回上下文

#### 7. 本地长期记忆 (`sb_longterm.py` — v3 新增)

- 对话即入库：ingest 自动从对话文本提取、分类、存储
- 零成本检索：预计算三进制哈希索引，O(1) 查找
- 跨会话关联：倒排索引 + 哈希桶双索引

#### 8. 记忆引擎升级 (`sb_memory.py` 升级)

- `auto_store`：自动感知+提取+存储
- `fuzzy_correct_query`：错别字纠偏（Levenshtein 编辑距离）
- `learn_expression`：学习用户表达习惯，建立表达档案

### 新增 — CLI 子命令

- `reason` (4 个)：extract / logic / conclude / decide
- `entangle` (3 个)：mine / list / stats
- `context-mem` (3 个)：cluster / trace / recall
- `longterm` (3 个)：ingest / search / stats
- `perceive` (3 个)：check / value / decide
- `pipeline` (3 个)：classify / decay / archive
- `memory auto-store` (1 个)
- 共 20 个新命令

### 变更 — 现有模块

- `sb_core.py`：版本号升级至 3.0.0
- `sb_search.py`：六通道融合搜索 + 三进制哈希 + 字词网络
- `sb_memory.py`：新增 auto_store / fuzzy_correct_query / learn_expression
- `superbrain.py`：注册全部新模块和子命令
- `SKILL.md`：v3 版本文档，新增被动触发场景表

### 测试

- v3 新功能测试：61 项全部通过
- 累计测试：181 项（49 + 71 + 61）
- v1/v2 测试无回归

---

## [2.1.0] — 2026-06-28

> 未单独发布到 GitHub，合入 v3.0.1 一起发布。

### 新增 — 记忆双时间机制

- `valid_from` / `valid_until` / `replaces` / `replaced_by` 四个时间生命周期字段
- 冲突检测：同一实体的新记忆自动替代旧记忆，建立替代链
- 搜索时间感知降权：已过期记忆自动降权

### 新增 — 动态阈值检索

- 自适应质量线：根据记忆库规模动态调整检索阈值
- 避免小库过度召回、大库漏召回

### 变更 — 自检系统

- 新增第六项指标：时间有效性（检查过期/冲突记忆）
- `sb_selfcheck.py`：从五项升级为六项诊断

### 变更 — 搜索引擎

- `sb_search.py`：搜索结果中已过期记忆自动降权

---

## [2.0.0] — 2026-06-27

### 新增 — SkillOpt 自我进化引擎

- **`sb_skillopt.py`**：完整 SkillOpt 优化循环（rollout → reflect → edit → gate → update）
  - 文本学习率控制编辑幅度
  - 验证门控（只在留出验证集分数严格提升时接受更新）
  - 拒绝编辑缓冲（记住有害方向，避免重复错误）
  - 支持优化外部技能和超脑自我进化两种模式
- **`sb_trace.py`**：执行轨迹记录器
  - 三信号源加权反馈：显式 (×1.0) + 隐式 (×0.3) + 验证集 (×0.5)
  - 隐式信号自动采集：任务完成/报错/超时/空结果
  - 轨迹过滤、统计、导出功能
- **新增 CLI 子命令**：`skillopt` (6 个) + `trace` (6 个)，共 12 个新命令
- **新增测试**：`test_v2.py` — 71 项全面覆盖

### 变更 — 现有模块

- `sb_core.py`：新增 SkillOpt 配置项（learning_rate、batch_size、validation_threshold）
- `superbrain.py`：新增 skillopt 和 trace 模块导入及子命令注册
- `SKILL.md`：v2 版本文档，新增自我进化触发规则和工作流
- `config.json`：版本号升级至 2.0.0，新增 skillopt 配置节
- `test_superbrain.py`：修复多工作区清理遗漏 bug

### 测试

- v1 核心测试：49 项全部通过（无回归）
- v2 新功能测试：71 项全部通过
- 累计测试：120 项

### 致谢

- Microsoft SkillOpt (https://github.com/microsoft/SkillOpt) — 自我进化框架理论基础

---

## [1.0.0] — 2026-06-26

### 初始发布

- 持久记忆引擎（7 种记忆类型，置信度，自动合并）
- 知识图谱（节点/边/实体对齐/多跳查询）
- SimHash + TF-IDF 混合语义检索
- 五项自检系统（一致性/时效性/完整性/孤立节点/重复数据）
- Workspace 隔离机制
- Token 优化（上下文压缩、按需加载）
- 零外部依赖，纯 Python 标准库
- 49 项单元测试全部通过
