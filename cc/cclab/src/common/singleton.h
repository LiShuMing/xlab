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

#pragma once

#include <atomic>
#include <mutex>
#include <utility>

// Thread-safe singleton implementations, written for interview drill.
//
// Two required versions, plus the `call_once` alternative for comparison:
//
//   1. MeyersSingleton<T>  - function-local static ("magic static").
//   2. DclSingleton<T>     - std::atomic<T*> + std::mutex, double-checked locking.
//   3. CallOnceSingleton<T> - std::call_once alternative.
//
// ---------------------------------------------------------------------------
// Why MeyersSingleton needs no lock: [stmt.dcl]/4 (C++11 and later)
// ---------------------------------------------------------------------------
// "If control enters the declaration concurrently while the variable is being
//  initialized, the concurrent execution shall wait for completion of the
//  initialization."
//
// (This is the block-scope-static "magic statics" wording, added in C++11.
//  The surrounding paragraph is what makes a non-trivial initializer of a
//  block-scope static a *dynamic* initialization in the first place.)
//
// So the compiler must emit a guard (the canonical __cxa_guard_acquire /
// __cxa_guard_release pair on Itanium ABI) around the initializer. Only the
// *first* thread to enter runs the constructor; every other thread blocks until
// it finishes, then sees the completely-initialized object. This thread-safety
// guarantee is new in C++11 - in C++03 it was undefined and the usual workaround
// was `call_once` or a hand-rolled double-checked lock.
//
// Two consequences worth knowing:
//   * If the constructor THROWS, the initialization is not complete: the guard
//     is released WITHOUT the object being considered initialized, so the next
//     thread to enter retries the constructor. The exception propagates out of
//     instance() to the calling thread.
//   * `instance()` and the object live until program exit. The object is
//     destroyed when main() returns (or std::exit is called), in reverse order
//     of construction, AFTER the destruction of objects constructed earlier in
//     that same thread.
// ---------------------------------------------------------------------------

namespace cclab {

// ---------------------------------------------------------------------------
// 1) Meyers singleton.
//
// Simplest correct thread-safe singleton in C++11, and the one to reach for by
// default. No explicit synchronization, no leak, deterministic destruction.
// ---------------------------------------------------------------------------
template <typename T>
class MeyersSingleton {
public:
    static T& instance() {
        static T instance;
        return instance;
    }

    MeyersSingleton() = delete;
    ~MeyersSingleton() = delete;
    MeyersSingleton(const MeyersSingleton&) = delete;
    MeyersSingleton& operator=(const MeyersSingleton&) = delete;
};

// ---------------------------------------------------------------------------
// 2) Double-checked locking with std::atomic + std::mutex.
//
// The double check exists so that the common case (already initialized) does
// not take the mutex. That only works because `instance_` is atomic:
//
//   * load(acquire) pairs with store(release). The release store publishes the
//     fully-constructed object: every write performed by T's constructor
//     happens-before the acquire load that observes the pointer. Without the
//     acquire, the reader could see a non-null pointer while still observing a
//     partially-constructed object.
//   * The SECOND load may be memory_order_relaxed: we already hold the mutex,
//     and the mutex acquire/release provides the ordering, so no extra fence is
//     needed on that read.
//   * store(release) is required; store(relaxed) would allow the object's
//     initialization writes to become visible AFTER the pointer.
//
// Why the classic "plain pointer + mutex" version is BROKEN (both reasons are
// real, not theoretical):
//
//   * Data race / UB: with a plain T*, the unsynchronized read in the fast path
//     races with the write done under the mutex. That alone is undefined
//     behavior - the compiler is entitled to assume nobody else writes
//     `instance_` and may hoist the read out of the function, collapsing the
//     double check into a single check (the classic "DCL is broken" result).
//   * Reordering: even where the read/write races were tolerated, the
//     processor or compiler may make the store of `instance_` visible before the
//     constructor's stores, so a second thread can win the race and dereference
//     a half-built object.
//
// Compare with MeyersSingleton: same one-time construction, but the object is
// heap-allocated and (deliberately) never destroyed here, because running a
// destructor from a static destructor can resurrect the singleton: another
// static's destructor may call instance() after this one has been destroyed.
// Keeping it alive ("leaking") is the usual choice; see the note on
// CallOnceSingleton for the alternative.
// ---------------------------------------------------------------------------
template <typename T>
class DclSingleton {
public:
    static T& instance() {
        T* p = instance_.load(std::memory_order_acquire);
        if (p == nullptr) {
            std::lock_guard<std::mutex> guard(mutex_);
            p = instance_.load(std::memory_order_relaxed);
            if (p == nullptr) {
                p = new T();
                instance_.store(p, std::memory_order_release);
            }
        }
        return *p;
    }

    DclSingleton() = delete;
    ~DclSingleton() = delete;
    DclSingleton(const DclSingleton&) = delete;
    DclSingleton& operator=(const DclSingleton&) = delete;

private:
    static std::atomic<T*> instance_;
    static std::mutex mutex_;
};

template <typename T>
std::atomic<T*> DclSingleton<T>::instance_{nullptr};

template <typename T>
std::mutex DclSingleton<T>::mutex_;

// ---------------------------------------------------------------------------
// 3) std::call_once alternative (the follow-up question).
//
// Same one-time guarantee as the magic static, and it is not implemented with
// a double-checked lock internally, so it sidesteps the memory-ordering
// reasoning entirely. Differences that matter:
//
//   * Exceptions: if the callable throws, the once_flag is NOT consumed, so a
//     later call retries - the same semantic as the magic static.
//   * Destruction: the object is a heap object here as well, so the same
//     destruction-order problem applies as for DclSingleton.
//   * std::call_once is generally slower on the fast path than the magic
//     static, which after the first call is a single non-atomic load of the
//     guard variable (plus, on some ABIs, an acquire fence).
// ---------------------------------------------------------------------------
template <typename T>
class CallOnceSingleton {
public:
    static T& instance() {
        std::call_once(once_, [] { instance_ = new T(); });
        return *instance_;
    }

    CallOnceSingleton() = delete;
    ~CallOnceSingleton() = delete;
    CallOnceSingleton(const CallOnceSingleton&) = delete;
    CallOnceSingleton& operator=(const CallOnceSingleton&) = delete;

private:
    static std::once_flag once_;
    static T* instance_;
};

template <typename T>
std::once_flag CallOnceSingleton<T>::once_;

template <typename T>
T* CallOnceSingleton<T>::instance_ = nullptr;

} // namespace cclab
