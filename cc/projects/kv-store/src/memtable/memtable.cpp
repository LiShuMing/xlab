#include "tinykv/memtable/memtable.hpp"

#include <cstring>

namespace tinykv {

MemTable::MemTable()
    : list_(std::make_unique<SkipList<Slice, Slice>>(&slice_comparator_, &arena_)) {}

MemTable::~MemTable() = default;

auto MemTable::ApproximateSizeOf(const Slice& key, const Slice& value)
    -> size_t {
    return key.size() + value.size() + kEntryOverhead;
}

auto MemTable::Put(const Slice& key, const Slice& value) -> size_t {
    std::unique_lock lock(mutex_);

    size_t size_before = arena_.MemoryUsage();

    // Allocate copies in Arena since Slice doesn't own memory
    char* key_buf = arena_.Allocate(key.size());
    std::memcpy(key_buf, key.data(), key.size());
    Slice key_copy(key_buf, key.size());  // Use size-aware constructor

    char* value_buf = arena_.Allocate(value.size());
    std::memcpy(value_buf, value.data(), value.size());
    Slice value_copy(value_buf, value.size());  // Use size-aware constructor

    list_->Insert(key_copy, value_copy);

    size_t size_after = arena_.MemoryUsage();
    return size_after - size_before;
}

auto MemTable::Get(const Slice& key, std::string* value) const -> bool {
    std::shared_lock lock(mutex_);

    Slice stored_value;
    bool found = list_->Get(key, &stored_value);

    if (found && value != nullptr) {
        *value = stored_value.ToString();
    }

    return found;
}

auto MemTable::Delete(const Slice& key) -> size_t {
    std::unique_lock lock(mutex_);

    size_t size_before = arena_.MemoryUsage();
    list_->Delete(key);
    size_t size_after = arena_.MemoryUsage();

    return size_after - size_before;
}

auto MemTable::Size() const -> size_t {
    std::shared_lock lock(mutex_);
    return list_->Size();
}

auto MemTable::NewIterator() const -> Iterator {
    return list_->NewIterator();
}

}  // namespace tinykv
