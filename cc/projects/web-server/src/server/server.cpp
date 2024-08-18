#include "ringserver/server/server.hpp"

#include <arpa/inet.h>
#include <cstring>
#include <iostream>
#include <signal.h>
#include <sys/event.h>
#include <sys/socket.h>

#include "ringserver/common/likely.hpp"
#include "ringserver/common/util.hpp"

// EV_EOF is not defined on macOS, define it as EVFLAG0
#ifndef EV_EOF
#define EV_EOF 0x1000
#endif

namespace ringserver {

namespace {

// Signal handler for graceful shutdown
volatile sig_atomic_t g_signal_received = 0;

void SignalHandler(int sig) {
    g_signal_received = sig;
}

}  // namespace

Server::Server(const ServerConfig& config)
    : config_(config), backend_(CreateIoBackend()) {}

Server::~Server() {
    Shutdown();
}

Status Server::Start() {
    // Setup signal handlers
    signal(SIGINT, SignalHandler);
    signal(SIGTERM, SignalHandler);
    signal(SIGPIPE, SIG_IGN);

    // Initialize I/O backend
    auto status = backend_->Init();
    if (!status.ok()) {
        std::cerr << "Failed to init backend: " << status.ToString() << std::endl;
        return status;
    }

    // Create listening socket
    listen_fd_ = CreateNonBlockingSocket();
    if (listen_fd_ < 0) {
        return Status::Unknown("Failed to create socket");
    }

    // Bind
    struct sockaddr_in addr;
    std::memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(config_.port);
    if (inet_pton(AF_INET, config_.address.data(), &addr.sin_addr) <= 0) {
        return Status::InvalidArg("Invalid address");
    }

    if (::bind(listen_fd_, reinterpret_cast<struct sockaddr*>(&addr), sizeof(addr)) < 0) {
        return Status::Unknown("Failed to bind");
    }

    // Listen
    if (::listen(listen_fd_, SOMAXCONN) < 0) {
        return Status::Unknown("Failed to listen");
    }

    std::cout << "Server listening on " << config_.address << ":" << config_.port << std::endl;
    std::cout << "Backend: " << backend_->name() << std::endl;

    // Register accept interest
    status = backend_->SubmitAccept(listen_fd_, /*user_data=*/0);
    if (!status.ok()) {
        return status;
    }

    // Main event loop
    running_ = true;
    std::vector<CompletionEvent> events;

    while (running_ && !shutdown_requested_) {
        // Poll for events
        status = backend_->Poll(&events, /*timeout_ms=*/100);
        if (RINGSERVER_UNLIKELY(!status.ok() && !status.IsAgain())) {
            std::cerr << "Poll error: " << status.ToString() << std::endl;
            continue;
        }

        // Process each event
        for (const auto& ev : events) {
            if (ev.fd == listen_fd_ && ev.op == OpKind::kRead) {
                // New connection
                HandleAccept(listen_fd_);
            } else if (ev.fd != listen_fd_) {
                // Connection I/O
                auto it = connections_.find(ev.fd);
                if (it == connections_.end()) {
                    continue;
                }

                Connection* conn = it->second.get();

                if (ev.op == OpKind::kRead) {
                    HandleRead(conn, ev.result);
                } else if (ev.op == OpKind::kWrite) {
                    HandleWrite(conn, ev.result);
                } else if (ev.op == OpKind::kClose || (ev.flags & EV_EOF)) {
                    HandleClose(ev.fd);
                }
            }
        }

        // Periodic cleanup
        CleanupClosed();
    }

    running_ = false;
    return Status::Ok();
}

Status Server::HandleAccept(int listen_fd) {
    struct sockaddr_in client_addr;
    socklen_t addr_len = sizeof(client_addr);

    int client_fd = ::accept(listen_fd,
                             reinterpret_cast<struct sockaddr*>(&client_addr),
                             &addr_len);

    if (client_fd < 0) {
        if (errno == EAGAIN || errno == EWOULDBLOCK) {
            return Status::Again();
        }
        return Status::Unknown(std::strerror(errno));
    }

    // Check connection limit
    if (connections_.size() >= config_.max_connections) {
        ::close(client_fd);
        return Status::Again("Connection limit exceeded");
    }

    // Make non-blocking
    int flags = ::fcntl(client_fd, F_GETFL, 0);
    ::fcntl(client_fd, F_SETFL, flags | O_NONBLOCK);

    // Create connection object
    int64_t conn_id = next_conn_id_++;
    auto conn = std::make_unique<Connection>(client_fd, conn_id);
    connections_[client_fd] = std::move(conn);

    // Register read interest
    Connection* c = connections_[client_fd].get();
    return backend_->SubmitRead(client_fd, c->read_buf(), c->read_cap(), conn_id);
}

Status Server::HandleRead(Connection* conn, int32_t bytes_read) {
    if (bytes_read <= 0) {
        // Connection closed or error
        HandleClose(conn->fd());
        return Status::Ok();
    }

    conn->AddBytesRead(bytes_read);

    // For Phase 0, just send fixed 200 OK response
    // In Phase 2, we'll parse the HTTP request first
    std::string_view response = GetResponse();
    conn->SetResponse(response);
    conn->SetWriting();

    // Submit write
    auto status = backend_->SubmitWrite(conn->fd(), conn->write_buf(), conn->write_len(),
                                         conn->id());
    if (RINGSERVER_UNLIKELY(!status.ok())) {
        HandleClose(conn->fd());
        return status;
    }

    total_requests_++;
    return Status::Ok();
}

Status Server::HandleWrite(Connection* conn, int32_t bytes_written) {
    if (bytes_written <= 0) {
        HandleClose(conn->fd());
        return Status::Ok();
    }

    conn->AddBytesWritten(bytes_written);

    // Check if we sent the full response
    if (static_cast<size_t>(bytes_written) >= conn->write_len()) {
        // Response complete
        if (conn->KeepAlive()) {
            // Prepare for next request
            conn->SetReading();
            auto status = backend_->SubmitRead(conn->fd(), conn->read_buf(),
                                                conn->read_cap(), conn->id());
            return status;
        } else {
            conn->MarkForClosure();
        }
    }

    return Status::Ok();
}

void Server::HandleClose(int fd) {
    auto it = connections_.find(fd);
    if (it != connections_.end()) {
        Connection* conn = it->second.get();
        backend_->SubmitClose(fd, conn->id());
        conn->Close();
        connections_.erase(it);
    }
}

void Server::CleanupClosed() {
    // Remove closed connections from map
    for (auto it = connections_.begin(); it != connections_.end(); ) {
        if (it->second->closed()) {
            it = connections_.erase(it);
        } else {
            ++it;
        }
    }
}

void Server::Shutdown() {
    if (running_) {
        shutdown_requested_ = true;
        running_ = false;
    }

    // Close all connections
    for (auto& [fd, conn] : connections_) {
        conn->Close();
    }
    connections_.clear();

    // Close listen socket
    if (listen_fd_ >= 0) {
        ::close(listen_fd_);
        listen_fd_ = -1;
    }
}

}  // namespace ringserver
