#include <getopt.h>

#include <iostream>
#include <stdexcept>
#include <string>

#include "ringserver/server/server.hpp"
namespace {
unsigned Parse(const char* value, unsigned maximum) {
    std::string input(value);
    size_t used = 0;
    if (input.empty() || input[0] == '-') throw std::invalid_argument("negative/empty number");
    const auto result = std::stoul(input, &used);
    if (used != input.size() || result > maximum)
        throw std::invalid_argument("number out of range");
    return result;
}
} // namespace
int main(int argc, char** argv) {
    try {
        ringserver::ServerConfig config;
        int option;
        while ((option = getopt(argc, argv, "p:a:b:c:q:B:m:w:t:h")) != -1) {
            switch (option) {
            case 'p':
                config.port = Parse(optarg, 65535);
                break;
            case 'a':
                config.address = optarg;
                break;
            case 'b':
                config.backend = optarg;
                break;
            case 'c':
                config.max_connections = Parse(optarg, 65536);
                break;
            case 'q':
                config.depth = Parse(optarg, 65536);
                break;
            case 'B':
                config.batch = Parse(optarg, 256);
                break;
            case 'm':
                if (std::string(optarg) != "detailed" && std::string(optarg) != "basic")
                    throw std::invalid_argument("metrics: basic|detailed");
                config.detailed = std::string(optarg) == "detailed";
                break;
            case 'w':
                config.write_chunk = Parse(optarg, 65536);
                break;
            case 't':
                if (Parse(optarg, 1024) != 1)
                    throw std::invalid_argument("only one event loop is supported");
                break;
            case 'h':
                std::cout << "Usage: ringserver [-b epoll|epoll-recreate|uring|kqueue|"
                             "kqueue-compat|kqueue-compat-dispatch] "
                             "[-p port] [-a address]\n"
                             " [-c max_connections] [-q ring_depth] [-B completion_batch]\n"
                             " [-m basic|detailed] [-w write_chunk_for_testing] [-t 1]\n"
                             "Default: loopback:8080, epoll, 1024-byte body; SIGUSR1 emits JSON "
                             "metrics.\n";
                return 0;
            default:
                return 2;
            }
        }
        if (optind != argc || !config.max_connections || config.depth < 2 || !config.batch)
            throw std::invalid_argument("invalid arguments");
        if (config.backend == "uring" && config.max_connections >= config.depth)
            throw std::invalid_argument("uring max_connections must be below ring_depth");
        ringserver::Server server(config);
        const auto status = server.Start();
        if (!status.ok()) {
            std::cerr << status.ToString() << '\n';
            return 1;
        }
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
