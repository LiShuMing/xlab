
#pragma once

#include <stdio.h>
#include <time.h>

#include <iostream>
#include <stdatomic.h>

#include <atomic>
#include <iostream>
#include <string>

using namespace std;

template <typename T>
class MpmcQueue {
public:
    MpmcQueue(size_t buffer_size)
            : buffer_(new cell_t[buffer_size]), buffer_mask_(buffer_size - 1) {
        assert((buffer_size >= 2) && ((buffer_size & (buffer_size - 1)) == 0));

        for (size_t i = 0; i != buffer_size; i += 1) {
            // no needs to release_store, because it's the initialization phase
            buffer_[i].sequence_.store(i, std::memory_order_relaxed);
        }

        enqueue_pos_.store(0, std::memory_order_relaxed);
        dequeue_pos_.store(0, std::memory_order_relaxed);
    }

    ~MpmcQueue() { delete[] buffer_; }

    bool enqueue(T const& data) {
        cell_t* cell;
        size_t pos = enqueue_pos_.load(std::memory_order_relaxed);

        while (true) {
            cell = &buffer_[pos & buffer_mask_];

            // acquire load
            size_t seq = cell->sequence_.load(std::memory_order_acquire);
            intptr_t diff = (intptr_t)seq - (intptr_t)pos;
            if (diff == 0 &&
                enqueue_pos_.compare_exchange_weak(pos, pos + 1, std::memory_order_relaxed)) {
                break;
            } else if (diff < 0) {
                // when diff < 0, it means the cell is not ready for enqueue
                return false;
            } else {
                // advance the pos to the next cell
                pos = enqueue_pos_.load(std::memory_order_relaxed);
            }
        }

        cell->data_ = data;
        cell->sequence_.store(pos + 1, std::memory_order_release);

        return true;
    }

    bool dequeue(T& data) {
        cell_t* cell;
        size_t pos = dequeue_pos_.load(std::memory_order_relaxed);
        while (true) {
            cell = &buffer_[pos & buffer_mask_];
            size_t seq = cell->sequence_.load(std::memory_order_acquire);
            intptr_t dif = (intptr_t)seq - (intptr_t)(pos + 1);
            if (dif == 0 &&
                dequeue_pos_.compare_exchange_weak(pos, pos + 1, std::memory_order_relaxed)) {
                break;
            } else if (dif < 0) {
                return false;
            } else  {
                pos = dequeue_pos_.load(std::memory_order_relaxed);
            }
        }

        data = cell->data_;
        cell->sequence_.store(pos + buffer_mask_ + 1, std::memory_order_release);

        return true;
    }

private:
    struct cell_t {
        std::atomic<size_t> sequence_;
        T data_;
    };

    static size_t const L1_CACHE_LINE_SIZE = 64;
    typedef char cacheline_pad_t[L1_CACHE_LINE_SIZE];

    cacheline_pad_t pad0_;
    cell_t* const buffer_;
    size_t const buffer_mask_;
    cacheline_pad_t pad1_;
    std::atomic<size_t> enqueue_pos_;
    cacheline_pad_t pad2_;
    std::atomic<size_t> dequeue_pos_;
    cacheline_pad_t pad3_;

    MpmcQueue(MpmcQueue const&);
    void operator=(MpmcQueue const&);
};
