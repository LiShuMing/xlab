#include "../include/fwd.h"

/**
 * The implementation of the smooth weighted round-robin algorithm.
 *
 * This is a C++ adaptation of the classic Smooth Weighted Round-Robin (SWRR)
 * scheduling algorithm (popularised by nginx), extended with the notion of
 * "sub-queues" and "skip compensation".
 *
 * Conceptually we have several logical sub-queues. Each sub-queue has:
 *   - a fixed weight (bigger weight ⇒ more scheduling opportunities)
 *   - an internal `current` score used by the SWRR algorithm
 *   - a FIFO container that stores actual tasks
 *
 * Smooth WRR core rule:
 *   - On each pick:
 *       for each queue i: current[i] += weight[i]
 *       choose j with maximum current[j]
 *       current[j] -= totalWeight
 *
 * Skip & compensation rule (to better match real-world schedulers):
 *   - If the picked sub-queue is empty, we *still* update its internal
 *     state as usual but record a "skip".
 *   - We then immediately repeat the selection procedure until we find a
 *     non‑empty sub‑queue.
 *   - When a previously skipped sub‑queue becomes non‑empty again, we grant
 *     it extra credit proportional to the number of skips it accumulated.
 *
 * The rules to divide sub-queues are as follows:
 * <ul>
 * <li> The minimum slots of {@code subQueues[i]} is
 *      {@code 2^(lastSubQueueLog2Bound-(NUM_SUB_QUEUES-1-i) )},
 *      that is, the minimum slots of 0~7 sub-queues are
 *      2^(b-7), 2^(b-6), 2^(b-5), 2^(b-4), 2^(b-3), 2^(b-2), 2^(b-1), 2^b,
 *      respectively, where {@code b} denotes {@code lastSubQueueLog2Bound}.
 * <li> The weight of {@code subQueues[i]} is {@code 2.5^(NUM_SUB_QUEUES-1-i)},
 *      that is, the weights of 0~7 sub-queues are
 *      2.5^7, 2.5^6, 2.5^5, 2.5^4, 2.5^3, 2.5^2, 2.5^1, 2.5^0 respectively.
 * </ul>
 *
 * This file focuses on the algorithm itself and a few basic tests /
 * demonstrations in `main()`.
 */

// ---------------------------------------------------------------------------//
// Core data structures
// ---------------------------------------------------------------------------//

struct SlotSubQueue {
    // Logical identifier of this sub-queue.
    int id;

    // Static weight used by smooth WRR.
    double weight;

    // Minimum slots / capacity hint (not strictly required by the algorithm
    // but kept to match the original description).
    size_t min_slots;

    // Internal state for smooth WRR.
    double current = 0.0;

    // Number of times this queue was selected by the scheduler while empty.
    size_t skip_times = 0;

    // Actual payload queue; for demonstration we just store integers.
    std::queue<int> tasks;
};

class SmoothWeightedRoundRobinScheduler {
public:
    explicit SmoothWeightedRoundRobinScheduler(size_t num_sub_queues,
                                               int lastSubQueueLog2Bound = 8)
        : total_weight_(0.0) {
        if (num_sub_queues == 0) {
            throw std::invalid_argument("num_sub_queues must be > 0");
        }
        const size_t NUM_SUB_QUEUES = num_sub_queues;
        sub_queues_.reserve(NUM_SUB_QUEUES);

        // Construct queues according to the description in the comment.
        for (size_t i = 0; i < NUM_SUB_QUEUES; ++i) {
            size_t exp = static_cast<size_t>(
                lastSubQueueLog2Bound - (NUM_SUB_QUEUES - 1 - i));
            size_t min_slots = static_cast<size_t>(1u) << exp;

            double w_exp = static_cast<double>(NUM_SUB_QUEUES - 1 - i);
            double weight = std::pow(2.5, w_exp);

            SlotSubQueue q;
            q.id = static_cast<int>(i);
            q.weight = weight;
            q.min_slots = min_slots;
            q.current = 0.0;
            q.skip_times = 0;

            sub_queues_.push_back(std::move(q));
            total_weight_ += weight;
        }
    }

    size_t size() const { return sub_queues_.size(); }

    /** Set weights for all sub-queues and recalculate total weight. */
    void setWeights(const std::vector<double> &weights) {
        if (weights.size() != sub_queues_.size()) {
            throw std::invalid_argument("setWeights: size mismatch");
        }
        total_weight_ = 0.0;
        for (size_t i = 0; i < sub_queues_.size(); ++i) {
            sub_queues_[i].weight = weights[i];
            total_weight_ += weights[i];
        }
    }

    // Enqueue a task into a specific sub-queue.
    void enqueue(size_t idx, int task) {
        if (idx >= sub_queues_.size()) {
            throw std::out_of_range("sub-queue index out of range");
        }
        sub_queues_[idx].tasks.push(task);
    }

    // Whether all sub-queues are completely empty.
    bool empty() const {
        for (const auto &q : sub_queues_) {
            if (!q.tasks.empty()) return false;
        }
        return true;
    }

    // Try to pick the next task according to smooth WRR with skip
    // compensation. Returns pair<queue_index, task_value>.
    // Throws if all sub-queues are empty.
    std::pair<size_t, int> pick() {
        if (empty()) {
            throw std::runtime_error("No tasks available");
        }

        // Debug trace for first 20 picks and picks around #100 (only when we have 3 queues)
        static int pick_call = 0;
        bool trace = ((pick_call < 20 || (pick_call >= 95 && pick_call < 105)) && sub_queues_.size() == 3);
        if (trace) {
            cout << "[pick#" << pick_call << "] BEFORE: c=[" << sub_queues_[0].current
                 << "," << sub_queues_[1].current << "," << sub_queues_[2].current
                 << "] w=[" << sub_queues_[0].weight << "," << sub_queues_[1].weight
                 << "," << sub_queues_[2].weight << "]"
                 << " total_w=" << total_weight_ << "]" << endl;
        }

        // To avoid infinite loops in pathological states we cap the number of
        // attempts per call by some multiple of the number of queues.
        const size_t max_attempts = sub_queues_.size() * 4;
        size_t attempts = 0;

        while (attempts++ < max_attempts) {
            // Step 1: smooth WRR state update.
            size_t best_index = 0;
            double best_current = std::numeric_limits<double>::lowest();

            for (size_t i = 0; i < sub_queues_.size(); ++i) {
                auto &q = sub_queues_[i];
                q.current += q.weight;
                if (q.current > best_current) {
                    best_current = q.current;
                    best_index = i;
                }
            }

            if (trace) {
                cout << "[pick#" << pick_call << "] AFTER add: best=" << best_index
                     << " c=[" << sub_queues_[0].current << "," << sub_queues_[1].current
                     << "," << sub_queues_[2].current << "]" << endl;
            }

            auto &chosen = sub_queues_[best_index];
            chosen.current -= total_weight_;

            if (trace) {
                cout << "[pick#" << pick_call << "] AFTER sub: best=" << best_index
                     << " c=[" << sub_queues_[0].current << "," << sub_queues_[1].current
                     << "," << sub_queues_[2].current << "]" << endl;
            }

            if (!chosen.tasks.empty()) {
                // If this queue was previously skipped while empty, grant it
                // compensation by boosting its current score. This helps it
                // "catch up" after becoming non‑empty again.
                if (chosen.skip_times > 0) {
                    if (trace) {
                        cout << "  [SKIP COMP: idx=" << best_index
                             << " skip_times=" << chosen.skip_times << " add="
                             << (chosen.skip_times * chosen.weight) << "]" << endl;
                    }
                    chosen.current += chosen.skip_times * chosen.weight;
                    chosen.skip_times = 0;
                }

                int value = chosen.tasks.front();
                chosen.tasks.pop();
                if (trace) {
                    cout << "[pick#" << pick_call << "] PICK idx=" << best_index
                         << " val=" << value << endl;
                }
                ++pick_call;
                return {best_index, value};
            }

            // Empty queue selected: record a skip and try again.
            if (trace) {
                cout << "[pick#" << pick_call << "] EMPTY idx=" << best_index << " skip++" << endl;
            }
            chosen.skip_times++;
        }

        throw std::runtime_error("Failed to pick task after max attempts");
    }

    // Helper to expose the underlying queues for inspection in tests.
    const std::vector<SlotSubQueue> &subQueues() const { return sub_queues_; }

    double totalWeight() const { return total_weight_; }

private:
    std::vector<SlotSubQueue> sub_queues_;
    double total_weight_;
};

// ---------------------------------------------------------------------------//
// Basic tests / demonstrations
// ---------------------------------------------------------------------------//

// Verify that the minimum slots & weights are constructed as specified.
void test_subqueue_layout() {
    cout << "== test_subqueue_layout ==" << endl;
    const size_t NUM = 8;
    int b = 10;
    SmoothWeightedRoundRobinScheduler scheduler(NUM, b);

    const auto &qs = scheduler.subQueues();
    assert(qs.size() == NUM);

    for (size_t i = 0; i < NUM; ++i) {
        size_t expected_slots =
            static_cast<size_t>(1u)
            << static_cast<size_t>(b - (NUM - 1 - i));
        double expected_weight =
            std::pow(2.5, static_cast<double>(NUM - 1 - i));

        cout << "subQueue[" << i << "]: "
             << "min_slots=" << qs[i].min_slots
             << ", weight=" << qs[i].weight << endl;

        assert(qs[i].min_slots == expected_slots);
        // Allow small floating‑point error.
        assert(std::abs(qs[i].weight - expected_weight) < 1e-9);
    }

    cout << "OK: subqueue layout matches specification.\n" << endl;
}

// Check basic smooth WRR behaviour under static load.
void test_basic_smooth_wrr() {
    cout << "== test_basic_smooth_wrr ==" << endl;

    // Create scheduler with 3 sub-queues
    SmoothWeightedRoundRobinScheduler scheduler(3, /*b=*/4);
    scheduler.setWeights({5.0, 2.0, 1.0});

    // Verify weights were set correctly
    auto &qs = scheduler.subQueues();
    cout << "Weights: " << qs[0].weight << " " << qs[1].weight << " " << qs[2].weight
         << " total=" << scheduler.totalWeight() << endl;
    assert(qs[0].weight == 5.0);
    assert(qs[1].weight == 2.0);
    assert(qs[2].weight == 1.0);
    assert(scheduler.totalWeight() == 8.0);

    // Fill each sub-queue with tasks
    const int rounds = 80;
    for (int i = 0; i < rounds; ++i) {
        scheduler.enqueue(0, 1000 + i);
        scheduler.enqueue(1, 2000 + i);
        scheduler.enqueue(2, 3000 + i);
    }

    size_t c0 = 0, c1 = 0, c2 = 0;
    // First, do just 24 picks to verify one full cycle of the 2:1:1 pattern
    cout << "First 24 picks:" << endl;
    for (int i = 0; i < 24; ++i) {
        auto [idx, val] = scheduler.pick();
        cout << "  i=" << i << " idx=" << idx << " val=" << val << endl;
        if (idx == 0) ++c0;
        if (idx == 1) ++c1;
        if (idx == 2) ++c2;
    }
    cout << "After 24 picks: c0=" << c0 << " c1=" << c1 << " c2=" << c2 << endl;
    // With weights 5:2:1 and 24 picks, expect c0=15, c1=6, c2=3 (5:2:1 ratio)
    assert(c0 == 15 && c1 == 6 && c2 == 3);

    // Reset counters and do all picks (80 total since each queue has 80 items)
    c0 = c1 = c2 = 0;
    bool mid_weights_printed = false;
    for (int i = 0; i < 80; ++i) {
        auto [idx, val] = scheduler.pick();
        (void)val;  // unused
        if (idx == 0) ++c0;
        if (idx == 1) ++c1;
        if (idx == 2) ++c2;
        if (!mid_weights_printed && i == 40) {
            auto &qs = scheduler.subQueues();
            cout << "[MID] Weights: " << qs[0].weight << " " << qs[1].weight << " " << qs[2].weight
                 << " total=" << scheduler.totalWeight() << endl;
            mid_weights_printed = true;
        }
    }

    cout << "Dispatch counts: q0=" << c0
         << " q1=" << c1
         << " q2=" << c2 << endl;

    // Weights 5 : 2 : 1 => expect c0/c1 ~ 2.5, c0/c2 ~ 5.
    double r01 = static_cast<double>(c0) / c1;
    double r02 = static_cast<double>(c0) / c2;
    cout << "ratios: c0/c1=" << r01 << " c0/c2=" << r02 << endl;

    assert(r01 > 2.0 && r01 < 3.5);   // ~2.5
    assert(r02 > 4.0 && r02 < 6.5);   // ~5.0

    cout << "OK: smooth WRR roughly matches expected ratios.\n" << endl;
}

// Demonstrate skip compensation: when a heavy queue is empty for a while and
// then becomes non-empty again, it should temporarily be favoured.
void test_skip_compensation() {
    cout << "== test_skip_compensation ==" << endl;

    SmoothWeightedRoundRobinScheduler scheduler(2, /*b=*/4);
    scheduler.setWeights({4.0, 1.0});

    // Initially only queue 1 has work.
    for (int i = 0; i < 20; ++i) {
        scheduler.enqueue(1, 100 + i);
    }

    // Consume some tasks so that queue 0 accumulates skip credit.
    size_t from_q1_before = 0;
    for (int i = 0; i < 10; ++i) {
        auto [idx, val] = scheduler.pick();
        (void)val;
        if (idx == 1) ++from_q1_before;
    }
    cout << "Dispatched " << from_q1_before
         << " tasks from q1 while q0 was empty." << endl;

    // Now queue 0 becomes non-empty.
    for (int i = 0; i < 5; ++i) {
        scheduler.enqueue(0, 200 + i);
    }

    size_t from_q0_after = 0;
    size_t from_q1_after = 0;
    const int picks_after = 8;
    for (int i = 0; i < picks_after; ++i) {
        auto [idx, val] = scheduler.pick();
        (void)val;
        if (idx == 0) ++from_q0_after;
        if (idx == 1) ++from_q1_after;
    }

    cout << "After q0 becomes non-empty, picks: "
         << "q0=" << from_q0_after
         << " q1=" << from_q1_after << endl;

    // With compensation, q0 should get a majority of the next few picks
    // even though q1 still has more backlog.
    assert(from_q0_after > from_q1_after);

    cout << "OK: skip compensation favours the once‑empty heavy queue.\n"
         << endl;
}

// Simple smooth WRR verification (standalone, minimal)
void test_smooth_wrr_standalone() {
    cout << "== test_smooth_wrr_standalone ==" << endl;

    // Manually simulate smooth WRR with weights 5, 2, 1
    struct Peer { double weight; double current; };
    Peer peers[] = {{5.0, 0.0}, {2.0, 0.0}, {1.0, 0.0}};
    const int n = 3;
    const double total = 8.0;

    size_t counts[] = {0, 0, 0};
    const int iterations = 240;  // 80 per peer * 3

    for (int i = 0; i < iterations; ++i) {
        // Add weight to each peer
        for (int j = 0; j < n; ++j) {
            peers[j].current += peers[j].weight;
        }

        // Find max
        int best = 0;
        for (int j = 1; j < n; ++j) {
            if (peers[j].current > peers[best].current) {
                best = j;
            }
        }

        // Subtract total
        peers[best].current -= total;
        counts[best]++;

        if (i < 20) cout << best << " ";
    }
    cout << endl;

    cout << "Counts: " << counts[0] << " " << counts[1] << " " << counts[2] << endl;
    cout << "Ratios: " << (double)counts[0]/counts[1] << " " << (double)counts[0]/counts[2] << endl;

    // With 240 iterations, expect ~150, ~60, ~30 (ratio 5:2:1)
    assert((double)counts[0]/counts[1] > 2.0 && (double)counts[0]/counts[1] < 3.5);
    assert((double)counts[0]/counts[2] > 4.0 && (double)counts[0]/counts[2] < 6.5);
    cout << "OK: standalone test passed" << endl;
}

// Debug test using scheduler directly
void test_scheduler_direct() {
    cout << "== test_scheduler_direct ==" << endl;

    SmoothWeightedRoundRobinScheduler scheduler(3, /*b=*/4);
    scheduler.setWeights({5.0, 2.0, 1.0});

    // Enqueue enough tasks
    for (int i = 0; i < 100; ++i) {
        scheduler.enqueue(0, 1000 + i);
        scheduler.enqueue(1, 2000 + i);
        scheduler.enqueue(2, 3000 + i);
    }

    size_t counts[] = {0, 0, 0};
    const int iterations = 240;

    for (int i = 0; i < iterations; ++i) {
        auto [idx, val] = scheduler.pick();
        counts[idx]++;
    }

    cout << "Counts: " << counts[0] << " " << counts[1] << " " << counts[2] << endl;
    cout << "Ratios: c0/c1=" << (double)counts[0]/counts[1] << " c0/c2=" << (double)counts[0]/counts[2] << endl;

    assert((double)counts[0]/counts[1] > 2.0 && (double)counts[0]/counts[1] < 3.5);
    assert((double)counts[0]/counts[2] > 4.0 && (double)counts[0]/counts[2] < 6.5);
    cout << "OK: scheduler direct test passed" << endl;
}

int main() {
    cout << "[algo_scheduler built " << __DATE__ << " " << __TIME__ << "]" << endl;
    test_subqueue_layout();
    test_basic_smooth_wrr();
    test_skip_compensation();
    cout << "All scheduler tests passed." << endl;
    return 0;
}
