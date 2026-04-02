# 学习Bazel项目指南

## 项目概述

本项目旨在通过构建一个简单的C++应用程序，帮助您掌握Bazel构建工具的核心概念和工作流程。我们将创建一个包含主程序、工具库和第三方依赖的微型项目。

## 项目目标

构建一个简单的C++命令行工具，包含：

- 主程序入口
- 自定义工具库
- 第三方库依赖（使用`fmt`库进行格式化输出）

## 开发环境准备

### 安装Bazelisk

推荐使用Bazelisk来管理Bazel版本：

```
# 安装Bazelisk
npm install -g @bazel/bazelisk
# 或使用pip
pip install bazelisk
```

### 验证安装

```
bazel --version
```

## 项目结构

创建项目目录结构：

```
bazel-learning/
├── MODULE.bazel
├── main.cc
├── math_util.h
├── math_util.cc
├── BUILD
└── tests/
    ├── math_util_test.cc
    └── BUILD
```

## 第一步：项目初始化

### 创建MODULE.bazel文件

```
# MODULE.bazel
module(
    name = "bazel_learning",
    version = "1.0.0",
)

# 引入fmt库
bazel_dep(
    name = "fmt",
    version = "10.2.1",
)
```

**核心概念解释：**

- `MODULE.bazel`是Bazel项目的根配置文件
- `module()`定义当前模块的基本信息
- `bazel_dep()`声明项目依赖的外部模块

## 第二步：编写C++代码

### main.cc - 主程序

```
// main.cc
#include <iostream>
#include "math_util.h"
#include "fmt/core.h"

int main() {
    int a = 10;
    int b = 20;
    int result = add(a, b);
    
    fmt::print("计算结果: {} + {} = {}\n", a, b, result);
    
    return 0;
}
```

### math_util.h - 头文件

```
// math_util.h
#ifndef MATH_UTIL_H
#define MATH_UTIL_H

// 加法函数声明
int add(int a, int b);

#endif // MATH_UTIL_H
```

### math_util.cc - 实现文件

```
// math_util.cc
#include "math_util.h"

// 加法函数实现
int add(int a, int b) {
    return a + b;
}
```

## 第三步：创建构建规则

### 根目录BUILD文件

```
# BUILD
cc_binary(
    name = "calculator",
    srcs = ["main.cc"],
    deps = [
        "//:math_util",
        "@fmt//:fmt",
    ],
    copts = ["-std=c++17"],
)

cc_library(
    name = "math_util",
    srcs = ["math_util.cc"],
    hdrs = ["math_util.h"],
    visibility = ["//visibility:public"],
    copts = ["-std=c++17"],
)
```

**构建规则解释：**

- `cc_binary`：定义可执行程序
- `cc_library`：定义C++库
- `srcs`：源文件列表
- `hdrs`：头文件列表
- `deps`：依赖项
- `visibility`：可见性控制
- `copts`：编译选项

## 第四步：构建与运行

### 构建项目

```
# 构建可执行文件
bazel build //:calculator

# 运行程序
bazel run //:calculator

# 直接运行（自动构建并运行）
bazel run //:calculator
```

### 查看构建结果

```
# 查看生成的可执行文件位置
bazel info bazel-bin
```

## 第五步：添加单元测试

### 创建测试目录

```
mkdir tests
touch tests/math_util_test.cc
touch tests/BUILD
```

### math_util_test.cc - 测试代码

```
// tests/math_util_test.cc
#include <gtest/gtest.h>
#include "../math_util.h"

// 测试加法函数
TEST(MathUtilTest, AddFunction) {
    EXPECT_EQ(add(2, 3), 5);
    EXPECT_EQ(add(-1, 1), 0);
    EXPECT_EQ(add(0, 0), 0);
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
```

### tests/BUILD - 测试构建规则

```
# tests/BUILD
cc_test(
    name = "math_util_test",
    srcs = ["math_util_test.cc"],
    deps = [
        "//:math_util",
        "@com_google_googletest//:gtest_main",
    ],
    copts = ["-std=c++17"],
)
```

### 运行测试

```
# 构建并运行测试
bazel test //tests:math_util_test

# 查看详细测试输出
bazel test //tests:math_util_test --test_output=all
```

## 核心概念总结

### Bazel核心术语

- **Target**：构建的基本单元，格式为`//package:target`
- **Package**：包含BUILD文件的目录
- **Workspace**：项目根目录
- **Rule**：构建规则（如cc_binary, cc_library）

### 构建命令速查

```
# 构建指定目标
bazel build //:target_name

# 运行可执行目标
bazel run //:target_name

# 运行测试
bazel test //:test_target

# 清理构建缓存
bazel clean

# 查看依赖关系
bazel query 'deps(//:target_name)'
```

## 学习建议

### 推荐学习路径

1. **从简单开始**：先掌握基本的cc_binary和cc_library
2. **理解依赖**：学习如何管理内部和外部依赖
3. **项目结构**：掌握多包（multi-package）项目组织
4. **高级特性**：学习自定义规则和宏

### 调试技巧

```
# 查看详细的构建过程
bazel build //:calculator --sandbox_debug

# 查看构建图
bazel query 'deps(//:calculator)' --output=graph
```

## 后续学习资源

### 官方文档

- Bazel官方文档
- C++规则文档

### 实践项目建议

1. 添加更多复杂的库依赖
2. 实现多级目录结构
3. 集成数据库客户端库
4. 构建共享库（动态链接库）

通过这个迷你项目，您应该已经掌握了Bazel的基本使用方法。现在可以尝试在自己的项目中应用这些概念，逐步深入学习Bazel的强大功能。


