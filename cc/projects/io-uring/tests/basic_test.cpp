#include <liburing.h>
#include <iostream>

int main() {
    struct io_uring ring;
    int ret = io_uring_queue_init(256, &ring, 0);
    if (ret < 0) {
        std::cerr << "Failed to initialize io_uring: " << ", ret" << ret << std::endl;
        return 1;
    }
    std::cout << "io_uring initialized successfully." << std::endl;
    io_uring_queue_exit(&ring);
    return 0;
}