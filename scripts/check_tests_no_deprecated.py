"""Script simple para detectar patrones prohibidos en tests.

Busca patrones comunes que provoquen DeprecationWarning (por ejemplo `datetime.utcnow(`)
y falla con código de salida 1 si encuentra coincidencias.
"""
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_DIR = ROOT / 'app' / 'tests'

PATTERNS = [
    re.compile(r"datetime\.utcnow\(")
]


def find_issues() -> int:
    matches = []
    for p in TEST_DIR.rglob('*.py'):
        text = p.read_text(encoding='utf-8')
        for pat in PATTERNS:
            if pat.search(text):
                matches.append(str(p))
                break
    if matches:
        print("Se encontraron patrones prohibidos en tests:")
        for m in matches:
            print("  -", m)
        return 1
    print("No se encontraron patrones prohibidos.")
    return 0


if __name__ == '__main__':
    sys.exit(find_issues())
