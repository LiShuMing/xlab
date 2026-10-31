/**
 * 跳表（Skip List）
 *
 * 解决的问题：有序表 + 增删查 O(log n)，但它比平衡树好写得多，
 * 而且天然支持并发（这是它在工业界胜出的真正原因）。
 *
 * 核心直觉：给单链表「加索引」。
 *   普通单链表查找要 O(n) 个节点一个个走。如果每隔一个节点抽出一个做一层「快速通道」，
 *   走高速层就能跳过一半节点；再往上抽一层，又能跳一半……这就是「跳表」。
 *   每一层都是一条有序链表，上层是下层的「抽样」。
 *
 *   查找：从最高层开始，能往右就往右，不能往右就下降一层 —— 就像坐飞机转高铁再转公交。
 *   层数怎么定？每个节点以 1/2 概率往上长一层，用抛硬币决定。
 *   期望层数 O(log n)，所以查找、插入、删除都是期望 O(log n)。
 *
 * 对比平衡树：
 *   - 平衡树靠「旋转」维持平衡，插入删除的分支多、难写难调；
 *   - 跳表靠「随机」维持平衡，失败概率可以算得很小，代码量却只有 1/3；
 *   - 跳表的插入只需改动局部几条指针，天然适合无锁并发（RocksDB memtable 就是跳表）。
 *
 * 复杂度：查找 / 插入 / 删除 期望 O(log n)，空间期望 O(n)。
 */

#include "../include/fwd.h"

class SkipList {
public:
    static constexpr int kMaxLevel = 16;    // 最高层数，支持最多约 2^16 个节点
    static constexpr int kMinKey = INT_MIN; // 头节点哨兵键值

    SkipList() : level_(1), size_(0), seed_(2463534242u) {
        head_ = new Node(kMinKey, 0, kMaxLevel);
    }

    ~SkipList() {
        Node* cur = head_;
        while (cur != nullptr) {
            Node* next = cur->next[0];  // 第 0 层串起了所有节点
            delete cur;
            cur = next;
        }
    }

    SkipList(const SkipList&) = delete;
    SkipList& operator=(const SkipList&) = delete;

    int size() const { return size_; }
    int level() const { return level_; }

    // 插入或更新：key 已存在时覆盖 value
    void insert(int key, int value) {
        // prev[lvl] = 第 lvl 层里「最后一个 key 小于目标」的节点，也就是待插入位置的前驱
        vector<Node*> prev(kMaxLevel, head_);
        Node* cur = head_;
        // 从最高层往下逐层搜索，和查找的走法完全一致
        for (int lvl = level_ - 1; lvl >= 0; --lvl) {
            while (cur->next[lvl] != nullptr && cur->next[lvl]->key < key) cur = cur->next[lvl];
            prev[lvl] = cur;
        }

        Node* found = prev[0]->next[0];
        if (found != nullptr && found->key == key) {
            found->value = value;  // key 已存在，只更新
            return;
        }

        int newLevel = randomLevel();
        if (newLevel > level_) {
            // 新节点长到了当前最高层之上，超出的层前驱就是头节点
            for (int lvl = level_; lvl < newLevel; ++lvl) prev[lvl] = head_;
            level_ = newLevel;
        }

        Node* node = new Node(key, value, newLevel);
        // 最关键的三行：新节点在第 i 层接管前驱的 next，并指向原来的后继
        for (int lvl = 0; lvl < newLevel; ++lvl) {
            node->next[lvl] = prev[lvl]->next[lvl];
            prev[lvl]->next[lvl] = node;
        }
        ++size_;
    }

    // 查找：返回 value 指针，找不到返回 nullptr
    const int* find(int key) const {
        Node* cur = head_;
        for (int lvl = level_ - 1; lvl >= 0; --lvl) {
            while (cur->next[lvl] != nullptr && cur->next[lvl]->key < key) cur = cur->next[lvl];
        }
        Node* target = cur->next[0];
        return (target != nullptr && target->key == key) ? &target->value : nullptr;
    }

    bool erase(int key) {
        vector<Node*> prev(kMaxLevel, head_);
        Node* cur = head_;
        for (int lvl = level_ - 1; lvl >= 0; --lvl) {
            while (cur->next[lvl] != nullptr && cur->next[lvl]->key < key) cur = cur->next[lvl];
            prev[lvl] = cur;
        }

        Node* target = prev[0]->next[0];
        if (target == nullptr || target->key != key) return false;

        // 让每一层的前驱跳过被删节点（有些层并不包含它，所以要判断）
        for (int lvl = 0; lvl < level_; ++lvl) {
            if (prev[lvl]->next[lvl] == target) prev[lvl]->next[lvl] = target->next[lvl];
        }
        delete target;

        // 顶层可能已经被删空了，把层数收回来
        while (level_ > 1 && head_->next[level_ - 1] == nullptr) --level_;
        --size_;
        return true;
    }

    // 按 key 升序返回所有 (key, value)
    vector<pair<int, int>> entries() const {
        vector<pair<int, int>> out;
        for (Node* cur = head_->next[0]; cur != nullptr; cur = cur->next[0]) {
            out.emplace_back(cur->key, cur->value);
        }
        return out;
    }

    // 每层节点数，用来直观验证「每上一层大约少一半」
    vector<int> levelCounts() const {
        vector<int> counts(level_, 0);
        for (Node* cur = head_->next[0]; cur != nullptr; cur = cur->next[0]) {
            for (int lvl = 0; lvl < level_; ++lvl) {
                if (cur->next.size() > static_cast<size_t>(lvl)) ++counts[lvl];
            }
        }
        return counts;
    }

private:
    struct Node {
        int key;
        int value;
        vector<Node*> next;  // next[i]：第 i 层的下一个节点，长度取决于抽中的层数

        Node(int k, int v, int level) : key(k), value(v), next(level, nullptr) {}
    };

    // 抛硬币：以 1/2 的概率再长一层
    int randomLevel() {
        int lvl = 1;
        while (lvl < kMaxLevel && (nextRandom() & 1u) != 0) ++lvl;
        return lvl;
    }

    // xorshift32：确定性伪随机，跑多次结果一致，方便复现
    unsigned nextRandom() {
        seed_ ^= seed_ << 13;
        seed_ ^= seed_ >> 17;
        seed_ ^= seed_ << 5;
        return seed_;
    }

    Node* head_;   // 头哨兵，key 取 INT_MIN，让所有 key 都能排在它右边
    int level_;    // 当前实际使用的最高层数
    int size_;     // 节点个数
    unsigned seed_;
};

int main() {
    SkipList list;
    const vector<int> keys = {3, 1, 4, 1, 5, 9, 2, 6, 5, 3};
    for (int k : keys) list.insert(k, k * 10);  // 重复 key 会被覆盖，不是重复插入
    list.insert(4, 999);                        // 更新已存在的 key

    cout << "[跳表] 节点数: " << list.size() << endl;
    cout << "[跳表] 当前层数: " << list.level() << endl;

    vector<int> counts = list.levelCounts();
    cout << "[跳表] 每层节点数: ";
    printVector(counts);

    vector<pair<int, int>> all = list.entries();
    cout << "[跳表] 有序内容: ";
    for (size_t i = 0; i < all.size(); ++i) cout << all[i].first << "(" << all[i].second << ") ";
    cout << endl;

    // 1,2,3,4,5,6,9 共 7 个不同的 key，且必须升序
    assert(list.size() == 7);
    for (size_t i = 1; i < all.size(); ++i) assert(all[i - 1].first < all[i].first);
    assert(*list.find(4) == 999);
    assert(list.find(7) == nullptr);

    // 对照 std::set 验证增删查的一致性
    set<int> reference = {1, 2, 3, 4, 5, 6, 9};
    assert(list.erase(5));
    reference.erase(5);
    assert(!list.erase(5));  // 再删一次必须失败
    list.insert(8, 80);
    reference.insert(8);
    assert(list.size() == static_cast<int>(reference.size()));
    assert(list.entries().size() == reference.size());
    for (int k : reference) assert(list.find(k) != nullptr);

    cout << "algo_skiplist: all checks passed" << endl;
    return 0;
}
