#include <iostream>
#include "tinykv/memtable/arena.hpp"

struct Node {
    int* forward[1];
    int key;
    int value;
};

int main() {
    tinykv::Arena arena;

    // Allocate a node with height 4 (so forward[0..3])
    // Node size = sizeof(Node) + extra_forward_elements * sizeof(Node*)
    int height = 4;
    size_t base_size = sizeof(Node) - sizeof(Node*);  // Remove one forward pointer
    size_t total_size = base_size + height * sizeof(Node*);

    Node* node = reinterpret_cast<Node*>(arena.Allocate(total_size));
    std::cout << "Allocated node at " << (void*)node << std::endl;
    std::cout << "sizeof(Node) = " << sizeof(Node) << std::endl;
    std::cout << "base_size = " << base_size << std::endl;
    std::cout << "total_size = " << total_size << std::endl;

    // Check if forward pointers are accessible
    node->forward[0] = nullptr;
    node->forward[1] = nullptr;
    node->forward[2] = nullptr;
    node->forward[3] = nullptr;

    std::cout << "Forward pointers set successfully" << std::endl;

    return 0;
}
