# 第14章：解释执行与运行时

## 14.1 Interpreter 框架

Calcite 的解释执行器位于 `interpreter/` 包（34 文件），提供了不依赖代码生成的查询执行方式。

### 14.1.1 核心模型：Source → Node → Sink

解释执行的数据流模型：

```
Source（数据源）
  → 从上游 Node 拉取一行数据
  → 提供 send()/receive() 方法

Node（算子节点）
  → 从 Source 读取输入
  → 处理数据
  → 写入 Sink

Sink（数据汇聚）
  → 向下游 Node 推送一行数据
  → 连接到下游的 Source
```

### 14.1.2 Interpreter 类

```java
// interpreter/Interpreter.java
public class Interpreter {
  private final RelNode rootRel;
  private final DataContext dataContext;

  public Interpreter(DataContext dataContext, RelNode rootRel) {
    this.dataContext = dataContext;
    this.rootRel = rootRel;
  }

  public Enumerable<Object> enumerable() {
    return () -> {
      // 1. 为每个 RelNode 创建对应的 Node
      // 2. 连接 Source 和 Sink
      // 3. 返回根节点的迭代器
      return new Iterator<Object>() {
        @Override public boolean hasNext() { ... }
        @Override public Object next() { ... }
      };
    };
  }
}
```

### 14.1.3 各算子的解释执行

| Node | 对应的 RelNode | 执行逻辑 |
|------|---------------|---------|
| `TableScanNode` | TableScan | 从表读取数据，逐行发送 |
| `FilterNode` | Filter | 对每行评估条件，过滤不满足的行 |
| `ProjectNode` | Project | 对每行计算投影表达式 |
| `JoinNode` | Join | 构建哈希表，探测匹配 |
| `AggregateNode` | Aggregate | 维护聚合缓冲区，累加计算 |
| `SortNode` | Sort | 收集所有行后排序 |
| `UnionNode` | Union | 顺序读取各输入 |
| `ValuesNode` | Values | 发送常量行 |
| `WindowNode` | Window | 维护窗口帧，计算窗口函数 |
| `MatchNode` | Match | 模式匹配状态机 |

### 14.1.4 FilterNode 示例

```java
// interpreter/FilterNode.java (简化)
class FilterNode extends AbstractSingleNode {
  private final RexNode condition;
  private final Scalar scalar;  // 编译后的条件表达式

  @Override public void run() {
    Row row;
    while ((row = source.receive()) != null) {
      if (scalar.execute(row) != null) {  // 评估条件
        sink.send(row);                   // 满足条件则发送
      }
    }
  }
}
```

### 14.1.5 Scalar — 表达式执行器

`Scalar` 接口表示一个可执行的表达式：

```java
// interpreter/Scalar.java
public interface Scalar {
  Object execute(Context context);
}
```

`JaninoRexCompiler` 将 RexNode 编译为 `Scalar` 实现——这是解释执行中唯一的编译步骤。

## 14.2 运行时函数库

`runtime/` 包（72 文件）提供了 SQL 函数的 Java 实现和运行时支持。

### 14.2.1 SqlFunctions — SQL 标准函数

`SqlFunctions` 是最大的运行时类，包含 SQL 标准函数的 Java 实现：

```java
// runtime/SqlFunctions.java
public class SqlFunctions {
  // 算术函数
  public static long plus(long a, long b) { return a + b; }
  public static double plus(double a, double b) { return a + b; }

  // 字符串函数
  public static String substring(String s, int start, int length) { ... }
  public static String upper(String s) { return s.toUpperCase(); }
  public static String lower(String s) { return s.toLowerCase(); }
  public static String trim(String s) { return s.trim(); }
  public static String concat(String s1, String s2) { return s1 + s2; }

  // 日期函数
  public static int extract(TimeUnit unit, Calendar cal) { ... }
  public static Calendar dateAdd(Calendar cal, int interval, TimeUnit unit) { ... }

  // 条件函数
  public static <T> T coalesce(T... values) { ... }
  public static <T> T nullif(T a, T b) { ... }

  // 集合函数
  public static boolean in(Object value, Object[] array) { ... }
}
```

### 14.2.2 Like — 模式匹配

```java
// runtime/Like.java
public class Like {
  // SQL LIKE 模式匹配
  public static boolean like(String s, String pattern) { ... }

  // SIMILAR TO 正则匹配
  public static boolean similar(String s, String pattern) { ... }
}
```

Like 将 SQL LIKE 模式（`%`、`_`）转换为 Java 正则表达式进行匹配。

### 14.2.3 其他运行时类

| 类 | 功能 |
|----|------|
| `Resources` | 本地化错误消息 |
| `CalciteException` | Calcite 异常基类 |
| `CalciteContextException` | 携带源码位置的异常 |
| `Hook` | 运行时钩子（调试用） |
| `Enumerables` | Enumerable 工具方法 |
| `ConsList` | 不可变列表 |
| `FlatLists` | 小型不可变列表 |
| `PairList` | 对偶列表 |

### 14.2.4 空间函数

Calcite 1.42 包含空间类型函数（`SpatialTypeFunctions`、`CompressionFunctions`）：

```java
// runtime/SpatialTypeFunctions.java
// ST_Point, ST_LineFromText, ST_Contains, ST_Within 等
```

### 14.2.5 JSON/XML 函数

```java
// runtime/JsonFunctions.java — JSON 路径查询、构造
// runtime/XmlFunctions.java — XML 解析、生成
```

## 14.3 解释执行 vs 编译执行

| 维度 | 解释执行（Interpreter） | 编译执行（Enumerable） |
|------|----------------------|----------------------|
| 启动时间 | 快（无需编译） | 慢（Janino 编译） |
| 执行速度 | 慢（逐行解释） | 快（编译为字节码） |
| 内存占用 | 低 | 较高（类加载） |
| 调试友好 | 高 | 低（动态生成的代码） |
| 适用场景 | 原型、小查询、调试 | 生产查询 |

Calcite 默认使用编译执行（EnumerableConvention），解释执行只在特定场景使用（如 `InterpretableConvention` 或调试模式）。

---

## 本章小结

Calcite 的解释执行器使用 Source → Node → Sink 的数据流模型，每个算子节点从 Source 读取数据、处理后写入 Sink。运行时函数库（SqlFunctions、Like 等）提供了 SQL 函数的 Java 实现。JaninoRexCompiler 将 RexNode 编译为 Scalar 用于表达式求值。解释执行适合调试和小查询，编译执行适合生产。下一章将进入 Schema 体系。
