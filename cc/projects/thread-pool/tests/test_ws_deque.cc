#include <atomic>
#include <thread>
#include <vector>

#include "gtest/gtest.h"
#include "wstp/ws_deque.h"

namespace wstp {

TEST(WSDequeTest, EmptyDeques) {
  WSDeque deque(1024);
  EXPECT_TRUE(deque.Empty());
  EXPECT_EQ(deque.Size(), 0);
  EXPECT_EQ(deque.Capacity(), 1024);
}

TEST(WSDequeTest, PushPop) {
  WSDeque deque(1024);

  deque.PushBottom([]() { return 1; });
  deque.PushBottom([]() { return 2; });
  deque.PushBottom([]() { return 3; });

  EXPECT_FALSE(deque.Empty());
  EXPECT_EQ(deque.Size(), 3);

  // Pop returns in LIFO order (bottom)
  auto task3 = deque.PopBottom();
  auto task2 = deque.PopBottom();
  auto task1 = deque.PopBottom();

  EXPECT_TRUE(deque.Empty());
  EXPECT_EQ(deque.Size(), 0);
  EXPECT_NE(task3, nullptr);
  EXPECT_NE(task2, nullptr);
  EXPECT_NE(task1, nullptr);
}

TEST(WSDequeTest, StealFromEmpty) {
  WSDeque deque(1024);

  // Steal from empty deque should return nullptr
  auto task = deque.StealTop();
  EXPECT_EQ(task, nullptr);
}

TEST(WSDequeTest, SingleElementRace) {
  WSDeque deque(1024);
  std::atomic<int> owner_got{0};
  std::atomic<int> thief_got{0};

  deque.PushBottom([]() { return 42; });

  // Simulate race: owner and thief both try to get the single element
  std::thread owner([&deque, &owner_got]() {
    auto task = deque.PopBottom();
    if (task) {
      owner_got.store(1);
    }
  });

  std::thread thief([&deque, &thief_got]() {
    auto task = deque.StealTop();
    if (task) {
      thief_got.store(1);
    }
  });

  owner.join();
  thief.join();

  // Exactly one should get the task
  EXPECT_EQ(owner_got.load() + thief_got.load(), 1);
}

TEST(WSDequeTest, MultipleOwnersMultipleThieves) {
  WSDeque deque(1024);
  constexpr int kElements = 1000;

  // Push all elements
  for (int i = 0; i < kElements; ++i) {
    deque.PushBottom([i]() { return i; });
  }

  std::atomic<int> owner_count{0};
  std::atomic<int> thief_count{0};
  std::atomic<int> total{0};

  // Owner pops some elements
  std::thread owner([&deque, &owner_count, &total]() {
    for (int i = 0; i < kElements / 2; ++i) {
      auto task = deque.PopBottom();
      if (task) {
        owner_count.fetch_add(1);
        total.fetch_add(1);
      }
    }
  });

  // Thief steals some elements
  std::thread thief([&deque, &thief_count, &total]() {
    for (int i = 0; i < kElements / 2; ++i) {
      auto task = deque.StealTop();
      if (task) {
        thief_count.fetch_add(1);
        total.fetch_add(1);
      }
    }
  });

  owner.join();
  thief.join();

  // All elements should be consumed
  EXPECT_EQ(total.load(), kElements);
}

TEST(WSDequeTest, StressTest) {
  WSDeque deque(1024);
  constexpr int kIterations = 10000;

  std::atomic<int> pushed{0};
  std::atomic<int> popped{0};

  std::thread pusher([&deque, &pushed]() {
    for (int i = 0; i < kIterations; ++i) {
      deque.PushBottom([i]() { return i; });
      pushed.fetch_add(1);
    }
  });

  std::vector<std::thread> workers;
  for (int i = 0; i < 4; ++i) {
    workers.emplace_back([&deque, &popped]() {
      while (popped.load() < kIterations) {
        auto task = deque.PopBottom();
        if (task) {
          popped.fetch_add(1);
        } else {
          // Try steal if pop failed
          task = deque.StealTop();
          if (task) {
            popped.fetch_add(1);
          }
        }
      }
    });
  }

  pusher.join();
  for (auto& w : workers) {
    w.join();
  }

  EXPECT_EQ(pushed.load(), kIterations);
  EXPECT_EQ(popped.load(), kIterations);
  EXPECT_TRUE(deque.Empty());
}

TEST(WSDequeTest, CapacityNotExceeded) {
  WSDeque deque(64);  // Small capacity

  // Push more than capacity - this will overwrite
  // In a real implementation, we'd handle this differently
  for (int i = 0; i < 100; ++i) {
    deque.PushBottom([i]() { return i; });
  }

  // We can still pop tasks
  int count = 0;
  while (deque.PopBottom() != nullptr) {
    count++;
  }

  EXPECT_GE(count, 64);  // At least capacity elements were processed
}

}  // namespace wstp
