#include <iostream>
#include <string>

#include "policies.h"

namespace {
template <typename Policy>
void Probe(Policy& policy, std::size_t capacity) {
    cache_lab::Key key;
    std::string hits;
    while (std::cin >> key) {
        if (hits.size() >= 10000) throw std::invalid_argument("probe trace too long");
        hits += policy.Access(key) ? '1' : '0';
        auto keys = policy.Resident();
        std::sort(keys.begin(), keys.end());
        auto layout = policy.GetLayout();
        if (keys.size() > capacity || layout.history > capacity ||
            std::adjacent_find(keys.begin(), keys.end()) != keys.end())
            throw std::runtime_error("capacity/duplicate invariant");
    }
    auto keys = policy.Resident();
    std::sort(keys.begin(), keys.end());
    std::cout << "{\"hits\":\"" << hits << "\",\"resident\":[";
    for (std::size_t i = 0; i < keys.size(); ++i) {
        if (i) std::cout << ',';
        std::cout << keys[i];
    }
    std::cout << "]}\n";
}
} // namespace
int main(int argc, char** argv) {
    try {
        if (argc != 6) throw std::invalid_argument("algorithm capacity window protected aging");
        std::string algorithm = argv[1];
        auto capacity = std::stoull(argv[2]), window = std::stoull(argv[3]),
             protected_percent = std::stoull(argv[4]), aging = std::stoull(argv[5]);
        if (algorithm == "fifo") {
            cache_lab::Fifo p(capacity);
            Probe(p, capacity);
        } else if (algorithm == "lru") {
            cache_lab::Lru p(capacity);
            Probe(p, capacity);
        } else if (algorithm == "lfu") {
            cache_lab::Lfu p(capacity);
            Probe(p, capacity);
        } else if (algorithm == "slru") {
            cache_lab::Slru p(capacity, protected_percent);
            Probe(p, capacity);
        } else if (algorithm == "wtinylfu") {
            cache_lab::WTinyLfu p(capacity, window, protected_percent, aging);
            Probe(p, capacity);
        } else if (algorithm == "arc") {
            cache_lab::Arc p(capacity);
            Probe(p, capacity);
        } else
            throw std::invalid_argument("unknown algorithm");
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
