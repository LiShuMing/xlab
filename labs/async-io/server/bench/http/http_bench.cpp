#include <arpa/inet.h>
#include <sys/epoll.h>
#include <sys/socket.h>
#include <unistd.h>

#include <array>
#include <async_lab/measure.hpp>
#include <cerrno>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
namespace {
struct Client {
    int fd = -1;
    bool connected = false, stopped = false;
    size_t sent = 0, received = 0;
    uint64_t start = 0;
    std::array<char, 4096> buffer {};
};
} // namespace
int main(int argc, char** argv) {
    int epoll_fd = -1;
    std::vector<Client> clients;
    try {
        if (argc != 4) {
            std::cerr << "Usage: ringserver_bench port connections duration_ms\n";
            return 2;
        }
        const unsigned port = std::stoul(argv[1]), count = std::stoul(argv[2]);
        const unsigned duration = std::stoul(argv[3]);
        async_lab::Require(port > 0 && port <= 65535 && count > 0 && count <= 4096 &&
                                   duration > 0 && duration <= 60000,
                           "invalid arguments");
        const std::string request = "GET / HTTP/1.1\r\nHost: localhost\r\n\r\n";
        const std::string expected =
                "HTTP/1.1 200 OK\r\nContent-Length: 1024\r\n"
                "Connection: keep-alive\r\n\r\n" +
                std::string(1024, 'x');
        epoll_fd = epoll_create1(EPOLL_CLOEXEC);
        async_lab::Require(epoll_fd >= 0, "client epoll init");
        clients.resize(count);
        sockaddr_in address {};
        address.sin_family = AF_INET;
        address.sin_port = htons(port);
        inet_pton(AF_INET, "127.0.0.1", &address.sin_addr);
        const auto start = async_lab::NowNs(), deadline = start + uint64_t(duration) * 1000000;
        const auto usage = async_lab::Usage();
        auto arm = [&](unsigned index, uint32_t events, int command) {
            epoll_event event {};
            event.events = events;
            event.data.u32 = index;
            async_lab::Require(epoll_ctl(epoll_fd, command, clients[index].fd, &event) == 0,
                               "client epoll arm");
        };
        for (unsigned i = 0; i < count; ++i) {
            clients[i].fd = socket(AF_INET, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
            async_lab::Require(clients[i].fd >= 0, "client socket");
            const int result =
                    connect(clients[i].fd, reinterpret_cast<sockaddr*>(&address), sizeof(address));
            async_lab::Require(result == 0 || errno == EINPROGRESS, "client connect");
            arm(i, EPOLLOUT, EPOLL_CTL_ADD);
        }
        uint64_t success = 0, bytes = 0;
        unsigned active = count;
        async_lab::Histogram latency;
        std::array<epoll_event, 256> events {};
        while (active) {
            async_lab::Require(async_lab::NowNs() < deadline + 5000000000ULL,
                               "client drain timeout");
            int n = epoll_wait(epoll_fd, events.data(), events.size(), 100);
            if (n < 0 && errno == EINTR) continue;
            async_lab::Require(n >= 0, "client poll");
            for (int j = 0; j < n; ++j) {
                const unsigned index = events[j].data.u32;
                auto& client = clients[index];
                if (client.stopped) continue;
                if (!client.connected) {
                    int error = 0;
                    socklen_t size = sizeof(error);
                    async_lab::Require(
                            getsockopt(client.fd, SOL_SOCKET, SO_ERROR, &error, &size) == 0 &&
                                    error == 0,
                            "client connection refused");
                    client.connected = true;
                }
                if (events[j].events & EPOLLOUT) {
                    if (!client.sent) client.start = async_lab::NowNs();
                    while (client.sent < request.size()) {
                        ssize_t result = send(client.fd, request.data() + client.sent,
                                              request.size() - client.sent, MSG_NOSIGNAL);
                        if (result < 0 && errno == EINTR) continue;
                        if (result < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) break;
                        async_lab::Require(result > 0, "client send failed");
                        client.sent += result;
                    }
                    if (client.sent == request.size()) arm(index, EPOLLIN, EPOLL_CTL_MOD);
                }
                if (events[j].events & (EPOLLIN | EPOLLHUP | EPOLLERR)) {
                    while (client.received < expected.size()) {
                        ssize_t result = recv(client.fd, client.buffer.data() + client.received,
                                              client.buffer.size() - client.received, 0);
                        if (result < 0 && errno == EINTR) continue;
                        if (result < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) break;
                        async_lab::Require(result > 0, "client unexpected EOF/read error");
                        client.received += result;
                    }
                    if (client.received >= expected.size()) {
                        async_lab::Require(
                                std::string_view(client.buffer.data(), client.received) == expected,
                                "HTTP response/body mismatch");
                        const auto now = async_lab::NowNs();
                        latency.Add(now - client.start);
                        ++success;
                        bytes += client.received;
                        if (now >= deadline) {
                            client.stopped = true;
                            --active;
                            epoll_ctl(epoll_fd, EPOLL_CTL_DEL, client.fd, nullptr);
                        } else {
                            client.sent = 0;
                            client.received = 0;
                            arm(index, EPOLLOUT, EPOLL_CTL_MOD);
                        }
                    }
                }
            }
        }
        const auto end = async_lab::Usage();
        const double seconds = (async_lab::NowNs() - start) / 1e9;
        async_lab::Require(success > 0, "empty benchmark");
        std::cout << "{\"kind\":\"http_client\",\"connections\":" << count
                  << ",\"success\":" << success << ",\"errors\":0,\"seconds\":" << seconds
                  << ",\"requests_s\":" << success / seconds
                  << ",\"mib_s\":" << bytes / seconds / 1048576
                  << ",\"p50_ns\":" << latency.Quantile(.5)
                  << ",\"p95_ns\":" << latency.Quantile(.95)
                  << ",\"p99_ns\":" << latency.Quantile(.99) << ",\"client_cpu_ns_req\":"
                  << double(async_lab::CpuNs(end) - async_lab::CpuNs(usage)) / success << "}\n";
        for (auto& c : clients) close(c.fd);
        close(epoll_fd);
    } catch (const std::exception& e) {
        for (auto& c : clients)
            if (c.fd >= 0) close(c.fd);
        if (epoll_fd >= 0) close(epoll_fd);
        std::cerr << e.what() << '\n';
        return 1;
    }
}
