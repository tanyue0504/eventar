# ADR-1：事件基类层次与引擎定位

## 状态

**已采纳**

---

## 背景

### 框架定位

本框架面向**中低频回测**场景，不需要模拟纳秒级订单传输延迟，也不需要多引擎并发协调。
最重要的是保证**数据流推送的正确性**和**单次迭代的吞吐效率**。
因此引擎设计从最简单的单引擎推送出发，不引入多引擎复杂度。

### 事件不可变性的选择

考虑两种防止事件数据被下游组件意外篡改的方案：

| 方案 | 实现方式 | 性能 | 安全性 |
|------|---------|------|--------|
| **frozen dataclass** | Python 运行时直接拒绝赋值 | 无额外开销 | 高 |
| 引擎侧哈希校验 | 推送前后对比 hash | 每次推送增加计算 | 低（只能事后发现） |

结论：选择 `frozen=True` 的 dataclass，在最低运行时开销下实现不可变语义。

### 时间戳归属问题

最初的想法是"引擎统一为所有事件打上时间戳头部"，但这个设计在 frozen 约束下不成立——
引擎已无法在推送时修改事件字段。

进一步分析发现，时间戳对于不同类型的事件有不同意义：

- **数据类事件**（如 K 线、Tick）：时间戳是数据本身的一部分，**必须有且不可变**。
- **逻辑类事件**（如信号、订单指令）：时间戳不是核心语义，**不必强制携带**。

因此"所有事件都应有时间戳"这一约束被放弃，取而代之的是分类抽象。

---

## 决定

### 三层事件类层次

```
Event（根基类，可直接实例化）
├── DataEvent（数据类事件基类，含 timestamp）
│   └── 具体数据事件，例如 BarEvent、TickEvent
└── LogicEvent（逻辑类事件基类）
    └── 具体逻辑事件，例如 SignalEvent、OrderEvent
```

所有具体事件类均遵循以下约束：

- `@dataclass(frozen=True, slots=True)`
- 禁止在 `__post_init__` 或其他位置绕过 frozen 进行写操作
- 字段使用明确的类型标注，不允许 `Any`

### 为什么不用 ABC

最初版本将 `Event` 定义为 `ABC`，并添加了抽象方法 `event_type() -> str` 来阻止基类被直接实例化。
这个设计被放弃，原因有三：

1. **基类本身就应该可以实例化**。`Event()`、`DataEvent(timestamp=...)` 都是合法的轻量事件，强制要求子类才能实例化没有实际收益。
2. **`event_type()` 字符串没有必要**。路由分发直接使用类对象作为字典键更安全、更快：

   ```python
   handlers: dict[type[Event], Callable] = {
       BarEvent: on_bar,
       SignalEvent: on_signal,
   }
   handler = handlers[type(event)]
   ```

   字符串键存在拼写错误风险，且需要额外的命名约定。

3. **ABC 不能强制子类也是 `frozen+slots` dataclass**。既然 ABC 解决不了真正想解决的问题，就没有引入它的理由。

### 实例化时检查 frozen + slots 约束

`Event.__new__` 在分配内存前调用 `_assert_frozen_slots_dataclass(cls)`，检查三项：

| 检查项 | 检查方式 |
|--------|---------|
| 是否为 dataclass | `dataclasses.is_dataclass(cls)` |
| `frozen=True` | `cls.__dataclass_params__.frozen` |
| `slots=True` | `"__slots__" in cls.__dict__` |

违反任意一项，实例化立即抛出 `TypeError`。

**为什么不在 `__init_subclass__` 中检查？**
`__init_subclass__` 在类体执行完毕后、`@dataclass` 装饰器运行之前触发，
此时 `cls` 还不是 dataclass，无法做任何有意义的检查。`__new__` 是唯一正确的时机。

**`__new__` 中为什么用 `object.__new__(cls)` 而非 `super().__new__(cls)`？**
`slots=True` 时 `@dataclass` 会构造一个全新的类对象，导致 `__new__` 方法体内的
`__class__` 隐式单元格仍指向原始类，`super()` 校验会失败。直接调用 `object.__new__(cls)`
可规避这一 CPython 实现细节。

**`frozen=False` 是否需要在 `__new__` 中检查？**
不需要。Python 在处理 `@dataclass(frozen=False)` 继承 `frozen=True` 父类时，
会在类定义阶段（`@dataclass` 装饰器执行时）直接抛出 `TypeError`，早于任何实例化行为。

### 为什么用 slots

`slots=True` 使实例不使用 `__dict__`，改用固定偏移量访问字段，有两个好处：

1. **内存**：批量构造大量事件时（如回测的千万行数据），内存占用降低约 40%。
2. **属性访问速度**：比 `__dict__` 查找更快，适合在紧密循环中反复访问字段。

### 事件引擎路由模型：MRO 继承路由 + 三阶段派发

#### 背景与问题

最初的引擎采用**精确类型匹配**路由：只有注册类型与 `type(event)` 完全相同的监听器才会被触发。
这在纯数据事件场景下工作良好，但当业务对象存在继承层次时（例如 `LimitOrder` 继承自 `Order`），
若将监听注册在 `Order`，它**无法**接收任何子类实例，导致以下问题：

1. 组件必须提前知晓所有子类才能注册，破坏了开闭原则。
2. 要"全局监听"所有事件，只能引入专用全局监听接口（`register_global_pre / post`），概念冗余。
3. 职责链等组件不得不用 `isinstance` 手写分发逻辑，与引擎路由重复。

#### 放弃全局监听接口

旧接口提供了 `register_global_pre` 和 `register_global_post` 作为"覆盖所有事件"的手段。
引入 MRO 路由后，监听 `Event` 根类天然等价于"全局监听"，不再需要专用接口。
删除这两个方法可简化 API 表面，无行为损失。

#### 采用：MRO 继承路由 + 路由缓存

派发时，引擎遍历 `type(event).__mro__`（Python 标准方法解析顺序），
将所有注册在 MRO 链上任意类型的监听器合并，按 MRO 顺序（子类在前）排列后依次触发：

```
type(event).__mro__ = [SpecialPingEvent, PingEvent, Event, object]
触发顺序：SpecialPingEvent 的监听器 → PingEvent 的监听器 → Event 的监听器
```

**路由缓存**：每个 Phase 独立维护一个 `{ concrete_event_type: [resolved_listeners] }` 字典，
派发时懒惰填充，register / unregister 时按 Phase 全量清空（不按具体类型清空，实现简单）。
缓存命中时完全跳过 MRO 遍历，均摊派发开销极低。

#### 三阶段派发（Phase）

同一事件在单次派发中按 `PRE → MAIN → POST` 三个阶段触发，每个监听器在注册时指定阶段（默认 `MAIN`）：

| Phase | 典型用途 |
|-------|---------|
| PRE   | 日志、时序校验、审计 |
| MAIN  | 策略主逻辑、组件更新（默认） |
| POST  | 订单簿维护、下游通知、清理 |

同阶段内按注册顺序触发，不可调整优先级；跨阶段顺序固定，不可配置。
Phase 取代了旧版的 `global_pre / typed / global_post` 三层概念，语义更清晰，API 更统一：

```python
# 全局 PRE（替代 register_global_pre）
engine.register(Event, my_logger, Phase.PRE)

# 具体类型 MAIN（默认）
engine.register(Order, on_order)

# 子类自动继承父类监听器：无需额外注册
engine.register(Order, on_order)
engine.push(LimitOrder(...))  # on_order 会被触发
```

#### 事件回声（event echo）

如果某监听器在处理事件 A 时又 `push` 了事件 B，并且 B 仍然会路由到该监听器，
那么该监听器会再次收到并处理 B。这种"自回流"行为记为 **事件回声**。

当前版本不在引擎层自动阻断该行为（保持机制简单、可预测），但架构上将其视为
**不合格信号**：通常意味着事件类型建模过于宽泛，监听职责边界不清。

设计建议：

- 优先把语义拆分为更细粒度的事件类型，而不是复用一个"万能事件"
- 让监听器只订阅其真正关心的具体事件类型
- 通过类型隔离降低自回流概率，避免隐式反馈环

---

## 后果

### 好处

- **安全**：下游组件误写事件字段会立即抛出 `FrozenInstanceError`，避免数据源被悄悄污染。
- **性能**：`slots` 减少内存分配开销，`frozen` 无运行时额外代价，事件构造和访问均处于 Python 可达的最优路径。
- **语义清晰**：数据事件和逻辑事件的职责边界明确，新增具体事件类型时只需继承对应基类。
- **约束可验证**：忘记写 `@dataclass(frozen=True, slots=True)` 的子类，在第一次实例化时即报错，不会静默通过。

### 约束

- `frozen=True` 意味着字段必须在构造时一次性提供，不支持延迟赋值。
- 如果未来需要"可以附加状态"的事件（如带处理标记），需要通过包装对象而非修改事件本身来实现。
- `__new__` 检查是运行时行为，无法在静态分析阶段（mypy / pyright）发现违规子类。