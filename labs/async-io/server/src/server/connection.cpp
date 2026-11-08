#include "ringserver/server/connection.hpp"

#include <algorithm>
#include <cctype>
#include <cstring>
namespace ringserver {
ParseResult Connection::Parse() {
    std::string_view input(reinterpret_cast<const char*>(read_buf_.data()), read_size_);
    const auto end = input.find("\r\n\r\n");
    if (end == std::string_view::npos)
        return read_cap() == 0 ? ParseResult::kBad : ParseResult::kNeedMore;
    const auto line_end = input.find("\r\n");
    const auto first_line = input.substr(0, line_end);
    if (!first_line.starts_with("GET /") ||
        !(first_line.ends_with(" HTTP/1.1") || first_line.ends_with(" HTTP/1.0")))
        return ParseResult::kBad;
    keep_alive_ = first_line.ends_with(" HTTP/1.1");
    size_t position = line_end + 2;
    while (position < end) {
        const auto next = input.find("\r\n", position);
        auto line = input.substr(position, next - position);
        const auto colon = line.find(':');
        if (colon == std::string_view::npos || colon == 0) return ParseResult::kBad;
        std::string key(line.substr(0, colon));
        std::string value(line.substr(colon + 1));
        auto lower = [](unsigned char c) { return std::tolower(c); };
        std::transform(key.begin(), key.end(), key.begin(), lower);
        std::transform(value.begin(), value.end(), value.begin(), lower);
        if (key == "transfer-encoding") return ParseResult::kBad;
        if (key == "content-length" && value.find_first_not_of(" \t0") != std::string::npos)
            return ParseResult::kBad;
        if (key == "connection") {
            if (value.find("close") != std::string::npos)
                keep_alive_ = false;
            else if (value.find("keep-alive") != std::string::npos)
                keep_alive_ = true;
        }
        position = next + 2;
    }
    const size_t consumed = end + 4;
    read_size_ -= consumed;
    std::memmove(read_buf_.data(), read_buf_.data() + consumed, read_size_);
    return ParseResult::kReady;
}
} // namespace ringserver
