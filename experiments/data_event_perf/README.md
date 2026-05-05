# 数据-事件性能方案验证

本实验用于验证低频事件驱动场景中，市场数据到事件对象的转换与访问成本，重点覆盖以下问题：

1. 是否存在比逐行创建事件实例更快的批量化方案。
2. `zip + 列数组`、`df.values`、`df.iterrows()`、`df.itertuples()` 等逐行迭代方案的实际性能差异。
3. 事件结构设计上，扁平事件（所有字段直接挂在事件对象上）与“头部 + 载荷”事件（通过属性访问载荷字段）谁更快。

## 依赖

建议使用开发依赖安装：

```bash
python -m pip install -e ".[dev]"
```

## 数据集

默认读取：

```text
data/test/market_df_10000000.parquet
```

字段：

- `timestamp`
- `code`
- `name`
- `open`
- `high`
- `low`
- `close`
- `vol`
- `amount`

## 运行方式

默认跑全部基准：

```bash
python experiments/data_event_perf/benchmark.py --rows 200000
```

只跑某一组：

```bash
python experiments/data_event_perf/benchmark.py --group iteration --rows 200000
python experiments/data_event_perf/benchmark.py --group construction --rows 200000
python experiments/data_event_perf/benchmark.py --group event-shape --rows 200000
```

如果要贴近最终验证规模，可以增大 `--rows`，例如：

```bash
python experiments/data_event_perf/benchmark.py --rows 1000000
```

## 指标说明

- 使用 `pyperf` 做基准采样，避免简单 `time.time()` 带来的噪声。
- 每个基准都会在循环内真实访问事件属性，而不是只做对象创建。
- 基准返回校验值，防止 Python 优化掉访问路径。

## 输出解读建议

- `iteration/*`：比较不同逐行遍历方案的吞吐。
- `construction/*`：比较事件创建方式，包括逐个创建与可复用列视图。
- `event-shape/*`：比较扁平事件和头部 + 载荷事件在真实属性访问下的差异。

通常需要同时看两类成本：

- 单纯遍历数据的成本。
- 遍历 + 事件包装 + 属性访问的综合成本。