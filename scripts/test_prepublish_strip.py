"""
prepublish_strip_local_paths.py 的回归测试（纯标准库 unittest，零依赖）。

Copyright (c) 2026 A1m1ng777888. Licensed under MIT.
Author: A1m1ng777888

覆盖 v3.8.5 修补的真 bug：
- P0-1: DEFAULT_VAULT_PATH 赋值行带尾部注释时，仍应走 VAULT 分支产出
        os.path.expanduser("~/ObsidianVault") 包装，而非裸串 "~/ObsidianVault"。
- P0-2: 缩进赋值行替换后保留原始缩进。
- P1-1: 注释/帮助文本中的 Unix 绝对路径 (/home/xxx 等) 应被脱敏。
- P2-1: file:///E:/... 中的盘符路径不应被误伤。
- 控制组: https:// 不误伤、正常 Windows 路径仍脱敏、已通用值不改。
"""
import unittest

from prepublish_strip_local_paths import strip_text


class TestStripText(unittest.TestCase):
    def test_vault_assign_no_comment(self):
        line = 'DEFAULT_VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH", "E:/vault")'
        res, changed = strip_text(line)
        self.assertTrue(changed)
        self.assertIn('os.path.expanduser("~/ObsidianVault")', res)

    def test_vault_assign_with_trailing_comment(self):
        # P0-1: 带尾部注释必须仍匹配 VAULT 分支，产出 expanduser 包装（非裸串）
        line = 'DEFAULT_VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH", "E:/vault")  # 默认库'
        res, changed = strip_text(line)
        self.assertTrue(changed, "带尾部注释的赋值行应被脱敏")
        self.assertIn('os.path.expanduser("~/ObsidianVault")', res)
        self.assertNotIn(', "~/ObsidianVault")', res, "不应降级为裸串")

    def test_vault_assign_indented(self):
        # P0-2: 缩进赋值行替换后保留缩进
        line = '    DEFAULT_VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH", "E:/vault")'
        res, changed = strip_text(line)
        self.assertTrue(changed)
        self.assertTrue(res.startswith("    "), "应保留原始缩进")

    def test_vault_assign_already_generic(self):
        line = 'DEFAULT_VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH", os.path.expanduser("~/ObsidianVault"))'
        _, changed = strip_text(line)
        self.assertFalse(changed, "已是通用值不应改动")

    def test_drive_path_in_comment(self):
        line = '# 旧路径 E:/vault/data'
        res, changed = strip_text(line)
        self.assertTrue(changed)
        self.assertNotIn("E:/", res)

    def test_unix_home_path_stripped(self):
        # P1-1: Unix 绝对路径应被脱敏
        line = '# 默认: /home/a1m1ng/ObsidianVault'
        res, changed = strip_text(line)
        self.assertTrue(changed, "Unix 主目录路径应被脱敏")
        self.assertIn("~/ObsidianVault", res)
        self.assertNotIn("/home/a1m1ng", res)

    def test_file_url_not_corrupted(self):
        # P2-1: file:/// 中的盘符路径不应被误伤
        line = 'url = "file:///E:/foo/bar"'
        res, changed = strip_text(line)
        self.assertFalse(changed, "file:/// 路径不应被脱敏破坏")
        self.assertIn("file:///E:/foo/bar", res)

    def test_https_url_not_corrupted(self):
        line = 'url = "https://github.com/user/repo"'
        res, changed = strip_text(line)
        self.assertFalse(changed, "https:// URL 不应被误伤")
        self.assertIn("github.com", res)


if __name__ == "__main__":
    unittest.main(verbosity=2)
