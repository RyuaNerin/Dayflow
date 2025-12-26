import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from i18n import compile_po, _locales_dir


def build_po():
    for po_file in _locales_dir.rglob("*.po"):
        print(f"Compiling... {po_file}")
        compile_po(po_file)


if __name__ == "__main__":
    build_po()
