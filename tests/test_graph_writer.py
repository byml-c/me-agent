from __future__ import annotations

from backend.app.services import graph_writer


def test_infer_title_omits_parent_prefix_for_nested_create_request():
    assert graph_writer.infer_title("在 Tactile 下面新建一个文献整理节点") == "文献整理"
    assert graph_writer.infer_title("给 Work 里创建一个周会纪要 node") == "周会纪要"
