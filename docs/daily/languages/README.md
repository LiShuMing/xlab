# Java / C++ 变化专题

本目录按稳定身份维护深入材料，例如 `jep-xxxx.md`、`p26xx.md`。
尚无经过本流程核实的新动态，不预生成空专题。每日摘要放日报，长期背景与验证方法放专题。

| 来源 | 必须分别核实的阶段 | 最小验证方向 |
| --- | --- | --- |
| [JEP 索引](https://openjdk.org/jeps/0) | Draft/Candidate/Proposed to Target/Targeted/Integrated 等状态与目标JDK | 找JEP原文、实现commit与jtreg测试 |
| [JDK 构建](https://jdk.java.net/) | EA/RC/GA；特性preview/incubator/final；该版是否已发布 | 记录`java -version`、feature flags、兼容/并发/GC的边界输入 |
| [WG21](https://open-std.org/JTC1/SC22/WG21/) | 提案修订、采纳、进入工作草案 | 对照措辞与最小语义反例 |
| [GCC](https://gcc.gnu.org/projects/cxx-status.html)、[Clang](https://clang.llvm.org/cxx_status.html) | 具体编译器版本、实现状态、feature-test macro | 最小编译/执行示例、标准选项、诊断与结果 |
| [libc++](https://libcxx.llvm.org/Status/Cxx2c.html) / libstdc++ | 标准库实现及版本，与语言支持分开 | 编译器+标准库组合；不从编译器支持推导库支持 |

新闻优先关注正确性、并发、内存、性能与兼容性。验证思路不等于已执行结果。
没有新变化时只在连续课程中学习一个基础概念，并标明「学习内容」。
本地 `jdk/master` 是源码阅读快照，不证明 JEP 目标版本的发布或 preview 状态。
