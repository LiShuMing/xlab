# 第16章：适配器架构 — Calcite 的扩展哲学

## 16.1 适配器的本质

适配器是 Calcite 与外部数据源之间的桥梁。它的核心问题是：**数据源有多"聪明"？** 

- 最笨的数据源只能全表扫描（CSV 文件）
- 中等的数据源可以接受谓词和投影（JDBC 数据库）
- 最聪明的数据源可以执行完整的查询（Elasticsearch、Druid）

Calcite 通过三种接口梯度适配不同智能程度的数据源。

## 16.2 能力梯度

### 16.2.1 ScannableTable — 全表扫描

```java
// CSV 适配器示例
public class CsvScannableTable extends CsvTable implements ScannableTable {
  @Override public Enumerable<Object[]> scan(DataSet root) {
    return new CsvEnumerator(file, fields);  // 逐行读取 CSV
  }
}
```

Calcite 生成的计划：
```
EnumerableCalc(program: Filter + Project)
  EnumerableTableScan(table=[csv.EMP])
```

所有过滤和投影在 Calcite 侧执行。

### 16.2.2 FilterableTable — 谓词下推

```java
// CSV 适配器的 Filterable 实现
public class CsvFilterableTable extends CsvTable implements FilterableTable {
  @Override public Enumerable<Object[]> scan(DataSet root, List<RexNode> filters) {
    // 将 filters 转换为 CSV 文件读取时的过滤条件
    // 无法处理的条件留在 filters 列表中，由 Calcite 额外添加 Filter
    return new CsvEnumerator(file, fields, filters);
  }
}
```

Calcite 生成的计划：
```
EnumerableCalc(program: Project only)     ← Calcite 只做投影
  EnumerableTableScan(table=[csv.EMP], filters=[salary > 1000])  ← 过滤下推
```

### 16.2.3 TranslatableTable — 自定义 RelNode

```java
// Elasticsearch 适配器示例
public class ElasticsearchTable extends AbstractTable implements TranslatableTable {
  @Override public RelNode toRel(RelOptTable.ToRelContext context, RelOptTable relOptTable) {
    return new ElasticsearchTableScan(context.getCluster(), relOptTable, this);
  }
}
```

自定义 `ElasticsearchTableScan` 可以将过滤、投影、聚合全部翻译为 Elasticsearch 的查询 DSL。

## 16.3 CSV 适配器 — 最简适配器的完整实现

CSV 适配器位于 `example/csv/`，是 Calcite 官方的入门示例，展示了适配器的完整实现。

### 16.3.1 组件

| 文件 | 职责 |
|------|------|
| `CsvSchemaFactory` | 创建 Schema（从 model JSON 读取配置） |
| `CsvSchema` | 扫描目录，发现 CSV 文件对应的表 |
| `CsvTable` | 基础表定义（行类型从文件头推导） |
| `CsvScannableTable` | 全表扫描实现 |
| `CsvFilterableTable` | 谓词下推实现 |
| `CsvTranslatableTable` | 自定义 RelNode 实现 |
| `CsvTableScan` | 自定义 TableScan 算子 |
| `CsvProjectTableScanRule` | 将 Project+Scan 融合为 CsvTableScan |
| `CsvRules` | 规则集合 |

### 16.3.2 Schema 工厂

```java
// CsvSchemaFactory.java
public class CsvSchemaFactory implements SchemaFactory {
  @Override public Schema create(SchemaPlus parentSchema, String name, Map<String, Object> operand) {
    String directory = (String) operand.get("directory");
    File dir = new File(directory);
    return new CsvSchema(dir);  // 扫描目录下的 CSV 文件
  }
}
```

通过 model JSON 配置：

```json
{
  "version": "1.0",
  "defaultSchema": "SALES",
  "schemas": [{
    "name": "SALES",
    "type": "custom",
    "factory": "org.apache.calcite.adapter.csv.CsvSchemaFactory",
    "operand": { "directory": "/path/to/csv/files" }
  }]
}
```

### 16.3.3 自定义优化规则

`CsvProjectTableScanRule` 将 Project + CsvTableScan 融合为携带投影信息的 CsvTableScan：

```java
// CsvProjectTableScanRule.java
public class CsvProjectTableScanRule extends RelRule<CsvProjectTableScanRule.Config> {
  @Override public void onMatch(RelOptRuleCall call) {
    LogicalProject project = call.rel(0);
    CsvTableScan scan = call.rel(1);
    // 将 project 的表达式下推到 scan 中
    int[] fields = ProjectUtil.getFields(project, scan);
    call.transformTo(new CsvTableScan(scan.getCluster(), scan.getTable(),
        scan.csvTable, fields));  // fields 指定只需要读取哪些列
  }
}
```

## 16.4 JDBC 适配器 — 跨数据源联邦查询

JDBC 适配器将外部 JDBC 数据源包装为 Calcite 的 Schema。

```json
{
  "schemas": [{
    "name": "HR",
    "type": "custom",
    "factory": "org.apache.calcite.adapter.jdbc.JdbcSchema$Factory",
    "operand": {
      "jdbcUrl": "jdbc:mysql://localhost:3306/hr",
      "jdbcDriver": "com.mysql.jdbc.Driver",
      "jdbcUser": "root",
      "jdbcPassword": ""
    }
  }]
}
```

JDBC 适配器自动从数据库元数据读取表结构，将查询下推为 SQL 语句。

### 联邦查询示例

```sql
-- 跨 MySQL 和本地 CSV 的联邦查询
SELECT e.name, d.dept_name
FROM mysql_hr.emp e, csv_dept d
WHERE e.dept_id = d.id
```

Calcite 生成的计划：
```
EnumerableHashJoin(condition=[$7 = $9])
  JdbcToEnumerableConverter
    JdbcProject(name=[$1], dept_id=[$7])
      JdbcTableScan(table=[mysql_hr.emp])
  EnumerableCalc(project=[dept_name=[$1], id=[$0]])
    EnumerableTableScan(table=[csv_dept])
```

MySQL 侧的过滤和投影被下推为 JDBC 查询，CSV 侧在 Calcite 内执行。

## 16.5 Elasticsearch 适配器

ES 适配器是更复杂的适配器示例，支持谓词下推、聚合下推和排序下推：

```
SQL → Calcite 优化 → ElasticsearchTableScan
                          ↓
                    翻译为 Elasticsearch DSL
                          ↓
                    {"query": {"bool": {"must": [...]}}}
```

### 适配器对比

| 适配器 | Scan | Filter | Project | Aggregate | Sort |
|--------|------|--------|---------|-----------|------|
| CSV | ✓ | ✓ | ✓ | ✗ | ✗ |
| JDBC | ✓ | ✓ | ✓ | ✓ | ✓ |
| Elasticsearch | ✓ | ✓ | ✓ | ✓ | ✓ |
| MongoDB | ✓ | ✓ | ✓ | ✓ | ✗ |
| Kafka | ✓ | ✗ | ✗ | ✗ | ✗ |
| Redis | ✓ | ✗ | ✗ | ✗ | ✗ |
| Arrow | ✓ | ✓ | ✓ | ✗ | ✗ |

## 16.6 自定义适配器的完整开发流程

### 步骤 1：实现 Table

```java
public class MyTable extends ScannableTable {
  private final RelDataType rowType;
  @Override public RelDataType getRowType(RelDataTypeFactory typeFactory) {
    return rowType;
  }
  @Override public Enumerable<Object[]> scan(DataSet root) {
    return Linq4j.asEnumerable(readData());
  }
}
```

### 步骤 2：实现 Schema

```java
public class MySchema extends AbstractSchema {
  @Override protected Map<String, Table> getTableMap() {
    Map<String, Table> tables = new HashMap<>();
    tables.put("MY_TABLE", new MyTable(...));
    return tables;
  }
}
```

### 步骤 3：实现 SchemaFactory

```java
public class MySchemaFactory implements SchemaFactory {
  @Override public Schema create(SchemaPlus parentSchema, String name, Map<String, Object> operand) {
    return new MySchema(operand);
  }
}
```

### 步骤 4：注册到 model JSON

```json
{
  "schemas": [{
    "name": "MY",
    "type": "custom",
    "factory": "com.example.MySchemaFactory",
    "operand": { "connectionString": "..." }
  }]
}
```

### 步骤 5（可选）：实现 TranslatableTable + 自定义规则

当需要更智能的下推时，实现 TranslatableTable 和对应的 ConverterRule。

---

## 本章小结

适配器架构通过三种能力梯度（Scannable/Filterable/Translatable）适配不同智能程度的数据源。CSV 适配器是最简的完整示例。JDBC 适配器支持联邦查询。Elasticsearch 适配器展示了完整的下推能力。自定义适配器只需实现 Table、Schema、SchemaFactory 三步即可。下一章将深入 SQL 方言与双向转换。
