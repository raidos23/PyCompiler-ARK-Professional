# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Ague Samuel Amen
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

def _kill_process_tree(pid: int, *, timeout: float = 5.0, log=None) -> bool:
    def _log(msg: str):
        try:
            if log:
                log(msg)
        except Exception:
            pass

    import platform as _plat
    import subprocess as _sp
    import time

    try:
        import signal as _sig
    except Exception:
        _sig = None
    # First, try using psutil if available
    try:
        import psutil  # type: ignore

        try:
            proc = psutil.Process(int(pid))
        except Exception:
            return False
        try:
            children = proc.children(recursive=True)
        except Exception:
            children = []
        # 1) Polite terminate to children then parent
        for c in children:
            try:
                c.terminate()
            except Exception:
                pass
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            _ = psutil.wait_procs(children + [proc], timeout=max(0.1, timeout / 2))
            # collect alive after first wait
            alive = [p for p in [proc] + children if p.is_running()]
        except Exception:
            alive = [proc] + children
        # 2) Kill remaining
        for a in alive:
            try:
                a.kill()
            except Exception:
                pass
        try:
            psutil.wait_procs(alive, timeout=max(0.1, timeout / 2))
        except Exception:
            pass
        # Refresh liveness
        try:
            alive = [p for p in [proc] + children if p.is_running()]
        except Exception:
            alive = []
        # 3) OS-level fallback if still alive
        if alive:
            system = _plat.system()
            if system == "Windows":
                try:
                    _sp.run(
                        ["taskkill", "/PID", str(pid), "/T", "/F"],
                        stdout=_sp.DEVNULL,
                        stderr=_sp.DEVNULL,
                        timeout=10,
                    )
                except Exception:
                    pass
            else:
                # Try kill process group
                try:
                    import os as _os

                    try:
                        pgrp = _os.getpgid(pid)
                    except Exception:
                        pgrp = None
                    if pgrp and _sig is not None:
                        try:
                            _os.killpg(pgrp, _sig.SIGTERM)
                            time.sleep(0.2)
                        except Exception:
                            pass
                except Exception:
                    pass
                # pkill children by parent
                try:
                    _sp.run(
                        ["pkill", "-TERM", "-P", str(pid)],
                        stdout=_sp.DEVNULL,
                        stderr=_sp.DEVNULL,
                        timeout=5,
                    )
                except Exception:
                    pass
                time.sleep(0.2)
                try:
                    _sp.run(
                        ["pkill", "-KILL", "-P", str(pid)],
                        stdout=_sp.DEVNULL,
                        stderr=_sp.DEVNULL,
                        timeout=5,
                    )
                except Exception:
                    pass
                # Hard kill parent last
                if _sig is not None:
                    try:
                        _sp.run(
                            ["kill", "-TERM", str(pid)],
                            stdout=_sp.DEVNULL,
                            stderr=_sp.DEVNULL,
                            timeout=3,
                        )
                    except Exception:
                        pass
                    time.sleep(0.2)
                    try:
                        _sp.run(
                            ["kill", "-KILL", str(pid)],
                            stdout=_sp.DEVNULL,
                            stderr=_sp.DEVNULL,
                            timeout=3,
                        )
                    except Exception:
                        pass
        # Final check
        try:
            alive2 = [p for p in [proc] + children if p.is_running()]
        except Exception:
            alive2 = []
        _log(
            f"✅ Process tree terminated (pid={pid})"
            if not alive2
            else f"🛑 Process tree forced killed (pid={pid}, remaining={len(alive2)})"
        )
        return True
    except Exception:
        # psutil not available or failed badly: use OS-level fallbacks only
        system = _plat.system()
        try:
            if system == "Windows":
                _sp.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    stdout=_sp.DEVNULL,
                    stderr=_sp.DEVNULL,
                    timeout=10,
                )
                _log(f"🪓 taskkill issued for pid={pid}")
            else:
                try:
                    import os as _os

                    if _sig is not None:
                        try:
                            pgrp = _os.getpgid(pid)
                            _os.killpg(pgrp, _sig.SIGTERM)
                        except Exception:
                            pass
                    _sp.run(
                        ["pkill", "-TERM", "-P", str(pid)],
                        stdout=_sp.DEVNULL,
                        stderr=_sp.DEVNULL,
                        timeout=5,
                    )
                    time.sleep(0.2)
                    _sp.run(
                        ["pkill", "-KILL", "-P", str(pid)],
                        stdout=_sp.DEVNULL,
                        stderr=_sp.DEVNULL,
                        timeout=5,
                    )
                    if _sig is not None:
                        _sp.run(
                            ["kill", "-TERM", str(pid)],
                            stdout=_sp.DEVNULL,
                            stderr=_sp.DEVNULL,
                            timeout=3,
                        )
                        time.sleep(0.2)
                        _sp.run(
                            ["kill", "-KILL", str(pid)],
                            stdout=_sp.DEVNULL,
                            stderr=_sp.DEVNULL,
                            timeout=3,
                        )
                    _log(f"🪓 pkill/kill issued for pid={pid}")
                except Exception:
                    pass
        except Exception:
            pass
        return True


def _kill_all_descendants(timeout: float = 2.0, log=None) -> None:
    """Kill every descendant process of the current GUI process (best-effort)."""
    try:
        import os as _os

        import psutil  # type: ignore

        me = psutil.Process(_os.getpid())
        # Snapshot children to avoid races while killing
        kids = []
        try:
            kids = me.children(recursive=True)
        except Exception:
            kids = []
        # Use our robust killer on each child tree
        for ch in kids:
            try:
                _kill_process_tree(int(ch.pid), timeout=timeout, log=log)
            except Exception:
                pass
    except Exception:
        # Fallback: OS-level broad attempts (risk-limited as last resort)
        try:
            import os as _os
            import subprocess as _sp

            _sp.run(
                ["pkill", "-KILL", "-P", str(_os.getpid())],
                stdout=_sp.DEVNULL,
                stderr=_sp.DEVNULL,
                timeout=2,
            )
        except Exception:
            pass
