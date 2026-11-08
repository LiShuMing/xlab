#include "ringserver/server/server.hpp"

#include <arpa/inet.h>
#include <fcntl.h>
#include <signal.h>
#include <sys/socket.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <iostream>
#include <utility>

namespace ringserver {
namespace {
volatile sig_atomic_t stop_requested = 0;
volatile sig_atomic_t snapshot_requested = 0;
void Signal(int signal) {
    if (signal == SIGUSR1)
        snapshot_requested = 1;
    else
        stop_requested = 1;
}
const std::string& Response(bool keep_alive, bool bad = false) {
    static const std::string ok =
            "HTTP/1.1 200 OK\r\nContent-Length: 1024\r\n"
            "Connection: keep-alive\r\n\r\n" +
            std::string(1024, 'x');
    static const std::string closing =
            "HTTP/1.1 200 OK\r\nContent-Length: 1024\r\n"
            "Connection: close\r\n\r\n" +
            std::string(1024, 'x');
    static const std::string invalid =
            "HTTP/1.1 400 Bad Request\r\nContent-Length: 11\r\n"
            "Connection: close\r\n\r\nBad Request";
    return bad ? invalid : (keep_alive ? ok : closing);
}
} // namespace
Server::Server(ServerConfig config)
        : config_(std::move(config)),
          backend_(CreateIoBackend(config_.backend, config_.depth, config_.batch)) {}
Server::~Server() {
    while (!connections_.empty()) Close(connections_.begin()->first);
    if (listen_fd_ >= 0) {
        const auto status = backend_->SubmitClose(listen_fd_, 0);
        if (!status.ok()) std::cerr << status.ToString() << '\n';
        ::close(listen_fd_);
        listen_fd_ = -1;
    }
    const auto status = backend_->Drain();
    if (!status.ok()) std::cerr << "drain failed: " << status.ToString() << '\n';
}
void Server::Close(int fd) {
    const auto found = connections_.find(fd);
    if (found == connections_.end()) return;
    const auto status = backend_->SubmitClose(fd, found->second->id());
    if (!status.ok()) ++errors_;
    ::shutdown(fd, SHUT_RDWR);
    connections_.erase(found);
}
Status Server::Read(Connection& connection) {
    return backend_->SubmitRead(connection.fd(), connection.read_buf(), connection.read_cap(),
                                connection.id());
}
Status Server::Write(Connection& connection) {
    const size_t size = config_.write_chunk
                                ? std::min<size_t>(connection.write_len(), config_.write_chunk)
                                : connection.write_len();
    return backend_->SubmitWrite(connection.fd(), connection.write_buf(), size, connection.id());
}
Status Server::Respond(Connection& connection) {
    const auto result = connection.Parse();
    if (result == ParseResult::kNeedMore) return Read(connection);
    if (result == ParseResult::kBad) {
        ++errors_;
        connection.invalid_request = true;
        connection.SetResponse(Response(false, true));
    } else
        connection.SetResponse(Response(connection.keep_alive()));
    // One response in flight per connection: reads resume only after the full write.
    ++backpressure_;
    if (config_.detailed && !connection.request_start)
        connection.request_start = async_lab::NowNs();
    return Write(connection);
}
void Server::Snapshot() const {
    const auto usage = async_lab::Usage();
    const auto& b = backend_->stats;
    std::cout << "{\"kind\":\"server_snapshot\",\"backend\":\"" << backend_->name()
              << "\",\"time_ns\":" << async_lab::NowNs() << ",\"success\":" << successful_
              << ",\"errors\":" << errors_ << ",\"accepted\":" << accepted_
              << ",\"rejected\":" << rejected_ << ",\"active\":" << connections_.size()
              << ",\"peak_connections\":" << peak_connections_ << ",\"bytes_read\":" << bytes_read_
              << ",\"bytes_written\":" << bytes_written_ << ",\"short_writes\":" << short_writes_
              << ",\"stale_events\":" << stale_events_ << ",\"read_pauses\":" << backpressure_
              << ",\"submitted\":" << b.submitted << ",\"completed\":" << b.completed
              << ",\"polls\":" << b.polls << ",\"empty_polls\":" << b.empty_polls
              << ",\"submit_calls\":" << b.submit_calls << ",\"eagain\":" << b.retries
              << ",\"queue_full\":" << b.queue_full << ",\"cancelled\":" << b.cancelled
              << ",\"max_pending\":" << b.max_pending
              << ",\"operation_allocations\":" << b.operation_allocations
              << ",\"copied_bytes\":" << b.copied_bytes << ",\"cpu_ns\":" << async_lab::CpuNs(usage)
              << ",\"context_switches\":" << usage.ru_nvcsw + usage.ru_nivcsw
              << ",\"max_rss_kib\":" << usage.ru_maxrss
              << ",\"service_p50_ns\":" << service_latency_.Quantile(.5)
              << ",\"service_p99_ns\":" << service_latency_.Quantile(.99) << "}" << std::endl;
}
Status Server::Start() {
    stop_requested = 0;
    snapshot_requested = 0;
    struct sigaction action {};
    action.sa_handler = Signal;
    sigemptyset(&action.sa_mask);
    sigaction(SIGINT, &action, nullptr);
    sigaction(SIGTERM, &action, nullptr);
    sigaction(SIGUSR1, &action, nullptr);
    signal(SIGPIPE, SIG_IGN);
    auto status = backend_->Init();
    if (!status.ok()) return status;
#ifdef __APPLE__
    listen_fd_ = socket(AF_INET, SOCK_STREAM, 0);
    if (listen_fd_ >= 0 &&
        (fcntl(listen_fd_, F_SETFL, O_NONBLOCK) < 0 || fcntl(listen_fd_, F_SETFD, FD_CLOEXEC) < 0))
        return Status::Unknown("cannot configure listen socket");
#else
    listen_fd_ = socket(AF_INET, SOCK_STREAM | SOCK_NONBLOCK | SOCK_CLOEXEC, 0);
#endif
    if (listen_fd_ < 0) return Status::Unknown(std::strerror(errno));
    int reuse = 1;
    setsockopt(listen_fd_, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));
    sockaddr_in address {};
    address.sin_family = AF_INET;
    address.sin_port = htons(config_.port);
    if (inet_pton(AF_INET, config_.address.c_str(), &address.sin_addr) != 1)
        return Status::InvalidArg("invalid listen address");
    if (bind(listen_fd_, reinterpret_cast<sockaddr*>(&address), sizeof(address)) < 0 ||
        listen(listen_fd_, SOMAXCONN) < 0)
        return Status::Unknown(std::strerror(errno));
    socklen_t length = sizeof(address);
    getsockname(listen_fd_, reinterpret_cast<sockaddr*>(&address), &length);
    status = backend_->SubmitAccept(listen_fd_, 0);
    if (!status.ok()) return status;
    std::cout << "{\"kind\":\"ready\",\"backend\":\"" << backend_->name()
              << "\",\"port\":" << ntohs(address.sin_port) << "}" << std::endl;
    std::vector<CompletionEvent> events;
    uint64_t last_cleanup = async_lab::NowNs();
    while (!stop_requested) {
        if (snapshot_requested) {
            snapshot_requested = 0;
            Snapshot();
        }
        status = backend_->Poll(&events, 50);
        if (status.IsAgain()) continue;
        if (!status.ok()) return status;
        for (const auto& event : events) {
            if (event.op == OpKind::kAccept) {
                status = backend_->SubmitAccept(listen_fd_, 0);
                if (!status.ok()) return status;
                if (event.result < 0) {
                    ++errors_;
                    continue;
                }
                const int fd = event.result;
                if (connections_.size() >= config_.max_connections) {
                    ::close(fd);
                    ++rejected_;
                    continue;
                }
                auto connection = std::make_unique<Connection>(fd, next_id_++);
                connection->last_activity = async_lab::NowNs();
                status = Read(*connection);
                if (status.ok()) {
                    connections_.emplace(fd, std::move(connection));
                    ++accepted_;
                    peak_connections_ = std::max<uint64_t>(peak_connections_, connections_.size());
                } else
                    ++errors_;
                continue;
            }
            const auto found = connections_.find(event.fd);
            if (found == connections_.end() || found->second->id() != event.user_data) {
                ++stale_events_;
                continue;
            }
            auto& connection = *found->second;
            connection.last_activity = async_lab::NowNs();
            if (event.result == -EAGAIN || event.result == -EWOULDBLOCK) {
                ++backend_->stats.retries;
                status = connection.writing() ? Write(connection) : Read(connection);
            } else if (event.result <= 0) {
                if (event.result < 0 && event.result != -ECONNRESET && event.result != -EPIPE)
                    ++errors_;
                Close(event.fd);
                continue;
            } else if (event.op == OpKind::kRead) {
                if (config_.detailed && !connection.request_start)
                    connection.request_start = async_lab::NowNs();
                bytes_read_ += event.result;
                connection.AddRead(event.result);
                status = Respond(connection);
            } else {
                bytes_written_ += event.result;
                if (size_t(event.result) < connection.write_len()) ++short_writes_;
                connection.AddWritten(event.result);
                if (connection.write_len())
                    status = Write(connection);
                else {
                    if (!connection.invalid_request) ++successful_;
                    if (config_.detailed)
                        service_latency_.Add(async_lab::NowNs() - connection.request_start);
                    connection.request_start = 0;
                    connection.FinishWrite();
                    if (!connection.keep_alive()) {
                        Close(event.fd);
                        continue;
                    }
                    status =
                            Respond(connection); // Consume a pipelined header before reading again.
                }
            }
            if (!status.ok()) {
                ++errors_;
                Close(event.fd);
            }
        }
        // Bounded slow-client retention, outside the per-event fast path.
        const auto now = async_lab::NowNs();
        if (now - last_cleanup >= 1000000000ULL) {
            for (auto it = connections_.begin(); it != connections_.end();) {
                const int fd = it->first;
                const bool expired = now - it->second->last_activity > 5000000000ULL;
                ++it;
                if (expired) {
                    ++rejected_;
                    Close(fd);
                }
            }
            last_cleanup = now;
        }
    }
    // Cancel and drain while connection buffers are still valid.
    while (!connections_.empty()) Close(connections_.begin()->first);
    status = backend_->SubmitClose(listen_fd_, 0);
    if (!status.ok()) return status;
    ::close(listen_fd_);
    listen_fd_ = -1;
    status = backend_->Drain();
    Snapshot();
    return status;
}
} // namespace ringserver
