#ifndef TINYKV_MEMTABLE_MEMTABLE_HPP_
#define TINYKV_MEMTABLE_MEMTABLE_HPP_

#include <memory>
#include <shared_mutex>
#include <string>

#include "tinykv/common/slice.hpp"
#include "tinykv/memtable/arena.hpp"
#include "tinykv/memtable/skiplist.hpp"

namespace tinykv {

// MemTable: an in-memory key-value store with ordered iteration.
class MemTable {
public:
    static constexpr size_t kEntryOverhead = 32;

    explicit MemTable();
    ~MemTable();

    MemTable(const MemTable&) = delete;
    MemTable& operator=(const MemTable&) = delete;

    auto Put(const Slice& key, const Slice& value) -> size_t;
    auto Get(const Slice& key, std::string* value) const -> bool;
    auto Delete(const Slice& key) -> size_t;
    auto Contains(const Slice& key) const -> bool { return Get(key, nullptr); }
    auto ApproximateMemoryUsage() const -> size_t { return arena_.MemoryUsage(); }
    auto Size() const -> size_t;

    static auto ApproximateSizeOf(const Slice& key, const Slice& value) -> size_t;

    using Iterator = SkipList<Slice, Slice>::Iterator;
    auto NewIterator() const -> Iterator;

private:
    std::unique_ptr<SkipList<Slice, Slice>> list_;
    Arena arena_;
    mutable std::shared_mutex mutex_;
};

}  // namespace tinykv

#endif  // TINYKV_MEMTABLE_MEMTABLE_HPP_
