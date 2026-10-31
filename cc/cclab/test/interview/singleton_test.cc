// Copyright 2021-present StarRocks, Inc. All rights reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Concurrency verification for the three singleton variants in
// src/common/singleton.h. The point is not "it compiles" but that many threads
// entering at the same instant construct the object exactly once and all
// observe the same address.

#include <gtest/gtest.h>

#include <atomic>
#include <stdexcept>
#include <thread>
#include <vector>

#include "common/singleton.h"

namespace {

constexpr int kThreads = 32;

// Counts how many times the tracked type was constructed, per tag type, so each
// test gets its own counter instead of sharing one global.
template <typename Tag>
struct Tracked {
    static std::atomic<int> constructions;

    Tracked() { constructions.fetch_add(1, std::memory_order_relaxed); }
};

template <typename Tag>
std::atomic<int> Tracked<Tag>::constructions{0};

// Throws on its first construction attempt only, so a second attempt can
// succeed. Used to observe what happens when the initializer throws.
template <typename Tag>
struct ThrowingOnce {
    static std::atomic<int> attempts;

    ThrowingOnce() {
        if (attempts.fetch_add(1, std::memory_order_relaxed) == 0) {
            throw std::runtime_error("first construction attempt fails");
        }
    }
};

template <typename Tag>
std::atomic<int> ThrowingOnce<Tag>::attempts{0};

struct MeyersTag {};
struct DclTag {};
struct CallOnceTag {};

// Runs `body` on kThreads threads that all start at the same moment, so the
// first entry into the singleton is genuinely concurrent. Returns the addresses
// each thread observed.
template <typename Fn>
std::vector<const void*> runConcurrently(Fn body) {
    std::atomic<int> ready{0};
    std::atomic<bool> go{false};
    std::vector<const void*> observed(kThreads, nullptr);
    std::vector<std::thread> threads;
    threads.reserve(kThreads);

    for (int i = 0; i < kThreads; ++i) {
        threads.emplace_back([&, i]() {
            ready.fetch_add(1, std::memory_order_acq_rel);
            while (!go.load(std::memory_order_acquire)) {
                // Yield rather than hot-spin: a tight spin is very costly under
                // ThreadSanitizer, which slows every memory access.
                std::this_thread::yield();
            }
            observed[i] = body();
        });
    }
    while (ready.load(std::memory_order_acquire) != kThreads) {
        // wait for all threads to be ready, so they enter together
        std::this_thread::yield();
    }
    go.store(true, std::memory_order_release);
    for (auto& t : threads) {
        t.join();
    }
    return observed;
}

void expectAllSameAndConstructedOnce(const std::vector<const void*>& observed, int constructions) {
    ASSERT_EQ(observed.size(), static_cast<size_t>(kThreads));
    for (const void* address : observed) {
        ASSERT_NE(address, nullptr);
        ASSERT_EQ(address, observed.front()) << "threads observed different instances";
    }
    EXPECT_EQ(constructions, 1) << "the singleton was constructed more than once";
}

} // namespace

// ---------------------------------------------------------------------------
// Concurrency: each variant must construct exactly once under contention.
// ---------------------------------------------------------------------------

TEST(SingletonTest, meyersConstructsOnceUnderContention) {
    auto observed = runConcurrently([]() -> const void* {
        return static_cast<const void*>(&cclab::MeyersSingleton<Tracked<MeyersTag>>::instance());
    });
    expectAllSameAndConstructedOnce(observed, Tracked<MeyersTag>::constructions.load());
}

TEST(SingletonTest, doubleCheckedLockingConstructsOnceUnderContention) {
    auto observed = runConcurrently([]() -> const void* {
        return static_cast<const void*>(&cclab::DclSingleton<Tracked<DclTag>>::instance());
    });
    expectAllSameAndConstructedOnce(observed, Tracked<DclTag>::constructions.load());
}

TEST(SingletonTest, callOnceConstructsOnceUnderContention) {
    auto observed = runConcurrently([]() -> const void* {
        return static_cast<const void*>(&cclab::CallOnceSingleton<Tracked<CallOnceTag>>::instance());
    });
    expectAllSameAndConstructedOnce(observed, Tracked<CallOnceTag>::constructions.load());
}

// ---------------------------------------------------------------------------
// Repeated calls after the first one must return the same object (the fast path
// of the double-checked lock - it must agree with the slow path).
// ---------------------------------------------------------------------------

TEST(SingletonTest, repeatedCallsReturnTheSameObject) {
    auto* first = &cclab::MeyersSingleton<Tracked<MeyersTag>>::instance();
    auto* second = &cclab::MeyersSingleton<Tracked<MeyersTag>>::instance();
    EXPECT_EQ(first, second);

    auto* dcl_first = &cclab::DclSingleton<Tracked<DclTag>>::instance();
    auto* dcl_second = &cclab::DclSingleton<Tracked<DclTag>>::instance();
    EXPECT_EQ(dcl_first, dcl_second);
}

// ---------------------------------------------------------------------------
// If the initializer throws, the object is NOT considered initialized, so the
// next caller retries the constructor. This is the same for the magic static
// and for the atomic+mutex version.
// ---------------------------------------------------------------------------

TEST(SingletonTest, meyersRetriesAfterTheInitializerThrows) {
    using Singleton = cclab::MeyersSingleton<ThrowingOnce<std::atomic<int>>>;
    EXPECT_THROW(Singleton::instance(), std::runtime_error);
    EXPECT_EQ(ThrowingOnce<std::atomic<int>>::attempts.load(), 1);
    // The failed attempt did not count as initialization: the next call retries.
    EXPECT_NO_THROW(Singleton::instance());
    EXPECT_EQ(ThrowingOnce<std::atomic<int>>::attempts.load(), 2);
}

TEST(SingletonTest, doubleCheckedLockingRetriesAfterTheInitializerThrows) {
    using Singleton = cclab::DclSingleton<ThrowingOnce<std::vector<int>>>;
    EXPECT_THROW(Singleton::instance(), std::runtime_error);
    EXPECT_EQ(ThrowingOnce<std::vector<int>>::attempts.load(), 1);
    EXPECT_NO_THROW(Singleton::instance());
    EXPECT_EQ(ThrowingOnce<std::vector<int>>::attempts.load(), 2);
}
