#include "ringserver/io/io_backend.hpp"

#include <stdexcept>
namespace ringserver {
#if defined(RINGSERVER_PLATFORM_APPLE) || defined(RINGSERVER_KQUEUE_COMPAT)
std::unique_ptr<IoBackend> MakeKqueueBackend(unsigned batch, bool dispatch);
#endif
#ifndef RINGSERVER_PLATFORM_APPLE
std::unique_ptr<IoBackend> MakeEpollBackend(unsigned batch, bool recreate);
#endif
#ifdef RINGSERVER_ENABLE_URING
std::unique_ptr<IoBackend> MakeUringBackend(unsigned depth, unsigned batch);
#endif
std::unique_ptr<IoBackend> CreateIoBackend(std::string_view name, [[maybe_unused]] unsigned depth,
                                           unsigned batch) {
#ifdef RINGSERVER_PLATFORM_APPLE
    if (name == "kqueue") return MakeKqueueBackend(batch, false);
#else
    if (name == "epoll") return MakeEpollBackend(batch, false);
    if (name == "epoll-recreate") return MakeEpollBackend(batch, true);
#endif
#ifdef RINGSERVER_KQUEUE_COMPAT
    if (name == "kqueue-compat") return MakeKqueueBackend(batch, false);
    if (name == "kqueue-compat-dispatch") return MakeKqueueBackend(batch, true);
#endif
#ifdef RINGSERVER_ENABLE_URING
    if (name == "uring") return MakeUringBackend(depth, batch);
#endif
    throw std::invalid_argument("backend unavailable; no implicit fallback");
}
} // namespace ringserver
