#include "ringserver/io/io_backend.hpp"

#ifdef RINGSERVER_PLATFORM_APPLE
#include "ringserver/io/kqueue_backend.hpp"
#elif defined(RINGSERVER_ENABLE_URING)
#include "ringserver/io/uring_backend.hpp"
#else
// Default to kqueue on Linux if io_uring not enabled
#include "ringserver/io/kqueue_backend.hpp"
#endif

namespace ringserver {

std::unique_ptr<IoBackend> CreateIoBackend() {
#ifdef RINGSERVER_PLATFORM_APPLE
    return std::make_unique<KqueueBackend>();
#elif defined(RINGSERVER_ENABLE_URING)
    return std::make_unique<IoUringBackend>();
#else
    return std::make_unique<KqueueBackend>();
#endif
}

}  // namespace ringserver
