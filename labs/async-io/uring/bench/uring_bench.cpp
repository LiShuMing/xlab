#include <sys/socket.h>
#include <unistd.h>

#include <array>
#include <async_lab/measure.hpp>
#include <iostream>
#include <liburing/io_service.hpp>
#include <memory>
#include <string>
#include <vector>

namespace {
struct SocketPair {
    SocketPair() {
        async_lab::Require(socketpair(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0, fds.data()) == 0,
                           "socketpair failed");
    }
    ~SocketPair() {
        close(fds[0]);
        close(fds[1]);
    }
    std::array<int, 2> fds {};
    std::array<char, 64> input {}, output {};
};
uio::Task<> Nops(uio::IoService& service, unsigned count, bool detailed,
                 async_lab::Histogram& histogram, SocketPair* sockets) {
    for (unsigned i = 0; i < count; ++i) {
        const auto start = detailed ? async_lab::NowNs() : 0;
        if (!sockets)
            async_lab::Require(co_await service.Nop() == 0, "NOP completion error");
        else {
            const unsigned phase = i % 4;
            const int result = phase % 2 == 0 ? co_await service.Write(sockets->fds[phase / 2],
                                                                       sockets->output.data(), 64)
                                              : co_await service.Read(sockets->fds[1 - phase / 2],
                                                                      sockets->input.data(), 64);
            async_lab::Require(result == 64, "socketpair operation did not transfer 64 bytes");
            if (phase % 2)
                async_lab::Require(sockets->input == sockets->output, "socketpair payload");
        }
        if (detailed) histogram.Add(async_lab::NowNs() - start);
    }
}
} // namespace
int main(int argc, char** argv) {
    try {
        if (argc != 7) {
            std::cerr << "Usage: uring_bench raw|coroutine depth batch ops detailed(0|1) "
                         "nop|socketpair\n";
            return 2;
        }
        const std::string mode = argv[1];
        const unsigned depth = std::stoul(argv[2]), batch = std::stoul(argv[3]);
        const unsigned total = std::stoul(argv[4]);
        const bool detailed = std::string(argv[5]) == "1";
        const std::string workload = argv[6];
        async_lab::Require((mode == "raw" || mode == "coroutine") && depth > 0 && depth <= 128 &&
                                   batch > 0 && batch <= 256 && total >= depth &&
                                   total % depth == 0 &&
                                   (workload == "nop" || total % (4 * depth) == 0) &&
                                   (workload == "nop" || workload == "socketpair"),
                           "invalid benchmark arguments");
        async_lab::Histogram latency;
        uint64_t submissions = 0, completions = 0, waits = 0;
        const auto usage = async_lab::Usage();
        const auto start = async_lab::NowNs();
        std::vector<std::unique_ptr<SocketPair>> sockets;
        if (workload == "socketpair") {
            for (unsigned i = 0; i < depth; ++i) {
                sockets.push_back(std::make_unique<SocketPair>());
                sockets.back()->output.fill('x');
            }
        }
        if (mode == "coroutine") {
            uio::IoService service(depth, batch);
            std::vector<uio::Task<>> tasks;
            for (unsigned i = 0; i < depth; ++i)
                tasks.push_back(Nops(service, total / depth, detailed, latency,
                                     sockets.empty() ? nullptr : sockets[i].get()));
            service.RunAll(tasks);
            submissions = service.submissions;
            completions = service.completions;
            waits = service.waits;
        } else {
            io_uring ring {};
            const int init = io_uring_queue_init(depth, &ring, 0);
            if (init < 0) throw std::system_error(-init, std::generic_category());
            std::vector<unsigned> remaining(depth, total / depth);
            std::vector<uint64_t> starts(depth);
            auto submit_one = [&](unsigned slot) {
                if (detailed) starts[slot] = async_lab::NowNs();
                auto* entry = io_uring_get_sqe(&ring);
                async_lab::Require(entry != nullptr, "raw SQ full");
                if (sockets.empty())
                    io_uring_prep_nop(entry);
                else {
                    auto& pair = *sockets[slot];
                    const unsigned phase = (total / depth - remaining[slot]) % 4;
                    if (phase % 2 == 0)
                        io_uring_prep_write(entry, pair.fds[phase / 2], pair.output.data(), 64, -1);
                    else
                        io_uring_prep_read(entry, pair.fds[1 - phase / 2], pair.input.data(), 64,
                                           -1);
                }
                io_uring_sqe_set_data64(entry, slot + 1);
            };
            for (unsigned i = 0; i < depth; ++i) submit_one(i);
            while (completions < total) {
                if (io_uring_sq_ready(&ring)) {
                    int r;
                    do {
                        r = io_uring_submit(&ring);
                    } while (r == -EINTR);
                    async_lab::Require(r >= 0, "raw submit failed");
                    ++submissions;
                }
                io_uring_cqe* entry = nullptr;
                __kernel_timespec timeout {5, 0};
                int r;
                do {
                    r = io_uring_wait_cqe_timeout(&ring, &entry, &timeout);
                } while (r == -EINTR);
                async_lab::Require(r == 0, "raw wait failed");
                ++waits;
                std::array<io_uring_cqe*, 256> ready {};
                const unsigned count = io_uring_peek_batch_cqe(&ring, ready.data(), batch);
                std::array<unsigned, 256> slots {};
                for (unsigned i = 0; i < count; ++i) {
                    async_lab::Require(ready[i]->res == (sockets.empty() ? 0 : 64),
                                       "raw I/O failed");
                    slots[i] = io_uring_cqe_get_data64(ready[i]) - 1;
                    if (!sockets.empty()) {
                        auto& pair = *sockets.at(slots[i]);
                        const unsigned phase = (total / depth - remaining[slots[i]]) % 4;
                        if (phase % 2)
                            async_lab::Require(pair.input == pair.output, "raw payload mismatch");
                    }
                    if (detailed) latency.Add(async_lab::NowNs() - starts.at(slots[i]));
                }
                io_uring_cq_advance(&ring, count);
                completions += count;
                for (unsigned i = 0; i < count; ++i)
                    if (--remaining.at(slots[i])) submit_one(slots[i]);
            }
            io_uring_queue_exit(&ring);
        }
        const double seconds = (async_lab::NowNs() - start) / 1e9;
        const auto end = async_lab::Usage();
        std::cout << "{\"kind\":\"uring\",\"workload\":\"" << workload << "\",\"mode\":\"" << mode
                  << "\",\"depth\":" << depth << ",\"batch\":" << batch
                  << ",\"detailed\":" << (detailed ? "true" : "false")
                  << ",\"success\":" << completions << ",\"errors\":0,\"seconds\":" << seconds
                  << ",\"ops_s\":" << completions / seconds << ",\"cpu_ns_op\":"
                  << double(async_lab::CpuNs(end) - async_lab::CpuNs(usage)) / total
                  << ",\"submissions\":" << submissions << ",\"waits\":" << waits
                  << ",\"p50_ns\":" << latency.Quantile(.5)
                  << ",\"p95_ns\":" << latency.Quantile(.95)
                  << ",\"p99_ns\":" << latency.Quantile(.99) << ",\"context_switches\":"
                  << end.ru_nvcsw + end.ru_nivcsw - usage.ru_nvcsw - usage.ru_nivcsw << "}\n";
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
