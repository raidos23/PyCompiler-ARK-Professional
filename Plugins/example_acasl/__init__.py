# SPDX-License-Identifier: GPL-3.0-only
"""
Example ACASL Plugin - Post-Compilation Actions

This plugin demonstrates the ACASL plugin architecture with:
- Metadata with tags for classification
- Dependencies on other plugins
- Priority-based execution ordering
- Unified i18n system
"""
from __future__ import annotations

from Plugins_SDK.ACASL_SDK import (
    Ac_PluginBase,
    PluginMeta,
    PostCompileContext,
    apply_plugin_i18n,
    wrap_post_context,
)

# Plugin metadata with tags for classification
META = PluginMeta(
    id="example_acasl",
    name="Example ACASL Plugin",
    version="1.0.0",
    description="Example post-compilation plugin demonstrating ACASL architecture",
    author="PyCompiler Team",
    tags=("example", "demo", "post-compile"),
)


class ExampleAcaslPlugin(Ac_PluginBase):
    """Example ACASL plugin showing post-compilation actions."""

    def on_post_compile(self, ctx: PostCompileContext) -> None:
        """Execute post-compilation actions.

        This hook is called after compilation completes.
        """
        try:
            sctx = wrap_post_context(ctx)
        except Exception as exc:
            print(f"[ERROR][example_acasl] {exc}")
            return

        # Load plugin translations (apply_plugin_i18n returns a mapping-like object)
        tr = apply_plugin_i18n(self, __file__, getattr(sctx, "_tr", {}))

        sctx.log_info(tr.get("starting_analysis", "🔍 Example ACASL Plugin: Starting post-compilation analysis"))

        # Access compiled artifacts
        artifacts = list(ctx.iter_artifacts())
        sctx.log_info(tr.get("artifacts_found", "📦 Found {count} artifact(s)").format(count=len(artifacts)))
        for art in artifacts:
            try:
                sctx.log_info(f"  - {art.name} ({art.stat().st_size} bytes)")
            except Exception:
                sctx.log_info(f"  - {art}")

        # Access project files
        py_files = list(
            ctx.iter_files(["**/*.py"], exclude=["venv/**", "**/__pycache__/**"])
        )
        sctx.log_info(tr.get("python_files_found", "📄 Found {count} Python file(s)").format(count=len(py_files)))

        sctx.log_info(tr.get("analysis_complete", "✅ Example ACASL Plugin: Post-compilation analysis complete"))


# Create plugin instance
PLUGIN = ExampleAcaslPlugin(
    META,
    requires=[],  # No dependencies
    priority=100,  # Standard priority
)


# ACASL registration function (required)
def acasl_register(manager):
    """Register this plugin with the ACASL manager.

    This function is called by the ACASL loader to register the plugin.
    """
    manager.add_plugin(PLUGIN)
