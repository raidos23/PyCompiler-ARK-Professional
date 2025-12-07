from typing import Any


def compute_tag_order(meta_map: dict[str, dict[str, Any]]) -> list[str]:
    """Trie les plugins par score de tag (plus petit d'abord), puis par id.
    Tags pris depuis meta_map[pid]["tags"]. Inconnu => 100.
    """
    tag_score = {}

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
