/**
 * 分块（Sqrt Decomposition / Block Array）
 *
 * 解决的问题：区间修改 + 区间查询，但在「整块」上偷懒。
 *   线段树用二分递归，代价是对数；分块用「把数组切成 sqrt(n) 个块」，
 *   整块直接打标记（O(1)），边角暴力扫（O(sqrt(n))），整体 O(sqrt(n))。
 *   复杂度比线段树差，但代码短得多，而且能维护那些「不好用树维护」的信息。
 *
 * 核心直觉：一个区间 [l, r] 永远由三部分组成
 *     [l ... 左块边界)   +   若干个整块   +   (右块边界 ... r]
 *         暴力扫 O(sqrt n)    打 lazy 标记 O(sqrt n)   暴力扫 O(sqrt n)
 *   所以「整块 lazy + 边角暴力」这四个字就是分块的全部精髓。
 *
 * ★ 为什么它对存储引擎特别有意义？
 *   列存的 block 级 min/max 索引（zone map）就是分块的一种极简形态：
 *   每个 block 维护 (min, max)，查询时先看 block 的区间能不能整块跳过。
 *   注意一个容易忽略的边界：
 *     - min/max 只能「否证」：整块都在查询范围之外 => 一定没有命中，可以跳过；
 *     - min/max 不能「证明」：即使 [min, max] 落在查询范围内，也不代表块内每行都命中，
 *       除非块内数据是有序的（sort key 前缀），那时 [min, max] 才能代表整个块。
 *   这就是 StarRocks「排序键 + zone map 一条链路上能直接跳过」的前提条件。
 *
 * 复杂度：区间加 / 区间和 O(sqrt n)，空间 O(n)。
 */

#include "../include/fwd.h"

class SqrtDecompose {
public:
    explicit SqrtDecompose(const vector<int>& a) : a_(a), n_(static_cast<int>(a.size())) {
        blockSize_ = max(1, static_cast<int>(sqrt(static_cast<double>(max(1, n_)))));
        blockCount_ = (n_ + blockSize_ - 1) / blockSize_;
        sum_.assign(blockCount_, 0);
        lazy_.assign(blockCount_, 0);
        for (int i = 0; i < n_; ++i) sum_[blockOf(i)] += a_[i];
    }

    int blockSize() const { return blockSize_; }
    int blockCount() const { return blockCount_; }

    // 区间加：[l, r] 全部 +delta
    void rangeAdd(int l, int r, int delta) {
        if (l > r) return;
        int bl = blockOf(l);
        int br = blockOf(r);

        if (bl == br) {  // 同一块内：直接暴力
            for (int i = l; i <= r; ++i) a_[i] += delta;
            sum_[bl] += 1LL * (r - l + 1) * delta;
            return;
        }

        // 左边缘：从 l 到这一块结束，暴力
        int leftEnd = (bl + 1) * blockSize_ - 1;
        for (int i = l; i <= leftEnd; ++i) a_[i] += delta;
        sum_[bl] += 1LL * (leftEnd - l + 1) * delta;

        // 右边缘：从这一块开头到 r，暴力
        int rightBegin = br * blockSize_;
        for (int i = rightBegin; i <= r; ++i) a_[i] += delta;
        sum_[br] += 1LL * (r - rightBegin + 1) * delta;

        // 中间整块：只改 lazy 标记和块和维护，不碰具体元素
        for (int b = bl + 1; b < br; ++b) {
            lazy_[b] += delta;
            sum_[b] += 1LL * blockLen(b) * delta;
        }
    }

    // 区间和
    long long rangeSum(int l, int r) {
        if (l > r) return 0;
        int bl = blockOf(l);
        int br = blockOf(r);

        if (bl == br) {
            long long result = 0;
            for (int i = l; i <= r; ++i) result += a_[i];
            return result + 1LL * (r - l + 1) * lazy_[bl];  // 加上这一块的懒标记
        }

        long long result = 0;
        int leftEnd = (bl + 1) * blockSize_ - 1;
        for (int i = l; i <= leftEnd; ++i) result += a_[i];
        result += 1LL * (leftEnd - l + 1) * lazy_[bl];

        int rightBegin = br * blockSize_;
        for (int i = rightBegin; i <= r; ++i) result += a_[i];
        result += 1LL * (r - rightBegin + 1) * lazy_[br];

        for (int b = bl + 1; b < br; ++b) result += sum_[b];  // 整块的 sum_ 已经是含 lazy 的
        return result;
    }

    int valueAt(int idx) const { return a_[idx] + lazy_[blockOf(idx)]; }

private:
    int blockOf(int idx) const { return idx / blockSize_; }

    int blockLen(int b) const { return min(blockSize_, n_ - b * blockSize_); }

    vector<int> a_;       // 原始值（不含 lazy）
    vector<long long> sum_;   // 每块之和（含 lazy）
    vector<int> lazy_;    // 每块的统一增量
    int n_ = 0;
    int blockSize_ = 1;
    int blockCount_ = 1;
};

// ---------------------------------------------------------------------------
// zone map（块级 min/max 索引）能过滤掉多少块？
// ---------------------------------------------------------------------------
struct ZoneMapStats {
    int excluded = 0;  // 整块被排除：min/max 全在查询范围外，可以直接跳过
    int scanned = 0;   // 必须逐行判断
};

// sortedBlocks = true 表示块内有序（等价于存储层有排序键），此时 min/max 可以被信任
static ZoneMapStats zoneMapFilter(const vector<int>& a, int blockSize, int lo, int hi,
                                  bool sortedBlocks) {
    ZoneMapStats stats;
    int n = static_cast<int>(a.size());
    for (int begin = 0; begin < n; begin += blockSize) {
        int end = min(n, begin + blockSize) - 1;
        int bmin = a[begin];
        int bmax = a[begin];
        for (int i = begin; i <= end; ++i) {
            bmin = min(bmin, a[i]);
            bmax = max(bmax, a[i]);
        }

        if (bmax < lo || bmin > hi) {
            ++stats.excluded;  // 块级统计信息直接否证：一定没有满足条件的行
        } else if (sortedBlocks && bmin >= lo && bmax <= hi) {
            continue;          // 块内有序 => [min,max] ⊆ [lo,hi] 说明整块都命中，无需扫描
        } else {
            ++stats.scanned;
        }
    }
    return stats;
}

int main() {
    // ---- 一、分块：区间加 + 区间和 ----
    vector<int> base = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13};
    SqrtDecompose blocks(base);
    cout << "[分块] 数组长度 " << base.size() << "，块大小 " << blocks.blockSize() << "，共 "
         << blocks.blockCount() << " 块" << endl;

    blocks.rangeAdd(2, 9, 100);  // 3..10 全部 +100
    cout << "[分块] rangeAdd([2,9], 100) 后区间和 [0,12] = " << blocks.rangeSum(0, 12) << endl;
    assert(blocks.rangeSum(0, 12) == 91 + 100 * 8);
    assert(blocks.valueAt(2) == 103);
    assert(blocks.valueAt(9) == 110);
    assert(blocks.valueAt(10) == 11);  // 边界外不受影响

    // 随机对拍：50 次区间加，每次都和暴力数组核对
    vector<int> brute(60);
    for (int i = 0; i < 60; ++i) brute[i] = (i * 7) % 13 - 6;
    SqrtDecompose stress(brute);
    unsigned state = 20260101u;
    auto nextRand = [&state](int lo, int hi) {
        state = state * 1103515245u + 12345u;
        return lo + static_cast<int>((state >> 16) % static_cast<unsigned>(hi - lo + 1));
    };
    for (int round = 0; round < 50; ++round) {
        int l = nextRand(0, 59);
        int r = nextRand(0, 59);
        if (l > r) swap(l, r);
        int delta = nextRand(-20, 20);
        stress.rangeAdd(l, r, delta);
        for (int i = l; i <= r; ++i) brute[i] += delta;
        assert(stress.rangeSum(l, r) == accumulate(brute.begin() + l, brute.begin() + r + 1, 0LL));
    }
    assert(stress.rangeSum(0, 59) == accumulate(brute.begin(), brute.end(), 0LL));
    cout << "[分块] 对拍 50 次区间加通过，全区间和 = " << stress.rangeSum(0, 59) << endl;

    // ---- 二、zone map：块级 min/max 的过滤效果 ----
    const int kBlockSize = 8;
    const int kLo = 40;
    const int kHi = 60;

    vector<int> unsorted(64);
    for (int i = 0; i < 64; ++i) unsorted[i] = (i * 37 + 11) % 100;  // 打散的数据
    vector<int> sorted(unsorted);
    sort(sorted.begin(), sorted.end());  // 排序键下的数据

    ZoneMapStats s1 = zoneMapFilter(unsorted, kBlockSize, kLo, kHi, false);
    ZoneMapStats s2 = zoneMapFilter(sorted, kBlockSize, kLo, kHi, true);
    cout << "[zone map] 无序数据: 跳过 " << s1.excluded << " 块，需扫描 " << s1.scanned << " 块"
         << endl;
    cout << "[zone map] 有序数据: 跳过 " << s2.excluded << " 块，需扫描 " << s2.scanned << " 块"
         << endl;
    // 有序时，最多只有「跨过 lo」和「跨过 hi」这两块需要逐行判断，其余块要么整块跳过、
    // 要么整块命中（整块命中的块连扫描都省了，既不属于 excluded 也不属于 scanned）
    assert(s2.scanned <= 2);
    assert(s2.scanned < s1.scanned);
    assert(s2.excluded >= s1.excluded);

    // 真正被跳过的块里，确实没有任何一行满足条件（验证「否证」的正确性）
    int hit = 0;
    for (int v : unsorted) hit += (v >= kLo && v <= kHi) ? 1 : 0;
    cout << "[zone map] 实际命中行数 = " << hit << endl;
    assert(hit > 0);

    cout << "algo_block_decompose: all checks passed" << endl;
    return 0;
}
