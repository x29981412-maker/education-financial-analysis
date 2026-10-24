"""从仓库目录直接复现实验，不需要安装项目。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from receipts.cli import main

if __name__ == "__main__":
    main(["demo", "--root", str(ROOT), *sys.argv[1:]])
