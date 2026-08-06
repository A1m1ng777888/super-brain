# 双轴代码审阅规范（Code Review Guide）— v3.9.8

> 借鉴 mattpocock/skills `code-review` 技能，把 2026-07-14~15 GLM-5.2 外部审阅实验
> 中验证有效的纪律固化为可复用资产。当对代码改动做审阅（自审/外审/发布前审查）时按此执行。

## 核心：双轴分离，不合并结论

一次代码审阅沿两条独立轴并行进行，**结论绝不合并**——合并 = 重新排序 = 让一轴掩盖另一轴：

| 轴 | 问什么 | 失败示例 |
|----|--------|---------|
| **Standards 标准轴** | 代码是否符合仓库编码标准 + Fowler 坏味道基线？ | 遵循所有标准但实现错了东西 → Standards pass, Spec fail |
| **Spec 需求轴** | 代码是否忠实实现来源 issue/spec？ | 完全照 issue 做了但打破项目约定 → Spec pass, Standards fail |

**执行方式**：两条轴作为**并行子 agent** 运行（互不污染上下文），主 agent 聚合。
每条轴的子 agent prompt 必须**全文注入**该轴所需的基线文本——子 agent 没有其他途径访问它
（GLM 审阅实验教训：保真是审阅生命线，基线/规则不缩写、不转述）。

## Fowler 12 坏味道基线（Standards 轴默认携带）

无论仓库是否写了编码标准，Standards 轴始终携带以下基线（《Refactoring》ch.3）。
每条是**带标签的启发式**（"possible Feature Envy"），不是硬违规；格式：*是什么 → 怎么修*。

1. **Mysterious Name 神秘命名** — 名字不揭示函数做什么/变量存什么 → 改名；想不出诚实的名字说明设计本身模糊。
2. **Duplicated Code 重复代码** — 同一逻辑形态出现在多个 hunk/文件 → 提取共享形态，两处调用。
3. **Feature Envy 依恋情结** — 方法摸别人对象的数据比摸自己的多 → 把方法移到它垂涎的数据上。
4. **Data Clumps 数据泥团** — 同几个字段/参数老结伴出行（一个想诞生的类型）→ 打包成一个类型。
5. **Primitive Obsession 基本类型偏执** — 用基本类型/字符串顶替值得拥有专属类型的领域概念 → 给概念建小类型。
6. **Repeated Switches 重复 switch** — 对同一类型的 switch/if 级联在变更中反复出现 → 多态替换，或共享同一张 map。
7. **Shotgun Surgery 霰弹式修改** — 一个逻辑变更逼散落多文件编辑 → 把一起变的东西收进一个模块。
8. **Divergent Change 发散式变更** — 一个文件/模块因多个无关理由被编辑 → 拆到每个模块为一个理由变。
9. **Speculative Generality 投机性泛化** — 为 spec 不需要的需求加抽象/参数/钩子 → 删掉，内联回直实需求出现。
10. **Message Chains 消息链** — 长 `a.b().c().d()` 导航，调用方不该依赖 → 把遍历藏进第一个对象的一个方法。
11. **Middle Man 中间人** — 类/函数多数时候只是转手委托 → 砍掉，直接调真正目标。
12. **Refused Bequest 拒绝遗产** — 子类/实现者忽略或覆盖大部分继承内容 → 放弃继承，用组合。

## 两条绑定规则

- **The repo overrides 仓库标准覆盖基线**：仓库文档化了的标准总是优先；仓库认可基线会标记的东西时，抑制该味道。
- **Always a judgement call 永远是判断**：每个味道是带标签的启发式，不是硬违规；工具已强制检查的项跳过。

## 审阅流程

1. **钉住基准点**（fixed point）：commit SHA / branch / tag / `HEAD~N`；diff 用三点式 `git diff <fixed>...HEAD`（对 merge-base 比较）。确认基准可解析且 diff 非空——坏引用/空 diff 在此失败，而不是在并行子 agent 里。
2. **找 spec 来源**：commit message 的 issue 引用 → 用户传参路径 → `docs/`/`specs/`/`.scratch/` 匹配文件 → 问用户。没有 spec 则 Spec 轴跳过并在报告注明。
3. **找标准来源**：仓库 `CODING_STANDARDS.md`/`CONTRIBUTING.md` 等；叠加上述 12 味道基线。
4. **并行 spawn 两个子 agent**（general-purpose）：
   - Standards prompt：diff 命令 + commit 列表 + 标准源文件列表 + **12 味道基线全文粘贴** + 指令"逐文件/hunk 报告：违反文档化标准处（引用文件+规则）；基线味道处（命名+引用 hunk）。硬违规 vs 判断区分开；工具已强制的跳过。400 词以内。"
   - Spec prompt：diff 命令 + commit 列表 + spec 路径/内容 + 指令"报告：spec 要求但缺失/不完整的；diff 里没被要求的（scope creep）；看似实现但实现错的（每条引用 spec 原文）。400 词以内。"
5. **聚合**：两轴报告在 `## Standards` / `## Spec` 标题下**逐字或轻清理**呈现，不合并不重排；结尾一行总结：每轴发现总数 + 每轴最严重问题（不跨轴选冠军）。

## 审阅实验沉淀（为什么这些纪律存在）

2026-07-14~15 用 GLM-5.2 对超脑 15 个核心模块做了外部审阅（19 包 ~6,150 行），发现并修复 40+ 真实缺陷（P0×5、P1×20+、P2×15+），提炼 6 种系统性缺陷模式：

1. 静默数据丢失（写路径失败无感知）
2. 量纲/归一化错误（阈值比较单位不一致）
3. 异常静默吞掉（except 后无记录）
4. 写副作用混进只读函数
5. 文档与行为不一致
6. 死代码/冗余读取

信任但验证（trust-but-verify）：外部审阅结论必须实跑验证后再采纳；误报稳定在 1-2 条/轮，属正常成本。

## 使用场景

- 发布前审查（配合 `github-project-publisher` 的 Phase 1 安全审查）
- 大型改动提交前自审
- 外部 AI 审阅大脑模式（Tabbit Pro GLM-5.2 / 其他模型）
