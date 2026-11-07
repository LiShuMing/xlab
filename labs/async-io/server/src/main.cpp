#include <getopt.h>
#include <iostream>

#include "ringserver/server/server.hpp"

namespace {

void PrintUsage(const char* prog) {
    std::cerr << "Usage: " << prog << " [options]\n"
              << "Options:\n"
              << "  -p <port>     Port to listen on (default: 8080)\n"
              << "  -a <addr>     Address to bind (default: 0.0.0.0)\n"
              << "  -t <threads>  Number of threads (default: 1)\n"
              << "  -c <conns>    Max connections (default: 10000)\n"
              << "  -h            Show this help\n";
}

}  // namespace

int main(int argc, char* argv[]) {
    ringserver::ServerConfig config;

    // Parse arguments
    int opt;
    while ((opt = getopt(argc, argv, "p:a:t:c:h")) != -1) {
        switch (opt) {
            case 'p':
                config.port = static_cast<uint16_t>(std::stoi(optarg));
                break;
            case 'a':
                config.address = optarg;
                break;
            case 't':
                config.num_threads = std::stoi(optarg);
                break;
            case 'c':
                config.max_connections = std::stoul(optarg);
                break;
            case 'h':
                PrintUsage(argv[0]);
                return 0;
            default:
                PrintUsage(argv[0]);
                return 1;
        }
    }

    std::cout << "RingServer v0.1.0\n"
              << "===============\n"
              << "Port: " << config.port << "\n"
              << "Address: " << config.address << "\n"
              << "Max connections: " << config.max_connections << "\n\n"
              << "Press Ctrl+C to stop\n\n";

    ringserver::Server server(config);
    auto status = server.Start();

    if (!status.ok()) {
        std::cerr << "Server error: " << status.ToString() << std::endl;
        return 1;
    }

    std::cout << "Server stopped\n";
    return 0;
}
