#include <cstdio>
#include <cstdint>
#include <cassert>

int main() {
    static char buf[1 << 20];
    int bpos = 0, blen = 0;

    auto nextc = [&]() -> int {
        if (bpos >= blen) { blen = (int)fread(buf, 1, sizeof(buf), stdin); bpos = 0; }
        return blen > 0 ? (unsigned char)buf[bpos++] : -1;
    };

    uint64_t sum = 0;
    uint64_t count = 0;

    int c = nextc();
    while (c >= 0) {
        assert(c >= '0' && c <= '9');
        uint64_t v = 0;
        while (c >= '0' && c <= '9') {
            v = v * 10 + (uint64_t)(c - '0');
            assert(v <= 2147483647ULL);
            c = nextc();
        }
        assert(c == '\n');
        sum += v;
        ++count;
        c = nextc();
    }

    assert(count == 50'000'000ULL);

    printf("%lu\n", sum);
    return 0;
}
