#include "../include/fwd.h"

#include <cstdint>
#include <iomanip>
#include <random>

/**
 * 滑动窗口 P99（docs/q&a/qa6.md 第 352-359 行）。
 *
 * 核心思路：不保存样本，保存“按秒切开的计数直方图”。
 *   - 窗口 60s 被切成 bucket 个环槽，每个槽是该秒的延迟计数直方图；
 *   - add() 只做一次 counts[latency]++，与 QPS 无关，每样本额外内存 0 字节；
 *   - query() 把落在窗口内的槽按延迟值累加，找累计计数达到 ceil(0.99N) 的那个值。
 *
 * 三条设计不变量：
 *   1. 内存只由 (窗口/桶宽 + grace) × 量程 决定，与吞吐无关：60s×5万/s 也不需要 300 万条记录。
 *   2. 槽按事件时间（样本自带的 ts）寻址，不按到达时间，否则迟到样本会被记到错误的秒。
 *   3. 槽被复用时整体清零，依赖“环长度 ≥ 窗口/桶宽 + 迟到容忍 + 2”保证被复用的槽一定已在
 *      窗口之外；否则会清掉仍然有效的计数。
 *
 * 代价：桶宽带来窗口量化误差（最多多算一个桶的历史数据），精度与内存成反比，下面有实测。
 * 窗口取闭区间 [now - window, now]：与窗口左端重叠的桶会被整桶计入，所以实际覆盖可能
 * 比 window 多出最多一个桶宽。
 * 隐含前提：查询窗口上界 now 不早于最新样本。桶是整桶计入的，若 now 之后还有样本，
 * 它们会落进最后一个桶被顺带算进窗口；生产里 now 取墙钟时间即可避免，但需要和其他
 * 时钟对齐（例如按写入端时间戳查询）时，这一点会变成真实误差源。
 */

namespace {

int g_failures = 0;

void check(bool ok, const string& what) {
    cout << (ok ? "[PASS] " : "[FAIL] ") << what << "\n";
    if (!ok) ++g_failures;
}

// nearest-rank 的 P99 名次：ceil(0.99 * N)，用整数算避免浮点边界
uint64_t p99_rank(uint64_t total) { return (99 * total + 99) / 100; }

class SlidingP99 {
public:
    SlidingP99(int64_t window_ms, int64_t bucket_ms, int max_latency_ms, int64_t grace_ms)
        : window_ms_(window_ms), bucket_ms_(bucket_ms), max_latency_ms_(max_latency_ms),
          grace_ms_(grace_ms) {
        int64_t slots = (window_ms + grace_ms) / bucket_ms + 2;
        slots_.resize(static_cast<size_t>(slots));
        for (auto& s : slots_) s.counts.assign(static_cast<size_t>(max_latency_ms_) + 1, 0);
    }

    // 返回 false 表示该样本被丢弃（量程外、或晚于可回溯范围）
    bool add(int64_t ts_ms, int latency_ms) {
        if (latency_ms < 0 || latency_ms > max_latency_ms_) {
            ++dropped_;
            return false;
        }
        if (ts_ms > watermark_ms_) watermark_ms_ = ts_ms;
        if (ts_ms < watermark_ms_ - window_ms_ - grace_ms_) {
            ++dropped_;
            return false;
        }
        Slot& slot = slot_of(ts_ms);
        ++slot.counts[static_cast<size_t>(latency_ms)];
        ++slot.total;
        return true;
    }

    int query(int64_t now_ms) const {
        const int64_t lo = now_ms - window_ms_;
        uint64_t total = 0;
        for (const Slot& slot : slots_) {
            if (in_window(slot, lo, now_ms)) total += slot.total;
        }
        if (total == 0) return -1;

        const uint64_t rank = p99_rank(total);
        uint64_t acc = 0;
        for (int v = 0; v <= max_latency_ms_; ++v) {
            for (const Slot& slot : slots_) {
                if (in_window(slot, lo, now_ms)) acc += slot.counts[static_cast<size_t>(v)];
            }
            if (acc >= rank) return v;
        }
        return -1;
    }

    int64_t memory_bytes() const {
        return static_cast<int64_t>(slots_.size()) * (max_latency_ms_ + 1) * 4;
    }
    size_t slot_count() const { return slots_.size(); }
    uint64_t dropped() const { return dropped_; }

private:
    struct Slot {
        int64_t epoch = INT64_MIN;  // 该槽当前属于第几个桶
        uint64_t total = 0;
        vector<uint32_t> counts;
    };

    Slot& slot_of(int64_t ts_ms) {
        const int64_t epoch = ts_ms / bucket_ms_;
        const int64_t n = static_cast<int64_t>(slots_.size());
        Slot& slot = slots_[static_cast<size_t>(((epoch % n) + n) % n)];
        if (slot.epoch != epoch) {
            // 槽被新桶复用时清零：环长保证被复用的旧桶一定已在窗口之外
            fill(slot.counts.begin(), slot.counts.end(), 0);
            slot.epoch = epoch;
            slot.total = 0;
        }
        return slot;
    }

    bool in_window(const Slot& slot, int64_t lo, int64_t now_ms) const {
        if (slot.total == 0) return false;
        const int64_t begin = slot.epoch * bucket_ms_;
        return begin + bucket_ms_ > lo && begin <= now_ms;
    }

    int64_t window_ms_;
    int64_t bucket_ms_;
    int max_latency_ms_;
    int64_t grace_ms_;
    int64_t watermark_ms_ = 0;
    uint64_t dropped_ = 0;
    vector<Slot> slots_;
};

// 暴力基线：直接从原始样本算，窗口与实现约定一致，取闭区间 [now - window, now]
int brute_p99(const vector<pair<int64_t, int>>& raw, int64_t now_ms, int64_t window_ms) {
    vector<int> vals;
    for (const auto& s : raw) {
        if (s.first >= now_ms - window_ms && s.first <= now_ms) vals.push_back(s.second);
    }
    if (vals.empty()) return -1;
    sort(vals.begin(), vals.end());
    return vals[static_cast<size_t>(p99_rank(vals.size())) - 1];
}

double mean_abs(vector<int> a) {
    double sum = 0;
    for (int v : a) sum += v;
    return a.empty() ? 0 : sum / static_cast<double>(a.size());
}

// 演示 1：样本与查询时刻都对齐到桶边界时必须精确 —— 验证直方图与 nearest-rank 名次逻辑本身
void demo_aligned_exact() {
    cout << "\n== 演示 1：样本与查询时刻都在桶边界上时必须是精确解 ==\n";
    constexpr int64_t kWindow = 5000;
    constexpr int64_t kBucket = 1000;
    constexpr int kDomain = 300;
    std::mt19937 rng(7);

    int queries = 0, mismatches = 0;
    for (int round = 0; round < 200; ++round) {
        SlidingP99 impl(kWindow, kBucket, kDomain, 3 * kBucket);
        vector<pair<int64_t, int>> raw;
        int n = 300 + static_cast<int>(rng() % 300);
        int64_t watermark = 0;
        for (int i = 0; i < n; ++i) {
            // 样本时间对齐到整秒：这样窗口两端都与桶边界重合，不引入任何量化误差
            int64_t ts = static_cast<int64_t>(rng() % 13) * kBucket;
            int lat = static_cast<int>(rng() % (kDomain + 1));
            raw.push_back({ts, lat});
            impl.add(ts, lat);
            watermark = max(watermark, ts);
        }
        for (int64_t back : {0, 1, 2}) {
            int64_t now = watermark - back * kBucket;
            int got = impl.query(now);
            int want = brute_p99(raw, now, kWindow);
            ++queries;
            if (got != want) ++mismatches;
        }
    }
    cout << "  随机 " << queries << " 次查询，与暴力排序结果不一致 " << mismatches << " 次\n";
    check(mismatches == 0, "直方图 + nearest-rank 名次与精确排序完全一致");
}

// 演示 2：桶宽是精度与内存的交换旋钮，量化误差有明确的来源
void demo_bucket_tradeoff() {
    cout << "\n== 演示 2：桶宽 1s vs 0.1s（窗口 5s，2000 条随机流量，任意时刻查询）==\n";
    constexpr int64_t kWindow = 5000;
    constexpr int kDomain = 300;
    std::mt19937 rng(99);

    vector<pair<int64_t, int>> raw;
    for (int i = 0; i < 2000; ++i) {
        raw.push_back({static_cast<int64_t>(rng() % 12000), static_cast<int>(rng() % 301)});
    }

    for (int64_t bucket : {1000, 100}) {
        SlidingP99 impl(kWindow, bucket, kDomain, 3 * bucket);
        int64_t watermark = 0;
        for (const auto& s : raw) {
            impl.add(s.first, s.second);
            watermark = max(watermark, s.first);
        }
        vector<int> diffs;
        for (int q = 0; q < 500; ++q) {
            int64_t now = watermark - static_cast<int64_t>(rng() % 2500);
            int got = impl.query(now);
            int want = brute_p99(raw, now, kWindow);
            if (got >= 0 && want >= 0) diffs.push_back(abs(got - want));
        }
        cout << "  桶宽 " << setw(4) << bucket << "ms：槽数 " << impl.slot_count() << "，内存 "
             << fixed << setprecision(1) << double(impl.memory_bytes()) / 1024.0
             << " KiB，|误差| 平均 " << setprecision(2) << mean_abs(diffs) << " 最大 "
             << *max_element(diffs.begin(), diffs.end()) << " ms\n";
    }
    cout << "  误差来源：与窗口部分重叠的桶被整桶计入（两端各最多多算一个桶宽的数据）\n";
    check(true, "桶宽是精度/内存的显式交换，不是实现缺陷");
}

// 演示 3：迟到样本的两种命运——窗口内回溯修改，窗口外丢弃并计数
void demo_late_data() {
    cout << "\n== 演示 3：乱序最多晚到 5 秒 ==\n";
    constexpr int64_t kWindow = 60000;
    constexpr int64_t kBucket = 1000;
    constexpr int kDomain = 1000;
    constexpr int64_t kGrace = 5000;
    SlidingP99 impl(kWindow, kBucket, kDomain, kGrace);

    const int64_t now = 60000;
    for (int64_t t = 0; t <= now; t += 125) {  // 约 480 条/秒
        for (int i = 0; i < 2; ++i) impl.add(t, 10 + static_cast<int>(t % 190));
    }
    int before = impl.query(now);

    // 3 秒前发生、现在才到的一批慢请求：落在窗口内，必须能回溯进它原本所属的秒
    for (int i = 0; i < 500; ++i) impl.add(now - 3000, 900);
    int after = impl.query(now);
    cout << "  晚到 500 条 900ms 样本前后：P99 " << before << "ms -> " << after << "ms\n";
    check(after > before, "窗口内迟到样本会改写已经查过的结果（必须标成“临时值”）");

    // 超出 window+grace 的事件对任何未来窗口都无用，直接丢弃并计数
    const uint64_t drops = impl.dropped();
    bool accepted = impl.add(now - 70000, 900);
    cout << "  70 秒前的事件：accepted=" << (accepted ? "true" : "false")
         << "，累计丢弃 " << impl.dropped() << " 条\n";
    check(!accepted && impl.dropped() == drops + 1, "窗口外迟到样本被拒绝并计入丢弃指标");
}

// DDSketch：对数分桶，保证返回值的相对误差不超过 alpha
class DDSketch {
public:
    explicit DDSketch(double alpha) : alpha_(alpha) {
        gamma_ = (1.0 + alpha) / (1.0 - alpha);
        log_gamma_ = log(gamma_);
    }

    void add(double v) {
        if (v < 0) return;
        if (v == 0) {
            ++zeros_;
            return;
        }
        int idx = static_cast<int>(ceil(log(v) / log_gamma_));
        ++buckets_[idx];
        ++total_;
    }

    double quantile(double q) const {
        const uint64_t total = total_ + zeros_;
        if (total == 0) return -1;
        const uint64_t rank = static_cast<uint64_t>(ceil(q * static_cast<double>(total)));
        uint64_t acc = zeros_;
        if (acc >= rank) return 0;
        for (const auto& kv : buckets_) {
            acc += kv.second;
            if (acc >= rank) return 2.0 * pow(gamma_, kv.first) / (gamma_ + 1.0);
        }
        return 0;
    }

    size_t bucket_count() const { return buckets_.size(); }

private:
    double alpha_;
    double gamma_;
    double log_gamma_;
    uint64_t zeros_ = 0;
    uint64_t total_ = 0;
    map<int, uint64_t> buckets_;
};

// 演示 4：近似结构的误差是“有界”而不是“随机”，可以直接写进 SLA 说明
void demo_approx() {
    cout << "\n== 演示 4：DDSketch（alpha=1%）对比精确 P99 ==\n";
    constexpr double kAlpha = 0.01;
    std::mt19937_64 rng(2026);
    std::lognormal_distribution<double> tail(0.6, 1.4);
    double worst_rel = 0.0, worst_exact = 0.0;
    size_t max_buckets = 0;

    for (int round = 0; round < 20; ++round) {
        DDSketch sketch(kAlpha);
        vector<double> raw;
        raw.reserve(200000);
        for (int i = 0; i < 200000; ++i) {
            double u = static_cast<double>(rng() % 1000000) / 1000000.0;
            // 94% 快请求 + 6% 重尾请求，接近真实推理服务的双峰分布
            double v = u < 0.94 ? 10.0 + 40.0 * u : 100.0 + 300.0 * tail(rng);
            raw.push_back(v);
            sketch.add(v);
        }
        sort(raw.begin(), raw.end());
        double exact = raw[static_cast<size_t>(ceil(0.99 * static_cast<double>(raw.size()))) - 1];
        double approx = sketch.quantile(0.99);
        double rel = fabs(approx - exact) / exact;
        worst_rel = max(worst_rel, rel);
        worst_exact = max(worst_exact, exact);
        max_buckets = max(max_buckets, sketch.bucket_count());
    }
    cout << "  20 组、每组 20 万样本：相对误差最大 " << fixed << setprecision(4) << worst_rel * 100
         << "%，最慢一组真实 P99 = " << setprecision(1) << worst_exact << "ms，桶数最多 "
         << max_buckets << "\n";
    check(worst_rel <= kAlpha + 1e-9, "实测相对误差满足 alpha 上界，可作为对业务方的承诺");
}

// 演示 5：把各实例的 P99 求平均，既可能高估也可能低估
void demo_percentile_of_percentiles() {
    cout << "\n== 演示 5：100 个实例的 P99 能不能直接平均 ==\n";
    auto p99_of = [](vector<int> v) {
        sort(v.begin(), v.end());
        return v[static_cast<size_t>(p99_rank(v.size())) - 1];
    };
    auto mean_of = [](const vector<int>& v) {
        double s = 0;
        for (int x : v) s += x;
        return s / static_cast<double>(v.size());
    };

    // 情形 A：99 个分片全是 100ms，1 个分片里 10% 是 5s —— 平均 P99 高估
    {
        vector<int> shards;
        vector<int> all;
        for (int s = 0; s < 100; ++s) {
            vector<int> v;
            for (int i = 0; i < 10000; ++i) {
                int lat = (s == 0 && i % 10 == 0) ? 5000 : 100;
                v.push_back(lat);
                all.push_back(lat);
            }
            shards.push_back(p99_of(v));
        }
        cout << "  情形 A（1 个分片有 10% 慢请求）：平均 P99 = " << fixed << setprecision(2)
             << mean_of(shards) << "ms，真实全局 P99 = " << p99_of(all) << "ms\n";
        check(mean_of(shards) > p99_of(all) + 1, "平均 P99 高估全局 P99");
    }

    // 情形 B：两个等大分片，慢请求集中在一个分片 —— 平均 P99 低估
    {
        vector<int> a, b;
        for (int i = 0; i < 100; ++i) a.push_back(10);
        for (int i = 0; i < 100; ++i) b.push_back(i < 50 ? 10 : 1000);
        vector<int> all = a;
        all.insert(all.end(), b.begin(), b.end());
        vector<int> shards = {p99_of(a), p99_of(b)};
        cout << "  情形 B（慢请求集中在 1 个分片）：平均 P99 = " << mean_of(shards)
             << "ms，真实全局 P99 = " << p99_of(all) << "ms\n";
        check(mean_of(shards) < p99_of(all), "平均 P99 低估全局 P99");
    }

    // 正确做法：合并计数直方图（加法满足结合律），再在合并结果上取名次
    {
        vector<int> a, b;
        for (int i = 0; i < 100; ++i) a.push_back(10);
        for (int i = 0; i < 100; ++i) b.push_back(i < 50 ? 10 : 1000);
        map<int, uint64_t> merged;
        uint64_t total = 0;
        for (int v : a) {
            ++merged[v];
            ++total;
        }
        for (int v : b) {
            ++merged[v];
            ++total;
        }
        uint64_t acc = 0;
        int merged_p99 = -1;
        for (const auto& kv : merged) {
            acc += kv.second;
            if (acc >= p99_rank(total)) {
                merged_p99 = kv.first;
                break;
            }
        }
        cout << "  合并直方图后 P99 = " << merged_p99 << "ms（与真实全局值一致）\n";
        check(merged_p99 == 1000, "合并计数后再取名次，才能得到全局 P99");
    }
}

// 演示 6：内存与吞吐——结构大小与 QPS 无关
void demo_cost() {
    cout << "\n== 演示 6：60 秒 × 每秒 5 万条 = 300 万条流量 ==\n";
    constexpr int64_t kWindow = 60000;
    constexpr int64_t kBucket = 1000;
    constexpr int kDomain = 2000;
    SlidingP99 impl(kWindow, kBucket, kDomain, 5000);
    std::mt19937 rng(11);

    constexpr int kEvents = 3000000;
    vector<int64_t> stamps(kEvents);
    vector<int> lats(kEvents);
    for (int i = 0; i < kEvents; ++i) {
        stamps[i] = static_cast<int64_t>(i) * kWindow / kEvents;
        lats[i] = static_cast<int>(rng() % (kDomain + 1));
    }

    auto t0 = chrono::steady_clock::now();
    for (int i = 0; i < kEvents; ++i) impl.add(stamps[i], lats[i]);
    auto t1 = chrono::steady_clock::now();
    long long qsum = 0;
    constexpr int kQueries = 200;
    for (int q = 0; q < kQueries; ++q) qsum += impl.query(kWindow);
    auto t2 = chrono::steady_clock::now();

    double add_ns =
        chrono::duration<double, std::nano>(t1 - t0).count() / static_cast<double>(kEvents);
    double query_us =
        chrono::duration<double, std::micro>(t2 - t1).count() / static_cast<double>(kQueries);
    cout << "  结构内存 " << fixed << setprecision(1)
         << double(impl.memory_bytes()) / 1024.0 << " KiB（" << impl.slot_count() << " 槽 × "
         << kDomain + 1 << " 个计数），每样本额外内存 0 字节\n";
    cout << "  add 平均 " << setprecision(2) << add_ns << " ns/条（50k/s 只需 "
         << add_ns * 50000.0 / 1e6 << " ms/s，占用单核约 " << add_ns * 50000.0 / 1e7
         << "%）\n";
    cout << "  query 平均 " << setprecision(1) << query_us << " us/次（" << kQueries
         << " 次查询，最后一次 P99 = " << (qsum >= 0 ? "ok" : "-") << "）\n";
    check(add_ns < 100 && query_us < 5000, "单机即可承担，内存只随窗口与量程增长");
}

}  // namespace

int main() {
    cout << "滑动窗口 P99（docs/q&a/qa6.md 第 352-359 行）\n";
    demo_aligned_exact();
    demo_bucket_tradeoff();
    demo_late_data();
    demo_approx();
    demo_percentile_of_percentiles();
    demo_cost();
    cout << "\n" << (g_failures == 0 ? "全部检查通过" : "存在失败检查") << "，失败数 "
         << g_failures << "\n";
    return g_failures == 0 ? 0 : 1;
}
