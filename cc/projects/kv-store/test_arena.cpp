#include <iostream>
#include "tinykv/memtable/arena.hpp"

int main() {
    tinykv::Arena arena;

    // Simple allocation
    char* p1 = arena.Allocate(100);
    std::cout << "Allocated 100 bytes at " << (void*)p1 << std::endl;

    // Another allocation
    char* p2 = arena.Allocate(200);
    std::cout << "Allocated 200 bytes at " << (void*)p2 << std::endl;

    std::cout << "Memory usage: " << arena.MemoryUsage() << std::endl;

    return 0;
}
