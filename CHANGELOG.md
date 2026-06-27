# Changelog

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
