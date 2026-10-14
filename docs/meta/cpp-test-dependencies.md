# 便携 C++ 测试依赖：两项定向恢复

2026-10-14：本批仅为两个已有消费者和固定版本的依赖补齐 Git submodule 记录，不升级版本、不恢复全部第三方仓库。

| 路径 | 官方来源 | Gitlink commit |
| --- | --- | --- |
| cc/thirdparty/googletest | https://github.com/google/googletest/tree/v1.15.2 | b514bdc898e2951020cbdca1304b75f5950d1f59 |
| cc/thirdparty/benchmark | https://github.com/google/benchmark/tree/v1.9.1 | c58e6d0710581e3a08d65c349664128a8d9a2461 |

原 benchmark 固定值 `96afad55c79e02f5dfca1374e772c2be72ba631b` 是有效的 v1.9.1 annotated-tag 对象；Gitlink 必须记录解引用后的 commit。本次 CMake 与 Gitlink 统一为 `c58e6d…`，源版本不变，并非修复坏 pin。

## 从干净 checkout 验证

```sh
git submodule update --init -- cc/thirdparty/googletest cc/thirdparty/benchmark
cmake -S . -B /tmp/xlab-pinned-debug -DCMAKE_BUILD_TYPE=Debug \
  -DXLAB_FETCH_DEPENDENCIES=OFF -DXLAB_BUILD_BENCHMARKS=ON \
  -DCMAKE_DISABLE_FIND_PACKAGE_GTest=ON -DCMAKE_DISABLE_FIND_PACKAGE_benchmark=ON
cmake --build /tmp/xlab-pinned-debug --parallel 4
ctest --test-dir /tmp/xlab-pinned-debug --output-on-failure --no-tests=error
```

另用独立目录验证 Release。初始化阶段需要访问两个官方仓库；上述 CMake 构建不下载缺失依赖，也禁用系统包捷径，因而必须实际消费已初始化的路径。该模式仅覆盖 portable cclab 与 thread-pool，启用基准目标的编译不等于已完成性能测量。

CI 的专用 Linux Debug/Release job 验证实际 Gitlink 版本和 fetch-OFF 构建；既有 Linux/Windows fetch-ON 矩阵保留。Windows 的原生源码打包不含 thirdparty，因此不能将其称为 Gitlink 初始化测试。

## 未解决的范围

仍有 67 个声明未配 Gitlink，健康检查应继续报告失败，不能把回归测试通过说成全仓健康。某个库被 Cargo、Python 或系统包引用，不意味着同名 thirdparty 路径需要恢复。阅读资料与未知用途声明继续保留，后续逐项评估。

回退只需普通 Git revert 本批提交；不删除用户机器上已有依赖工作区，不清除运行数据。
