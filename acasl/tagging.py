from typing import Any


# Hiérarchie de priorité basée sur les tags (ordre d'exécution post-compilation)
TAG_PRIORITY_MAP = {
    # Phase 0: Nettoyage et hygiène des artefacts
    "clean": 0,
    "cleanup": 0,
    "sanitize": 0,
    "prune": 0,
    "tidy": 0,
    
    # Phase 1: Validation et vérification des artefacts
    "validation": 10,
    "verify": 10,
    "check": 10,
    "integrity": 10,
    
    # Phase 2: Optimisation et post-traitement
    "optimize": 20,
    "optimization": 20,
    "compress": 20,
    "strip": 20,
    "minify": 20,
    
    # Phase 3: Signature et sécurité
    "sign": 30,
    "signature": 30,
    "security": 30,
    "encrypt": 30,
    "hash": 30,
    
    # Phase 4: Packaging et distribution
    "package": 40,
    "packaging": 40,
    "bundle": 40,
    "archive": 40,
    "zip": 40,
    
    # Phase 5: Reporting et documentation
    "report": 50,
    "reporting": 50,
    "stats": 50,
    "statistics": 50,
    "document": 50,
    "log": 50,
}

# Valeur par défaut pour les tags inconnus
DEFAULT_TAG_PRIORITY = 100


def compute_tag_order(meta_map: dict[str, dict[str, Any]]) -> list[str]:
    """Trie les plugins par score de tag (plus petit d'abord), puis par id.
    
    Utilise TAG_PRIORITY_MAP pour déterminer la priorité basée sur les tags.
    Tags pris depuis meta_map[pid]["tags"]. Inconnu => DEFAULT_TAG_PRIORITY.
    
    Phases d'exécution post-compilation:
    - 0: Nettoyage (clean, cleanup, sanitize)
    - 10: Validation (check, verify, integrity)
    - 20: Optimisation (optimize, compress, strip)
    - 30: Signature (sign, security, encrypt)
    - 40: Packaging (package, bundle, archive)
    - 50: Reporting (report, stats, document)
    - 100: Défaut (aucun tag reconnu)
    """
    def _compute_score(pid: str) -> int:
        """Calcule le score de priorité pour un plugin.
        
        Retourne le score minimum parmi tous les tags du plugin.
        Si aucun tag, retourne DEFAULT_TAG_PRIORITY.
        """
        try:
            tags = meta_map.get(pid, {}).get("tags")
            if not tags:
                return DEFAULT_TAG_PRIORITY
            
            if not isinstance(tags, (list, tuple)):
                return DEFAULT_TAG_PRIORITY
            
            # Normaliser les tags et trouver le score minimum
            scores = []
            for tag in tags:
                tag_str = str(tag).strip().lower()
                if tag_str:
                    score = TAG_PRIORITY_MAP.get(tag_str, DEFAULT_TAG_PRIORITY)
                    scores.append(score)
            
            return min(scores) if scores else DEFAULT_TAG_PRIORITY
        except Exception:
            return DEFAULT_TAG_PRIORITY
    
    # Trier par (score, id) pour stabilité et lisibilité
    return sorted(meta_map.keys(), key=lambda x: (_compute_score(x), x))


def get_tag_phase_name(tag: str) -> str:
    """Retourne le nom lisible de la phase pour un tag donné."""
    tag_lower = str(tag).strip().lower()
    score = TAG_PRIORITY_MAP.get(tag_lower, DEFAULT_TAG_PRIORITY)
    
    phase_names = {
        0: "Nettoyage",
        10: "Validation",
        20: "Optimisation",
        30: "Signature",
        40: "Packaging",
        50: "Reporting",
        100: "Défaut",
    }
    
    return phase_names.get(score, f"Phase {score}")


def describe_plugin_priority(plugin_id: str, tags: list[str]) -> str:
    """Retourne une description lisible de la priorité d'un plugin.
    
    Exemple: "plugin_id (optimize, compress) -> Phase 2: Optimisation"
    """
    if not tags:
        return f"{plugin_id} (aucun tag) -> Phase {DEFAULT_TAG_PRIORITY}: Défaut"
    
    tag_str = ", ".join(str(t).strip().lower() for t in tags)
    scores = [TAG_PRIORITY_MAP.get(str(t).strip().lower(), DEFAULT_TAG_PRIORITY) for t in tags]
    min_score = min(scores) if scores else DEFAULT_TAG_PRIORITY
    phase_name = get_tag_phase_name(min_score)
    
    return f"{plugin_id} ({tag_str}) -> Phase {min_score}: {phase_name}"
