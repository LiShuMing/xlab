# 算法与设计题精编

> 本文整理了技术面试中的常见算法题和系统设计题，涵盖数据结构、算法思想、海量数据处理、系统设计等内容。

---

## 一、基础数据结构题

### 1.1 数组与链表

#### 链表反转
```cpp
// 迭代版本
ListNode* reverseList(ListNode* head) {
    ListNode *prev = nullptr, *curr = head;
    while (curr) {
        ListNode* next = curr->next;
        curr->next = prev;
        prev = curr;
        curr = next;
    }
    return prev;
}

// 递归版本
ListNode* reverseList(ListNode* head) {
    if (!head || !head->next) return head;
    ListNode* newHead = reverseList(head->next);
    head->next->next = head;
    head->next = nullptr;
    return newHead;
}
```

#### 链表判环与找入口
```cpp
// 快慢指针判环
bool hasCycle(ListNode* head) {
    ListNode *slow = head, *fast = head;
    while (fast && fast->next) {
        slow = slow->next;
        fast = fast->next->next;
        if (slow == fast) return true;
    }
    return false;
}

// 找环的入口
ListNode* detectCycle(ListNode* head) {
    ListNode *slow = head, *fast = head;
    while (fast && fast->next) {
        slow = slow->next;
        fast = fast->next->next;
        if (slow == fast) {
            // 相遇后，一个指针回到头，同速前进
            ListNode* ptr = head;
            while (ptr != slow) {
                ptr = ptr->next;
                slow = slow->next;
            }
            return ptr;  // 入口
        }
    }
    return nullptr;
}
```
**数学证明**：设头到入口距离为 a，环长为 b，相遇时慢指针走了 a + c，快指针走了 a + c + kb。因为快指针速度是 2 倍，有 2(a + c) = a + c + kb，得 a = kb - c = (k-1)b + (b - c)。

#### 删除链表倒数第 N 个节点
```cpp
ListNode* removeNthFromEnd(ListNode* head, int n) {
    ListNode dummy(0, head);
    ListNode *slow = &dummy, *fast = &dummy;
    
    // fast 先走 n+1 步
    for (int i = 0; i <= n; i++) {
        fast = fast->next;
    }
    
    // 一起走到 fast 为 nullptr
    while (fast) {
        slow = slow->next;
        fast = fast->next;
    }
    
    // slow->next 就是要删除的节点
    slow->next = slow->next->next;
    return dummy.next;
}
```

#### 合并 K 个有序链表
```cpp
// 优先队列解法 O(N log K)
ListNode* mergeKLists(vector<ListNode*>& lists) {
    auto cmp = [](ListNode* a, ListNode* b) { return a->val > b->val; };
    priority_queue<ListNode*, vector<ListNode*>, decltype(cmp)> pq(cmp);
    
    for (auto list : lists) {
        if (list) pq.push(list);
    }
    
    ListNode dummy(0);
    ListNode* tail = &dummy;
    
    while (!pq.empty()) {
        ListNode* node = pq.top(); pq.pop();
        tail->next = node;
        tail = node;
        if (node->next) pq.push(node->next);
    }
    
    return dummy.next;
}
```

### 1.2 二叉树

#### 二叉树遍历
```cpp
// 前序遍历（递归）
void preorder(TreeNode* root, vector<int>& res) {
    if (!root) return;
    res.push_back(root->val);
    preorder(root->left, res);
    preorder(root->right, res);
}

// 前序遍历（迭代）
vector<int> preorder(TreeNode* root) {
    vector<int> res;
    stack<TreeNode*> stk;
    if (root) stk.push(root);
    
    while (!stk.empty()) {
        TreeNode* node = stk.top(); stk.pop();
        res.push_back(node->val);
        if (node->right) stk.push(node->right);  // 先右后左
        if (node->left) stk.push(node->left);
    }
    return res;
}
```

#### 二叉树层序遍历
```cpp
vector<vector<int>> levelOrder(TreeNode* root) {
    vector<vector<int>> res;
    if (!root) return res;
    
    queue<TreeNode*> q;
    q.push(root);
    
    while (!q.empty()) {
        int size = q.size();
        vector<int> level;
        for (int i = 0; i < size; i++) {
            TreeNode* node = q.front(); q.pop();
            level.push_back(node->val);
            if (node->left) q.push(node->left);
            if (node->right) q.push(node->right);
        }
        res.push_back(level);
    }
    return res;
}
```

#### 最近公共祖先 (LCA)
```cpp
TreeNode* lowestCommonAncestor(TreeNode* root, TreeNode* p, TreeNode* q) {
    if (!root || root == p || root == q) return root;
    
    TreeNode* left = lowestCommonAncestor(root->left, p, q);
    TreeNode* right = lowestCommonAncestor(root->right, p, q);
    
    if (left && right) return root;  // p 和 q 在左右子树
    return left ? left : right;      // 都在左或都在右
}
```

### 1.3 栈与队列

#### 两个栈实现队列
```cpp
class MyQueue {
    stack<int> inStack, outStack;
    
    void transfer() {
        while (!inStack.empty()) {
            outStack.push(inStack.top());
            inStack.pop();
        }
    }
    
public:
    void push(int x) { inStack.push(x); }
    
    int pop() {
        if (outStack.empty()) transfer();
        int x = outStack.top(); outStack.pop();
        return x;
    }
    
    int peek() {
        if (outStack.empty()) transfer();
        return outStack.top();
    }
    
    bool empty() { return inStack.empty() && outStack.empty(); }
};
```

#### 最小栈
```cpp
class MinStack {
    stack<int> data;
    stack<int> mins;  // 同步压入当前最小值
    
public:
    void push(int x) {
        data.push(x);
        if (mins.empty() || x <= mins.top()) {
            mins.push(x);
        } else {
            mins.push(mins.top());
        }
    }
    
    void pop() {
        data.pop();
        mins.pop();
    }
    
    int top() { return data.top(); }
    int getMin() { return mins.top(); }
};
```

---

## 二、经典算法

### 2.1 排序算法

| 算法 | 时间复杂度 | 空间复杂度 | 稳定性 | 适用场景 |
|------|-----------|-----------|--------|---------|
| 快速排序 | O(n log n) | O(log n) | 不稳定 | 通用，平均性能最好 |
| 归并排序 | O(n log n) | O(n) | 稳定 | 链表排序，外部排序 |
| 堆排序 | O(n log n) | O(1) | 不稳定 | 内存受限 |
| 插入排序 | O(n²) | O(1) | 稳定 | 小数组 |
| 计数排序 | O(n + k) | O(k) | 稳定 | 数据范围小 |

#### 快速排序
```cpp
void quickSort(vector<int>& nums, int left, int right) {
    if (left >= right) return;
    
    int pivot = partition(nums, left, right);
    quickSort(nums, left, pivot - 1);
    quickSort(nums, pivot + 1, right);
}

int partition(vector<int>& nums, int left, int right) {
    int pivot = nums[right];
    int i = left;
    
    for (int j = left; j < right; j++) {
        if (nums[j] < pivot) {
            swap(nums[i], nums[j]);
            i++;
        }
    }
    swap(nums[i], nums[right]);
    return i;
}
```

#### 归并排序
```cpp
void mergeSort(vector<int>& nums, int left, int right) {
    if (left >= right) return;
    
    int mid = left + (right - left) / 2;
    mergeSort(nums, left, mid);
    mergeSort(nums, mid + 1, right);
    merge(nums, left, mid, right);
}

void merge(vector<int>& nums, int left, int mid, int right) {
    vector<int> temp(right - left + 1);
    int i = left, j = mid + 1, k = 0;
    
    while (i <= mid && j <= right) {
        if (nums[i] <= nums[j]) temp[k++] = nums[i++];
        else temp[k++] = nums[j++];
    }
    
    while (i <= mid) temp[k++] = nums[i++];
    while (j <= right) temp[k++] = nums[j++];
    
    for (int p = 0; p < k; p++) {
        nums[left + p] = temp[p];
    }
}
```

### 2.2 动态规划

#### 最长递增子序列 (LIS)
```cpp
// O(n²) 解法
int lengthOfLIS(vector<int>& nums) {
    int n = nums.size();
    vector<int> dp(n, 1);  // dp[i] 表示以 nums[i] 结尾的 LIS 长度
    
    for (int i = 1; i < n; i++) {
        for (int j = 0; j < i; j++) {
            if (nums[i] > nums[j]) {
                dp[i] = max(dp[i], dp[j] + 1);
            }
        }
    }
    return *max_element(dp.begin(), dp.end());
}

// O(n log n) 解法（二分优化）
int lengthOfLIS(vector<int>& nums) {
    vector<int> tails;
    for (int num : nums) {
        auto it = lower_bound(tails.begin(), tails.end(), num);
        if (it == tails.end()) tails.push_back(num);
        else *it = num;
    }
    return tails.size();
}
```

#### 背包问题
```cpp
// 0/1 背包
int knapsack(vector<int>& weights, vector<int>& values, int W) {
    int n = weights.size();
    vector<vector<int>> dp(n + 1, vector<int>(W + 1, 0));
    
    for (int i = 1; i <= n; i++) {
        for (int w = 0; w <= W; w++) {
            if (weights[i-1] <= w) {
                dp[i][w] = max(dp[i-1][w], 
                              dp[i-1][w-weights[i-1]] + values[i-1]);
            } else {
                dp[i][w] = dp[i-1][w];
            }
        }
    }
    return dp[n][W];
}

// 空间优化
int knapsack(vector<int>& weights, vector<int>& values, int W) {
    vector<int> dp(W + 1, 0);
    for (int i = 0; i < weights.size(); i++) {
        for (int w = W; w >= weights[i]; w--) {  // 倒序！
            dp[w] = max(dp[w], dp[w-weights[i]] + values[i]);
        }
    }
    return dp[W];
}
```

#### 打家劫舍
```cpp
// 不能偷相邻的房子
int rob(vector<int>& nums) {
    int n = nums.size();
    if (n == 0) return 0;
    if (n == 1) return nums[0];
    
    vector<int> dp(n);
    dp[0] = nums[0];
    dp[1] = max(nums[0], nums[1]);
    
    for (int i = 2; i < n; i++) {
        dp[i] = max(dp[i-1], dp[i-2] + nums[i]);
    }
    return dp[n-1];
}
```

### 2.3 双指针与滑动窗口

#### 两数之和
```cpp
vector<int> twoSum(vector<int>& nums, int target) {
    unordered_map<int, int> map;
    for (int i = 0; i < nums.size(); i++) {
        int complement = target - nums[i];
        if (map.count(complement)) {
            return {map[complement], i};
        }
        map[nums[i]] = i;
    }
    return {};
}
```

#### 滑动窗口最大值
```cpp
vector<int> maxSlidingWindow(vector<int>& nums, int k) {
    deque<int> dq;  // 存储下标，保持单调递减
    vector<int> res;
    
    for (int i = 0; i < nums.size(); i++) {
        // 移除窗口外的元素
        if (!dq.empty() && dq.front() <= i - k) {
            dq.pop_front();
        }
        
        // 保持单调递减
        while (!dq.empty() && nums[dq.back()] <= nums[i]) {
            dq.pop_back();
        }
        
        dq.push_back(i);
        
        // 记录结果
        if (i >= k - 1) {
            res.push_back(nums[dq.front()]);
        }
    }
    return res;
}
```

### 2.4 二分查找

```cpp
// 标准二分查找（找目标值）
int binarySearch(vector<int>& nums, int target) {
    int left = 0, right = nums.size() - 1;
    while (left <= right) {
        int mid = left + (right - left) / 2;
        if (nums[mid] == target) return mid;
        else if (nums[mid] < target) left = mid + 1;
        else right = mid - 1;
    }
    return -1;
}

// 找左边界（第一个 ≥ target 的位置）
int lowerBound(vector<int>& nums, int target) {
    int left = 0, right = nums.size();
    while (left < right) {
        int mid = left + (right - left) / 2;
        if (nums[mid] < target) left = mid + 1;
        else right = mid;
    }
    return left;
}

// 找右边界（最后一个 ≤ target 的位置）
int upperBound(vector<int>& nums, int target) {
    int left = 0, right = nums.size();
    while (left < right) {
        int mid = left + (right - left) / 2;
        if (nums[mid] <= target) left = mid + 1;
        else right = mid;
    }
    return left - 1;
}
```

---

## 三、海量数据处理

### 3.1 Top K 问题

**问题**：1T 文件，内存 1GB，找出现频率最高的 10 个词。

**解决方案**：
1. **分治**：将 1T 文件哈希分成 1000 个小文件（每个约 1GB）
2. **局部统计**：每个小文件用 HashMap 统计词频
3. **小顶堆**：维护大小为 10 的小顶堆，找每个文件的 Top 10
4. **全局合并**：合并所有文件的 Top 10，再用小顶堆找全局 Top 10

```cpp
// 小顶堆找 Top K
vector<string> topKFrequent(vector<string>& words, int k) {
    unordered_map<string, int> freq;
    for (auto& w : words) freq[w]++;
    
    auto cmp = [](pair<string, int>& a, pair<string, int>& b) {
        return a.second > b.second;  // 小顶堆
    };
    priority_queue<pair<string, int>, vector<pair<string, int>>, decltype(cmp)> pq(cmp);
    
    for (auto& p : freq) {
        pq.push(p);
        if (pq.size() > k) pq.pop();
    }
    
    vector<string> res;
    while (!pq.empty()) {
        res.push_back(pq.top().first);
        pq.pop();
    }
    reverse(res.begin(), res.end());
    return res;
}
```

### 3.2 去重问题

**问题**：海量 URL 去重。

**解决方案**：
1. **Hash 分片**：将 URL 哈希到不同文件
2. **布隆过滤器**：快速判断可能存在或肯定不存在
3. **Bitmap**：如果数据范围可控，使用位图

### 3.3 一致性哈希

**解决的问题**：分布式缓存中，节点增减时减少数据迁移。

**原理**：
- 将节点和数据都哈希到一个环上（0 ~ 2^32-1）
- 数据存储在顺时针方向的第一个节点
- 虚拟节点解决数据倾斜

**优点**：
- 节点增减只影响相邻节点
- 数据迁移量从 O(n) 降到 O(n/k)

---

## 四、系统设计题

### 4.1 设计 LRU Cache

**要求**：
- get 和 put 操作都是 O(1)
- 容量满时淘汰最久未使用的

**实现**：
```cpp
class LRUCache {
    int capacity;
    list<pair<int, int>> cache;  // 队首是最近使用的
    unordered_map<int, list<pair<int, int>>::iterator> map;
    
public:
    LRUCache(int cap) : capacity(cap) {}
    
    int get(int key) {
        if (!map.count(key)) return -1;
        // 移动到队首
        cache.splice(cache.begin(), cache, map[key]);
        return map[key]->second;
    }
    
    void put(int key, int value) {
        if (map.count(key)) {
            map[key]->second = value;
            cache.splice(cache.begin(), cache, map[key]);
            return;
        }
        
        if (cache.size() == capacity) {
            map.erase(cache.back().first);
            cache.pop_back();
        }
        
        cache.push_front({key, value});
        map[key] = cache.begin();
    }
};
```

### 4.2 设计线程池

```cpp
class ThreadPool {
    vector<thread> workers;
    queue<function<void()>> tasks;
    mutex mtx;
    condition_variable cv;
    bool stop = false;
    
public:
    ThreadPool(size_t numThreads) {
        for (size_t i = 0; i < numThreads; i++) {
            workers.emplace_back([this] {
                while (true) {
                    function<void()> task;
                    {
                        unique_lock<mutex> lock(mtx);
                        cv.wait(lock, [this] { return stop || !tasks.empty(); });
                        if (stop && tasks.empty()) return;
                        task = move(tasks.front());
                        tasks.pop();
                    }
                    task();
                }
            });
        }
    }
    
    template<typename F>
    void enqueue(F&& f) {
        {
            unique_lock<mutex> lock(mtx);
            tasks.push(forward<F>(f));
        }
        cv.notify_one();
    }
    
    ~ThreadPool() {
        {
            unique_lock<mutex> lock(mtx);
            stop = true;
        }
        cv.notify_all();
        for (auto& worker : workers) {
            worker.join();
        }
    }
};
```

### 4.3 设计短链接服务

**核心问题**：长 URL 到短 URL 的映射。

**方案**：
1. **哈希算法**：MD5 后取前 6 位，冲突时+1
2. **发号器**：自增 ID，转 62 进制（a-zA-Z0-9）

**架构**：
```
客户端 → Nginx → 短链服务 → 发号器
                        ↓
                      Redis（缓存）
                        ↓
                      MySQL（持久化）
```

### 4.4 设计秒杀系统

**核心挑战**：
- 高并发读写
- 库存超卖
- 流量突增

**解决方案**：

| 层级 | 方案 |
|------|------|
| **前端** | 静态化、CDN、验证码、限流 |
| **接入层** | Nginx 限流、黑名单 |
| **应用层** | 异步处理、消息队列削峰 |
| **数据层** | Redis 预减库存、原子操作 |

**库存扣减方案**：
```cpp
// Redis Lua 脚本保证原子性
local stock = redis.call('get', KEYS[1])
if tonumber(stock) > 0 then
    redis.call('decr', KEYS[1])
    return 1  // 成功
end
return 0  // 失败
```

---

## 五、智力题

### 5.1 倒水问题

**问题**：5L 和 7L 杯子，量出 6L 水。

**解法**：
1. 装满 7L，倒入 5L，剩 2L
2. 倒掉 5L，将 2L 倒入 5L 杯
3. 再装满 7L，倒入 5L（已有 2L，只能倒 3L），剩 4L
4. 倒掉 5L，将 4L 倒入 5L 杯
5. 装满 7L，倒入 5L（已有 4L，只能倒 1L），剩 6L

### 5.2 称重找假币

**问题**：10 机器，9 台产 5g 金币，1 台产 4g，一次找出。

**解法**：
- 从第 i 台机器取 i 个金币（1+2+3+...+10=55 个）
- 称重，如果少 x 克，第 x 台就是假币机器

### 5.3 赛马问题

**问题**：64 匹马，8 赛道，无计时器，找出最快的 4 匹。

**解法**：
1. 分 8 组比，每组 8 匹（8 场）
2. 每组第一名比，得总排名 A1>B1>C1>...（第 9 场）
3. A1 确定第 1，A2、A3、A4、B1、B2、B3、C1、C2 比出 2-4 名（第 10 场）
4. 总场次：10 场

---

## 六、设计模式

### 6.1 单例模式

```cpp
// 线程安全懒汉式（C++11）
class Singleton {
    Singleton() = default;
    ~Singleton() = default;
    Singleton(const Singleton&) = delete;
    Singleton& operator=(const Singleton&) = delete;
    
public:
    static Singleton& getInstance() {
        static Singleton instance;  // C++11 保证线程安全
        return instance;
    }
};

// 饿汉式
class Singleton {
    static Singleton instance;
public:
    static Singleton& getInstance() { return instance; }
};
Singleton Singleton::instance;
```

### 6.2 观察者模式

```cpp
class Observer {
public:
    virtual void update(int state) = 0;
};

class Subject {
    vector<Observer*> observers;
    int state;
    
public:
    void attach(Observer* obs) { observers.push_back(obs); }
    
    void setState(int s) {
        state = s;
        notify();
    }
    
    void notify() {
        for (auto obs : observers) {
            obs->update(state);
        }
    }
};
```

---

> 📌 **面试技巧**：算法题注重思路沟通。先确认题意，再讲思路，分析复杂度，最后写代码。遇到困难主动与面试官交流，展示解决问题的能力比写出完美代码更重要。
