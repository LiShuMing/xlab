#include <cmath>
#include <cstdlib>
#include <limits>

#include "bench/bench.h"
#include "cases.h"

namespace hashmap_lab {
namespace {
Options Parse(int argc, char** argv) {
    Options options;
    for (int i = 1; i < argc; i += 2) {
        if (i + 1 == argc) throw std::invalid_argument("every option requires a value");
        std::string flag = argv[i], value = argv[i + 1];
        std::size_t used = 0;
        auto integer = [&]() {
            if (value.empty() || value[0] == '-') throw std::invalid_argument("invalid integer");
            auto parsed = std::stoull(value, &used);
            if (used != value.size()) throw std::invalid_argument("invalid integer");
            return parsed;
        };
        auto real = [&]() {
            double parsed = std::stod(value, &used);
            if (used != value.size() || !std::isfinite(parsed))
                throw std::invalid_argument("invalid number");
            return parsed;
        };
        if (flag == "--method")
            options.method = value;
        else if (flag == "--case")
            options.case_name = value;
        else if (flag == "--mode")
            options.mode = value;
        else if (flag == "--distribution")
            options.distribution = value;
        else if (flag == "--n")
            options.size = integer();
        else if (flag == "--seed")
            options.seed = integer();
        else if (flag == "--hit") {
            auto hit = integer();
            if (hit > 100) throw std::invalid_argument("hit must be <=100");
            options.hit = hit;
        } else if (flag == "--repeat") {
            auto repeat = integer();
            if (repeat > 1000) throw std::invalid_argument("repeat must be <=1000");
            options.repeat = repeat;
        } else if (flag == "--batch-ms")
            options.batch_ms = real();
        else if (flag == "--load")
            options.load = real();
        else
            throw std::invalid_argument("unknown option: " + flag);
    }
    if (!options.size || options.size > 10000000 || options.repeat < 1 || options.batch_ms <= 0 ||
        options.batch_ms > 10000 || options.load <= 0 || options.load >= 1) {
        throw std::invalid_argument("invalid size, repeats, batch duration or load");
    }
    if (options.method != "std" && options.method != "linear" && options.method != "sorted" &&
        options.method != "perfect" && options.method != "wide")
        throw std::invalid_argument("unknown method");
    if (options.mode != "lookup" && options.mode != "build-reserved" &&
        options.mode != "build-growing" && options.mode != "churn")
        throw std::invalid_argument("unknown mode");
    if (options.distribution != "uniform" && options.distribution != "hot")
        throw std::invalid_argument("unknown distribution");
    if (options.mode != "lookup" && options.method != "std" && options.method != "linear") {
        throw std::invalid_argument("this strategy supports only fixed-key lookup");
    }
    return options;
}

template <typename Key>
void Run(const Options& options, const Dataset<Key>& data) {
    if (options.method == "std")
        RunMutable<StdMap<Key>>(options, data);
    else if (options.method == "linear")
        RunMutable<LinearMap<Key>>(options, data);
    else if (options.method == "sorted") {
        SortedMap<Key> map(data.keys);
        RunLookup(map, options, data, "sorted-array");
    } else {
#ifdef HASHMAP_HAS_PERFECT
        if constexpr (std::is_same_v<Key, std::string_view>)
            RunPerfect(options, data);
        else
            throw std::invalid_argument("perfect hash needs a compiled string key set");
#else
        throw std::invalid_argument("perfect hash not built: set PERFECT_HASH_ROOT");
#endif
    }
}
} // namespace
} // namespace hashmap_lab

int main(int argc, char** argv) {
    using namespace hashmap_lab;
    try {
        const auto options = Parse(argc, argv);
        PrintHeader();
        if (options.case_name == "uint64")
            Run(options, MakeDataset<std::uint64_t>(options));
        else if (options.case_name == "strings")
            Run(options, MakeDataset<std::string_view>(options));
        else
            Run(options, MakeDataset<std::string_view>(options, FixedKeys(options.case_name)));
    } catch (const std::exception& error) {
        std::cerr << "hashmap_bench: " << error.what() << '\n';
        return EXIT_FAILURE;
    }
}
