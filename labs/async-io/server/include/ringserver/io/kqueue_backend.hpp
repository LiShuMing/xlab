#pragma once
#include <memory>

#include "ringserver/io/io_backend.hpp"
namespace ringserver {
std::unique_ptr<IoBackend> MakeKqueueBackend(unsigned batch);
} // namespace ringserver
