#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prepublish_strip_local_paths.py — Super Brain 发布前脱敏（路径无关 / PATH-AGNOSTIC）

背景
----
本地版（作者 ~/.workbuddy/skills/super-brain/）为开箱即用便利，将
DEFAULT_VAULT_PATH 硬编码为作者主库的绝对路径。但通用版（GitHub clone）必须
使用通用回退值 os.path.expanduser("~/ObsidianVault")，否则 github-project-publisher
的 Phase 1 安全审查会把硬编码绝对路径判定为「个人路径泄露」并拦截发布。

本脚本在「发布副本（clone-temp）」上运行，把硬编码的绝对 vault 路径还原为通用
回退值。脚本本身 PATH-AGNOSTIC：不含任何作者个人路径，仅按结构识别并替换，故
自身也能通过 Phase 1 审查。

! 重要约定
- 本脚本只修改 --target-dir 指定的「发布副本」，绝不触碰源 skill 目录。
- 默认 dry-run：只预览改动，不写文件；加 --apply 才真正改写。
- 只处理两个事实源文件：sb_obsidian.py（DEFAULT_VAULT_PATH 定义）与
  superbrain.py（--vault-path 帮助文本）。其余 .py / .md 不在范围内，
  其路径示例应由人工/审查保持 path-free。

检测逻辑（路径无关）
- DEFAULT_VAULT_PATH 行：若回退值不是通用 expanduser 形式，强制改写为通用回退。
- 注释 / 帮助文本中的残留绝对路径（盘符 + 斜杠）：用负向后行断言排除 https://，
  匹配到则替换为 ~/ObsidianVault。

用法
----
  # 预览（不改写）
  python prepublish_strip_local_paths.py --target-dir /path/to/clone-temp/super-brain

  # 真正改写发布副本
  python prepublish_strip_local_paths.py --target-dir /path/to/clone-temp/super-brain --apply

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888
"""

import argparse
import os
import re
import sys

# 通用回退值（与 sb_obsidian.py 发布版保持一致）
GENERIC_FALLBACK = 'os.path.expanduser("~/ObsidianVault")'

# DEFAULT_VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH", <回退值>)
VAULT_ASSIGN_RE = re.compile(
    r'DEFAULT_VAULT_PATH\s*=\s*os\.environ\.get\(\s*"OBSIDIAN_VAULT_PATH"\s*,\s*(.*?)\)\s*$'
)

# 绝对路径（盘符 + 斜杠），负向后行断言排除 https:// 等协议 URL。
# 路径字符类显式列出（含中文 \u4e00-\u9fff），遇到空白/标点（; ； 。 ，等）即停，
# 避免把后面的说明文字（如 OBSIDIAN_VAULT_PATH）一起吞掉。
# 例：某 Windows 盘符绝对路径（如 `X:\some\path`）；但 https:// 中的 s:/ 不会被匹配
DRIVE_PATH_RE = re.compile(r'(?<![A-Za-z])[A-Za-z]:[\\/][\u4e00-\u9fffa-zA-Z0-9_./\\-]+')

# 只处理这两个事实源文件
TARGET_FILES = ("sb_obsidian.py", "superbrain.py")


def strip_text(text):
    """返回 (新文本, 是否改动)。路径无关替换。"""
    changed = False
    lines = text.split("\n")
    out = []
    for line in lines:
        # 1) DEFAULT_VAULT_PATH 赋值行：强制回退为通用值
        m = VAULT_ASSIGN_RE.search(line)
        if m:
            current = m.group(1).strip()
            if current != GENERIC_FALLBACK:
                out.append(
                    'DEFAULT_VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH", '
                    + GENERIC_FALLBACK
                    + ')'
                )
                changed = True
                continue
            out.append(line)
            continue
        # 2) 注释 / 帮助文本中的残留绝对路径：替换为 ~/ObsidianVault
        if DRIVE_PATH_RE.search(line):
            new_line = DRIVE_PATH_RE.sub("~/ObsidianVault", line)
            if new_line != line:
                changed = True
            out.append(new_line)
            continue
        out.append(line)
    return "\n".join(out), changed


def find_target_files(target_dir):
    found = []
    for root, _dirs, files in os.walk(target_dir):
        for fn in files:
            if fn in TARGET_FILES:
                found.append(os.path.join(root, fn))
    return found


def main():
    ap = argparse.ArgumentParser(description="Strip hardcoded local vault paths before publishing (path-agnostic).")
    ap.add_argument("--target-dir", required=True, help="Path to the publish copy (clone-temp/super-brain). Dry-run by default.")
    ap.add_argument("--apply", action="store_true", help="Actually rewrite files. Without this, only preview.")
    args = ap.parse_args()

    if not os.path.isdir(args.target_dir):
        print(f"[ERR] target-dir not found: {args.target_dir}", file=sys.stderr)
        return 2

    files = find_target_files(args.target_dir)
    if not files:
        print(f"[WARN] no target files ({', '.join(TARGET_FILES)}) found under {args.target_dir}", file=sys.stderr)
        return 1

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[strip] mode={mode}  target-dir={args.target_dir}")
    print(f"[strip] scanning: {', '.join(os.path.relpath(f, args.target_dir) for f in files)}")

    any_changed = False
    for fpath in files:
        with open(fpath, "r", encoding="utf-8") as fh:
            original = fh.read()
        new_text, changed = strip_text(original)
        rel = os.path.relpath(fpath, args.target_dir)
        if not changed:
            print(f"  - {rel}: clean (no local path)")
            continue
        any_changed = True
        print(f"  * {rel}: STRIPPED")
        if args.apply:
            with open(fpath, "w", encoding="utf-8") as fh:
                fh.write(new_text)
            print(f"      wrote {rel}")
        else:
            # 预览：打印差异行
            o_lines = original.split("\n")
            n_lines = new_text.split("\n")
            for i, (o, n) in enumerate(zip(o_lines, n_lines)):
                if o != n:
                    print(f"      - {o}")
                    print(f"      + {n}")

    # 改写后再扫一遍，确保没有遗漏的绝对路径
    if args.apply:
        leftover = []
        for fpath in files:
            with open(fpath, "r", encoding="utf-8") as fh:
                for ln, line in enumerate(fh.readlines(), 1):
                    if DRIVE_PATH_RE.search(line):
                        leftover.append(f"{os.path.relpath(fpath, args.target_dir)}:{ln}: {line.rstrip()}")
        if leftover:
            print("\n[WARN] 改写后仍存在未处理的绝对路径，请人工确认：")
            for item in leftover:
                print(f"  {item}")
            return 1

    print("\n[strip] done." + ("" if any_changed else " 无需改动。"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
