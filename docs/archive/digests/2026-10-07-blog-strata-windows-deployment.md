# Strata 在 Windows 上的源码部署与分层推理实现分析

这次实验想回答两个问题：一张 16 GB 显存的消费级显卡，如何运行远大于显存容量的 MoE 模型；模型跑起来之后，怎样确认部署正确，并把它变成项目中可调用、可评测的服务。

最后采用的方案是 Windows 原生 Strata 引擎，加上 WSL 中的开发和评测客户端。源码构建、模型校验、API 验证、代码审查和小样本 benchmark 都完成了。但更值得记录的不是“安装成功”，而是其中几个边界：下载长度不等于模型完整，GPU 掉线不等于驱动被覆盖，API 返回 200 不等于推理正确，benchmark 判错也不一定意味着模型算错。

本文基于 2026 年 10 月 7 日的实际实验。Strata 源码固定在 commit `82f46a8c8f475f001ad76d92f58f4a4f8ffb0253`，本地引擎版本为 `0.1.40`。分析以这次单卡、文本、低内存运行路径为主，不把其他硬件上的项目成绩当成本机成绩。

## 实验环境和模型选择

| 项目 | 本次配置 |
| --- | --- |
| 操作系统 | Windows 11，开发仓库位于 WSL Ubuntu |
| CPU | AMD Ryzen AI 9 HX 370，12 核 24 线程 |
| 系统内存 | 标称 32 GB，系统查询约 31.12 GiB |
| GPU | NVIDIA RTX 5070 Ti，标称 16 GB 显存 |
| 外接方式 | OCuLink |
| 模型所在磁盘 | Kingston SNV3S1000G，1 TB NVMe SSD |
| NVIDIA 驱动 | 实验核对时为 610.62 |
| 编译工具 | Visual Studio 2022 Build Tools，MSVC 19.44 |
| CUDA 工具链 | CUDA Toolkit 13.0.2，nvcc 13.0.88 |
| CUDA 架构 | `sm_120` |
| 上下文 | 32,768 tokens，KV 使用 int8 |
| 模型 | `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-Coder-GGUF`，IQ1_M |

先区分三个名称。Qwen3.8-Flash-Next 是模型家族，GSQ-RCO Coder 是针对编码能力保留专家的压缩版本，Strata 是运行这些权重的推理引擎。它们不是同一件事。

本次 Coder GGUF 页面标注约 117B 参数。它从原模型中移除一半 routed experts，同时保留 n-gram 表。参数总量、每 token 激活参数量、文件大小和显存占用，是四种不同统计口径，不能混用。

本次每层保留 256 个 routed experts，每个 token 选择其中 10 个。剪枝首先减小的是专家全集和存储压力；只要每层激活数量不变，删掉一半专家就不等于单 token 专家计算量减半。稀疏激活解释了为什么每步不用计算全部专家，剪枝和量化则让保留下来的专家更容易进入 GPU 和 RAM。

`IQ1_M` 也不意味着全部权重都用 1 bit 存储。发布者说明，该版本把剪枝和混合精度量化的效果合并报告；保留权重约为 3.5 bpw，n-gram 表约为 4.5 bpw。两片文件合计仍有 58.4 GB。因此，“117B 模型只占十几 GB 显存”主要依赖分层存储和计算，并不意味着所有参数都装进了 GPU。[Coder 模型说明](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-Coder-GGUF)

### 为什么引擎放在 Windows

这台机器原先在 WSL 中已经可以使用 CUDA，所以选择 Windows 不是因为“WSL 不支持 CUDA”。当时 WSL 的可用内存预算约为 16 GB，而主机有 32 GB；对这个模型，CPU 侧专家驻留同样重要。Windows 原生引擎能够直接利用主机资源，也方便核对外接显卡的设备状态。

Strata 的安装文档还明确区分了 WSL 的 KV streaming 限制。不过本次只配置 32K 上下文，没有启用长上下文 KV streaming，不能把它说成本次性能改善的来源。[安装指南](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/docs/AI_SETUP.md)

最终边界很简单：模型进程和权重在 Windows，代码、实验脚本和 benchmark 在 WSL，两边通过本机 HTTP API 通信。

## Strata 的整体实现逻辑

从代码组织看，可以把系统分成三层。

| 层次 | 入口 | 主要职责 |
| --- | --- | --- |
| 安装与制备 | `setup.py`、`tools/iq_pack.py` | 检测硬件，选择模型，下载或构建引擎，生成 pack、配置和启动脚本 |
| API 与文本处理 | `serve/server.py` | HTTP 协议，chat template，tokenization，队列，流式输出和状态接口 |
| 推理执行 | `src/program/generate.cpp` 及 `src/core`、`src/prefill`、`src/kernels` | 权重加载，专家分层，CPU/GPU 调度，prefill、decode 和推测验证 |

请求的主路径可以概括为：

```text
客户端 messages
    → Python Service 渲染模板并编码为 token IDs
    → StrataEngine 向常驻 C++ 进程发送生成命令
    → prefill 更新模型状态
    → decode 和草稿验证产生 token IDs
    → Python 解码并返回 JSON 或 SSE
```

这里不是“每次请求启动一次模型”。`StrataEngine` 管理常驻引擎，权重、状态和专家缓存加载一次后复用。C++ 主程序的服务协议包括 `GEN`、逐 token 的 `T`、结束统计 `DONE`，以及进度、停止和退出消息。协议两端分别位于 [StrataEngine](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/serve/server.py#L533) 和 [generate.cpp 的服务循环](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/src/program/generate.cpp#L5034)。

`Service` 默认使用一把锁串行处理生成请求。当前部署没有配置并行解码，所以网页聊天和 benchmark 共用同一条队列。一次短 API 请求也可能因前面的长推理而超时；模型加载正常，与客户端等待超时并不矛盾。本次就遇到过网页正在思考、后续测试请求等待 60 秒后超时的情况。

### GPU 保存热专家，CPU 计算未命中的专家

MoE 的专家数量很大，但每个 token 只选择其中一部分。Strata 的关键并不是简单把某几层永久交给 CPU，而是在 routed experts 这一粒度上分工：GPU 缓存命中的专家走 GPU，未命中的专家由 CPU 专家池计算，随后汇合结果。

`ExpertCache` 管理显存 slot 和 `(layer, expert)` 到 slot 的映射。它本身不是计算算子，计算消费者位于 GPU 内核和执行调度中。缓存可以依据 routing profile 初始化；运行期间的热度统计和交换逻辑继续调整驻留集合。[ExpertCache 接口](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/include/strata/core/expert_cache.hpp)

CPU 路径的 `expert_pool_dispatch()` 消费这一轮已经确定的 hit/miss 分类，只为 miss 建立 `ExpertJob`。命中位置的 CPU 输出需要清零，不能留着上一轮缓冲区里的值，也不能被 CPU 再算一遍。`ExpertPool` 再利用绑核的 worker 和 CPU 量化内核执行这些任务。[专家分派实现](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/src/core/expert_source.cpp#L2281)、[CPU 专家池](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/include/strata/kernels/cpu/pool.hpp)

这很像数据库 buffer pool 的问题，但又有区别。普通页缓存命中主要减少 I/O；这里缓存命中还改变了计算位置，减少 CPU 读取专家权重的内存流量。显存多一些，可能同时改变命中率、CPU 内存带宽压力和跨设备等待，而不仅仅是改变模型能否加载。

不能用“缓存装了多少比例的专家”直接推导命中率。专家访问不是均匀分布，不同层的 blob 大小也不同。本次启动日志记录了 4,360 个缓存专家、约 8.30 GiB 的专家缓存；首次四 token smoke test 的命中率为 40.4%。这个数字只描述那次很短的请求，不代表所有代码或数学任务。

### 低内存模式保存缓存补集

对 32 GB 主机，另一个容易误读的地方是 RAM 驻留方式。文档中“全部专家在 RAM”描述的是一种运行路径，不能直接套到本次 `--resident-experts` 配置。

`FileExpertSource::pin_cache_complement()` 为 GPU 缓存未持有的专家建立紧凑的 host 副本；prefill 借用某些缓存 slot 时，还可能需要保留相应的 host 镜像。Windows 的可用 RAM、commit capacity 和保留余量都会影响它是否能成立。若无法完整驻留，源码还包含降级路径。[FileExpertSource 的补集接口](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/include/strata/core/expert_source.hpp#L433)

本次启动确实走了部分驻留的降级路径。日志中完整专家补集需要 15.12 GiB，当时可用 RAM 为 14.45 GiB、可用 commit 为 14.32 GiB；扣除 4 GiB 安全余量和 0.25 GiB margin，最终按 profile 热度保留 5,289 个专家，共 10.07 GiB，全部锁页并映射。剩余专家仍从模型文件映射读取，可能由 Windows 文件缓存满足，也可能发生实际 SSD 读取。`--resident-experts` 是请求驻留策略，不是所有专家已常驻的证明。

因此，本次内存需求更接近“CPU 专家补集、必要镜像和工作区”，而不是“再在 RAM 里复制整个 58.4 GB 模型”。但补集也不等于完全没有重复副本：cache lending、交换缓冲和文件映射仍然要维护一致性。

源码中的 `resident_stage_swaps()` 展示了这类状态转换的复杂性。把一个 RAM 专家提升到 GPU 前，被逐出的 GPU 专家需要先回到可用的 host 存储；交换未完成期间，CPU 和 GPU 都必须读到正确版本。对系统工程而言，缓存替换策略和替换过程的正确性，是两个不同问题。

### n-gram 表留在 SSD

第二个 GGUF 分片不是“下一半普通 Transformer 层”，而是约 28.8 GB 的 per-layer n-gram lookup table。这部分主要做按行查找，适合采用不同于专家矩阵的存储策略。

`PleReader` 的接口明确把读取拆成 `issue()` 和 `collect()`：token ID 确定后先提交行读取，在 embedding、早期层计算期间覆盖一部分 I/O，到消费点再等待。prefill 可以批量提交行请求，并做页去重、排序和并发控制；行缓存也不等于整张表常驻。[PleReader](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/include/strata/ngram/ple_reader.hpp)

Windows 的 `DirectFile` 使用无缓冲、异步文件 I/O 标志，Linux 路径使用 `O_DIRECT` 和并行读取。这说明 SSD 不只是安装介质，它进入了推理的数据路径。[DirectFile 实现](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/src/platform/direct_file.cpp)

把系统理解成三层后，16 GB 显存能够运行大模型就不再神秘：

| 存储层 | 本次主要承载的内容 |
| --- | --- |
| GPU VRAM | dense/attention 等计算所需权重与状态、KV、MTP，以及热专家缓存 |
| 系统 RAM | 10.07 GiB 锁页驻留的热专家补集、必要镜像、工作缓冲及 OS 文件缓存 |
| SSD | n-gram 表、GGUF 和 pack，未驻留且未被文件缓存满足的专家读取 |

这不是把容量问题消除了，而是把它转化成缓存、内存带宽、PCIe 传输和 SSD 延迟的协调问题。

### prefill 和 decode 采用不同策略

`Prefill` 按 chunk 处理输入。一个 chunk 内有多个 token，专家可以按 ID 分组，投影能够用 GEMM，GPU 未驻留专家则通过 pinned ring 和 copy stream 送入 GPU。它要留下与逐 token 路径对应的模型状态，供后续 decode 继续使用。[Prefill 接口和实现说明](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/include/strata/prefill/prefill.hpp)

decode 的 token 较少，矩阵复用机会小，访问权重的成本更加突出。此时热专家留在 GPU、CPU 原地计算 miss，是另一种权衡。不能仅因为两条路径都执行 MoE，就认定它们有相同的最优调度策略。

本次配置了 `--prefill auto`。自动选择仍受可用显存、ring 和缓存借用约束；源码默认自动上限与更大的显式选项也有区别。把上下文设为 32K，不等于每次都用一个 32K chunk 处理提示词。

### MTP 用目标模型验证草稿

本次还加载了单独准备的 MTP draft layer，配置包括 `--mtp` 和 `--spec 4`。草稿不会直接作为最终答案提交，必须经过目标模型的验证窗口。

当前主循环接入的是 `DraftPolicy`，它依据窗口接受率和测得的成本，选择 MTP 或 suffix/prompt lookup 的验证方案。`Pick.t` 是包含草稿的窗口大小，并不等于“每轮一定提交这么多新 token”。[DraftPolicy](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/include/strata/spec/draft_policy.hpp)

从系统角度看，它在优化“每次验证的平均有效 token 数除以验证成本”。如果草稿接受率低，增加窗口反而可能变慢。本次 smoke test 中有三个 draft 被接受，但没有关闭 MTP 做同题、同状态的 A/B，所以不能从这一次结果计算 MTP 的加速倍数。

同样，草稿验证不意味着整个量化引擎等价于原始 BF16 模型。推测策略的正确性、量化误差以及 CPU/GPU 不同计算路径的数值一致性，需要分别讨论。

## Windows 原生源码部署

### 二进制与源码构建如何选择

Strata 有预构建引擎，不是所有用户都需要安装编译器。对于希望尽快验证模型的机器，可以先检查预构建版本是否覆盖 GPU；对于需要核对架构、研究引擎或修改代码的场景，再选择本机源码构建。

本次最终使用源码构建。`setup.py::build_engine()` 会计算源码指纹、检查已有构建覆盖的架构，调用 CMake，并把结果及元数据放入 `engine`。本机生成的构建脚本使用 Ninja、Release 配置和 `CMAKE_CUDA_ARCHITECTURES=120`，并链接需要的 ggml 相关代码，而不是在运行时依赖一个 PyTorch 模型进程。[build_engine 实现](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/setup.py#L2644)

CUDA Toolkit 是编译和运行库的一部分，GPU driver 是另一层依赖。已有 CUDA 可以工作，不意味着需要重装驱动；缺少 nvcc 或 MSVC，也不是 GPU 驱动损坏的证据。本次安装了构建工具和 Toolkit，其中还包含 Nsight 等组件。记录安装清单，比事后把所有新组件笼统称作“显卡驱动”更容易定位问题。

### 获取源码和运行安装

下面对应一次新建目录的部署；已有目录不要直接覆盖。

```powershell
Set-Location C:\AI
git clone https://github.com/Niko1221/Strata.git
Set-Location C:\AI\Strata
git checkout 82f46a8c8f475f001ad76d92f58f4a4f8ffb0253

cmd /c START-HERE.bat --check
cmd /c START-HERE.bat --build --yes --family coder --model IQ1_M --context 32768 --vision no --no-start
```

`--no-start` 把安装和服务启动分开，便于先校验数据。源码位于 `C:\AI\Strata`，模型和运行数据默认放在旁边的 `C:\AI\Strata-data`，不是 WSL 文件系统。启用图片会增加另一个编码器及资源预算，本次没有启用。

检查实际构建产物：

```powershell
Get-Content C:\AI\Strata\engine\BUILD.json
```

本机记录的关键字段为：

```json
{
  "source": "local",
  "version": "0.1.40",
  "archs": [120],
  "vision": "none",
  "src": "106ece8a3433328b"
}
```

这比“目录里有一个 strata.exe”更明确。另一个边界是，该构建脚本设置了 `STRATA_BUILD_TESTS=OFF`；后面提到的 Python 测试通过，不等于 Strata 全部上游引擎测试都跑过了。

### pack 为什么不是普通解压

`tools/iq_pack.py` 读取全部 GGUF 分片，生成引擎需要的索引、专家布局、tokenizer 和运行数据。它保留 native quantized blocks；部分浮点张量按引擎格式存入 `dense.bin`，转换记录进入 `conversions.json`。[iq_pack.py](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/tools/iq_pack.py)

本次低内存路径还生成了 `experts.bin`。它把专家数据排成引擎读取方便的连续文件，所以部署后同时存在 GGUF 和 pack。这个额外文件并不表示“旧模型没有删干净”。

源码也提供了不生成专家副本、从 GGUF 原地读取的路径，但本次配置不是那组实验。不能不改布局和配置、不做加载验证，就直接删除 `experts.bin` 假定服务仍会正常运行。

## 模型下载和完整性验证

最早一批模型文件最终 SHA256 不符，输出也曾出现长串重复感叹号。它们被隔离，未作为后续部署的有效输入。此前使用过多连接下载，但现有证据不能把损坏的原因确定为下载工具本身；代理、分段响应或传输过程都需要独立证据。

重下时保留了原 HTTP 续传，并尝试低并发 Xet。第一分片由原 HTTP 流程先完成；第二分片由 Xet 完成并校验。第一分片通过哈希后，备用 Xet 进程被停止，暂存数据保留，没有再次打包另一份同样的模型。

| 分片 | 精确字节数 | SHA256 |
| --- | ---: | --- |
| 00001-of-00002 | 29,608,446,496 | `e11083ba855e7666b48ea3f2db6a9c3a20c18751a012cc24f948de91b7087fad` |
| 00002-of-00002 | 28,800,138,432 | `316b46f3a2dbd68c900f43136ab9449f9dcc3725dfd8c794847c204bc161e113` |

固定模型 revision 为 `5348543e0147355ac9cbcb031184a3546350988e`。这次以精确大小和完整 SHA256 共同作为验收条件。

过程中还遇到两个容易造成假进度的现象。第一，正在写入的文件，目录列表中的长度或更新时间可能暂时没有刷新；可以结合共享读方式读取长度和进程写入计数判断是否推进。第二，暂存文件可能已经分配完整长度；它不能证明字节全部收到，更不能证明内容正确。

实际传输增长是进度证据，最终哈希才是完整性证据。`.part`、`.incomplete` 或 `.done` 只是工作流标记，不应被当成同等强度的验证。

本次原安装流程在下载完成后自动打包，独立哈希 watcher 同时验证文件；部署辅助程序等打包完成，再完整校验两个分片，然后才启动服务。不是“打包成功就跳过校验”。若要进一步改进安装流程，可以把固定哈希验证前移到正式打包之前，让损坏数据更早失败。

## GPU 掉线和恢复过程

构建准备过程中，外接 GPU 曾报告 `GPU is lost`。随后重启后，GPU 和上游 GPP9 PCIe 设备都处于非当前存在状态，NVIDIA App 也无法正常使用。把这几个现象放在一起看，问题已经不只是应用界面故障。

当时核对了 driver、App 版本以及相关文件的签名和时间，未得到“安装覆盖了原驱动或 App 文件”的证据。电脑和 OCuLink 显卡坞完整断电后冷启动，GPU 再次枚举，后续源码构建和推理恢复正常。

这支持“存在 PCIe 链路或设备电源状态异常”这一方向，但不能确定具体是哪个部件，也不能排除安装期间的负载、重启时序或已有配置参与触发。仅凭先后顺序，不能把 CUDA Toolkit 安装认定为已证实的根因；冷启动恢复也不能证明某条线缆一定有问题。

这个案例的排查顺序应当是：先确认设备是否还存在，再检查驱动是否能访问设备，最后看应用。GPU 风扇转动只能说明某种供电状态，不能替代 PCIe 枚举和计算设备检查。设备和上游端口同时消失时，直接反复重装应用通常不能区分原因。

后续工作没有再安装或重装驱动，没有修改 BIOS、电源或系统代理，也没有主动重启电脑。

## 服务验收和磁盘占用

### 三个验收层次

模型部署不能只检查进程存在。本次使用了三层验收：

1. 文件层：两个分片的固定 SHA256 全部通过，确认本机 `sm_120` 构建和新配置。
2. 服务层：`/health` 返回 `loaded=true`，`/v1/models` 列出实际模型。
3. 行为层：真实聊天请求准确返回 `STRATA_OK`，而不是空响应或异常重复文本。

启动可以使用安装生成的 `C:\AI\Strata\run-coder-iq1_m.bat`。验证请求如下，默认只监听本机：

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health -NoProxy
Invoke-RestMethod http://127.0.0.1:8080/v1/models -NoProxy

$body = @{
  model = "qwen3.8-flash-next-coder-iq1_m"
  messages = @(@{role="user"; content="Reply with exactly STRATA_OK and nothing else."})
  max_tokens = 64
  temperature = 0
  reasoning_effort = "none"
} | ConvertTo-Json -Depth 6

Invoke-RestMethod http://127.0.0.1:8080/v1/chat/completions `
  -NoProxy -Method Post -ContentType "application/json" -Body $body
```

`-NoProxy` 用于支持该参数的 PowerShell 7；其他客户端应显式绕过本机地址的代理。

2026 年 10 月 7 日 14:38，部署检查进入 ready。首次启动日志显示约一分钟后接近就绪，并记录了 4,360 个 GPU 缓存专家。验证时总显存约 14.5 GiB，空闲 GPU 利用率可以降到 0%。模型仍加载在显存里，与 GPU 当前没有计算并不矛盾。

首次四 token 的 `chat.json` 中，服务端 decode 指标约为 8.7 tok/s。四 token 太短，不能据此给机器下长期吞吐结论，也不能把另一个日志口径的 tok/s 与它直接混为一个指标。

### 为什么清理后仍占很多磁盘

完成哈希验证后，删除了明确授权的旧损坏模型和旧 pack 两个目录，文件逻辑大小合计 85.04 GB。这是永久删除，不是移动到回收站；当前模型、MTP 和其他暂存没有扩大清理。

清理后的一个存储快照如下，单位为十进制 GB，按文件逻辑长度统计：

| 内容 | 占用 |
| --- | ---: |
| 正式 GGUF 两片 | 58.41 GB |
| 当前 Strata pack | 26.63 GB |
| MTP 运行与制备文件 | 6.93 GB |
| 停止的第一片 Xet 暂存 | 21.14 GB |
| 另一份下载暂存 | 1.09 GB |
| Strata 源码、引擎和 Python 环境 | 约 1.50 GB |
| 合计 | 约 115.7 GB |

这不包含系统级 Visual Studio 和 CUDA 工具链。逻辑长度也不等于 NTFS 上精确的物理分配量；并发写文件时，磁盘剩余空间的变化不一定恰好等于删除文件的大小。

所以需要分别统计正式权重、当前运行布局、draft 制备文件、下载残留和隔离旧文件。用整个目录的大小判断“模型有多大”，会把不同生命周期的数据混在一起。

## 当前机型的性能与优化贡献

这台机器能够较流畅地运行模型，主要不是因为每一步都用 GPU 计算全部参数，而是因为大多数专家访问命中显存，剩余工作由 CPU 配合 RAM 和文件映射后备承担，验证窗口又提供了权重复用机会。容量优化使部署成为可能，访问热点和调度优化才进一步解释生成速度。

### 实测速度及统计口径

以下统计取自 2026 年 10 月 7 日运行日志中连续 20 个完整请求，生成汇总行位于 `C:\AI\Strata\strata-coder-iq1_m.log` 第 248 至 335 行，最后一项的缓存统计紧随其后。这是一个固定日志样本，不是每次打开文章都重新计算的“当前速度”。

| 指标 | 该批请求的结果 |
| --- | ---: |
| 请求数 | 20 |
| 提示词长度 | 59～164 tokens |
| 生成 token 合计 | 4,503 |
| 生成阶段耗时合计 | 116.500 秒 |
| 总 token 除以总生成耗时 | 38.65 tok/s |
| 单请求生成速度范围 | 26.2～53.6 tok/s |
| GPU 缓存命中率范围 | 71.6%～87.0% |
| 按访问次数加权的缓存命中率 | 82.15% |
| 草稿接受率，含 MTP 和 suffix lookup | 88.05% |
| 提示词复用 | 0 tokens |

38.65 tok/s 是 `4503 / 116.500`，不是对各请求速度做简单平均。缓存命中率为 `1934371 / 2354612`，草稿接受率为 `3219 / 3656`。分子与分母分别累加，避免不同长度请求得到不合理的相同权重。

这些是 C++ 引擎日志的生成阶段指标，包含草稿生成、验证和提交等窗口工作，不是仅计算某个 CUDA kernel 的速度，也不是从发送 HTTP 到拿到完整回答的端到端速度。源码在生成循环前后计时，并用 `1000 × produced_n / decode_ms` 输出 tok/s，其中 `decode_ms` 的单位为毫秒。[生成耗时统计](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/src/program/generate.cpp#L9782)

这批请求没有提示词复用，因此不能把高生成速度归因于 prefix cache。但它们是在引擎已加载、缓存已运行一段时间之后完成的，也不能代替冷启动成绩。

### 热专家覆盖率比模型参数量更能解释速度

48 层、每层 256 个专家，共有 12,288 个 routed experts。GPU 实际保留 4,360 个 slot，约占专家数量的 35.5%，却覆盖了这批请求约八成的专家访问。容量比例与访问比例的差异，来自 routing 热点、profile 初始化和运行时调整。

命中的收益有三个层面：不再让 CPU 计算这个专家，不再让 CPU 从 RAM 或文件读取其权重，也不必每次通过 OCuLink 把权重送到 GPU。显存缓存减少的不只是 SSD I/O，而是整条 CPU 与跨设备路径的压力。

日志的 `hits / lookups` 排除了另行 PCIe offload 的访问。把另外 28,588 次 offload 也计入分母，GPU 缓存承担的比例是 `1934371 / (2354612 + 28588)`，约 81.17%。这些计数包含验证窗口中的 routed 访问，不应被误当成最终输出 token 数。

首次四 token smoke test 只有 40.4% 命中，后续这批请求达到 71.6%～87.0%。这与工作负载变化和缓存演化相容，但不是受控实验，不能把差值全部归因于缓存“预热”。

### CPU 协同和多 token 权重复用

启动日志记录了 7 个 pool worker，分别绑定逻辑处理器 `2,4,6,8,10,12,14`；host 线程绑定到 `0`，等待专家池时也参与计算。配置不是简单把 CPU 的 24 个逻辑线程全部拉满，而是为模型循环和专家计算安排不同核心。

本次 native pack 的验证窗口主要走 `expert_pool_dispatch_multi()`。它先把 GPU 驻留、PCIe offload 和 CPU miss 分类，再按专家 ID 聚合 CPU 任务：同一个专家为窗口内多个 token 服务时，建立一个 `ExpertJobMulti`，复用权重并引用各 token 对应的 activation。`run_split_multi_native()` 将专家的矩阵行分给 worker，避免 miss 专家少于 worker 时只用少数核心。[多 token 专家分派](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/src/core/expert_source.cpp#L2411)、[多 token 专家池](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/src/kernels/cpu/pool.cpp#L753)

原生量化内核还提供 AVX-512、AVX2 的运行时选择，多 token 路径可以一次解码权重后用于多个 activation。源码中的其他 CPU 上的加速数字不能直接移用到 HX 370；本次没有按 SIMD 路径单独计时。[原生专家内核](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/src/kernels/cpu/native_expert.cpp#L98)

GPU 工作提交后，CPU 可以处理剩余专家。层内关键路径更接近 CPU 与 GPU 两侧较慢的一侧，加上同步和未覆盖的数据读取，而不是完整累加两边时间。但层与层之间仍有依赖，这不是把整条推理链任意并行化。

部分 RAM 补集驻留也给性能留下了边界。`FileExpertSource::blob()` 在 RAM 命中时返回驻留指针，未命中时才返回文件映射位置并累加计数。日志中的累计文件读取 MB，是逻辑 blob 访问量，不是磁盘控制器实际传输了同样多的字节；系统页缓存可以消除部分物理 I/O。[blob 来源与计数实现](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/src/core/expert_source.cpp#L2226)

### OCuLink 带宽决定哪些 miss 留给 CPU

本机启动时的 host-to-device 实测带宽为 7.2 GB/s。Strata 随后把 native pack 的 `pcie_frac` 从默认 0.55 调整为 0.20：

```text
PCIe probe: 7.2 GB/s host->device
→ pcie_frac 0.20 (default 0.55)

0.55 × min(1, 7.2 / 20) ≈ 0.20
```

`probe_pcie_h2d_gbps()` 用锁页内存、预热和四次传输测带宽，`pcie_frac_for_gbps()` 据此缩放分工比例。它没有假设外接显卡与高速内置 PCIe 链路相同。[PCIe 探测与比例选择](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/src/program/generate.cpp#L1434)

对这台机器，把更多未命中专家交给 GPU，可能先遇到搬权重的成本。让 CPU 原地计算部分 miss，反而能避免链路进入关键路径。`pcie_frac=0.20` 是 miss 分工参数，不表示全部 routed 访问有 20% 都在传输；该批日志中的 offload 合计只占全部 routed 访问约 1.2%。

### MTP 和 CUDA Graph 共同减少窗口开销

该批请求的草稿接受率约 88.05%，意味着多数候选能通过目标模型验证。它既减少逐 token 验证的串行轮数，也让同一窗口内的专家权重具有复用机会。后者对 CPU 专家内核尤其重要：重复读取和解码权重往往比多算一个 activation 更贵。

这个接受率包含 MTP 和 suffix lookup，不能全部记在 MTP 名下，也不能换算成 88% 的加速。草稿本身有成本，被拒绝的候选也会消耗验证时间；真正收益取决于每窗口提交多少有效 token，以及窗口完整耗时。当前 `DraftPolicy` 正是按这一关系选择方案。

日志还记录了多个长度验证窗口的 CUDA Graph 捕获成功。`Verifier::capture()` 保存执行图供窗口复用，减少反复提交大量小 kernel 的开销；当前不是所有专家都在 VRAM 的零 CPU 路径，专家池仍需要参与执行。[验证窗口捕获](https://github.com/Niko1221/Strata/blob/82f46a8c8f475f001ad76d92f58f4a4f8ffb0253/src/core/verify.cpp#L1479)

### SSD lookup 和 prefill 的延迟与容量优化

本机 NVMe 承担 lookup 表的按行读取。`PleReader` 将提交和等待分开，在 embedding、早期层计算期间覆盖部分延迟，并使用行缓存、页去重和并发读取。启动日志还确认了 SSD keepalive：没有读取超过 100 ms 时，在近期请求窗口内读取一页，降低某些 SSD 空闲后首次读取可能出现的延迟。是否显著改善这块 Kingston SSD，需要独立 A/B，不能直接套用源码注释中另一款 SSD 的表现。

prefill 的日志配置为自动上限 8192 tokens、96-slot ring，并借用 1800 个 GPU cache slots，约 3.40 GiB。批量投影使用 GEMM，未驻留专家通过 pinned ring 和 copy stream 传输。借用 cache 空间使输入处理不必永久再占一套大工作区，代价是要在进入 decode 前维护专家驻留状态。

这两项分别优化提示词处理和 lookup I/O，不应把它们都算成最近短请求的 decode 加速。32K 上下文、int8 KV 和禁用 vision 也给资源预算留下空间，但没有对应的配置对照，无法给出它们各自的加速倍数。

### 流畅运行的适用范围

近期短请求的 38.65 tok/s，并不代表整段交互都没有等待。另一条日志记录了 375 token 提示词，其中 153 个复用，12,036 token 的生成阶段耗时 578.395 秒，约 20.8 tok/s；Python 服务日志中的约 584 秒还包含提示词处理等时间。这是长输出样本，不是与短请求相同输入的长上下文对照。

长思考可能生成大量 reasoning tokens，即使流式生成速度尚可，最终答案仍需等待。RAM 压力、文件缓存状态、专家路由和草稿接受率也可能改变速度。当前默认串行服务，单请求流畅不等于多用户并发流畅。

源码构建确保引擎包含本机 `sm_120` 目标，但本次没有与同架构预编译引擎做对照，不能把性能解释为“源码构建天然更快”。更符合证据的解释是：压缩和稀疏激活降低容量与工作量，热专家覆盖大多数访问，CPU 与 GPU 分担剩余计算，多 token 验证增加复用，未覆盖的传输和 I/O 再尽量隐藏。

## 把本地 API 接入代码实验

Windows 服务启动后，本机 WSL 已实测可以直接访问 `127.0.0.1:8080`：

```bash
curl --noproxy '*' http://127.0.0.1:8080/health
```

这是这台机器上的连通性结果，不是对所有 WSL 网络模式的保证。连接失败时，应先检查网络边界；不要为了调试就把无鉴权服务改成对外监听。

第一个落地工具是只读代码审查原型，位于 `/home/lism/work/xlab/python/projects/strata-review`。它把指定文件或限定路径的 Git diff 发给模型，要求输出 JSON 问题清单。`validate_review()` 再核对文件名、行号和证据片段是否真的存在。

这一步能拦住虚构引用，却不能证明问题判断正确。模型不会自动读取整个仓库，外部工具的文件访问范围、执行权限和补丁权限，也不会因为接入 API 就自然得到控制。

验证分成三部分：10 项离线单元测试，6 个已知缺陷与 4 个正常实现的模型测试，以及真实项目文件审查。小样例中六个已知缺陷样例命中，四个正常样例未误报；越界和释放后使用另外用 AddressSanitizer 验证。正常求和样例还补上了明确的输入上界，避免测试定义自身遗漏大输入溢出的可能性。

真实文件 `/home/lism/work/xlab/cc/cclab/src/utils/task_thread.h` 中，模型指出停止阶段持有 mutex 执行延迟回调，回调再次调用 `add()` 会重复获取同一把非递归锁。独立复现使用原始头文件：普通回调正常退出；重入回调进入后，3 秒截止时间内未返回。未修改这个头文件，也没有直接执行模型提供的复现代码。

这组证据比“解释看起来合理”更有用：源码锚点、触发条件、控制组和运行结果共同支撑判断。该文件的 low 思考等级审查耗时约 79 秒，但十个小样例仍不足以估算真实仓库审查的漏报率和误报率。

## 基于 API 的 benchmark 实验

评测复用了 `/home/lism/work/xlab/python/llm_benchmark`，增加独立的 `strata` 入口。检查原实现时发现两类问题：数学评分允许推理中的任意数字命中参考答案；旧 `CodeSandbox` 只有子进程和临时目录，并没有隔离文件系统、网络或实际执行其声明的内存限制。

这两类问题都会污染结论。前者把评分器错误表现为模型能力，后者把普通代码执行包装成了安全沙箱。因此新的本地评测路径把它们分开处理。

### 数据和评分如何固定

GSM8K 固定在 commit `3101c7d5072418e28b9008a6636bde82a006892c`，HumanEval 固定在 `6d43fb980f9fee3c892a914eda09951f772ad10d`，下载和缓存都核对固定 SHA256。抽样采用 `random.Random(42).sample`，每题的原始索引进入结果文件。

GSM8K 使用严格的最终数字比较：只接受最后的 `####` 答案或纯数字响应，不因为中间步骤提到参考数字而给分。HumanEval 每题生成一个候选，在隔离环境中执行官方 `check`；只有一个候选时报告 pass@1，不制造没有样本支撑的 pass@5 或 pass@10。两者的公开来源分别为 [GSM8K](https://github.com/openai/grade-school-math) 和 [HumanEval](https://github.com/openai/human-eval)。

API 默认并发 1、温度 0、超时 600 秒，推理 POST 不自动重试。传输异常会停止继续提交，保留逐题 checkpoint，避免前一轮还在计算时又排入同样的请求。`finish_reason=length` 的响应记为截断，不把其中可能出现的正确数字当成完整作答。

`samples.jsonl` 在每题结束后立即写入；最终 JSON 包含数据指纹、抽样列表、请求参数、答案、思考、finish reason、token 数和 timings。一次无 Key 接口联调还暴露了空 `Bearer` header 的问题，修正为未配置 Key 时不发送 Authorization，而不是伪造一个空凭证。

### 代码候选如何执行

HumanEval 使用新 `IsolatedPython`，不是旧的普通子进程 runner。Ubuntu 官方 Bubblewrap 包校验后只解包到项目 `.tools`，不安装系统包。

策略包括独立用户、进程和网络命名空间，清空环境，只读运行库，不挂载 home 或项目目录，移除 capabilities，并限制地址空间 256 MiB、CPU 5 秒、墙钟 10 秒、tmpfs 8 MiB 和输出文件 1 MiB。运行前检查策略，再让所有选中题目的标准解答通过同一个执行器，避免把执行环境故障算成模型失败。

实际测试覆盖了主机文件和环境变量不可见、主机 API 网络不可达、运行库不可写、内存限制、超时，以及错误实现和提前退出不能被算作通过。这个边界适合本次小规模候选测试，但不是虚拟机，也不是可对外开放的恶意代码执行服务。[Bubblewrap 的安全边界说明](https://github.com/containers/bubblewrap#sandbox-security)

### 本次成绩和数据质量问题

| 数据集 | 请求思考等级 | 按原始标签评分 | 平均 API 耗时 | 超时 | 截断 |
| --- | --- | ---: | ---: | ---: | ---: |
| GSM8K 8 题 | none | 7/8，87.5% | 11.38 秒/题 | 0 | 0 |
| GSM8K 同样 8 题 | low | 7/8，87.5% | 9.89 秒/题 | 0 | 0 |
| HumanEval 8 题 | none | pass@1 = 8/8 | 5.33 秒/题 | 0 | 0 |

GSM8K 两组题号为 `[1309, 228, 51, 563, 501, 457, 285, 209]`；HumanEval 为 `[163, 28, 6, 70, 62, 57, 35, 26]`。改造后的测试共 88 项通过，相关改动的 lint 通过。

最有意思的不是 HumanEval 的八题全过，而是 GSM8K 唯一的“错误”。零基索引 1309 的题目中，四人的金额应分别为 750、430、700、300，总和是 2180。原始解答最后求和却把 Sarah 的 300 写成了 400，得出参考标签 2280。模型在 none 和 low 两组都返回 2180，因此按原始标签被判错。[固定版本的原始题目和解答](https://github.com/openai/grade-school-math/blob/3101c7d5072418e28b9008a6636bde82a006892c/grade_school_math/data/test.jsonl)

原始评分保留为 7/8，人工核对作为单独的数据质量备注，不悄悄把 benchmark 改成“满分”。这说明：模型、评分器、参考标签和执行环境，需要分别验证。

耗时也应保持同样的谨慎。none 后 low 是固定运行顺序，没有独立热身或随机交错，缓存和系统负载可能影响均值；9.89 秒小于 11.38 秒，不能证明 low 在一般情况下更快。API 耗时包含排队、prefill、思考、输出和协议处理，不能直接当成 CUDA decode 的 tokens/s。

### 如何复跑

在本次 WSL 仓库中执行：

```bash
cd /home/lism/work/xlab/python/llm_benchmark
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'

.venv/bin/llm-bench strata --dataset gsm8k --max-samples 8 --seed 42 --effort none
.venv/bin/llm-bench strata --dataset gsm8k --max-samples 8 --seed 42 --effort low

.venv/bin/python -m llm_benchmark.prepare_bwrap
.venv/bin/llm-bench strata --dataset humaneval --max-samples 8 --seed 42 --effort none
.venv/bin/python -m pytest -q
```

新路径生成的报告默认位于评测目录的 `results/strata` 下，本次记录在 `/home/lism/work/xlab/python/llm_benchmark/results/strata-20261007`。HTML 图表依赖 Chart.js CDN，完整逐题证据以 JSON 为准。这里使用的是本次改造后的 xlab 工具，不是 Strata 上游自带的 benchmark 命令。

## 与通用推理框架的关系

| 框架 | 主要取向 | 理解本次实验时的区别 |
| --- | --- | --- |
| llama.cpp | 广泛模型、量化格式和硬件后端上的 C/C++ 推理 | 是通用本地推理实现，也提供 CPU/GPU 混合能力；Strata 构建中复用部分 ggml 代码 |
| vLLM | 高吞吐服务、批处理和 KV 管理 | 更强调服务层面的吞吐和调度，不能仅拿 API 兼容性与 Strata 判断优劣 |
| Strata 的本次路径 | 特定 MoE 模型在消费级单卡和有限 RAM 上运行 | 把专家缓存、CPU miss 计算、SSD lookup 和推测窗口结合起来 |

前两者的定位见 [llama.cpp](https://github.com/ggml-org/llama.cpp) 和 [vLLM](https://github.com/vllm-project/vllm)。本次没有在同一台机器、同一模型、同一量化和采样条件下运行它们，因此没有横向性能排名。

Strata 值得研究的地方，是围绕模型访问模式进行存储与调度设计；这不意味着所有 MoE 都能直接得到同样收益。专家热点分布、CPU 内存带宽、PCIe 链路和 lookup 表访问行为都可能改变最优方案。

## 后续实验和工程改进

从实现和这次故障看，接下来更有价值的工作有四类。

第一，把文件完整性检查前移并标准化。大小、固定哈希、模型 revision 和 pack 来源应组成一份可回查的制品描述。继续安装不能只依赖“文件已经存在”。

第二，单独测存储和调度变量。prefill chunk、专家缓存大小、CPU worker 数和 MTP 开关分别做同题 A/B，记录峰值 RAM、显存、CPU drain、PLE 等待和 cache hit。不能在同时改多个参数后，把收益全部归给某一个优化。

第三，扩大质量样本，同时保留逐题审计。GSM8K 扩大到 100 题，HumanEval 扩大到完整测试集，是后续实验，而不是这次已经取得的成绩。已发现的标签问题应有独立清单；温度 0 的重复运行也不能被当作独立随机样本计算 pass@k。

第四，给跨层状态增加回归测试。缓存提升和逐出、RAM 补集交换、prefill lending、推测验证与请求取消，都涉及不同执行单元对同一状态的所有权。`generate.cpp` 承担了参数、资源预算和服务循环等大量协调职责，继续演进时，值得把状态转换约束和测试边界做得更明确，而不只增加更多开关。

可以用一个简化的成本模型帮助选择观测指标：每层的 CPU miss 计算和 GPU hit 计算有重叠，但层间依赖、同步和未被覆盖的 I/O 仍在关键路径上。它不是把整条推理链路任意并行化，也不能仅用总 FLOPS 预测速度。

最终，这次实验验证的是一条完整工程路径：原生构建、正确权重、可用服务、受控客户端、可审计评测。Strata 的核心启发是按照计算和访问模式重新安排 GPU、RAM、SSD 的职责；而实验过程的核心启发，是把模型错误与基础设施、评分器和数据错误分开。只有这样，“本地大模型跑起来了”才会变成可以继续研究的系统。
