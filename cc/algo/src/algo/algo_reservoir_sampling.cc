#include "../include/fwd.h"

#include <cstdint>
#include <iomanip>
#include <random>

/**
 * 蓄水池采样（Reservoir Sampling）演示，对应 docs/q&a/qa6.md 的 Q2。
 *
 * 题目：内存有限，从未知长度的数据流里均匀抽取 K 条记录。
 * Algorithm R：先留住前 K 条；处理第 i 条时，在前 i 个位置里均匀随机选一个，
 * 落进前 K 个位置就替换。时间 O(N)，空间 O(K)。
 *
 * 这里用可观测的实验把几个结论变成证据：
 *   1. 单机 Algorithm R 确实均匀，且任意前缀结束时池内都是该前缀的均匀 K-样本。
 *   2. 同种子可复现，前提是随机源作为参数注入，而不是藏在全局 / thread_local 里。
 *   3. 把两份 Algorithm R 样本直接合并再抽 K 个并不均匀：分片大小不同即产生偏差，
 *      因为概率只取决于各自分片大小 K/(2*N_i)，与另一分片无关。
 *   4. 换成 bottom-K 键（每个元素独立抽随机优先级，保留最小的 K 个）后，
 *      “各分片 bottom-K 再取全局 bottom-K” 仍然均匀，这才是可并行的版本。
 *   5. 抽样单位是“行”还是“去重后的键”，概率完全不同：重复 100 次的热键
 *      在行级口径下的入选概率约 99.9%，键级口径下只有 10%。
 */

namespace {

// 每个试验用不同的种子，试验之间相互独立，整体又可复现
uint64_t derive_seed(uint64_t trial) { return 0x9e3779b97f4a7c15ULL * (trial + 1); }

int g_failures = 0;

void check(bool ok, const string& what) {
    cout << (ok ? "[PASS] " : "[FAIL] ") << what << "\n";
    if (!ok) ++g_failures;
}

// 二项分布下观测频率偏离理论概率多少个 sigma
double sigma_gap(double observed, double expected, int trials) {
    double sigma = sqrt(expected * (1.0 - expected) / trials);
    return sigma == 0 ? 0.0 : fabs(observed - expected) / sigma;
}

// Algorithm R：单遍扫描，O(K) 空间，不需要知道 N
class ReservoirSampler {
public:
    ReservoirSampler(size_t k, uint64_t seed) : k_(k), seen_(0), rng_(seed) {}

    void add(uint64_t value) {
        ++seen_;
        if (sample_.size() < k_) {
            sample_.push_back(value);
            return;
        }
        // 第 seen_ 条以 k / seen_ 的概率留下：均匀挑一个位置，落进前 k 个才替换
        std::uniform_int_distribution<uint64_t> pick(1, seen_);
        uint64_t slot = pick(rng_);
        if (slot <= k_) sample_[slot - 1] = value;
    }

    const vector<uint64_t>& sample() const { return sample_; }

private:
    size_t k_;
    uint64_t seen_;
    std::mt19937_64 rng_;
    vector<uint64_t> sample_;
};

// bottom-K 键：每个元素独立取一个随机优先级，保留最小的 K 个。
// 与 Algorithm R 的关键差别是可合并：各分片 bottom-K 的并集里取全局最小的 K 个，
// 等价于对全局数据做一次 bottom-K，因此并行后仍然均匀。
class BottomKSampler {
public:
    struct Entry {
        uint64_t key;
        uint64_t value;
        bool operator<(const Entry& other) const { return key < other.key; }
    };

    BottomKSampler(size_t k, uint64_t seed) : k_(k), rng_(seed) {}

    void add(uint64_t value) {
        std::uniform_int_distribution<uint64_t> dist(0, std::numeric_limits<uint64_t>::max());
        Entry e{dist(rng_), value};
        if (heap_.size() < k_) {
            heap_.push(e);
            return;
        }
        if (e.key < heap_.top().key) {
            heap_.pop();
            heap_.push(e);
        }
    }

    vector<Entry> items() const {
        vector<Entry> out;
        auto heap = heap_;  // 大顶堆拷贝一份再出堆，保持采样器本身不变
        while (!heap.empty()) {
            out.push_back(heap.top());
            heap.pop();
        }
        return out;
    }

    static vector<Entry> merge(const vector<vector<Entry>>& parts, size_t k) {
        vector<Entry> all;
        for (const auto& part : parts) all.insert(all.end(), part.begin(), part.end());
        sort(all.begin(), all.end());
        if (all.size() > k) all.resize(k);
        return all;
    }

private:
    size_t k_;
    std::mt19937_64 rng_;
    std::priority_queue<Entry> heap_;  // 堆顶是当前最大的 key，正好用来淘汰
};

double shard_freq(const vector<uint64_t>& hit, size_t from, size_t count, int trials) {
    double sum = 0;
    for (size_t i = from; i < from + count; ++i) sum += double(hit[i]);
    return sum / (double(count) * double(trials));
}

void demo_algorithm_r_uniform() {
    cout << "\n== 演示 1：Algorithm R 单机采样是否均匀 ==\n";
    constexpr size_t kN = 500;
    constexpr size_t kK = 5;
    constexpr int kTrials = 100000;

    vector<uint64_t> hit(kN, 0);
    for (int t = 0; t < kTrials; ++t) {
        ReservoirSampler sampler(kK, derive_seed(t));
        for (size_t i = 0; i < kN; ++i) sampler.add(i);
        // 每个记录只会被放进池一次，所以样本内不会有重复
        assert(sampler.sample().size() == kK);
        for (uint64_t v : sampler.sample()) ++hit[v];
    }

    double expected = double(kK) / double(kN);
    double lo = 1.0, hi = 0.0, worst_sigma = 0.0, sum = 0.0;
    size_t lo_idx = 0, hi_idx = 0;
    for (size_t i = 0; i < kN; ++i) {
        double freq = double(hit[i]) / kTrials;
        sum += freq;
        if (freq < lo) {
            lo = freq;
            lo_idx = i;
        }
        if (freq > hi) {
            hi = freq;
            hi_idx = i;
        }
        worst_sigma = max(worst_sigma, sigma_gap(freq, expected, kTrials));
    }

    cout << "  N=" << kN << ", K=" << kK << ", 试验 " << kTrials << " 轮，理论入选率 K/N = "
         << fixed << setprecision(6) << expected << "\n";
    cout << "  观测最小值 " << lo << "（下标 " << lo_idx << "），最大值 " << hi << "（下标 "
         << hi_idx << "），全体均值 " << sum / double(kN) << "\n";
    cout << "  最大偏离 " << setprecision(2) << worst_sigma << " sigma\n";
    check(worst_sigma < 4.5, "500 个元素的入选率都落在理论值附近，采样均匀");
}

void demo_prefix_invariant() {
    cout << "\n== 演示 2：任意前缀结束时，池内都是该前缀的均匀样本（“在线”语义）==\n";
    constexpr size_t kN = 200;
    constexpr size_t kK = 2;
    constexpr int kTrials = 40000;
    const vector<size_t> checkpoints = {20, 50, 200};

    vector<vector<uint64_t>> hit(checkpoints.size(), vector<uint64_t>(kN, 0));
    for (int t = 0; t < kTrials; ++t) {
        ReservoirSampler sampler(kK, derive_seed(t));
        size_t cp = 0;
        for (size_t i = 1; i <= kN; ++i) {
            sampler.add(i - 1);
            while (cp < checkpoints.size() && checkpoints[cp] == i) {
                for (uint64_t v : sampler.sample()) ++hit[cp][v];
                ++cp;
            }
        }
    }

    bool all_ok = true;
    for (size_t c = 0; c < checkpoints.size(); ++c) {
        size_t n = checkpoints[c];
        double expected = double(kK) / double(n);
        double worst_sigma = 0.0;
        for (size_t i = 0; i < n; ++i) {
            double freq = double(hit[c][i]) / kTrials;
            worst_sigma = max(worst_sigma, sigma_gap(freq, expected, kTrials));
        }
        cout << "  前 " << setw(3) << n << " 条：理论 K/i = " << fixed << setprecision(6)
             << expected << "，最大偏离 " << setprecision(2) << worst_sigma << " sigma\n";
        all_ok = all_ok && worst_sigma < 4.5;
    }
    cout << "  注意：后到的记录会替换早期记录，但任意时刻的池只均匀覆盖“已见前缀”\n";
    check(all_ok, "三个检查点的前缀样本都均匀，说明无需回看历史数据");
}

void demo_reproducible() {
    cout << "\n== 演示 3：抽样可复现 ==\n";
    auto run = [](uint64_t seed) {
        ReservoirSampler sampler(5, seed);
        for (uint64_t i = 0; i < 1000; ++i) sampler.add(i);
        return sampler.sample();
    };
    vector<uint64_t> a = run(42), b = run(42), c = run(43);
    cout << "  seed=42：" << strJoin(a, " ") << "\n";
    cout << "  seed=42：" << strJoin(b, " ") << "\n";
    cout << "  seed=43：" << strJoin(c, " ") << "\n";
    check(a == b, "同种子两次运行完全一致");
    check(a != c, "换种子结果不同（否则说明随机源没被真正用上）");
    cout << "  前提：random seed 必须作为参数传入并随实验一起记录；\n"
            "        若用全局或 thread_local 的随机源，“同种子复现”就退化成“同进程顺序复现”。\n";
}

void demo_naive_merge_bias() {
    cout << "\n== 演示 4：并行处理时直接合并两份 Algorithm R 样本 ==\n";
    constexpr size_t kN1 = 100;
    constexpr size_t kN2 = 1000;
    constexpr size_t kK = 10;
    constexpr int kTrials = 12000;
    const size_t n = kN1 + kN2;

    vector<uint64_t> hit(n, 0);
    std::mt19937_64 shuffle_rng(20261103);
    for (int t = 0; t < kTrials; ++t) {
        ReservoirSampler s1(kK, derive_seed(t) ^ 0x1111ULL);
        ReservoirSampler s2(kK, derive_seed(t) ^ 0x2222ULL);
        for (size_t i = 0; i < kN1; ++i) s1.add(i);
        for (size_t i = 0; i < kN2; ++i) s2.add(kN1 + i);
        vector<uint64_t> pool = s1.sample();
        pool.insert(pool.end(), s2.sample().begin(), s2.sample().end());
        shuffle(pool.begin(), pool.end(), shuffle_rng);
        for (size_t i = 0; i < kK; ++i) ++hit[pool[i]];
    }

    double truth = double(kK) / double(n);
    double f1 = shard_freq(hit, 0, kN1, kTrials);
    double f2 = shard_freq(hit, kN1, kN2, kTrials);
    cout << "  N1=" << kN1 << ", N2=" << kN2 << ", K=" << kK << ", 试验 " << kTrials
         << " 轮；全局均匀口径下每元素入选率 = " << fixed << setprecision(6) << truth << "\n";
    cout << "  shard1 观测 " << f1 << "，理论 K/(2*N1) = " << double(kK) / (2.0 * kN1)
         << "，是全局均匀值的 " << setprecision(2) << f1 / truth << " 倍\n";
    cout << "  shard2 观测 " << setprecision(6) << f2 << "，理论 K/(2*N2) = "
         << setprecision(6) << double(kK) / (2.0 * kN2) << "，是全局均匀值的 "
         << setprecision(2) << f2 / truth << " 倍\n";
    check(f1 > 3.0 * truth && f2 < 0.6 * truth,
          "小分片被过度采样、大分片被压低：直接合并两份样本是有偏的");
}

void demo_bottom_k_merge() {
    cout << "\n== 演示 5：可合并的 bottom-K 键（同一配置）==\n";
    constexpr size_t kN1 = 100;
    constexpr size_t kN2 = 1000;
    constexpr size_t kK = 10;
    constexpr int kTrials = 12000;
    const size_t n = kN1 + kN2;

    vector<uint64_t> hit(n, 0);
    for (int t = 0; t < kTrials; ++t) {
        BottomKSampler s1(kK, derive_seed(t) ^ 0x1111ULL);
        BottomKSampler s2(kK, derive_seed(t) ^ 0x2222ULL);
        for (size_t i = 0; i < kN1; ++i) s1.add(i);
        for (size_t i = 0; i < kN2; ++i) s2.add(kN1 + i);
        for (const auto& e : BottomKSampler::merge({s1.items(), s2.items()}, kK)) ++hit[e.value];
    }

    double truth = double(kK) / double(n);
    double f1 = shard_freq(hit, 0, kN1, kTrials);
    double f2 = shard_freq(hit, kN1, kN2, kTrials);
    cout << "  各分片保留 K=" << kK << " 个最小 key，合并后再取全局最小的 " << kK << " 个\n";
    cout << "  shard1 观测 " << fixed << setprecision(6) << f1 << "，偏离 "
         << setprecision(2) << sigma_gap(f1, truth, kTrials) << " sigma\n";
    cout << "  shard2 观测 " << fixed << setprecision(6) << f2 << "，偏离 "
         << setprecision(2) << sigma_gap(f2, truth, kTrials) << " sigma\n";
    cout << "  理论值对两者都是 " << fixed << setprecision(6) << truth << "\n";
    bool ok = sigma_gap(f1, truth, kTrials) < 4.5 && sigma_gap(f2, truth, kTrials) < 4.5;
    // 每个元素只被抽一次随机数、样本就是 key 最小的 K 个，因此天然满足可合并性
    check(ok, "两个分片大小相差 10 倍仍然均匀：bottom-K 与分片边界无关");
}

void demo_sampling_unit() {
    cout << "\n== 演示 6：抽样单位是“行”还是“去重后的键” ==\n";
    constexpr size_t kDistinct = 100;
    constexpr size_t kHotCopies = 100;
    constexpr size_t kK = 10;
    constexpr int kTrials = 20000;
    const size_t rows = kDistinct - 1 + kHotCopies;  // 99 个普通键各 1 行，加 100 行热键

    int hot_by_row = 0, hot_by_key = 0;
    for (int t = 0; t < kTrials; ++t) {
        ReservoirSampler by_row(kK, derive_seed(t));
        for (size_t i = 0; i < kHotCopies; ++i) by_row.add(0);      // 同一个键重复出现
        for (size_t v = 1; v < kDistinct; ++v) by_row.add(v);
        for (uint64_t v : by_row.sample()) {
            if (v == 0) {
                ++hot_by_row;
                break;
            }
        }

        ReservoirSampler by_key(kK, derive_seed(t) ^ 0x5555ULL);
        for (size_t v = 0; v < kDistinct; ++v) by_key.add(v);  // 先按键去重再抽样
        for (uint64_t v : by_key.sample()) {
            if (v == 0) {
                ++hot_by_key;
                break;
            }
        }
    }

    // 行级口径下样本是 K 行的均匀子集，热键缺席的概率 = C(99,10)/C(199,10)
    double missing = 1.0;
    for (size_t j = 0; j < kK; ++j) {
        missing *= double(rows - kHotCopies - j) / double(rows - j);
    }
    double exact_row = 1.0 - missing;
    double exact_key = double(kK) / double(kDistinct);

    cout << "  共 " << kDistinct << " 个去重键 / " << rows << " 行，键 0 出现 " << kHotCopies
         << " 次，K=" << kK << "\n";
    cout << "  按行抽样：键 0 入选 " << fixed << setprecision(4) << double(hot_by_row) / kTrials
         << "（精确值 " << exact_row << "）\n";
    cout << "  先键去重：" << "键 0 入选 " << double(hot_by_key) / kTrials << "（精确值 "
         << exact_key << "）\n";
    double row_gap = fabs(double(hot_by_row) / kTrials - exact_row);
    double key_gap = fabs(double(hot_by_key) / kTrials - exact_key);
    check(row_gap < 0.01 && key_gap < 0.01, "两种口径的概率相差约 10 倍，必须先声明抽样单位");
    cout << "  结论：题目说“抽 K 条记录”时，重复记录会被重复计数；\n"
            "        若业务要的是“均匀取 K 个不同对象”，必须先按键去重或改用按 key 加权的采样。\n";
}

}  // namespace

int main() {
    cout << "蓄水池采样演示（docs/q&a/qa6.md Q2）\n";
    demo_algorithm_r_uniform();
    demo_prefix_invariant();
    demo_reproducible();
    demo_naive_merge_bias();
    demo_bottom_k_merge();
    demo_sampling_unit();
    cout << "\n" << (g_failures == 0 ? "全部检查通过" : "存在失败检查") << "，失败数 "
         << g_failures << "\n";
    return g_failures == 0 ? 0 : 1;
}
