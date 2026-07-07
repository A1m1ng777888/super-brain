# Changelog

## v3.5.0 (2026-07-07)

### Token ROI 仪表盘全面升级

- `sb_token_roi.py` 新增 `calc_token_roi_trend()`：按日回溯计算 30 天 ROI 快照
- 每条 ROI breakdown 新增 `recommendation` 可行动建议字段
- `generate_dashboard_html()` 全面升级：新增趋势折线图 + 负 ROI 诊断表格
- CLI 新增 `--dashboard` 和 `--trend-days` 标志

### 测试修复

- `test_superbrain.py` workspace 隔离修复：setup 自动切换到 test workspace，cleanup 恢复原始 workspace，不再清空 production 数据
- 49/49 测试全通过

### 文档

- Obsidian Dataview 看板同步更新（趋势表 + 诊断区 + 洞察分析）
- SKILL.md 命令参考新增 `--dashboard` / `--trend-days`

## v3.4.3 (2026-07-06)

### Bug 修复

- P0 数据安全修复：`read_json()` 解析失败时打印警告而非静默返回 None
- `read_memories()` 检测到文件损坏时自动备份再返回空列表，防止 `memory add` 覆盖丢失全部记忆
- 修复 `sb_core.py` 版本号 3.4.1→3.4.3

## v3.4.2 (2026-07-05)

### 跨平台兼容

- 扣子 Linux 云端测试修复（5 项），210/211 测试通过

## v3.4.1 (2026-07-04)

### 功能改进

- T2 阶段感知自动触发协议（四类阶段转换信号检测）

## v3.4.0 (2026-07-03)

### 新功能

- 物理层自检升级（9 项指标，修复前自动备份）
- Token ROI 量化模块
- Goal Continuation 续跑机制

## v3.3.0 (2026-07-01)

### 新功能

- Goal Continuation 续跑机制（结构化评估 + SHA256 停滞检测 + 零 LLM 开销）

## v3.2.x (2026-07-02)

### 新功能

- v3.2.0：子 Agent 编排器
- v3.2.1：前置编配评估协议
- v3.2.2：评估提升至 SOUL.md

## v3.1.0 (2026-07-02)

### 新功能

- 反污染规则、Obsidian 双向同步、冷启动门控、退场生命周期、会话生命周期协议

## v3.0.x (2026-06-29 ~ 2026-07-02)

### 新功能

- v3.0.0：八大升级（三进制哈希、分类管线、感知增强、推理引擎等）
- v3.0.1：被动触发修复

## v2.x (2026-06-27 ~ 2026-06-28)

### 新功能

- v2.0.0：SkillOpt 自我进化引擎
- v2.1.0：记忆双时间机制、动态阈值检索

## v1.0.0 (2026-06-26)

### 初始版本

- 六模块：持久记忆、SimHash+TF-IDF 搜索、知识图谱、自检、Workspace 隔离
