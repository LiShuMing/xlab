#include <gtest/gtest.h>

#include <atomic>
#include <cstring>
#include <functional>
#include <iostream>
#include <list>
#include <map>
#include <queue>
#include <shared_mutex>
#include <string>
#include <vector>
#include <memory>
#include <thread>
#include <cstddef> // for alignof
#include <new>     // for placement new

// TODO: how to include boost
// #include "boost/array.hpp"

using namespace std;

namespace test {

// Basic Test
class BoostTest : public testing::Test {};
// class BoostTest : public testing::Test {
//   public:
//     template <typename T, size_t BlockSize = 7> class CustomDeque {
//         std::vector<std::unique_ptr<std::array<T, BlockSize>>> blocks;
//         size_t currentIndex = BlockSize;

//       public:
//         void push_back(const T &value) {
//             if (currentIndex == BlockSize) {
//                 blocks.push_back(std::make_unique<std::array<T, BlockSize>>());
//                 currentIndex = 0;
//             }
//             new (&(*blocks.back())[currentIndex]) T(value);
//             ++currentIndex;
//         }

//         T &operator[](size_t index) {
//             size_t blockIndex = index / BlockSize;
//             size_t elementIndex = index % BlockSize;
//             return (*blocks[blockIndex])[elementIndex];
//         }
//     };
// };

// TEST_F(BoostTest, BasicTest1) {
//     boost::array<int, 3> a = {1, 2, 3};
//     for (auto &i : a) {
//         cout << i << endl;
//         ASSERT_EQ(i, i);
//     }
// }

// TEST_F(BoostTest, BasicTest2) {
//     CustomDeque<int> queue;
//     queue.push_back(0);
//     queue.push_back(1);
//     std::cout << "queue[0]: " << queue[0] << std::endl;
//     std::cout << "queue[0]: " << queue[1] << std::endl;
// }

class ConcurrentQueue {
public:
    class ImplicitProducer {
    public:
        template <bool canAlloc, typename U>
        bool enqueue(U&& element) {
            if constexpr (canAlloc) {
                std::cout << "Enqueuing with allocation: " << element << std::endl;
            } else {
                std::cout << "Enqueuing without allocation: " << element << std::endl;
            }
            return true;
        }
    };

    // implicit producer
    ImplicitProducer* producer;

    template <bool canAlloc, typename U>
    bool enqueue(U&& element) {
        return producer == nullptr
            ? false
            : producer->ConcurrentQueue::ImplicitProducer::template enqueue<canAlloc>(std::forward<U>(element));
    }
};

TEST_F(BoostTest, BasicTest3) {
    ConcurrentQueue::ImplicitProducer producer;
    ConcurrentQueue queue{&producer};

    queue.enqueue<true>(42);  
    queue.enqueue<false>("Hello"); 

    ConcurrentQueue emptyQueue{nullptr};
    std::cout << emptyQueue.enqueue<true>("Should fail") << std::endl;
}


struct Node {
    int data;
    Node* next;

    Node(int value) : data(value), next(nullptr) {}
};

class LockFreeList {
private:
    std::atomic<Node*> tail;

public:
    LockFreeList() : tail(nullptr) {}

    void push(Node* producer) {
        Node* prevTail = tail.load(std::memory_order_relaxed);
        do {
            producer->next = prevTail;
        } while (!tail.compare_exchange_weak(prevTail, producer, std::memory_order_release, std::memory_order_relaxed));
    }

    void print() const {
        Node* current = tail.load(std::memory_order_relaxed);
        while (current) {
            std::cout << current->data << " ";
            current = current->next;
        }
        std::cout << std::endl;
    }
};

TEST_F(BoostTest, BasicTest4) {
    // !!!!
    // std::vector<std::shared_ptr<Node>> nodes;
    // LockFreeList list;
    // std::vector<std::thread> threads;
    // for (int i = 0; i < 10; ++i) {
    //     threads.emplace_back([&nodes, &list, i]() {
    //         auto node = std::make_shared<Node>(i);
    //         list.push(node.get());
    //         nodes.emplace_back(std::move(node));
    //     });
    // }
    std::vector<std::shared_ptr<Node>> nodes;
    for (int i = 0; i < 10; i++) {
        nodes.emplace_back(std::make_shared<Node>(i));
    }
    LockFreeList list;
    std::vector<std::thread> threads;
    for (int i = 0; i < 10; ++i) {
        threads.emplace_back([&nodes, &list, i]() {
            list.push(nodes[i].get());
        });
    }
    for (auto& t : threads) {
        t.join();
    }
    list.print();
}

#define MOODYCAMEL_ALIGNED_TYPE_LIKE(type, align_obj) alignas(alignof(align_obj)) type

template <typename T, size_t BLOCK_SIZE>
struct AlignedBlock {
    // MOODYCAMEL_ALIGNED_TYPE_LIKE(char[sizeof(T) * BLOCK_SIZE], T) elements;
    MOODYCAMEL_ALIGNED_TYPE_LIKE(char, T) elements[sizeof(T) * BLOCK_SIZE];

    T* get(size_t index) {
        return reinterpret_cast<T*>(&elements[index * sizeof(T)]);
    }

    void construct(size_t index, const T& value) {
        new (get(index)) T(value); // 在对齐的内存上构造对象
    }

    void destroy(size_t index) {
        get(index)->~T(); // 显式调用析构函数
    }
};

TEST_F(BoostTest, BasicTest5) {
    constexpr size_t BLOCK_SIZE = 4;
    AlignedBlock<int, BLOCK_SIZE> block;

    // 构造对象
    block.construct(0, 42);
    block.construct(1, 99);

    // 访问对象
    std::cout << "Element 0: " << *block.get(0) << std::endl;
    std::cout << "Element 1: " << *block.get(1) << std::endl;

    // 销毁对象
    block.destroy(0);
    block.destroy(1);
}

} // namespace test
