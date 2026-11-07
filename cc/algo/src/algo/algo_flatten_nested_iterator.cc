#include "../include/fwd.h"

#include <cstdint>
#include <deque>
#include <random>
#include <stdexcept>

/**
 * 嵌套列表的非递归遍历，对应 docs/q&a/qa7.ini 的 Q2（选做题）。
 *
 * 题目：元素只可能是整数或列表，结构无环。要求按深度优先、从左到右逐个产出整数，
 * 不预先生成完整结果（惰性游标），时间 O(N)，额外空间 O(D)，D 为最大嵌套深度。
 *
 * 迭代器栈只维护一件事：栈里每一帧代表“这一层还有哪些子元素没看”，每一步只看栈顶。
 *   1. 栈顶游标取到整数 → 直接产出，不碰其他层的状态；
 *   2. 取到列表 → 压入一帧，进入下一层；
 *   3. 栈顶耗尽 → 弹栈，回到上一层。
 * 空间是“当前路径上未耗尽的层数”，与某一层有多宽无关——这才是 O(D) 而不是 O(N)。
 * 反例是一次性把某层全部子元素压栈：那等于把当前层的宽度也算进空间。
 *
 * 追问（遍历时别的线程改列表）在这里做成三份可对照的实现：
 *   1. 引用视图 + fail-fast：每帧记住进入时的结构版本，改动即抛异常；
 *   2. 全量快照：先物化整个序列，空间 O(N)，正是题目明确不想要的“预先生成完整结果”；
 *   3. 路径快照：只冻结已经进入的层的结构，空间为路径上各层宽度之和，
 *      但它给出的是混合视图——还没进过的层仍会看到新内容，最容易被误用。
 */

namespace {

int g_failures = 0;

void check(bool ok, const string& what) {
    cout << (ok ? "[PASS] " : "[FAIL] ") << what << "\n";
    if (!ok) ++g_failures;
}

// ---------------------------------------------------------------------------
// 数据结构：节点要么是整数，要么是列表；子节点用非拥有指针，生命周期由 Arena 管理。
// 结构版本 version 在 children 增删时自增，供 fail-fast 校验。
// ---------------------------------------------------------------------------
struct Node {
    bool is_list = false;
    long long value = 0;
    vector<Node*> children;
    uint64_t version = 0;
};

// 用 deque 持有全部节点：push_back 不会让已发出的指针失效，析构是逐元素迭代的。
// 若让 Node 直接持有 vector<Node>，20 万层深链在析构时同样会递归 20 万次，
// 演示还没开始就先被调用栈打爆。
class Arena {
public:
    Node* make_int(long long v) {
        nodes_.push_back(Node{});
        nodes_.back().value = v;
        return &nodes_.back();
    }

    Node* make_list() {
        nodes_.push_back(Node{});
        nodes_.back().is_list = true;
        return &nodes_.back();
    }

    // 结构修改的唯一入口：顺手推进版本号，避免调用方漏掉
    void append(Node* list, Node* child) {
        list->children.push_back(child);
        ++list->version;
    }

    size_t size() const { return nodes_.size(); }

private:
    deque<Node> nodes_;
};

struct ConcurrentModification : runtime_error {
    ConcurrentModification() : runtime_error("list modified during iteration") {}
};

// ---------------------------------------------------------------------------
// 主实现：引用视图。strict=true 时启用 fail-fast 版本校验。
// ---------------------------------------------------------------------------
class NestedIterator {
public:
    explicit NestedIterator(Node* root, bool strict = false) : strict_(strict) {
        if (root != nullptr && root->is_list) push(root);
    }

    bool next(long long& out) {
        while (!stack_.empty()) {
            Frame& top = stack_.back();
            if (strict_ && top.owner->version != top.version) {
                throw ConcurrentModification();
            }
            if (top.index >= top.owner->children.size()) {
                stack_.pop_back();
                continue;
            }
            Node* child = top.owner->children[top.index];
            ++top.index;
            ++visited_;
            if (!child->is_list) {
                out = child->value;
                ++produced_;
                return true;
            }
            push(child);  // 空列表也入栈，下一轮由同一条规则弹出
        }
        return false;
    }

    size_t depth() const { return stack_.size(); }
    size_t max_depth() const { return max_depth_; }
    size_t visited() const { return visited_; }  // 查看过的槽位数，用于证明惰性
    size_t produced() const { return produced_; }

private:
    struct Frame {
        Node* owner;
        size_t index;
        uint64_t version;
    };

    void push(Node* list) {
        stack_.push_back(Frame{list, 0, list->version});
        if (stack_.size() > max_depth_) max_depth_ = stack_.size();
    }

    vector<Frame> stack_;
    bool strict_ = false;
    size_t max_depth_ = 0;
    size_t visited_ = 0;
    size_t produced_ = 0;
};

// 反例实现：一次性把某一层的全部子元素压栈，空间随宽度增长
class NaiveStackIterator {
public:
    explicit NaiveStackIterator(Node* root) {
        if (root != nullptr && root->is_list) push_children(root);
    }

    bool next(long long& out) {
        while (!pending_.empty()) {
            Node* node = pending_.back();
            pending_.pop_back();
            if (!node->is_list) {
                out = node->value;
                return true;
            }
            push_children(node);
        }
        return false;
    }

    size_t peak() const { return peak_; }

private:
    void push_children(Node* list) {
        for (size_t i = list->children.size(); i-- > 0;) {
            pending_.push_back(list->children[i]);
        }
        if (pending_.size() > peak_) peak_ = pending_.size();
    }

    vector<Node*> pending_;
    size_t peak_ = 0;
};

// 第三种语义：路径快照。只拷贝已经进入的层的结构，节点内容仍按引用读取
class PathSnapshotIterator {
public:
    explicit PathSnapshotIterator(Node* root) {
        if (root != nullptr && root->is_list) push(root);
    }

    bool next(long long& out) {
        while (!stack_.empty()) {
            Frame& top = stack_.back();
            if (top.index >= top.items.size()) {
                stack_.pop_back();
                continue;
            }
            Node* child = top.items[top.index];
            ++top.index;
            if (!child->is_list) {
                out = child->value;
                return true;
            }
            push(child);
        }
        return false;
    }

private:
    struct Frame {
        vector<Node*> items;
        size_t index = 0;
    };

    void push(Node* list) { stack_.push_back(Frame{list->children, 0}); }

    vector<Frame> stack_;
};

// 递归基准：只用来对拍，不作为交付实现
void flatten_recursive(Node* node, vector<long long>& out) {
    for (Node* child : node->children) {
        if (child->is_list) {
            flatten_recursive(child, out);
        } else {
            out.push_back(child->value);
        }
    }
}

Node* random_list(Arena& arena, mt19937_64& rng, int depth) {
    Node* list = arena.make_list();
    int n = static_cast<int>(rng() % 4);
    for (int i = 0; i < n; ++i) {
        if (depth > 0 && rng() % 3 == 0) {
            arena.append(list, random_list(arena, rng, depth - 1));
        } else {
            arena.append(list, arena.make_int(static_cast<long long>(rng() % 1000)));
        }
    }
    return list;
}

Node* fill_full(Arena& arena, int depth, int fanout) {
    Node* list = arena.make_list();
    for (int i = 0; i < fanout; ++i) {
        if (depth > 1) {
            arena.append(list, fill_full(arena, depth - 1, fanout));
        } else {
            arena.append(list, arena.make_int(i));
        }
    }
    return list;
}

void count_nodes(Node* node, size_t& ints, size_t& slots) {
    slots += node->children.size();
    for (Node* child : node->children) {
        if (child->is_list) {
            count_nodes(child, ints, slots);
        } else {
            ++ints;
        }
    }
}

struct Sample {
    Node* root;
    Node* inner;
};

// 题目示例结构：[1, [2, [], [3]], 4]
Sample build_sample(Arena& arena) {
    Node* root = arena.make_list();
    arena.append(root, arena.make_int(1));

    Node* inner = arena.make_list();
    arena.append(inner, arena.make_int(2));
    arena.append(inner, arena.make_list());  // 空列表

    Node* deeper = arena.make_list();
    arena.append(deeper, arena.make_int(3));
    arena.append(inner, deeper);

    arena.append(root, inner);
    arena.append(root, arena.make_int(4));
    return Sample{root, inner};
}

void demo_example() {
    cout << "\n== 演示 1：题目示例 ==\n";
    Arena arena;
    Sample s = build_sample(arena);

    vector<long long> got;
    NestedIterator it(s.root);
    long long v = 0;
    while (it.next(v)) got.push_back(v);

    cout << "  输出：" << strJoin(got, "、") << "\n";
    check(got == vector<long long>{1, 2, 3, 4}, "空列表不产出元素，顺序为 1、2、3、4");
}

void demo_against_recursive() {
    cout << "\n== 演示 2：与递归实现逐元素对拍 ==\n";
    constexpr int kRounds = 3000;
    int mismatch = 0;
    size_t total_ints = 0;

    for (int t = 0; t < kRounds; ++t) {
        Arena arena;
        mt19937_64 rng(static_cast<uint64_t>(t) + 1);
        Node* root = random_list(arena, rng, 4);

        vector<long long> expect;
        flatten_recursive(root, expect);

        vector<long long> got;
        NestedIterator it(root);
        long long v = 0;
        while (it.next(v)) got.push_back(v);

        if (expect != got) ++mismatch;
        if (it.max_depth() > arena.size()) ++mismatch;  // 栈深不可能超过节点数
        total_ints += got.size();
    }

    cout << "  " << kRounds << " 棵随机列表，共 " << total_ints << " 个整数\n";
    check(mismatch == 0, "迭代器栈与递归输出的序列完全一致");
}

void demo_space_shape() {
    cout << "\n== 演示 3：空间只跟深度走，不跟宽度走 ==\n";
    constexpr size_t kWide = 100000;

    Arena arena;
    Node* root = arena.make_list();
    for (size_t i = 0; i < kWide; ++i) {
        arena.append(root, arena.make_int(static_cast<long long>(i)));
    }

    NestedIterator it(root);
    long long v = 0;
    size_t produced = 0;
    while (it.next(v)) ++produced;

    NaiveStackIterator naive(root);
    size_t naive_produced = 0;
    while (naive.next(v)) ++naive_produced;

    cout << "  宽 " << kWide << " 的扁平列表：显式栈峰值 " << it.max_depth() << " 帧，"
         << "一次全压栈峰值 " << naive.peak() << " 帧\n";
    check(it.max_depth() == 1 && naive.peak() == kWide,
          "深 1 宽 10 万：显式栈占 1 帧，一次压子元素则占 10 万帧");
    check(produced == kWide && naive_produced == kWide, "两种实现产出数量相同，差别只在空间");
}

void demo_lazy() {
    cout << "\n== 演示 4：惰性——只取前 3 个整数 ==\n";
    Arena arena;
    Node* root = fill_full(arena, 6, 4);

    size_t ints = 0, slots = 0;
    count_nodes(root, ints, slots);

    NestedIterator it(root);
    vector<long long> head;
    long long v = 0;
    while (head.size() < 3 && it.next(v)) head.push_back(v);

    cout << "  树中有 " << ints << " 个整数、" << slots << " 个槽位；取 " << head.size()
         << " 个时只访问了 " << it.visited() << " 个槽位\n";
    cout << "  前置输出：" << strJoin(head, "、") << "\n";
    // 前几个整数共享同一条向下的路径：5 层各查 1 个槽位，最内层查 3 个，共 8 次；
    // 全量遍历才需要 5460 次，这就是“不预先生成完整结果”的实际含义。
    check(head.size() == 3 && it.visited() <= 20 && slots > 5000,
          "取前 3 个只碰路径上的槽位，不预先生成完整结果");
}

void demo_deep() {
    cout << "\n== 演示 5：20 万层深链，只有显式栈能过 ==\n";
    constexpr int kDepth = 200000;

    Arena arena;
    Node* root = arena.make_list();
    Node* cur = root;
    for (int i = 0; i < kDepth; ++i) {
        Node* next_list = arena.make_list();
        arena.append(cur, next_list);
        cur = next_list;
    }
    arena.append(cur, arena.make_int(7));

    NestedIterator it(root);
    long long v = 0;
    bool ok = it.next(v) && v == 7 && !it.next(v);
    cout << "  最大栈深 " << it.max_depth() << " 帧，节点数 " << arena.size() << "\n";
    // 递归版本每层至少要有返回地址、帧指针和循环变量，-O0 下每帧约 48~64 字节，
    // 20 万层即 9.6~12.8 MB，超过默认 8 MiB 线程栈，会直接段错误。
    check(ok && it.max_depth() == static_cast<size_t>(kDepth) + 1,
          "20 万层遍历成功，栈占用 200001 帧，不受调用栈大小限制");
}

void demo_mutation() {
    cout << "\n== 演示 6：遍历中修改列表的三种语义 ==\n";

    {
        Arena arena;
        Sample s = build_sample(arena);
        NestedIterator it(s.root, /*strict=*/true);
        long long v = 0;
        it.next(v);
        arena.append(s.root, arena.make_int(5));

        bool threw = false;
        try {
            it.next(v);
        } catch (const ConcurrentModification&) {
            threw = true;
        }
        check(threw, "fail-fast：根列表追加元素后，下一次 next 抛 ConcurrentModification");
    }

    {
        Arena arena;
        Sample s = build_sample(arena);
        vector<long long> snapshot;  // 物化 = 题目明确不想要的“预先生成完整结果”
        flatten_recursive(s.root, snapshot);

        arena.append(s.root, arena.make_int(5));
        arena.append(s.inner, arena.make_int(9));
        cout << "  全量快照输出：" << strJoin(snapshot, "、") << "\n";
        check(snapshot == vector<long long>{1, 2, 3, 4},
              "快照语义：修改完全不可见，代价是 O(N) 空间");
    }

    {
        Arena arena;
        Sample s = build_sample(arena);
        PathSnapshotIterator it(s.root);
        vector<long long> got;
        long long v = 0;
        it.next(v);
        got.push_back(v);  // 取到 1，根层结构已冻结

        arena.append(s.root, arena.make_int(5));   // 已进入的层：看不到
        arena.append(s.inner, arena.make_int(9));  // 尚未进入的层：看得到
        while (it.next(v)) got.push_back(v);

        cout << "  路径快照输出：" << strJoin(got, "、") << "\n";
        check(got == vector<long long>{1, 2, 3, 9, 4},
              "路径快照是混合视图：根层冻结、内层看到新元素，最容易误用");
    }

    cout << "  结论：对外只暴露 fail-fast 或真正的快照；不要提供“边遍历边改、\n"
            "        还能看到部分新内容”的隐式语义。\n";
    cout << "  注意：上面的版本校验只是单线程模拟。真正的并发写 vector 本身是\n"
            "        data race（未定义行为），无锁下的版本检测也不是可靠保证；\n"
            "        并发场景应由调用方持读锁，或改用不可变 / 持久化列表。\n";
}

}  // namespace

int main() {
    cout << "嵌套列表的迭代器栈遍历（docs/q&a/qa7.ini Q2）\n";
    demo_example();
    demo_against_recursive();
    demo_space_shape();
    demo_lazy();
    demo_deep();
    demo_mutation();
    cout << "\n"
         << (g_failures == 0 ? "全部检查通过" : "存在失败检查") << "，失败数 " << g_failures
         << "\n";
    return g_failures == 0 ? 0 : 1;
}
