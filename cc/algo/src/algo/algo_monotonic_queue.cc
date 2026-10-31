/**
 * 单调队列 + 单调栈（Monotonic Queue / Stack）
 *
 * 这两兄弟是同一个思想的两种形态：维护一个「单调」的候选集合，
 * 每次把没用的元素及时踢掉，让每个元素最多进出一次，于是总代价 O(n)。
 *
 * 一、单调队列：滑动窗口最值
 *   窗口每往右滑一格，就有一个元素进、一个元素出。暴力做法每格重新扫 k 个元素 => O(n*k)。
 *   关键观察：如果后来的元素比前面的大（求最大值时），那前面那个元素
 *   「又老又小」——它既比不过新来的，还会更早滑出窗口，永远不会再成为答案，可以直接扔掉。
 *   于是队列里剩下的下标，其值单调递减、下标单调递增，队首就是当前窗口最大值。
 *
 * 二、单调栈：下一个更大元素（Next Greater Element）
 *   维护一个「值单调递减」的栈。新元素入栈前，把所有比它小的栈顶弹掉，
 *   被弹掉的元素的「下一个更大元素」正是当前这个新元素。
 *
 * 数据库中的对应物：
 *   - 滑动窗口聚合（window function）的增量维护，就是 running max/min 的单调队列；
 *   - 「找最近一次比当前值大的行」= 股票跨度、会话切分、连续区间归并的边界判定。
 *
 * 复杂度：两种结构都是均摊 O(n)，空间 O(k) / O(n)。
 */

#include "../include/fwd.h"

// ---------------------------------------------------------------------------
// 一、单调队列：窗口最大值 / 最小值
// ---------------------------------------------------------------------------
// 队列里存的是「下标」而不是值，因为要靠下标判断队首是否已经滑出窗口。
vector<int> slidingWindowMax(const vector<int>& a, int k) {
    vector<int> result;
    deque<int> dq;  // 队首 = 当前窗口最大值的下标；内部值单调递减
    for (int i = 0; i < static_cast<int>(a.size()); ++i) {
        // 1. 队尾比当前元素小的，以后都不可能成为最大值，直接弹出
        while (!dq.empty() && a[dq.back()] <= a[i]) dq.pop_back();
        dq.push_back(i);

        // 2. 队首下标滑出窗口左边界，弹出
        if (dq.front() <= i - k) dq.pop_front();

        // 3. 窗口成型后记录答案
        if (i >= k - 1) result.push_back(a[dq.front()]);
    }
    return result;
}

vector<int> slidingWindowMin(const vector<int>& a, int k) {
    vector<int> result;
    deque<int> dq;  // 结构完全对称，只是比较方向反过来：内部值单调递增
    for (int i = 0; i < static_cast<int>(a.size()); ++i) {
        while (!dq.empty() && a[dq.back()] >= a[i]) dq.pop_back();
        dq.push_back(i);
        if (dq.front() <= i - k) dq.pop_front();
        if (i >= k - 1) result.push_back(a[dq.front()]);
    }
    return result;
}

// ---------------------------------------------------------------------------
// 二、单调栈：下一个更大元素
// ---------------------------------------------------------------------------
// 返回每个位置右边第一个严格更大的元素值，没有则填 -1
vector<int> nextGreaterElement(const vector<int>& a) {
    int n = static_cast<int>(a.size());
    vector<int> nextGreater(n, -1);
    stack<int> mono;  // 存下标，对应的值单调递减
    for (int i = 0; i < n; ++i) {
        // 当前元素 a[i] 就是所有比它小的栈顶元素的「下一个更大元素」
        while (!mono.empty() && a[mono.top()] < a[i]) {
            nextGreater[mono.top()] = a[i];
            mono.pop();
        }
        mono.push(i);
    }
    return nextGreater;  // 栈里剩下的元素右边没有更大的，保持 -1
}

int main() {
    const vector<int> a = {1, 3, -1, -3, 5, 3, 6, 7};
    const int k = 3;

    vector<int> maxWin = slidingWindowMax(a, k);
    vector<int> minWin = slidingWindowMin(a, k);
    cout << "[单调队列] 数组: ";
    printVector(a);
    cout << "[单调队列] 窗口 " << k << " 最大值: ";
    printVector(maxWin);
    cout << "[单调队列] 窗口 " << k << " 最小值: ";
    printVector(minWin);

    assert((maxWin == vector<int>{3, 3, 5, 5, 6, 7}));
    assert((minWin == vector<int>{-1, -3, -3, -3, 3, 3}));

    // 暴力对照：每个窗口都重新扫一遍，验证上面的 O(n) 写法
    for (int i = 0; i + k <= static_cast<int>(a.size()); ++i) {
        int mx = a[i], mn = a[i];
        for (int j = i; j < i + k; ++j) {
            mx = max(mx, a[j]);
            mn = min(mn, a[j]);
        }
        assert(maxWin[i] == mx);
        assert(minWin[i] == mn);
    }

    vector<int> nge = nextGreaterElement(a);
    cout << "[单调栈] 下一个更大元素: ";
    printVector(nge);
    assert((nge == vector<int>{3, 5, 5, 5, 6, 6, 7, -1}));

    cout << "algo_monotonic_queue: all checks passed" << endl;
    return 0;
}
