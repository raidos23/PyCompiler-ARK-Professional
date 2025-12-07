from typing import Any


def compute_tag_order(meta_map: dict[str, dict[str, Any]]) -> list[str]:
    """Trie les plugins par score de tag (plus petit d'abord), puis par id.
    Tags pris depuis meta_map[pid]["tags"]. Inconnu => 100.
    """
    tag_score = {
        # Clean early (workspace hygiene)
        "clean": 0,
        "cleanup": 0,
        "sanitize": 0,
        "prune": 0,
        "tidy": 0,
        # Validation / presence of inputs
        "validation": 10,
        "presence": 10,
        "check": 10,
        "requirements": 10,
        # Prepare / generate inputs and resources
        "prepare": 20,
        "codegen": 20,
        "generate": 20,
        "fetch": 20,
        "resources": 20,
        "download": 20,
        "install": 20,
        "bootstrap": 20,
        "configure": 20,
        # Conformity / headers before linters
        "license": 30,
        "header": 30,
        "normalize": 30,
        "inject": 30,
        "spdx": 30,
        "banner": 30,
        "copyright": 30,
        # Lint / format / typing
        "lint": 40,
        "format": 40,
        "typecheck": 40,
        "mypy": 40,
        "flake8": 40,
        "ruff": 40,
        "pep8": 40,
        "black": 40,
        "isort": 40,
        "sort-imports": 40,
        # Obfuscation / protect / transpile (final pre-compile passes)
        "obfuscation": 50,
        "obfuscate": 50,
        "transpile": 50,
        "protect": 50,
        "encrypt": 50,
    }

    def _score(pid: str) -> int:
        try:
            tags = meta_map.get(pid, {}).get("tags") or []
            if isinstance(tags, list) and tags:
                return int(
                    min((tag_score.get(str(t).lower(), 100) for t in tags), default=100)
                )
        except Exception:
            pass
        return 100

    return sorted(meta_map.keys(), key=lambda x: (_score(x), x))
