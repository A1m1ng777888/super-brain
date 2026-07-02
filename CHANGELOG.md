# Changelog

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
