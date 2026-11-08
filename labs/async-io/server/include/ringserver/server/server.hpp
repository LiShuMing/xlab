#pragma once
#include <cstdint>
#include <memory>
#include <string>
#include <unordered_map>

#include "async_lab/measure.hpp"
#include "ringserver/io/io_backend.hpp"
#include "ringserver/server/connection.hpp"

namespace ringserver {
struct ServerConfig {
    uint16_t port = 8080;
    std::string address = "127.0.0.1";
#ifdef __APPLE__
    std::string backend = "kqueue";
#else
    std::string backend = "epoll";
#endif
    unsigned depth = 512, batch = 64;
    size_t max_connections = 256;
    bool detailed = true;
    unsigned write_chunk = 0; // Fault injection: cap each submission to force short writes.
};
class Server {
public:
    explicit Server(ServerConfig config);
    ~Server();
    Status Start();

private:
    void Close(int fd);
    Status Read(Connection& connection);
    Status Respond(Connection& connection);
    Status Write(Connection& connection);
    void Snapshot() const;
    ServerConfig config_;
    std::unique_ptr<IoBackend> backend_;
    int listen_fd_ = -1;
    int64_t next_id_ = 1;
    std::unordered_map<int, std::unique_ptr<Connection>> connections_;
    uint64_t accepted_ = 0, successful_ = 0, errors_ = 0, rejected_ = 0;
    uint64_t short_writes_ = 0, bytes_read_ = 0, bytes_written_ = 0, peak_connections_ = 0;
    uint64_t stale_events_ = 0, backpressure_ = 0;
    async_lab::Histogram service_latency_;
};
} // namespace ringserver
