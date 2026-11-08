"""labs/ 的主题独立性与放置约定守卫。

三条不变量：

1. 每个 `labs/<topic>/` 必须有 README.md，否则主题无法被索引。
2. lab 内不得出现跨主题的相对引用（`../python/`、`../cc/` 等）；共享代码必须上提
   到 `labs/<topic>/common/` 或 `labs/libs/`。
3. lab 内不得写死本机 home 路径，否则换机器就失效。
"""

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LABS = ROOT / 'labs'

TEXT_SUFFIXES = {'.md', '.cc', '.c', '.h', '.hh', '.py', '.sh', '.toml', '.json', '.txt', '.mk'}
SIBLING_ROOTS = ('cc', 'python', 'rust', 'go', 'java', 'ocaml', 'lean4', 'shell', 'docs')
CROSS_REF = re.compile(r'\.\./(?:' + '|'.join(SIBLING_ROOTS) + r')/')
HOME_PATH = re.compile(r'/home/[A-Za-z0-9_.-]+/xwork/')
# 生成物不参与不变量检查：`.local` 是 labs/daft 的 chroot 运行环境，`site-packages`
# 是第三方源码（其中出现 `../cc/` 这样的字样与本仓库无关）。
SKIP_PARTS = {
    '.venv',
    'node_modules',
    '__pycache__',
    '.git',
    'bin',
    '.local',
    'site-packages',
    'rootfs',
    'uv-cache',
}


def lab_text_files():
    paths = subprocess.check_output(
        ['git', '-C', str(ROOT), 'ls-files', '--cached', '--others',
         '--exclude-standard', '-z', '--', 'labs/'],
    ).decode().split('\0')
    for name in filter(None, paths):
        path = ROOT / name
        if not path.is_file():
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            yield path


class LabIsolationTests(unittest.TestCase):
    def test_every_topic_has_readme(self):
        topics = sorted(path for path in LABS.iterdir() if path.is_dir())
        self.assertTrue(topics, 'labs/ 下至少应有一个主题目录')
        for topic in topics:
            with self.subTest(topic=topic.name):
                self.assertTrue((topic / 'README.md').is_file(), f'{topic.name} 缺少 README.md')

    def test_no_cross_topic_relative_reference(self):
        for path in lab_text_files():
            text = path.read_text(errors='replace')
            for match in CROSS_REF.finditer(text):
                self.fail(
                    f'{path.relative_to(ROOT)} 出现跨主题引用 {match.group(0)}；'
                    '共享代码应上提到 labs/<topic>/common/ 或 labs/libs/'
                )

    def test_no_absolute_home_path(self):
        for path in lab_text_files():
            text = path.read_text(errors='replace')
            for match in HOME_PATH.finditer(text):
                self.fail(
                    f'{path.relative_to(ROOT)} 写死了本机路径 {match.group(0)}；'
                    '改用相对路径或 $HOME'
                )


if __name__ == '__main__':
    unittest.main()
