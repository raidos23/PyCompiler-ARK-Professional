#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# PyCompiler Pro++ — High-grade launcher (Unix)
# Author: Samuel Amen Ague
# Copyright (c) 2025 Samuel Amen Ague. All rights reserved.

set -Eeuo pipefail

# --- Styling (ANSI) ---------------------------------------------------------
if [[ -t 1 ]]; then
  BOLD="\033[1m"; DIM="\033[2m"; RED="\033[31m"; GREEN="\033[32m"; YELLOW="\033[33m"; BLUE="\033[34m"; RESET="\033[0m"
else
  BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; BLUE=""; RESET=""
fi
log_info(){ echo -e "${BLUE}ℹ️  ${BOLD}$*${RESET}"; }
log_ok(){ echo -e "${GREEN}✅ $*${RESET}"; }
log_warn(){ echo -e "${YELLOW}⚠️  $*${RESET}"; }
log_err(){ echo -e "${RED}❌ $*${RESET}" 1>&2; }
section(){ echo -e "\n${BOLD}— $* —${RESET}"; }

# Always run from the script directory
cd "$(dirname "$0")"

# Load .env if present (export variables)
if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a; source ./.env; set +a || true
fi

# Platform quirks
export QT_WAYLAND_DISABLE_FRACTIONAL_SCALE=${QT_WAYLAND_DISABLE_FRACTIONAL_SCALE:-1}

# Global env safety
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
# Force interactive UI (disable any non-interactive mode)
export PYCOMPILER_NONINTERACTIVE=0

# Timing
__START_TS__=$(date +%s)
cleanup(){
  local rc=$?
  local end=$(date +%s); local dur=$(( end - __START_TS__ ))
  if (( rc == 0 )); then log_ok "Terminé en ${dur}s"; else log_err "Échec en ${dur}s (code ${rc})"; fi
}
errtrap(){ log_err "Erreur à la ligne ${BASH_LINENO[0]} (commande: '${BASH_COMMAND}')"; }
trap cleanup EXIT
trap errtrap ERR

# --- Defaults & CLI --------------------------------------------------------
VENV_DIR=${VENV_DIR:-venv}
VENV_DIR_CLI_SPECIFIED=0
REQ_FILE=${REQ_FILE:-requirements.txt}
PY_CMD_OVERRIDE=""
MIN_PY=${MIN_PY:-3.10}
RECREATE=0
SKIP_INSTALL=0
NO_UPGRADE=0
PIP_EXTRA=()
APP_ARGS=()
OFFLINE=0
WHEELHOUSE=""
FORCE_INSTALL=0
MIN_FREE_MB=${MIN_FREE_MB:-200}
NO_COLOR_OPT=0
LOG_FILE=""

usage(){ cat <<EOF
${BOLD}PyCompiler Pro++ launcher${RESET}
Usage: ./run.sh [options] [--] [app-args]

Options:
  --recreate            Recrée le venv avant le lancement
  --skip-install        N'installe pas requirements.txt
  --no-upgrade          N'exécute pas l'upgrade de pip
  --venv <dir>          Chemin du venv (défaut auto: .venv ou venv)
  --requirements <file> Fichier requirements (défaut: requirements.txt)
  --python <exe>        Binaire Python pour créer le venv (détection auto sinon)
  --min-py <X.Y>        Version Python minimale (défaut: ${MIN_PY})
  --pip-arg <arg>       Argument additionnel pour pip (répétable)
  --offline             Mode hors-ligne (pip --no-index; nécessite --wheelhouse)
  --wheelhouse <dir>    Dossier de roues locales pour --offline (--find-links)
  --force-install       Forcer réinstallation des requirements (ignore le cache hash)
  --min-free-mb <N>     Espace disque minimal requis (défaut: ${MIN_FREE_MB} MiB)
  --no-color            Désactiver la couleur dans les logs
  --log <file>          Journaliser (stdout/err) dans un fichier (avec tee)
  -h|--help             Affiche cette aide
  --                    Fin des options du script (le reste est passé à main.py)
EOF
}

while ((${#})); do
  case "$1" in
    -h|--help) usage; exit 0;;
    --recreate) RECREATE=1; shift;;
    --skip-install) SKIP_INSTALL=1; shift;;
    --no-upgrade) NO_UPGRADE=1; shift;;
    --venv) VENV_DIR="$2"; VENV_DIR_CLI_SPECIFIED=1; shift 2;;
    --requirements) REQ_FILE="$2"; shift 2;;
    --python) PY_CMD_OVERRIDE="$2"; shift 2;;
    --min-py) MIN_PY="$2"; shift 2;;
    --pip-arg) PIP_EXTRA+=("$2"); shift 2;;
    --offline) OFFLINE=1; shift;;
    --wheelhouse) WHEELHOUSE="$2"; shift 2;;
    --force-install) FORCE_INSTALL=1; shift;;
    --min-free-mb) MIN_FREE_MB="$2"; shift 2;;
    --no-color) NO_COLOR_OPT=1; shift;;
    --log) LOG_FILE="$2"; shift 2;;
    --) shift; APP_ARGS+=("$@"); break;;
    -*) log_err "Option inconnue: $1"; usage; exit 2;;
    *) APP_ARGS+=("$1"); shift;;
  esac
done

# Auto-detect venv directory when not specified explicitly
if [[ ${VENV_DIR_CLI_SPECIFIED:-0} -eq 0 ]]; then
  if [[ -d ".venv" ]]; then
    VENV_DIR=".venv"
  elif [[ -d "venv" ]]; then
    VENV_DIR="venv"
  else
    VENV_DIR=".venv"
  fi
fi

# Disable colors if requested
if [[ $NO_COLOR_OPT -eq 1 || -n "${NO_COLOR:-}" ]]; then BOLD=""; DIM=""; RED=""; GREEN=""; YELLOW=""; BLUE=""; RESET=""; fi

# Optional logging to file
if [[ -n "$LOG_FILE" ]]; then
  mkdir -p "$(dirname "$LOG_FILE")" || true
  exec > >(tee -a "$LOG_FILE") 2>&1
  log_info "Journal: $LOG_FILE"
fi

# --- Python discovery & version check -------------------------------------
choose_python(){
  if [[ -n "$PY_CMD_OVERRIDE" ]]; then echo "$PY_CMD_OVERRIDE"; return; fi
  # Prefer Python 3.12 by default, then fallback to 3.13 and lower (11..8)
  for cand in python3.12 python3.13 python3.11 python3.10 python3.9 python3.8; do
    if command -v "$cand" >/dev/null 2>&1; then echo "$cand"; return; fi
  done
  if command -v python3 >/dev/null 2>&1; then echo python3; return; fi
  if command -v python >/dev/null 2>&1; then echo python; return; fi
  return 1
}
PY_CMD=$(choose_python || true)
if [[ -z "$PY_CMD" ]]; then log_err "Python introuvable dans le PATH"; exit 1; fi

ver_ok=$("$PY_CMD" - <<PY
import sys
minv=tuple(map(int, "${MIN_PY}".split('.')))
ok = sys.version_info >= minv
print('OK' if ok else 'KO')
PY
)
if [[ "$ver_ok" != "OK" ]]; then
  log_err "Version Python trop ancienne (min ${MIN_PY}). Trouvé: $($PY_CMD -V 2>&1)"
  exit 1
fi
log_info "Python hôte: $($PY_CMD -V 2>&1)"

# --- Disk space check ------------------------------------------------------
if command -v df >/dev/null 2>&1; then
  AVAIL_MB=$(df -Pm . | awk 'NR==2{print $4}')
  if [[ -n "$AVAIL_MB" && "$AVAIL_MB" -lt "$MIN_FREE_MB" ]]; then
    log_err "Espace disque insuffisant: ${AVAIL_MB} MiB disponibles < ${MIN_FREE_MB} MiB requis"
    exit 1
  fi
fi

# --- Virtual environment ---------------------------------------------------
if [[ $RECREATE -eq 1 && -d "$VENV_DIR" ]]; then
  section "Recréation du venv"
  rm -rf "$VENV_DIR"
fi
if [[ ! -d "$VENV_DIR" ]]; then
  section "Création du venv"
  "$PY_CMD" -m venv "$VENV_DIR"
fi
VENV_PY="$VENV_DIR/bin/python"
if [[ ! -x "$VENV_PY" ]]; then log_err "Python du venv introuvable: $VENV_PY"; exit 1; fi
log_info "Python venv: $($VENV_PY -V 2>&1) @ $VENV_PY"

# --- Dependencies ----------------------------------------------------------
if [[ $NO_UPGRADE -eq 0 ]]; then
  section "Mise à jour pip"
  "$VENV_PY" -m pip install --upgrade pip
fi
if [[ $SKIP_INSTALL -eq 0 ]]; then
  if [[ -f "$REQ_FILE" ]]; then
    # requirements hash cache
    REQ_HASH=$(command -v sha256sum >/dev/null 2>&1 && sha256sum "$REQ_FILE" | awk '{print $1}' || openssl dgst -sha256 "$REQ_FILE" | awk '{print $2}')
    MARKER="$VENV_DIR/.requirements.sha256"
    if [[ $FORCE_INSTALL -eq 0 && -f "$MARKER" ]]; then
      CUR=$(cat "$MARKER" 2>/dev/null || true)
    else
      CUR=""
    fi
    if [[ "$REQ_HASH" == "$CUR" ]]; then
      log_ok "requirements.txt déjà installé (hash identique), saute l'installation"
    else
      section "Installation des dépendances ($REQ_FILE)"
      PIP_ARGS=(install -r "$REQ_FILE" "${PIP_EXTRA[@]}")
      if [[ $OFFLINE -eq 1 ]]; then
        if [[ -z "$WHEELHOUSE" ]]; then log_err "--offline nécessite --wheelhouse <dir>"; exit 2; fi
        PIP_ARGS=(install --no-index --find-links "$WHEELHOUSE" -r "$REQ_FILE" "${PIP_EXTRA[@]}")
      fi
      "$VENV_PY" -m pip "${PIP_ARGS[@]}"
      echo "$REQ_HASH" >"$MARKER" || true
    fi
  else
    log_warn "Aucun fichier $REQ_FILE trouvé — installation ignorée"
  fi
else
  log_warn "Installation des dépendances ignorée (--skip-install)"
fi

# --- Launch ---------------------------------------------------------------
APP_VERSION=$($VENV_PY - <<'PY'
try:
    import Core
    print(getattr(Core, '__version__', '?'))
except Exception:
    print('?')
PY
)
section "Lancement de main.py (version ${APP_VERSION})"
exec "$VENV_PY" main.py "${APP_ARGS[@]}"
