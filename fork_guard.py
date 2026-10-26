"""Detect a second copy of this plugin in the same custom_nodes folder.

ComfyUI registers nodes by their node_id, so two copies of this plugin cannot
both be active: the last one loaded overwrites the other's nodes, API routes
and frontend extensions. This guard lets the 熙云 fork step aside when the
original plugin is installed beside it.
"""

from __future__ import annotations

import os


def find_other_copy(plugin_dir: str, marker_rel: str, marker_text: str,
                    allow_env: str = "H3_XYIYUN_ALLOW_DUPLICATE") -> str | None:
    """Return the path of another copy of this plugin, or None.

    ``marker_rel`` is a file inside the other copy and ``marker_text`` is a
    string only that plugin contains. The check is by content, not folder
    name, so renamed installs are still detected. Folder names ending in
    ``.disabled`` are ignored, because ComfyUI ignores them too.

    Set ``H3_XYIYUN_ALLOW_DUPLICATE=1`` to force both copies to load. That is
    only for testing: the same node ids would overwrite each other.
    """
    if os.environ.get(allow_env) == "1":
        return None

    self_dir = os.path.abspath(plugin_dir)
    custom_nodes = os.path.dirname(self_dir)
    try:
        entries = list(os.scandir(custom_nodes))
    except OSError:
        return None

    for entry in entries:
        if not entry.is_dir():
            continue
        if entry.name == "__pycache__" or entry.name.startswith("."):
            continue
        if entry.name.endswith(".disabled"):
            continue
        other_dir = os.path.abspath(entry.path)
        if other_dir == self_dir:
            continue
        marker = os.path.join(other_dir, marker_rel)
        if not os.path.isfile(marker):
            continue
        try:
            with open(marker, "r", encoding="utf-8", errors="ignore") as stream:
                head = stream.read(200_000)
        except OSError:
            continue
        if marker_text in head:
            return other_dir
    return None
