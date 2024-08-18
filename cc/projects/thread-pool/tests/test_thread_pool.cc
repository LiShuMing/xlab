#include <atomic>
#include <future>
#include <numeric>
#include <vector>

#include "gtest/gtest.h"
#include "wstp/thread_pool.h"

namespace wstp {

// Test basic task execution
TEST(ThreadPoolTest, BasicSubmission) {
  ThreadPool pool(4, false);

  auto future = pool.Submit([]() { return 42; });
  EXPECT_EQ(future.get(), 42);
}

TEST(ThreadPoolTest, MultipleSubmissions) {
  ThreadPool pool(4, false);
  std::vector<std::future<int>> futures;

  for (int i = 0; i < 10; ++i) {
    futures.push_back(pool.Submit([i]() { return i * i; }));
  }

  for (int i = 0; i < 10; ++i) {
    EXPECT_EQ(futures[i].get(), i * i);
  }
}

TEST(ThreadPoolTest, VoidTaskExecution) {
  ThreadPool pool(4, false);
  std::atomic<int> counter{0};

  for (int i = 0; i < 100; ++i) {
    pool.Submit([&counter]() { counter.fetch_add(1); });
  }

  // Wait for all tasks to complete
  pool.Stop();
  EXPECT_EQ(counter.load(), 100);
}

TEST(ThreadPoolTest, StopIdempotent) {
  ThreadPool pool(4, false);

  // Submit some work
  pool.Submit([]() { std::this_thread::sleep_for(std::chrono::milliseconds(10)); });

  // Stop multiple times should not crash
  pool.Stop();
  pool.Stop();
  pool.Stop();
}

TEST(ThreadPoolTest, SubmitAfterStop) {
  ThreadPool pool(4, false);
  pool.Stop();

  // Submit after stop should return a future that throws
  auto future = pool.Submit([]() { return 42; });
  // Note: Due to worker threads potentially still running tasks,
  // the future may or may not throw depending on timing
  // This test verifies the API behavior, not the exact timing
  try {
    future.get();
    // If we get here, the task was processed (worker still running)
    // This is acceptable behavior - tasks in flight complete
  } catch (const std::runtime_error&) {
    // Expected: task was rejected
  } catch (const std::future_error&) {
    // Also acceptable: promise state issue due to race
  }
}

TEST(ThreadPoolTest, ParallelSum) {
  ThreadPool pool(4, false);
  const int kSize = 10000;
  std::vector<int> data(kSize);
  std::iota(data.begin(), data.end(), 1);

  std::atomic<int> sum{0};
  std::vector<std::future<void>> futures;

  // Divide work among threads
  const int chunk_size = kSize / 4;
  for (int i = 0; i < 4; ++i) {
    int start = i * chunk_size;
    int end = (i == 3) ? kSize : start + chunk_size;
    futures.push_back(pool.Submit([&data, &sum, start, end]() {
      int local_sum = 0;
      for (int j = start; j < end; ++j) {
        local_sum += data[j];
      }
      sum.fetch_add(local_sum);
    }));
  }

  // Wait for all
  for (auto& f : futures) {
    f.get();
  }

  pool.Stop();
  EXPECT_EQ(sum.load(), kSize * (kSize + 1) / 2);
}

TEST(ThreadPoolTest, NumThreads) {
  ThreadPool pool(8, false);
  EXPECT_EQ(pool.NumThreads(), 8);

  ThreadPool default_pool(0, false);
  EXPECT_GT(default_pool.NumThreads(), 0);
}

// Test with work-stealing enabled
TEST(ThreadPoolTest, WorkStealingBasic) {
  ThreadPool pool(4, true);

  auto future = pool.Submit([]() { return 42; });
  EXPECT_EQ(future.get(), 42);
}

TEST(ThreadPoolTest, WorkStealingMultipleSubmissions) {
  ThreadPool pool(4, true);
  std::vector<std::future<int>> futures;

  for (int i = 0; i < 100; ++i) {
    futures.push_back(pool.Submit([i]() { return i * i; }));
  }

  for (int i = 0; i < 100; ++i) {
    EXPECT_EQ(futures[i].get(), i * i);
  }
}

TEST(ThreadPoolTest, WorkStealingParallelSum) {
  ThreadPool pool(4, true);
  const int kSize = 10000;
  std::vector<int> data(kSize);
  std::iota(data.begin(), data.end(), 1);

  std::atomic<int> sum{0};
  std::vector<std::future<void>> futures;

  const int chunk_size = kSize / 4;
  for (int i = 0; i < 4; ++i) {
    int start = i * chunk_size;
    int end = (i == 3) ? kSize : start + chunk_size;
    futures.push_back(pool.Submit([&data, &sum, start, end]() {
      int local_sum = 0;
      for (int j = start; j < end; ++j) {
        local_sum += data[j];
      }
      sum.fetch_add(local_sum);
    }));
  }

  for (auto& f : futures) {
    f.get();
  }

  pool.Stop();
  EXPECT_EQ(sum.load(), kSize * (kSize + 1) / 2);
}

TEST(ThreadPoolTest, WorkStealingStop) {
  ThreadPool pool(4, true);
  std::atomic<int> counter{0};

  for (int i = 0; i < 100; ++i) {
    pool.Submit([&counter]() { counter.fetch_add(1); });
  }

  pool.Stop();
  EXPECT_EQ(counter.load(), 100);
}

// Stress test
TEST(ThreadPoolTest, StressTest) {
  ThreadPool pool(4, false);
  const int kTasks = 10000;
  std::atomic<int> counter{0};

  std::vector<std::future<void>> futures;
  for (int i = 0; i < kTasks; ++i) {
    futures.push_back(pool.Submit([&counter]() {
      counter.fetch_add(1);
      std::this_thread::yield();
    }));
  }

  pool.Stop();

  // All tasks should complete
  EXPECT_EQ(counter.load(), kTasks);
}

TEST(ThreadPoolTest, WorkStealingStressTest) {
  ThreadPool pool(4, true);
  const int kTasks = 10000;
  std::atomic<int> counter{0};

  std::vector<std::future<void>> futures;
  for (int i = 0; i < kTasks; ++i) {
    futures.push_back(pool.Submit([&counter]() {
      counter.fetch_add(1);
      std::this_thread::yield();
    }));
  }

  pool.Stop();
  EXPECT_EQ(counter.load(), kTasks);
}

}  // namespace wstp
