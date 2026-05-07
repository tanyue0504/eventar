"""DataEventSource：将 DataLoader 的 DataFrame 分块转换为 DataEvent 流。

设计要点：
- DataEventSource 是一个 Iterator[DataEvent]，按行逐条生成事件实例。
- 依赖三个构造参数：
    loader      DataLoader 实例，提供 DataFrame 分块。
    columns     列名列表，指定从分块中提取哪些列；列顺序须与 event_type
                构造函数的参数顺序一致（或使用与字段同名的关键字参数）。
    event_type  DataEvent 或其子类的类型对象，用于逐行构造事件。
- transform(chunk) 是可覆盖的钩子方法，在列提取之后、事件构造之前执行，
    默认行为是原样返回分块，子类可在此做单位换算、列重命名、过滤或新增列。
- 支持可重复迭代：每次调用 __iter__ 均会重置内部状态并从头读取 loader。
"""
from __future__ import annotations

from eventar.data import DataEvent

from abc import ABC, abstractmethod
from typing import Generator

class DataEventSource(ABC):
    @abstractmethod
    def __iter__(self) -> Generator[DataEvent, None, None]:
        pass