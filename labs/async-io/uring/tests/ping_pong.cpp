#include <sys/socket.h>
#include <unistd.h>

#include <array>
#include <async_lab/measure.hpp>
#include <iostream>
#include <liburing/io_service.hpp>
#include <liburing/utils.hpp>
#include <vector>

namespace {
uio::Task<> Peer(uio::IoService& service, int fd, bool initiator) {
    std::array<char, 64> output {}, input {};
    output.fill('x');
    for (int round = 0; round < 100; ++round) {
        for (bool write : {initiator, !initiator}) {
            size_t offset = 0;
            while (offset < output.size()) {
                const int result = write ? co_await service.Write(fd, output.data() + offset,
                                                                  output.size() - offset)
                                         : co_await service.Read(fd, input.data() + offset,
                                                                 input.size() - offset);
                async_lab::Require(result > 0, "short/failed peer transfer");
                offset += result;
            }
            if (!write) async_lab::Require(input == output, "payload mismatch");
        }
    }
}
} // namespace
int main() {
    std::array<int, 2> sockets {-1, -1};
    try {
        async_lab::Require(socketpair(AF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0, sockets.data()) == 0,
                           "socketpair failed");
        uio::IoService service(8);
        std::vector<uio::Task<>> tasks;
        tasks.push_back(Peer(service, sockets[0], true));
        tasks.push_back(Peer(service, sockets[1], false));
        service.RunAll(tasks);
        close(sockets[0]);
        close(sockets[1]);
        std::cout << "PASS 100 socketpair round trips, exact payload verification\n";
    } catch (const std::exception& e) {
        for (int fd : sockets)
            if (fd >= 0) close(fd);
        std::cerr << e.what() << '\n';
        return 1;
    }
}
