#include <iostream>
#include <string>
#include "tinykv/memtable/arena.hpp"
#include "tinykv/memtable/skiplist.hpp"

struct StringComparator : public tinykv::Comparator<std::string> {
    auto Compare(const std::string& a, const std::string& b) const -> int override {
        int result = (a < b) ? -1 : (a > b) ? 1 : 0;
        std::cout << "Compare: '" << a << "' vs '" << b << "' = " << result << std::endl;
        return result;
    }
};

int main() {
    std::cout << "Creating arena..." << std::endl;
    tinykv::Arena arena;
    std::cout << "Creating comparator..." << std::endl;
    StringComparator cmp;
    std::cout << "Creating skiplist..." << std::endl;
    tinykv::SkipList<std::string, std::string> list(&cmp, &arena);
    std::cout << "Skiplist created" << std::endl;

    std::cout << "\n=== Insert key1 ===" << std::endl;
    list.Insert("key1", "value1");
    std::cout << "Inserted, size=" << list.Size() << std::endl;

    std::cout << "\n=== Get key1 ===" << std::endl;
    std::string value;
    bool found = list.Get("key1", &value);
    std::cout << "Get returned: " << found << std::endl;
    if (found) {
        std::cout << "Value: " << value << std::endl;
    }

    return 0;
}
