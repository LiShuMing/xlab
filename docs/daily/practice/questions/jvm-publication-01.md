# JVM-01：后台加载的配置是否安全发布

预计15–25分钟。难度：基础到进阶。能力标识：`jvm.safe-publication`。
这是题目，尚无作答记录；参考解在作答或明确索要后另存。

数据库服务在启动线程中加载一个配置对象，查询线程只读这个配置。
类如下，`snapshot`没有同步保护：

```java
final class Config {
    int partitions;
    final int pageSize;

    Config(int partitions, int pageSize) {
        this.partitions = partitions;
        this.pageSize = pageSize;
    }
}

final class ConfigHolder {
    private Config snapshot;

    void install(int partitions, int pageSize) {
        snapshot = new Config(partitions, pageSize);
    }

    Config current() {
        return snapshot;
    }
}
```

## 约束

- 构造期间`this`不逸出；`partitions > 0`、`pageSize > 0`，对象发布后不再修改。
- 启动线程与查询线程已存在，没有由线程启动/结束建立的额外同步关系。
- 查询线程可以在配置尚未安装时得到`null`；请使用单次`current()`的局部结果讨论，
  不在表达式中多次读取并假设它们相同。
- 先讨论Java内存模型允许的行为，不用特定CPU的一次运行结果代替证明。

## 任务

1. 如果查询线程读到非`null`，哪些字段值可被规范保证？说明条件与理由。
2. 给出一种最小修改，让引用及普通字段安全发布；说明happens-before关系。
3. 如果以后允许更改已发布对象的`partitions`，这项修改是否仍覆盖所有问题？
4. 设计一个最小并发检验，区分「测试未观察到坏结果」与「规范禁止坏结果」。

## 边界用例与交付

覆盖安装前读取、与安装并发、反复替换不同配置、发布后字段更新这一契约变化。
提交约十行论证、修改后的最小代码及检验思路。若实际运行，记录JDK版本、运行参数、
迭代次数和观察结果；没有运行就只提交设计。无需今天构建完整OpenJDK。

可选定位：本地JDK的`src/java.base/share/classes/java/util/concurrent/`中查找
发布与volatile相关注释；规范依据应回到[JLS §17](https://docs.oracle.com/javase/specs/jls/se25/html/jls-17.html)。
