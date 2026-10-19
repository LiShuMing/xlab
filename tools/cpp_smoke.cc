#include <future>
#include <stdexcept>
#include <vector>
#include "wstp/thread_pool.h"
#include "common/consistent_hash/consistent_hash.h"
namespace {
void Require(bool condition) {
    if (!condition) {
        throw std::runtime_error("core smoke check failed");
    }
}
}  // namespace

int main() {
    ConsistentHash ring(32);
    ring.Initialize();
    const auto server = ring.GetServerIndex("quality-smoke");
    Require(!server.empty());
    Require(server == ring.GetServerIndex("quality-smoke"));
    for (bool stealing : {false, true}) {
        wstp::ThreadPool pool(4, stealing);
        std::vector<std::future<int>> results;
        for (int i = 0; i < 100; ++i) results.push_back(pool.Submit([i] { return i * i; }));
        pool.Stop();
        for (int i = 0; i < 100; ++i) Require(results[i].get() == i * i);
        pool.Stop();
        bool rejected = false;
        try { pool.Submit([] { return 42; }).get(); }
        catch (const std::runtime_error&) { rejected = true; }
        Require(rejected);
    }
}
