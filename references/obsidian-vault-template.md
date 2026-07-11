# 本地知识库搭建模板（Super Brain 通用版）

> 路径无关模板。把所有 `<VAULT>` 替换成你自己的仓库（vault）根目录即可。通用版**不写死任何路径**——你的 vault 由你自己定。

## 0. 前置：安装 Obsidian（可选但推荐）

1. 到 [obsidian.md](https://obsidian.md) 下载安装（Windows / macOS / Linux 均支持）。
2. 首次启动选「创建仓库」或「打开仓库」，记下你设定的仓库路径——它就是本模板的 `<VAULT>`。
   - 例：通用路径 `~/MyVault`（Windows / macOS / Linux 均适用；也可放在任意目录，把本模板的 <VAULT> 换成你的实际路径）
3. 若暂未安装：先按本模板搭建目录习惯，装好 Obsidian 后再执行第 3 步接入。

## 1. 推荐仓库目录结构

把以下骨架放到 `<VAULT>` 根目录（空文件夹即可）：

```
<VAULT>/
├── 00_Inbox/           # 临时收集，待整理
├── 01_Projects/        # 项目归档（每项目一个子文件夹）
├── 02_Areas/           # 长期关注的领域
├── 03_Resources/       # 参考资料、文章、素材
├── 04_Archive/         # 已完成 / 弃用的归档
├── 超脑记忆/           # ⚠️ Super Brain 自动导出目录，请勿手改
│   ├── _INDEX.md       #   记忆索引
│   ├── 知识图谱.canvas  #   记忆级知识图谱（json-canvas）
│   └── *.md            #   每条记忆一个文件（callout 格式）
├── 附件/
└── 模板/
```

> 目录编号（00~04）参考 PARA 法，便于排序检索；可调整，但请**保留 `超脑记忆/` 目录名**（导出依赖它）。

## 2. 告诉 Super Brain 你的 vault 在哪

**方式 A：环境变量（推荐，一次配置永久生效）**
- Windows（PowerShell）：
  ```powershell
  setx OBSIDIAN_VAULT_PATH "<VAULT>"
  ```
- macOS / Linux（写入 shell 配置）：
  ```bash
  echo 'export OBSIDIAN_VAULT_PATH="<VAULT>"' >> ~/.zshrc   # 或 ~/.bashrc
  ```

**方式 B：每次导出显式指定**
```bash
python superbrain.py obsidian export --vault-path "<VAULT>"
```

## 3. 首次导出记忆与知识图谱

```bash
python superbrain.py obsidian export
```

成功后在 `<VAULT>/超脑记忆/` 生成：
- `_INDEX.md`：所有记忆的索引
- 每条记忆一个 `.md`（callout 元数据 + block reference `^sb-content`）
- `知识图谱.canvas`：可视化知识网络（按类别上色、力导向、关系标签、图例）

## 4. 在 Obsidian 中查看

1. 用 Obsidian 打开 `<VAULT>` 作为 vault。
2. 文件树进入 `超脑记忆/`，查看记忆与图谱。
3. 推荐装 **Dataview** 插件，做动态检索看板。

## 5. 可选：vault 与 Super Brain 工作空间绑定

```bash
python superbrain.py workspace set <名称> --vault "<VAULT>"
```

## 常见问题

- **没装 Obsidian 能用吗？** 能。JSON 记忆照常工作，只是没有图谱可视化与双向编辑。装好后按本模板接入。
- **换电脑 / vault 路径变了？** 更新 `OBSIDIAN_VAULT_PATH` 或改用 `--vault-path`，重新 `export` 即可。
- **误改了 `超脑记忆/` 里的文件？** `python superbrain.py obsidian sync --apply` 可把改动写回 Super Brain（谨慎使用）。
