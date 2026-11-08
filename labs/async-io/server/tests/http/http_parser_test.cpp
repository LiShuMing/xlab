#include <async_lab/measure.hpp>
#include <cstring>
#include <iostream>

#include "ringserver/server/connection.hpp"
namespace {
void Feed(ringserver::Connection& connection, std::string_view data) {
    async_lab::Require(data.size() <= connection.read_cap(), "test buffer overflow");
    std::memcpy(connection.read_buf(), data.data(), data.size());
    connection.AddRead(data.size());
}
} // namespace
int main() {
    try {
        using ringserver::ParseResult;
        ringserver::Connection connection(-1, 1);
        Feed(connection, "GET / HTTP/1.1\r\nHost: local");
        async_lab::Require(connection.Parse() == ParseResult::kNeedMore, "partial header accepted");
        Feed(connection, "\r\n\r\nGET / HTTP/1.0\r\nConnection: close\r\n\r\n");
        async_lab::Require(connection.Parse() == ParseResult::kReady && connection.keep_alive(),
                           "HTTP/1.1");
        async_lab::Require(connection.Parse() == ParseResult::kReady && !connection.keep_alive(),
                           "pipeline");
        async_lab::Require(connection.Parse() == ParseResult::kNeedMore, "buffer not consumed");
        for (const auto* bad :
             {"POST / HTTP/1.1\r\n\r\n", "GET / HTTP/1.1\r\nContent-Length: 9\r\n\r\n",
              "GET / HTTP/1.1\r\nTransfer-Encoding: chunked\r\n\r\n",
              "GET / HTTP/1.1\r\nBadHeader\r\n\r\n"}) {
            ringserver::Connection invalid(-1, 2);
            Feed(invalid, bad);
            async_lab::Require(invalid.Parse() == ParseResult::kBad, "invalid request accepted");
        }
        ringserver::Connection oversized(-1, 3);
        Feed(oversized, std::string(16384, 'x'));
        async_lab::Require(oversized.Parse() == ParseResult::kBad, "unbounded request header");
        connection.SetResponse("abcdef");
        connection.AddWritten(2);
        async_lab::Require(
                connection.write_len() == 4 &&
                        std::string_view(reinterpret_cast<const char*>(connection.write_buf()),
                                         4) == "cdef",
                "partial write cursor");
        async_lab::Histogram histogram;
        histogram.Add(1000);
        histogram.Add(100000);
        async_lab::Require(histogram.Quantile(.99) >= 100000 && histogram.Quantile(.99) <= 112500,
                           "histogram bounds");
        std::cout << "PASS partial headers, pipeline, keep-alive, invalid/body rejection, cap, "
                     "write cursor, histogram\n";
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
