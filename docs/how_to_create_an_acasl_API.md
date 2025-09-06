# How to create an ACASL API (After Compilation Advanced System Loader) — Updated

Author: Samuel Amen Ague
License: GPL-3.0-only

Quick Navigation
- [What is ACASL?](#what-is-acasl)
- [Execution flow](#execution-flow-and-integration)
- [Package layout](#where-to-place-your-plugins-package-layout)
- [Templates](#plugin-templates)
- [SDK facade & Context](#acasl-sdk-facade-and-context-available-api)
- [Configuration](#configuration-acasljson)
- [System installs](#system-installs-pip-global-and-os-package-managers)
- [UI: ACASL Loader](#ui-acasl-loader-enable-and-order-plugins)
- [Cancellation & robustness](#cancellation-and-robustness)
- [Best practices](#best-practices-security-ux-logs)
- [Troubleshooting](#troubleshooting)
- [Extended examples](#extended-examples-rich-collection)
- [Recap](#recap)

This guide explains how to write, configure, and run ACASL plugins that operate on build artifacts after compilation (post‑build). Typical use cases include code signing, notarization, packaging installers, integrity checks, SBOM generation, hashing, smoke tests, and publishing releases.

Highlights (what changed)
- Extended plugin metadata supported by the loader UI: ACASL_NAME, ACASL_VERSION, ACASL_AUTHOR, ACASL_CREATED, ACASL_LICENSE, ACASL_COMPATIBILITY, ACASL_TAGS.
- System install helpers available in the ACASL SDK facade: ensure_system_pip_install (pip global) and ensure_system_packages (apt/dnf/pacman/zypper/winget/choco/brew) with user consent and non‑interactive safety.
- Examples updated to demonstrate system installs and best practices.

Important rules (strict)
- ACASL plugins must be Python packages under API/<plugin_id>/ (folder with an __init__.py).
- Mandatory package signature in __init__.py:
  - ACASL_PLUGIN = True
  - ACASL_ID = "your_id"
  - ACASL_DESCRIPTION = "short description"
- Each plugin package must expose a callable function acasl_run(ctx) in its __init__.py.
- Always import from the namespaced facade API_SDK.ACASL_SDK in your plugin code.
- The loader enforces this signature strictly and will skip/reject non‑conforming packages.
- Recommended extended metadata for better UX in the UI:
  - ACASL_NAME, ACASL_VERSION, ACASL_AUTHOR, ACASL_CREATED, ACASL_LICENSE, ACASL_COMPATIBILITY (list[str]), ACASL_TAGS (list[str])

Example: minimal import pattern within your package’s __init__.py

```python
from API_SDK.ACASL_SDK import wrap_post_context  # and other helpers if needed

# Required ACASL signature
ACASL_PLUGIN = True
ACASL_ID = "hello"
ACASL_DESCRIPTION = "Example plugin"

# Optional extended metadata (recommended for UI)
ACASL_NAME = "Hello"
ACASL_VERSION = "0.1.0"
ACASL_AUTHOR = "Samuel Amen Ague"
ACASL_CREATED = "2025-09-06"
ACASL_LICENSE = "GPL-3.0-only"
ACASL_COMPATIBILITY = ["PyCompiler ARK++ v3.2+", "Python 3.10+"]
ACASL_TAGS = ["post-compilation", "report"]

def acasl_run(ctx):
    sctx = wrap_post_context(ctx)  # convert host context to SDKContext
    # use sctx.* helpers (artifacts, file utils, subprocess, i18n, messages, ...)
    sctx.log_info("[hello] ACASL plugin started")
    for a in sctx.artifacts:
        sctx.log_info(f"[hello] artifact: {a}")
    sctx.log_info("[hello] finished")
```

Table of Contents
- What is ACASL?
- Execution flow and integration
- Where to place your plugins (package layout)
- Plugin templates (minimal to advanced)
- ACASL SDK facade and Context (available API)
- Configuration (acasl.json)
- System installs (pip global and OS package managers)
- UI: ACASL Loader (enable and order plugins)
- Cancellation and robustness
- Best practices (security, UX, logs)
- Troubleshooting
- Extended examples (rich collection)

---

## What is ACASL?
ACASL is the post‑compilation counterpart to BCASL. It runs automatically after builds finish and lets you handle distribution: signing, notarization, packaging, integrity checks, SBOM, hashing, smoke tests, publishing, etc.

## Execution flow and integration
- ACASL is triggered after all builds complete.
- The default artifact collector scans `<workspace>/dist` and `<workspace>/build` and passes the file list to plugins.
- Plugins are discovered under API/ at the project root. Only Python packages that declare ACASL_PLUGIN = True and expose acasl_run(ctx) are considered. The runtime further validates ACASL_ID/ACASL_DESCRIPTION; extended metadata are optional but recommended.
- ACASL runs asynchronously (non‑blocking UI). A soft timeout can be configured; each plugin run is measured (duration in ms).

## Where to place your plugins (package layout)
Create Python packages under API/ (not loose .py files):
```
API/
  ├── hash_report/
  │   └── __init__.py
  ├── compress_zip/
  │   └── __init__.py
  ├── signer_windows/
  │   └── __init__.py
  ├── codesign_macos/
  │   └── __init__.py
  ├── sbom_cyclonedx/
  │   └── __init__.py
  ├── publish_github/
  │   └── __init__.py
  └── …
```
Rules for each package (__init__.py):
- Must set ACASL_PLUGIN = True
- Must define ACASL_ID and ACASL_DESCRIPTION
- Must define acasl_run(ctx)
- Use imports from API_SDK.ACASL_SDK
- Optional: define extended metadata keys (NAME/VERSION/AUTHOR/CREATED/LICENSE/COMPATIBILITY/TAGS)

## Plugin templates
### Minimal plugin (facade‑based)
```python
# API/hello/__init__.py
from API_SDK.ACASL_SDK import wrap_post_context

ACASL_PLUGIN = True
ACASL_ID = "hello"
ACASL_DESCRIPTION = "Example plugin"

# Extended metadata (optional but recommended)
ACASL_NAME = "Hello"
ACASL_VERSION = "0.1.0"
ACASL_AUTHOR = "Samuel Amen Ague"
ACASL_CREATED = "2025-09-06"
ACASL_LICENSE = "GPL-3.0-only"
ACASL_COMPATIBILITY = ["PyCompiler ARK++ v3.2+", "Python 3.10+"]
ACASL_TAGS = ["post-compilation", "report"]

def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    sctx.log_info("[hello] ACASL plugin started")
    for a in sctx.artifacts:
        sctx.log_info(f"[hello] artifact: {a}")
    sctx.log_info("[hello] finished")
```

### Respecting cancellation and progress/messages
```python
# API/sample_long/__init__.py
import time
from API_SDK.ACASL_SDK import wrap_post_context, progress

ACASL_PLUGIN = True
ACASL_ID = "sample_long"
ACASL_DESCRIPTION = "Demonstrate progress and cancel"

# Optional metadata for UI friendliness
ACASL_NAME = "SampleLong"
ACASL_VERSION = "0.1.0"
ACASL_LICENSE = "GPL-3.0-only"
ACASL_TAGS = ["post-compilation", "report"]

def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    if not sctx.artifacts:
        sctx.log_warn("[sample_long] no artifacts")
        return
    with progress("Post‑build sample", "Processing artifacts…", maximum=len(sctx.artifacts), cancelable=True) as ph:
        for i, a in enumerate(sctx.artifacts):
            if ph.canceled:
                sctx.log_warn("[sample_long] canceled by user")
                return
            time.sleep(0.15)
            sctx.log_info(f"[sample_long] processed {i+1}/{len(sctx.artifacts)}: {a}")
            ph.step(1)
    # Prefer not to prompt in headless mode
    sctx.msg_info("Sample", "Processing complete.")
```

## ACASL SDK facade and Context (available API)
Always import from API_SDK.ACASL_SDK. Core items:
- wrap_post_context(post_ctx) -> SDKContext
  - Converts host ACASLContext (ctx) into SDKContext, loading workspace config and copying the artifacts list.
- SDKContext (sctx) provides:
  - Attributes: workspace_root, artifacts, engine_id (None in ACASL), config_view
  - Logging: sctx.log_info/warn/error
  - Messages: sctx.msg_info/warn/error/question (headless‑safe)
  - File utils: sctx.path/safe_path/is_within_workspace/require_files/open_text_safe
  - Scanning: sctx.iter_files, sctx.iter_project_files(use_cache=True)
  - Replacement: sctx.write_text_atomic, sctx.replace_in_file, sctx.batch_replace
  - Parallelism: sctx.parallel_map, Timing: sctx.time_step
  - Subprocess: sctx.run_command(cmd, timeout_s=60, cwd=None, env=None, shell=False)
- Additional helpers available from the facade when needed:
  - progress/create_progress, show_msgbox, ConfigView/load_workspace_config/ensure_settings_file
  - i18n: normalize_lang_pref, load_plugin_translations, get_translations
  - System installs: ensure_system_pip_install (pip global), ensure_system_packages (apt/dnf/pacman/zypper/winget/choco/brew)

Note: API_SDK version 3.2.3 or newer is required for ACASL facade features.

## Configuration (acasl.json)
The ACASL Loader UI writes configuration to `<workspace>/acasl.json`:
```json
{
  "plugins": { "hash_report": {"enabled": true, "priority": 0} },
  "plugin_order": ["hash_report"],
  "options": { "plugin_timeout_s": 0.0 }
}
```
- `enabled`: whether the plugin executes
- `priority`: order index (0 = first)
- `plugin_order`: explicit order (top → bottom)
- `options.plugin_timeout_s`: soft timeout per plugin (<= 0 means unlimited)

If your plugin needs options, read your own config file (e.g. `config/my_plugin.yaml`) from the workspace via sctx.safe_path. Prefer sctx.write_text_atomic for writes.

## System installs (pip global and OS package managers)
- Use these helpers to request user consent and install dependencies system‑wide.
- In non‑interactive mode the helpers return False and do not attempt installation.

Install Python tools globally (pip):
```python
from API_SDK.ACASL_SDK import ensure_system_pip_install, wrap_post_context

ACASL_PLUGIN = True
ACASL_ID = "ensure_boto3"
ACASL_DESCRIPTION = "Ensure boto3 is available globally before upload"

def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    ok = ensure_system_pip_install(
        sctx,
        ["boto3"],
        title="Install Python tool",
        body="Install 'boto3' system-wide now?",
        python_candidates=["/usr/bin/python3", "python3", "python"],
        timeout_s=600,
    )
    if not ok:
        sctx.log_warn("boto3 not installed; skipping S3 publish")
        return
    import boto3  # now expected to be present
    sctx.log_info("boto3 available")
```

Install native packages via OS manager (Linux/Windows/macOS):
```python
from API_SDK.ACASL_SDK import ensure_system_packages, wrap_post_context

ACASL_PLUGIN = True
ACASL_ID = "ensure_zip_tools"
ACASL_DESCRIPTION = "Ensure zip/p7zip tools are installed"

def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    ok = ensure_system_packages(
        sctx,
        ["zip", "p7zip-full"],
        title="Install native tools",
        body="Install zip and 7zip with your system package manager?",
    )
    if not ok:
        sctx.log_warn("zip/7zip missing; skipping packaging")
        return
    sctx.log_info("Native tools available")
```

## UI: ACASL Loader (enable and order plugins)
- Open via the sidebar button “🔌 ACASL API Loader”.
- Enable/disable plugins and reorder via drag & drop.
- Save: writes `acasl.json` in the workspace root.
- Discovery is strict: only packages with ACASL_PLUGIN = True are listed (extended metadata enrich tooltips/UI).

## Cancellation and robustness
- If the user clicks “Cancel” during ACASL:
  - The ACASL thread is stopped best‑effort.
- In your plugin:
  - Check for cancel points (e.g. progress handle’s .canceled) or provide periodic safe prompts.
  - Always set timeouts when using sctx.run_command.
  - Favor atomic writes (sctx.write_text_atomic) and idempotent operations.

## Best practices (security, UX, logs)
- Security: secrets only via environment or separate secure files; never commit secrets.
- UX: reduce modal prompts; prefer logs and one final summary dialog, and respect non‑interactive mode.
- Logs: always log the output file paths you create.
- Idempotency: running twice should not corrupt artifacts; write side‑artifacts to distinct files.
- Licensing: declare ACASL_LICENSE (e.g., GPL‑3.0‑only) consistently across your plugins.

## Troubleshooting
- “ACASL Loader unavailable”
  - Ensure `acasl/__init__.py` points to `acasl/acasl_loader.py`.
  - Ensure UI connects to `from acasl import open_acasl_loader_dialog`.
- Plugin not listed
  - Your plugin must be a Python package under API/<plugin_id>/ with an __init__.py.
  - __init__.py must define ACASL_PLUGIN = True and a callable acasl_run(ctx).
  - Required metadata missing: ensure ACASL_ID and ACASL_DESCRIPTION are defined (strings) — the loader/runtime enforce these.
- No artifacts
  - Verify builds produced files under `dist/` and/or `build/`.
- System installs not happening
  - The helpers require an interactive session for consent; in non‑interactive mode they return False.

---

## Extended examples (rich collection)
These examples favor clarity. Add proper error handling, path validations, and security for production use. Each example is a package __init__.py.

### 0) Zip bundle (compress main executable or app dir)
```python
# API/compress_zip/__init__.py
from pathlib import Path
from API_SDK.ACASL_SDK import wrap_post_context
import os, sys, stat, zipfile

ACASL_PLUGIN = True
ACASL_ID = "compress_zip"
ACASL_DESCRIPTION = "Create a ZIP archive from the built executable or app folder"


def _is_exec(p: Path) -> bool:
    try:
        m = p.stat().st_mode
        return p.is_file() and bool(m & stat.S_IXUSR or m & stat.S_IXGRP or m & stat.S_IXOTH)
    except Exception:
        return False


def _pick(artifacts: list[Path]) -> Path | None:
    arts = [p for p in artifacts if p.exists()]
    if not arts:
        return None
    if sys.platform == 'darwin':
        apps = [p for p in arts if p.is_dir() and p.suffix.lower() == '.app']
        if apps:
            return max(apps, key=lambda p: p.stat().st_mtime)
    exes = [p for p in arts if p.is_file() and p.suffix.lower() == '.exe']
    if exes:
        return max(exes, key=lambda p: p.stat().st_mtime)
    execs = [p for p in arts if _is_exec(p)]
    if execs:
        return max(execs, key=lambda p: p.stat().st_mtime)
    files = [p for p in arts if p.is_file() and p.stat().st_size > 0]
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def _next(path: Path) -> Path:
    if not path.exists():
        return path
    i = 1
    while True:
        p = path.with_name(f"{path.stem}_{i}{path.suffix}")
        if not p.exists():
            return p
        i += 1


def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    arts = [Path(a) for a in sctx.artifacts]
    if not arts:
        sctx.log_warn('[zip] no artifacts')
        return
    t = _pick(arts)
    if not t:
        sctx.log_warn('[zip] cannot select a target')
        return
    # If t is executable in a one-folder layout, zip the whole directory for better UX
    if t.is_file():
        try:
            entries = list(t.parent.iterdir())
            if len(entries) >= 5:
                t = t.parent
        except Exception:
            pass
    out_dir = t.parent
    name = (t.stem if t.is_file() else t.name) + '.zip'
    out = _next(out_dir / name)
    sctx.log_info(f"[zip] target: {t}")
    try:
        with zipfile.ZipFile(str(out), 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            if t.is_dir():
                for p in t.rglob('*'):
                    if p.is_file():
                        zf.write(str(p), arcname=str(p.relative_to(t)))
            else:
                zf.write(str(t), arcname=t.name)
        sctx.log_info(f"[zip] written: {out}")
    except Exception as e:
        sctx.log_error(f"[zip] failed: {e}")
```

### 1) Hash report (SHA‑256)
```python
# API/hash_report/__init__.py
from pathlib import Path
import hashlib, json
from API_SDK.ACASL_SDK import wrap_post_context

ACASL_PLUGIN = True
ACASL_ID = "hash_report"
ACASL_DESCRIPTION = "Compute SHA‑256 for artifacts"


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    if not sctx.artifacts:
        sctx.log_warn("[hash] no artifacts")
        return
    rows = []
    for a in sctx.artifacts:
        p = Path(a)
        if p.is_file():
            rows.append({"path": str(p), "sha256": _sha256(p)})
    out = Path(sctx.artifacts[0]).parent / "acasl_hashes.json"
    payload = json.dumps({"artifacts": rows}, indent=2)
    try:
        sctx.write_text_atomic(out, payload)
    except Exception:
        out.write_text(payload, encoding='utf-8')
    sctx.log_info(f"[hash] written: {out}")
```

### 2) Integrity check: ldd/otool (Linux/macOS)
```python
# API/integrity_check/__init__.py
import subprocess, sys
from pathlib import Path
from API_SDK.ACASL_SDK import wrap_post_context

ACASL_PLUGIN = True
ACASL_ID = "integrity_check"
ACASL_DESCRIPTION = "List linked libraries for binaries"


def _run(cmd, cwd=None, timeout=30):
    return subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)


def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    if not sctx.artifacts:
        sctx.log_warn("[integrity] no artifacts")
        return
    is_macos = sys.platform == 'darwin'
    for a in sctx.artifacts[:50]:  # limit for performance
        p = Path(a)
        if not p.is_file():
            continue
        try:
            r = _run(["otool", "-L", str(p)]) if is_macos else _run(["ldd", str(p)])
            if r.returncode == 0 and r.stdout:
                sctx.log_info(f"[integrity] {p.name}:\n{r.stdout[:2000]}")
        except Exception as e:
            sctx.log_warn(f"[integrity] {p.name}: {e}")
```

### 3) Smoke test: launch built app briefly
```python
# API/smoke_test/__init__.py
import subprocess, time
from pathlib import Path
from API_SDK.ACASL_SDK import wrap_post_context

ACASL_PLUGIN = True
ACASL_ID = "smoke_test"
ACASL_DESCRIPTION = "Launch built artifact briefly"


def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    arts = [Path(a) for a in sctx.artifacts]
    candidates = [p for p in arts if p.is_file() and p.stat().st_mode & 0o111]
    if not candidates:
        sctx.log_warn("[smoke] no executable candidates found")
        return
    target = max(candidates, key=lambda p: p.stat().st_mtime)
    sctx.log_info(f"[smoke] launching {target}")
    try:
        proc = subprocess.Popen([str(target)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        time.sleep(5)
        proc.terminate()
        proc.wait(timeout=5)
        sctx.log_info("[smoke] ok")
    except Exception as e:
        sctx.log_error(f"[smoke] failed: {e}")
```

### 4) Windows code signing (signtool) — stub
```python
# API/signer_windows/__init__.py
import os, subprocess
from pathlib import Path
from API_SDK.ACASL_SDK import wrap_post_context

ACASL_PLUGIN = True
ACASL_ID = "signer_windows"
ACASL_DESCRIPTION = "Sign Windows binaries with signtool"


def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    if os.name != 'nt':
        sctx.log_warn("[sign] Windows only")
        return
    cert = os.environ.get("WIN_CERT_PATH")
    pw = os.environ.get("WIN_CERT_PASS")
    if not cert or not pw:
        sctx.log_warn("[sign] WIN_CERT_PATH / WIN_CERT_PASS not set")
        return
    for a in sctx.artifacts:
        p = Path(a)
        if p.suffix.lower() in (".exe", ".dll"):
            try:
                cmd = [
                    "signtool", "sign", "/f", cert, "/p", pw,
                    "/tr", "http://timestamp.digicert.com", "/td", "sha256",
                    "/fd", "sha256", str(p)
                ]
                r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
                if r.returncode == 0:
                    sctx.log_info(f"[sign] signed: {p}")
                else:
                    sctx.log_warn(f"[sign] failed: {p}\n{r.stdout}")
            except Exception as e:
                sctx.log_error(f"[sign] error {p}: {e}")
```

### 5) macOS code signing + notarization — stub
```python
# API/codesign_macos/__init__.py
import sys, subprocess
from pathlib import Path
from API_SDK.ACASL_SDK import wrap_post_context

ACASL_PLUGIN = True
ACASL_ID = "codesign_macos"
ACASL_DESCRIPTION = "codesign and notarization stubs"


def _run(cmd, timeout=120):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)


def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    if sys.platform != 'darwin':
        sctx.log_warn("[codesign] macOS only")
        return
    identity = "Developer ID Application: Your Name (TEAMID)"
    for a in sctx.artifacts:
        p = Path(a)
        if p.suffix.lower() in (".app", ".dylib", ""):
            try:
                r = _run(["codesign", "--deep", "--force", "--options", "runtime", "--sign", identity, str(p)])
                sctx.log_info(f"[codesign] {p}: {r.returncode}\n{r.stdout[:800]}")
            except Exception as e:
                sctx.log_error(f"[codesign] error {p}: {e}")
    # Notarize example (requires prior credentials configuration)
    # _run(["xcrun", "notarytool", "submit", str(dmg_or_zip), "--keychain-profile", "AC_PROFILE", "--wait"]) 
```

### 6) SBOM (CycloneDX) — stub
```python
# API/sbom_cyclonedx/__init__.py
import subprocess
from pathlib import Path
from API_SDK.ACASL_SDK import wrap_post_context

ACASL_PLUGIN = True
ACASL_ID = "sbom_cyclonedx"
ACASL_DESCRIPTION = "Generate SBOM with cyclonedx-py"


def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    ws = sctx.workspace_root
    out = ws / "dist" / "sbom-cyclonedx.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(["cyclonedx-py", "-j", "-o", str(out)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if r.returncode == 0:
            sctx.log_info(f"[sbom] written: {out}")
        else:
            sctx.log_warn(f"[sbom] failed:\n{r.stdout}")
    except Exception as e:
        sctx.log_error(f"[sbom] error: {e}")
```

### 7) Packaging — stubs
```python
# API/packaging/__init__.py
import sys, subprocess
from pathlib import Path
from API_SDK.ACASL_SDK import wrap_post_context

ACASL_PLUGIN = True
ACASL_ID = "packaging"
ACASL_DESCRIPTION = "Build platform‑specific packages"


def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    ws = sctx.workspace_root
    if sys.platform == 'win32':
        iss = ws / "installer" / "setup.iss"
        if iss.exists():
            r = subprocess.run(["iscc", str(iss)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            sctx.log_info(f"[pkg] InnoSetup: {r.returncode}\n{r.stdout[:800]}")
    elif sys.platform == 'darwin':
        dmg_out = ws / "dist" / "MyApp.dmg"
        app_dir = ws / "dist" / "MyApp.app"
        if app_dir.exists():
            r = subprocess.run(["hdiutil", "create", "-volname", "MyApp", "-srcfolder", str(app_dir), str(dmg_out)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            sctx.log_info(f"[pkg] DMG: {r.returncode}\n{r.stdout[:800]}")
    else:
        appdir = ws / "dist" / "AppDir"
        if appdir.exists():
            r = subprocess.run(["appimagetool", str(appdir)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            sctx.log_info(f"[pkg] AppImage: {r.returncode}\n{r.stdout[:800]}")
```

### 8) Publish to GitHub Releases — stub
```python
# API/publish_github/__init__.py
import os, subprocess
from pathlib import Path
from API_SDK.ACASL_SDK import wrap_post_context

ACASL_PLUGIN = True
ACASL_ID = "publish_github"
ACASL_DESCRIPTION = "Upload artifacts to GitHub Releases"


def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    token = os.environ.get("GITHUB_TOKEN")
    repo  = os.environ.get("GITHUB_REPOSITORY")  # e.g. "owner/repo"
    tag   = os.environ.get("GITHUB_TAG", "v0.0.0")
    if not token or not repo:
        sctx.log_warn("[gh] set GITHUB_TOKEN/GITHUB_REPOSITORY")
        return
    from pathlib import Path as _P
    assets = [a for a in sctx.artifacts if _P(a).is_file() and _P(a).stat().st_size > 0][:10]
    if not assets:
        sctx.log_warn("[gh] no assets to upload")
        return
    for a in assets:
        cmd = ["gh", "release", "upload", tag, a, "--repo", repo, "--clobber"]
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if r.returncode == 0:
            sctx.log_info(f"[gh] uploaded: {a}")
        else:
            sctx.log_warn(f"[gh] fail: {a}\n{r.stdout}")
```

### 9) GPG/PGP sign a manifest — stub
```python
# API/sign_manifest/__init__.py
import json, subprocess
from pathlib import Path
from API_SDK.ACASL_SDK import wrap_post_context

ACASL_PLUGIN = True
ACASL_ID = "sign_manifest"
ACASL_DESCRIPTION = "Sign a JSON manifest with gpg"


def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    if not sctx.artifacts:
        return
    manifest = Path(sctx.artifacts[0]).parent / "manifest.json"
    payload = json.dumps({"artifacts": sctx.artifacts}, indent=2)
    try:
        sctx.write_text_atomic(manifest, payload)
    except Exception:
        manifest.write_text(payload, encoding="utf-8")
    asc = manifest.with_suffix(".json.asc")
    try:
        r = subprocess.run(["gpg", "--batch", "--yes", "--armor", "--detach-sign", str(manifest)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if r.returncode == 0 and asc.exists():
            sctx.log_info(f"[gpg] signed: {asc}")
        else:
            sctx.log_warn(f"[gpg] sign failed: {r.stdout}")
    except Exception as e:
        sctx.log_error(f"[gpg] error: {e}")
```

### 10) Publish to S3 (boto3) — with system install helper
```python
# API/publish_s3/__init__.py
import os
from pathlib import Path
from API_SDK.ACASL_SDK import wrap_post_context, ensure_system_pip_install

ACASL_PLUGIN = True
ACASL_ID = "publish_s3"
ACASL_DESCRIPTION = "Upload artifacts to S3"


def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        sctx.log_warn("[s3] set S3_BUCKET")
        return
    # Ensure boto3 system-wide with consent
    ok = ensure_system_pip_install(
        sctx,
        ["boto3"],
        title="Install Python tool",
        body="Install 'boto3' system-wide now?",
    )
    if not ok:
        sctx.log_warn("[s3] boto3 not available; aborting")
        return
    try:
        import boto3
    except Exception as e:
        sctx.log_error(f"[s3] boto3 import failed even after install: {e}")
        return
    s3 = boto3.client("s3")
    for a in sctx.artifacts[:20]:
        p = Path(a)
        if p.is_file():
            key = f"releases/{p.name}"
            try:
                s3.upload_file(str(p), bucket, key)
                sctx.log_info(f"[s3] uploaded: s3://{bucket}/{key}")
            except Exception as e:
                sctx.log_warn(f"[s3] failed {p}: {e}")
```

### 11) Artifact pruning/renaming
```python
# API/prune_artifacts/__init__.py
from pathlib import Path
from API_SDK.ACASL_SDK import wrap_post_context

ACASL_PLUGIN = True
ACASL_ID = "prune_artifacts"
ACASL_DESCRIPTION = "Delete temp files and rename main artifact"


def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    kept = []
    for a in sctx.artifacts:
        p = Path(a)
        if p.suffix.lower() in (".log", ".tmp") and p.exists():
            try:
                p.unlink()
                sctx.log_info(f"[prune] removed {p.name}")
            except Exception:
                pass
        else:
            kept.append(a)
    # Optional: rename main artifact with version suffix
    if kept:
        p = Path(kept[0])
        newp = p.with_name(p.stem + "_v1" + p.suffix)
        try:
            p.rename(newp)
            sctx.log_info(f"[prune] renamed {p.name} -> {newp.name}")
        except Exception:
            pass
```

### 12) Release notes (HTML) generator
```python
# API/release_notes/__init__.py
from datetime import datetime
from pathlib import Path
from API_SDK.ACASL_SDK import wrap_post_context

ACASL_PLUGIN = True
ACASL_ID = "release_notes"
ACASL_DESCRIPTION = "Generate HTML release notes"


def acasl_run(ctx):
    sctx = wrap_post_context(ctx)
    ws = sctx.workspace_root
    html = ws / "dist" / "release_notes.html"
    html.parent.mkdir(parents=True, exist_ok=True)
    items = "\n".join(f"<li>{Path(a).name}</li>" for a in sctx.artifacts)
    html.write_text(f"""
<!doctype html>
<meta charset="utf-8" />
<title>Release Notes</title>
<h1>Release {datetime.now():%Y-%m-%d %H:%M}</h1>
<ul>{items}</ul>
""".strip(), encoding="utf-8")
    sctx.log_info(f"[notes] written: {html}")
```

---

## Recap
- Put your plugin in `API/<plugin_id>/__init__.py` as a Python package (folder + __init__.py).
- Declare `ACASL_PLUGIN = True`, provide metadata (ACASL_ID, ACASL_DESCRIPTION, optional extended fields), and define `acasl_run(ctx)`.
- Always import from API_SDK.ACASL_SDK and wrap the context: `sctx = wrap_post_context(ctx)`.
- Use the “🔌 ACASL API Loader” to enable and order plugins; the config is saved to `acasl.json` (with `options.plugin_timeout_s`).
- ACASL runs automatically after builds; plugins operate on sctx.artifacts.
- Use ensure_system_pip_install and ensure_system_packages for system‑level dependencies with user consent.
- Check cancellation, use timeouts, and keep plugins idempotent. Integrate signing, packaging, SBOM, tests, and publishing as separate, composable steps.
