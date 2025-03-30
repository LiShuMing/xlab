#include "Map.h"
#include "bench.h"
#include "sfc64.h"

BENCHMARK(InsertHugeInt) {
    sfc64 rng(213);

    {
        bench.beginMeasure("insert 100M int");
        Map<int, int> map;
        for (size_t n = 0; n < 100'000'000; ++n) {
            map[static_cast<int>(rng())];
        }
        bench.endMeasure(98841586, map.size());

        bench.beginMeasure("clear 100M int");
        map.clear();
        bench.endMeasure(0, map.size());

        // remember the rng's state so we can remove like we've added
        auto const state = rng.state();
        bench.beginMeasure("reinsert 100M int");
        for (size_t n = 0; n < 100'000'000; ++n) {
            map[static_cast<int>(rng())];
        }
        bench.endMeasure(98843646, map.size());

        rng.state(state);
        bench.beginMeasure("remove 100M int");
        for (size_t n = 0; n < 100'000'000; ++n) {
            map.erase(static_cast<int>(rng()));
        }
        bench.endMeasure(0, map.size());

        bench.beginMeasure("destructor empty map");
    }
    bench.endMeasure(0, 0);
}
