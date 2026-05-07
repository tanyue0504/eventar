"""data.loader 模块测试。"""
from __future__ import annotations

import pandas as pd

from eventar.data.loader import DataLoader


def test_data_loader_generator_subclass_iterable():
    """只实现生成器式 __iter__ 的子类也应可正常迭代。"""

    class SingleChunk(DataLoader):
        def __iter__(self):
            yield pd.DataFrame({"x": [1, 2, 3]})

    loader = SingleChunk()
    chunks = list(loader)
    assert len(chunks) == 1
    assert list(chunks[0]["x"]) == [1, 2, 3]
