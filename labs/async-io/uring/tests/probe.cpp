#include <liburing.h>

#include <iostream>
int main() {
    io_uring ring {};
    io_uring_params params {};
    const int result = io_uring_queue_init_params(8, &ring, &params);
    if (result < 0) {
        std::cout << "{\"available\":false,\"errno\":" << -result << "}\n";
        return 77;
    }
    auto* probe = io_uring_get_probe_ring(&ring);
    if (!probe) {
        io_uring_queue_exit(&ring);
        return 1;
    }
    std::cout << "{\"available\":true,\"features\":" << params.features << ",\"opcodes\":[";
    bool first = true;
    for (unsigned i = 0; i < probe->ops_len; ++i) {
        if (probe->ops[i].flags & IO_URING_OP_SUPPORTED) {
            if (!first) std::cout << ',';
            first = false;
            std::cout << unsigned(probe->ops[i].op);
        }
    }
    std::cout << "]}\n";
    io_uring_free_probe(probe);
    io_uring_queue_exit(&ring);
}
