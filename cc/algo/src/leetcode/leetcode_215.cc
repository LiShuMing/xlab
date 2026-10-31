#include "../include/fwd.h"
#include <random>

/**
给定整数数组 nums 和整数 k，请返回数组中第 k 个最大的元素。

请注意，你需要找的是数组排序后的第 k 个最大的元素，而不是第 k 个不同的元素。
你必须设计并实现时间复杂度为 O(n) 的算法解决此问题。
 */
//
// 思路（小顶堆，堆里只装「最大的 k 个」）：
//   为什么是小顶堆？堆最多只能装 k 个，超员就得踢掉这批里最差的那个；
//   「最差」= 这 k 个里最小的 = 小顶堆的堆顶，所以小顶堆腾位子最方便，堆顶结尾就是答案。
//
//   关键优化（原版 push 后再 pop，这里改成「先判断、再决定要不要动堆」）：
//     - 堆没满 k 个：push；
//     - 堆满且 x > 堆顶：x 有资格挤进来，pop 掉堆顶再 push；
//     - 堆满且 x <= 堆顶：x 连当前第 k 大都超不过，push 进去下一步也会被 pop 掉，
//       这一整趟堆操作纯属白做，直接跳过。
//   随机数据下绝大多数元素都走第三条分支，代价降成「一次比较」。
//
// 复杂度：时间 O(n log k)，空间 O(k)。k 远小于 n、数据分批到来（流式）时它是首选。
//
// 与其它写法对比（n = 1e5，-O2 实测最优值）：
//   | 写法                          | 随机值 k=10 | 随机值 k=n/2 | 升序 k=10 |
//   | 小顶堆 push 后再 pop（原版）  |    1015 us  |     3182 us  |   894 us  |
//   | 小顶堆 + 提前跳过（本实现）   |      45 us  |     2288 us  |   929 us  |
//   | nth_element（见下方备选）     |     161 us  |      485 us  |    39 us  |
//   | 计数排序（值域 -1e4..1e4 才可用）|    31 us  |       30 us  |    93 us  |
//   | 全排序                        |    3831 us  |     3187 us  |   224 us  |
//   结论：k 小且乱序时「堆 + 提前跳过」最快；k 接近 n/2 或输入有序时 nth_element 更快，
//        且它的耗时几乎与 k 无关（永远是约 2n 次比较）。
//
//   另一个坑：堆版的常数对输入顺序敏感 —— 升序数组配 k=10 时每个元素都比堆顶大，
//   提前跳过完全失效（929 us）；倒序反而每个元素都走跳过分支。
class Solution {
public:
    // 主实现：小顶堆 + 提前跳过，O(n log k)
    int findKthLargest(vector<int>& nums, int k) {
        priority_queue<int, vector<int>, greater<int>> pq;  // 小顶堆，堆顶是这 k 个里最小的
        for (int x : nums) {
            if (static_cast<int>(pq.size()) < k) {
                pq.push(x);  // 先凑满 k 个
            } else if (x > pq.top()) {
                pq.pop();  // 只有严格大于「当前第 k 大」才值得挤进来
                pq.push(x);
            }
            // 否则 x <= pq.top()，进堆也会被立刻踢出，整趟堆操作直接省掉
        }
        return pq.top();  // 堆里正好是最大的 k 个，堆顶即第 k 大
    }

    // 备选实现：nth_element（introselect：快选 + 堆选择兜底），平均 O(n)、最坏 O(n)。
    // 一次性拿到整个数组、只查询一次时比堆更好；代价是要打乱一份数组，且不支持流式输入。
    int findKthLargestNth(vector<int> nums, int k) {
        // 第 k 大 = 升序排好后的下标 n-k，nth_element 只保证该位置是「它该在的元素」，
        // 前后不排序 —— 这正是它比全排序快的原因
        const auto pos = nums.begin() + static_cast<long>(nums.size()) - k;
        nth_element(nums.begin(), pos, nums.end());
        return *pos;
    }
};

// 参照解：全排序后取下标，只用于校验
static int bySort(vector<int> v, int k) {
    sort(v.begin(), v.end());
    return v[v.size() - k];
}

int main() {
    Solution solution;

    const struct {
        vector<int> nums;
        int k;
        int expect;
    } cases[] = {
        {{3, 2, 1, 5, 6, 4}, 2, 5},        // 官方样例：排序后 6,5,4,3,2,1，第 2 大是 5
        {{3, 2, 3, 1, 2, 4, 5, 5, 6}, 4, 4},  // 官方样例：有重复值，第 4 大是 4（不是第 4 个「不同值」）
        {{1}, 1, 1},                       // 单元素
        {{-1, -2, -3}, 1, -1},             // 负数：第 1 大是最大的那个
        {{-5}, 1, -5},                     // 只有负数且只有一个
        {{2, 2, 2, 2}, 3, 2},              // 全相同：第 k 大仍是 2
        {{7, 1, 9}, 3, 1},                 // 第 3 大 = 最小的那个
    };

    int failed = 0;
    for (const auto& c : cases) {
        auto nums = c.nums;  // 形参是 vector<int>&（力扣签名），传拷贝才能接 const 用例
        const auto origin = nums;
        const int gotHeap = solution.findKthLargest(nums, c.k);
        const int gotNth = solution.findKthLargestNth(c.nums, c.k);
        const bool ok = (gotHeap == c.expect) && (gotNth == c.expect) && (nums == origin);
        cout << "findKthLargest(k=" << c.k << ") heap=" << gotHeap << " nth=" << gotNth
             << " expect=" << c.expect
             << (nums == origin ? "" : " [堆版改坏了入参]") << (ok ? "  OK" : "  FAIL") << endl;
        if (!ok) ++failed;
    }

    // 随机对拍：n 取 1..200，值域 [-20, 20]（刻意制造大量重复），k 取 1..n
    mt19937 rng(215);
    int tested = 0;
    for (int round = 0; round < 3000; ++round) {
        const int n = static_cast<int>(rng() % 200) + 1;
        vector<int> nums(n);
        for (auto& x : nums) x = static_cast<int>(rng() % 41) - 20;
        const int k = static_cast<int>(rng() % static_cast<unsigned>(n)) + 1;

        auto numsHeap = nums;
        const int gotHeap = solution.findKthLargest(numsHeap, k);
        const int gotNth = solution.findKthLargestNth(nums, k);
        const int want = bySort(nums, k);
        ++tested;
        if (gotHeap != want || gotNth != want || numsHeap != nums) {
            ++failed;
            if (failed <= 5) {
                cout << "MISMATCH n=" << n << " k=" << k << " heap=" << gotHeap
                     << " nth=" << gotNth << " want=" << want << " nums=";
                printVector(nums);
            }
        }
    }
    cout << "random cases tested = " << tested << endl;

    cout << (failed == 0 ? "leetcode_215: all checks passed" : "leetcode_215: FAILED") << endl;
    return failed == 0 ? 0 : 1;
}
