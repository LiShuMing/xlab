#ifndef RINGSERVER_SERVER_SERVER_HPP_
#define RINGSERVER_SERVER_SERVER_HPP_

#include <atomic>
#include <cstdint>
#include <memory>
#include <string_view>
#include <unordered_map>

#include "ringserver/io/io_backend.hpp"
#include "ringserver/server/connection.hpp"

namespace ringserver {

// Server configuration
struct ServerConfig {
    uint16_t port = 8080;
    std::string_view address = "0.0.0.0";
    int num_threads = 1;
    int timeout_ms = 5000;  // Connection timeout
    size_t max_connections = 10000;
};

// HTTP response template
inline constexpr std::string_view kFixedResponse =
    "HTTP/1.1 200 OK\r\n"
    "Content-Type: text/plain\r\n"
    "Content-Length: 13\r\n"
    "Connection: keep-alive\r\n"
    "\r\n"
    "Hello, World!";

// Main server class
// Runs the event loop and dispatches I/O to the backend
class Server {
public:
    explicit Server(const ServerConfig& config);
    ~Server();

    // Disable copy
    Server(const Server&) = delete;
    Server& operator=(const Server&) = delete;

    // Start the server (blocking)
    // Returns on shutdown signal
    [[nodiscard]] Status Start();

    // Signal server to shutdown
    void Shutdown();

    // Server statistics
    [[nodiscard]] size_t active_connections() const { return connections_.size(); }
    [[nodiscard]] uint64_t total_requests() const { return total_requests_.load(); }

private:
    // Handle incoming connection
    Status HandleAccept(int listen_fd);

    // Handle completed read
    Status HandleRead(Connection* conn, int32_t bytes_read);

    // Handle completed write
    Status HandleWrite(Connection* conn, int32_t bytes_written);

    // Handle closed connection
    void HandleClose(int fd);

    // Clean up stale connections
    void CleanupClosed();

    // Build the fixed 200 OK response
    static std::string_view GetResponse() { return kFixedResponse; }

    ServerConfig config_;
    std::unique_ptr<IoBackend> backend_;
    int listen_fd_ = -1;
    bool running_ = false;
    std::atomic<bool> shutdown_requested_{false};

    // Active connections indexed by fd
    std::unordered_map<int, std::unique_ptr<Connection>> connections_;

    // Connection ID counter
    std::atomic<int64_t> next_conn_id_{1};

    // Statistics
    std::atomic<uint64_t> total_requests_{0};
};

}  // namespace ringserver

#endif  // RINGSERVER_SERVER_SERVER_HPP_
