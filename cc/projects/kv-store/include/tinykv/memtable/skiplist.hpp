#ifndef TINYKV_MEMTABLE_SKIPLIST_HPP_
#define TINYKV_MEMTABLE_SKIPLIST_HPP_

#include <cmath>
#include <iostream>
#include <new>
#include <random>

#include "tinykv/common/slice.hpp"
#include "tinykv/memtable/arena.hpp"

namespace tinykv {

// Comparator interface for SkipList
template<typename Key>
class Comparator {
public:
    virtual ~Comparator() = default;
    virtual auto Compare(const Key& a, const Key& b) const -> int = 0;
};

// Byte-wise comparator for Slice
class SliceComparator : public Comparator<Slice> {
public:
    auto Compare(const Slice& a, const Slice& b) const -> int override {
        return a.Compare(b);
    }
};

// Global instance for use in MemTable
inline SliceComparator slice_comparator_;

// SkipList: an ordered key-value map with O(log n) expected time for
// insert, delete, and search operations.
template<typename Key, typename Value>
class SkipList {
public:
    // Node stored in the skip list
    // Uses separate allocation for forward pointers to avoid standard layout issues
    // with non-trivial types like std::string
    struct Node {
        Node(Node** forward_ptrs, const Key& key, const Value& value)
            : forward_(forward_ptrs), key_(key), value_(value) {}

        // Get forward pointer at level n
        auto GetForward(int n) const -> Node* { return forward_[n]; }
        void SetForward(int n, Node* node) { forward_[n] = node; }

        // Access key (for internal use)
        auto GetKey() -> Key& { return key_; }
        auto GetKey() const -> const Key& { return key_; }

        // Access value (for internal use)
        auto GetValue() -> Value& { return value_; }
        auto GetValue() const -> const Value& { return value_; }

    private:
        friend class SkipList;
        // Pointer to dynamically allocated forward array
        Node** forward_;
        // Key and value stored inline
        Key key_;
        Value value_;
    };

    // Iterator for traversing the skip list
    class Iterator {
    public:
        explicit Iterator(const SkipList* list) : list_(list), node_(nullptr) {}

        auto Valid() const -> bool { return node_ != nullptr; }
        void Seek(const Key& key) { node_ = list_->FindGreaterOrEqual(key, nullptr); }
        void SeekToFirst() { node_ = list_->head_->GetForward(0); }
        void SeekToLast() { node_ = list_->FindLast(); }
        void Next() { node_ = node_->GetForward(0); }
        void Prev() { node_ = list_->FindLessThan(node_->GetKey()); }
        auto CurrentKey() const -> const Key& { return node_->GetKey(); }
        auto CurrentValue() const -> const Value& { return node_->GetValue(); }

    private:
        const SkipList* list_;
        Node* node_;
    };

    // Constructor
    explicit SkipList(Comparator<Key>* cmp, Arena* arena, uint32_t seed = 0);
    ~SkipList() = default;

    SkipList(const SkipList&) = delete;
    SkipList& operator=(const SkipList&) = delete;

    auto Insert(const Key& key, const Value& value) -> bool;
    auto Get(const Key& key, Value* value) const -> bool;
    auto Delete(const Key& key) -> bool;
    auto Contains(const Key& key) const -> bool { return Get(key, nullptr); }
    auto Empty() const -> bool { return size_ == 0; }
    auto Size() const -> size_t { return size_; }
    auto NewIterator() const -> Iterator { return Iterator(this); }

private:
    static constexpr int kMaxHeight = 12;
    static constexpr double kP = 0.5;
    static constexpr uint32_t kBranching = 4;

    auto RandomHeight() -> int;
    auto FindGreaterOrEqual(const Key& key, Node** prev) const -> Node*;
    auto FindLast() const -> Node*;
    auto FindLessThan(const Key& key) const -> Node*;

    Comparator<Key>* cmp_;
    Arena* arena_;
    Node* head_;
    int max_height_ = 1;
    size_t size_ = 0;
    mutable std::mt19937 rng_;
};

// Implementation

template<typename Key, typename Value>
SkipList<Key, Value>::SkipList(Comparator<Key>* cmp, Arena* arena, uint32_t seed)
    : cmp_(cmp), arena_(arena), head_(nullptr), max_height_(1), size_(0) {
    rng_.seed(seed == 0 ? std::random_device{}() : seed);

    // Allocate forward pointer array for head
    Node** head_forward = reinterpret_cast<Node**>(
        arena_->Allocate(kMaxHeight * sizeof(Node*)));
    for (int i = 0; i < kMaxHeight; ++i) {
        head_forward[i] = nullptr;
    }

    // Construct head node with empty key/value
    head_ = new (arena_->Allocate(sizeof(Node))) Node(head_forward, Key{}, Value{});
}

template<typename Key, typename Value>
auto SkipList<Key, Value>::RandomHeight() -> int {
    int height = 1;
    static std::uniform_int_distribution<int> dist(0, kBranching - 1);
    while (height < kMaxHeight && dist(rng_) == 0) {
        ++height;
    }
    return height;
}

template<typename Key, typename Value>
auto SkipList<Key, Value>::FindGreaterOrEqual(const Key& key, Node** prev) const
    -> Node* {
    Node* x = head_;
    int level = max_height_ - 1;

    while (true) {
        Node* next = x->GetForward(level);
        if (next != nullptr && cmp_->Compare(next->GetKey(), key) < 0) {
            x = next;
        } else {
            if (prev != nullptr) prev[level] = x;
            if (level == 0) return next;
            --level;
        }
    }
}

template<typename Key, typename Value>
auto SkipList<Key, Value>::FindLast() const -> Node* {
    Node* x = head_;
    int level = max_height_ - 1;

    while (true) {
        Node* next = x->GetForward(level);
        if (next == nullptr) {
            if (level == 0) return x;
            --level;
        } else {
            x = next;
        }
    }
}

template<typename Key, typename Value>
auto SkipList<Key, Value>::FindLessThan(const Key& key) const -> Node* {
    Node* x = head_;
    int level = max_height_ - 1;

    while (true) {
        Node* next = x->GetForward(level);
        if (next != nullptr && cmp_->Compare(next->GetKey(), key) < 0) {
            x = next;
        } else {
            if (level == 0) return x;
            --level;
        }
    }
}

template<typename Key, typename Value>
auto SkipList<Key, Value>::Insert(const Key& key, const Value& value) -> bool {
    Node* prev[kMaxHeight];
    Node* node = FindGreaterOrEqual(key, prev);

    if (node != nullptr && cmp_->Compare(node->GetKey(), key) == 0) {
        // Key exists, update value
        node->GetValue() = value;
        return false;
    }

    int height = RandomHeight();
    if (height > max_height_) {
        for (int i = max_height_; i < height; ++i) {
            prev[i] = head_;
        }
        max_height_ = height;
    }

    // Allocate forward pointer array
    Node** forward_ptrs = reinterpret_cast<Node**>(
        arena_->Allocate(height * sizeof(Node*)));
    for (int i = 0; i < height; ++i) {
        forward_ptrs[i] = nullptr;
    }

    // Construct node with key and value
    Node* new_node = new (arena_->Allocate(sizeof(Node))) Node(forward_ptrs, key, value);

    for (int i = 0; i < height; ++i) {
        new_node->SetForward(i, prev[i]->GetForward(i));
        prev[i]->SetForward(i, new_node);
    }

    ++size_;
    return true;
}

template<typename Key, typename Value>
auto SkipList<Key, Value>::Get(const Key& key, Value* value) const -> bool {
    Node* x = head_;
    int level = max_height_ - 1;

    while (true) {
        Node* next = x->GetForward(level);
        if (next != nullptr) {
            int cmp = cmp_->Compare(next->GetKey(), key);
            if (cmp < 0) {
                x = next;
                continue;
            }
            if (cmp == 0) {
                if (value != nullptr) *value = next->GetValue();
                return true;
            }
        }
        if (level == 0) return false;
        --level;
    }
}

template<typename Key, typename Value>
auto SkipList<Key, Value>::Delete(const Key& key) -> bool {
    Node* prev[kMaxHeight];
    Node* node = FindGreaterOrEqual(key, prev);

    if (node == nullptr || cmp_->Compare(node->GetKey(), key) != 0) {
        return false;
    }

    for (int i = 0; i < max_height_; ++i) {
        if (prev[i]->GetForward(i) != node) break;
        prev[i]->SetForward(i, node->GetForward(i));
    }

    --size_;
    return true;
}

}  // namespace tinykv

#endif  // TINYKV_MEMTABLE_SKIPLIST_HPP_
