# 超脑 Skill → GitHub 推送指令（完整版）

> 执行者：任意有命令行权限的 Agent（本地终端 / 远程服务器均可）
> 前置条件：已安装 git，有 GitHub 账号，仓库已创建（或协助创建）

---

## 第一步：确认 GitHub 仓库已创建

请在 GitHub 上创建仓库（如未创建）：

1. 登录 https://github.com
2. 点右上角 ➕ → **New repository**
3. 填写：
   - Repository name：`super-brain`
   - Description：`AI Agent 认知增强系统 — 持久记忆、知识图谱、SimHash语义搜索、自检修复`
   - Visibility：**Public**
   - ✅ 勾选 **Add a LICENSE** → 选 **MIT License**
   - ❌ 不勾选 Initialize with README（已有自己的 README）
4. 点 **Create repository**
5. 复制仓库 HTTPS 地址，格式如：
   ```
   https://github.com/你的用户名/super-brain.git
   ```

---

## 第二步：准备本地仓库目录

将以下目录完整复制到本地工作目录（如 `~/projects/super-brain/`）：

```
super-brain-v1.0.0/          ← 这是根目录
├── LICENSE
├── README.md                  ← 需替换 yourusername
├── examples/
│   ├── basic_memory.py
│   └── knowledge_graph.py
├── super-brain/
│   ├── SKILL.md
│   └── scripts/
│       ├── superbrain.py
│       ├── sb_core.py
│       ├── sb_memory.py
│       ├── sb_search.py
│       ├── sb_graph.py
│       ├── sb_selfcheck.py
│       └── test_superbrain.py
└── super-brain/references/
    ├── architecture.md
    ├── data-schema.md
    └── token-optimization.md
```

---

## 第三步：替换 README.md 中的用户名占位符

打开 `README.md`，将所有的 `yourusername` 替换为你的 GitHub 用户名。

替换前：
```
https://github.com/yourusername/super-brain
```

替换后（示例）：
```
https://github.com/leonxlnx/super-brain
```

共 3 处需要替换（标题徽章链接 + 安装说明中的 pip 命令示例）。

---

## 第四步：初始化 git 仓库并推送

在 `super-brain-v1.0.0/` 目录下执行：

```bash
# 1. 初始化 git
git init

# 2. 配置用户信息（如未全局配置）
git config user.name "你的GitHub用户名"
git config user.email "你的GitHub邮箱"

# 3. 添加所有文件
git add .

# 4. 首次提交
git commit -m "v1.0.0: 初始发布 — AI Agent认知增强系统

- 持久记忆引擎（增删改查 + 置信度 + 自动合并）
- 知识图谱（节点/边/实体对齐/邻居查询）
- SimHash + TF-IDF 混合语义检索
- 五项自检系统（一致性/时效性/完整性/关联性/重复数据）
- Workspace 隔离机制
- Token 优化引擎（上下文压缩 + 按需加载）
- 49 项单元测试全通过
- 零外部依赖，纯 Python 标准库"

# 5. 关联远程仓库（替换成你的仓库地址）
git remote add origin https://github.com/你的用户名/super-brain.git

# 6. 推送到 GitHub
git push -u origin main
# 如果报错 "main 不存在"，先运行：
#   git branch -M main
# 然后重新 push
```

---

## 第五步：处理 GitHub 认证（如遇到）

### 方式 A：GitHub Personal Access Token（推荐）

1. 登录 GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token：
   - Expiration：90 days
   - 勾选 `repo`（完整仓库权限）
3. 复制生成的 token（形如 `ghp_xxxxxxxx`）
4. 推送时用户名填 GitHub 用户名，密码填 token

### 方式 B：GitHub CLI（如环境支持）

```bash
gh auth login
# 按提示选择 GitHub.com → HTTPS → 浏览器登录
gh repo create super-brain --public --source=. --push
```

---

## 第六步：推送后检查清单

推送成功后，在 GitHub 仓库页面确认：

- [ ] `README.md` 正确渲染，徽章显示正常
- [ ] `LICENSE` 文件存在，页面显示 MIT 许可证徽章
- [ ] `examples/` 目录可见
- [ ] `super-brain/SKILL.md` 存在
- [ ] 代码文件语法高亮正常（Python）

### 建议补充的操作（在 GitHub 页面操作）：

1. **创建 Release**：
   - 进入仓库 → Releases → Create new release
   - Tag：`v1.0.0`
   - Release title：`v1.0.0 — 初始发布`
   - 描述：复制 commit message 内容
   - 附件：上传 `super-brain-v1.0.0.zip`

2. **添加 Topics**（仓库页面右侧 Settings → Topics）：
   ```
   ai-agent, memory, knowledge-graph, python, cognitive-enhancement, semantic-search, self-check
   ```

---

## 故障排查

| 问题 | 解决方案 |
|------|----------|
| `git push` 报错 403 | 认证失败 → 用 Personal Access Token 代替密码 |
| `main` 分支不存在 | `git branch -M main` 然后重新 push |
| README 中链接 404 | 检查 `yourusername` 是否已全部替换 |
| 中文字符乱码 | 确保 git 配置 `git config --global core.autocrlf false` |

---

## 附：一键推送脚本（Linux/macOS）

如环境支持，可直接运行此脚本（填好用户名和邮箱）：

```bash
#!/bin/bash
USERNAME="你的GitHub用户名"
EMAIL="你的GitHub邮箱"
REPO_URL="https://github.com/${USERNAME}/super-brain.git"

git init
git config user.name "$USERNAME"
git config user.email "$EMAIL"
git add .
git commit -m "v1.0.0: 初始发布"
git branch -M main
git remote add origin "$REPO_URL"
git push -u origin main
```
