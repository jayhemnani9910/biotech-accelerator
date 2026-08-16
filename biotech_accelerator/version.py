"""Single source of the package version.

Read by biotech_accelerator/__init__.py, by the MCP server (clients display it
in their server list), and by hatchling at build time via [tool.hatch.version],
so the number lives in exactly one place.
"""

__version__ = "0.1.0"
