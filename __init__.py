"""ComfyUI H3 ClipStream. V3 migration by RAFOLIE, 2026-09-28.

Based on AraneaQwQ/ComfyUI-H3-ClipStream, incorporating
NikoDemon80/ComfyUI-H3-Motion-Context (GPLv3) and
knoic/ComfyUI-MiniMaxH3-PrefixStream (MIT). See LICENSE and ATTRIBUTION.md.
"""
import logging
import os

from comfy_api.latest import ComfyExtension
from .clipbin import NODE_LIST as CLIP_NODES
from .clipbin.clip_bin_api import register_clip_bin_routes
from .motion_context import NODE_LIST as CONTEXT_NODES
from .motion_context.nodes import register_chain_routes
from .fork_guard import find_other_copy

logger = logging.getLogger(__name__)

_OTHER_COPY = find_other_copy(
    os.path.dirname(os.path.abspath(__file__)),
    os.path.join("clipbin", "long_nodes.py"),
    "node_id='MiniMaxClipBinLongBuilder'",
)

if _OTHER_COPY:
    logger.warning(
        "[H3 ClipStream 熙云版] 检测到另一份 ComfyUI-H3-ClipStream：%s。"
        "为避免同名节点、API 路由和前端互相覆盖，熙云版已跳过加载。"
        "要使用熙云版，请禁用或改名另一份（例如改成 ComfyUI-H3-ClipStream.disabled）；"
        "确实需要强制同时加载时，设置环境变量 H3_XYIYUN_ALLOW_DUPLICATE=1（不推荐）。",
        _OTHER_COPY,
    )

# When another copy exists, serving this fork's web files would let its panels
# attach to the other copy's identically named nodes. Keep the fork inert.
WEB_DIRECTORY = None if _OTHER_COPY else "./web"


class H3ClipStreamExtension(ComfyExtension):
    async def get_node_list(self):
        if _OTHER_COPY:
            return []
        return [*CONTEXT_NODES, *CLIP_NODES]


async def comfy_entrypoint():
    if not _OTHER_COPY:
        register_clip_bin_routes()
        register_chain_routes()
    return H3ClipStreamExtension()
