# 第20章 LTO与链接时优化

## 20.1 LTO架构

### 20.1.1 Full LTO vs ThinLTO：设计权衡

```
LTO(Link-Time Optimization): 在链接时进行跨模块优化

Full LTO:
  1. 所有编译单元的LLVM IR合并为一个模块
  2. 对整个模块运行优化Pass流水线
  3. 生成目标代码

  优势: 最大优化空间(跨模块内联、常量传播、去虚化)
  劣势: 内存占用大(所有IR同时加载), 编译时间长(单线程)

ThinLTO:
  1. 每个编译单元生成摘要(Index)
  2. 基于摘要决定跨模块优化机会
  3. 并行优化各编译单元(只导入需要的函数)
  4. 并行代码生成

  优势: 编译时间接近普通编译, 内存占用小
  劣势: 优化空间略小于Full LTO

| 维度 | Full LTO | ThinLTO |
|------|---------|---------|
| 编译时间 | 极长(串行) | 接近普通编译(并行) |
| 内存 | 所有IR同时加载 | 只加载需要的函数 |
| 优化能力 | 最强 | 强(约Full LTO的90%) |
| 并行度 | 低 | 高(按编译单元并行) |
| 适用 | 小型项目/最终发布 | 大型项目/日常开发 |
```

### 20.1.2 核心逻辑

**源码**：`llvm/lib/LTO/` + `llvm/lib/Linker/`

```
Full LTO核心流程(llvm/lib/LTO/LTO.cpp):
  1. addModule(): 接收每个编译单元的bitcode
  2. run():
     a. 链接所有bitcode为单一模块(llvm/lib/Linker/Linker.cpp)
     b. 运行优化Pass流水线(PassBuilder)
     c. 运行后端代码生成(llc逻辑)
     d. 生成目标代码

ThinLTO核心流程(llvm/lib/LTO/ThinLTOCodeGenerator.cpp):
  1. generateCombinedModuleIndex():
     - 扫描每个bitcode, 提取函数摘要
     - 构建跨模块调用图
     - 生成全局索引(每个函数在哪、调用谁)

  2. runParallel():
     对每个编译单元(并行):
     a. 加载当前编译单元的bitcode
     b. 根据全局索引决定需要导入的函数
     c. 导入函数(IR级链接, 只复制需要的函数)
     d. 运行优化Pass流水线
     e. 运行后端代码生成
```

---

## 20.2 跨模块优化机会

### 20.2.1 跨模块内联与常量传播

```
没有LTO:
  // a.cpp
  int helper(int x) { return x * 2; }  // 单独编译, 无法看到调用者

  // b.cpp
  int result = helper(21);  // 不知道helper的实现, 无法内联

有LTO:
  // 合并后
  int result = 21 * 2;  // 内联 + 常量折叠 → 42

关键跨模块优化:
  1. 跨模块内联: 消除函数调用开销, 暴露新的优化机会
  2. 跨模块常量传播: 常量从定义传播到使用
  3. 跨模块DCE: 删除只在其他模块使用但现在不需要的函数
  4. 跨模块别名分析: 不同模块的全局变量肯定不别名
```

### 20.2.2 WholeProgramDevirt在LTO中的角色

```
WholeProgramDevirt + LTO: 最强大的C++优化组合

没有LTO: 虚函数调用无法去虚化(看不到所有实现)
有LTO: 整个程序的虚表信息可见 → 去虚化 + 内联

  // 基类声明(在头文件)
  class Shape { virtual void draw(); };

  // 派生类实现(在不同编译单元)
  class Circle : public Shape { void draw() override { ... } };

  // 调用点
  shape->draw();  // 间接调用

  LTO后:
  - 看到所有Shape的派生类只有Circle
  - 去虚化: shape->draw() → Circle::draw()
  - 内联: Circle::draw()的函数体直接嵌入调用点
  - 收益: 10-100倍性能提升(间接调用→内联)
```

---

## 20.3 Caching与增量编译

### 20.3.1 ThinLTO缓存机制

```
ThinLTO缓存:
  - 每个编译单元的优化结果缓存在磁盘
  - 下次编译时, 只重新编译修改过的编译单元
  - 未修改的编译单元直接使用缓存

  缓存键: 编译单元bitcode的hash + 依赖的摘要hash
  → 任何依赖变化都会使缓存失效

  缓存目录结构:
  thinlto-cache/
  ├── thinltocache-abc123.o    # 缓存的目标文件
  ├── thinltocache-def456.o
  └── ...

  启用: -Wl,--thinlto-cache-dir=./thinlto-cache
```

### 20.3.2 CAS(Content Addressable Storage)

**源码**：`llvm/lib/CAS/`

```
CAS: 基于内容寻址的存储系统

设计:
  - 每个编译产物(IR/object/摘要)按内容hash存储
  - 相同内容只存储一份(去重)
  - 跨构建复用: 不同项目的相同代码共享缓存

应用:
  - 分布式编译: 编译产物可以跨机器共享
  - 增量编译: 精确的依赖追踪, 只重建变化的部分
  - 远程执行: 编译任务可以发送到远程机器, 结果通过CAS共享

源码入口:
  llvm/lib/CAS/CASDB.cpp
  llvm/lib/CAS/ActionCache.cpp

  这是LLVM构建系统的基础设施级项目,
  与Bazel的Remote Execution和Reclient的设计理念类似
```

---

## 20.4 本章小结

本章解析了LTO的架构和实践：

1. **Full LTO vs ThinLTO**——Full LTO优化最强但编译慢，ThinLTO并行编译且接近Full LTO的优化效果。
2. **跨模块优化**——内联、常量传播、WholeProgramDevirt是LTO的核心收益。
3. **Caching与增量编译**——ThinLTO缓存和CAS基础设施实现快速增量构建。

下一章进入体系结构感知编译——缓存、分支预测、内存模型的编译器适配。
