// Experiment 1A: Page Cache hit/miss & readahead workload generator.
// Modes:
//   seq        - sequential 4 KiB reads (triggers kernel readahead)
//   rand       - uniform random 4 KiB reads (defeats default readahead)
//   fadv_rand  - random 4 KiB reads with POSIX_FADV_RANDOM (disables readahead)
//   fadv_will  - sequential reads after POSIX_FADV_WILLNEED (pre-populates cache)
//   warm       - repeat sequential reads without evicting cache (pure cache hit)

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

static uint64_t now_ns(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (uint64_t)ts.tv_sec * 1000000000ULL + (uint64_t)ts.tv_nsec;
}

static uint64_t xorshift64(uint64_t *state) {
  uint64_t x = *state;
  x ^= x << 13;
  x ^= x >> 7;
  x ^= x << 17;
  *state = x;
  return x;
}

static int ensure_test_file(const char *path, size_t size_bytes) {
  struct stat st;
  if (stat(path, &st) == 0 && (size_t)st.st_size == size_bytes) {
    return 0;
  }
  int fd = open(path, O_CREAT | O_WRONLY | O_TRUNC, 0644);
  if (fd < 0) {
    perror("open create");
    return -1;
  }
  const size_t chunk = 1024 * 1024;
  unsigned char *buf = malloc(chunk);
  if (!buf) {
    close(fd);
    return -1;
  }
  for (size_t i = 0; i < chunk; ++i) {
    buf[i] = (unsigned char)((i * 131 + 17) & 0xff);
  }
  size_t remaining = size_bytes;
  while (remaining > 0) {
    size_t to_write = remaining < chunk ? remaining : chunk;
    ssize_t n = write(fd, buf, to_write);
    if (n <= 0) {
      perror("write");
      free(buf);
      close(fd);
      return -1;
    }
    remaining -= (size_t)n;
  }
  fsync(fd);
  free(buf);
  close(fd);
  return 0;
}

int main(int argc, char **argv) {
  const char *mode = argc > 1 ? argv[1] : "seq";
  const char *path = argc > 2 ? argv[2] : "/var/tmp/ebpf_pagecache.dat";
  size_t file_mb = argc > 3 ? (size_t)strtoul(argv[3], NULL, 10) : 32;
  size_t file_bytes = file_mb * 1024 * 1024;
  const size_t block_size = 4096;
  const size_t num_pages = file_bytes / block_size;
  const size_t ops = num_pages;  // Read 32 MiB worth of 4 KiB blocks.

  if (ensure_test_file(path, file_bytes) != 0) {
    return 1;
  }

  int fd = open(path, O_RDONLY);
  if (fd < 0) {
    perror("open read");
    return 1;
  }

  // Evict file pages from page cache before cold modes.
  if (strcmp(mode, "warm") != 0) {
    if (posix_fadvise(fd, 0, (off_t)file_bytes, POSIX_FADV_DONTNEED) != 0) {
      perror("posix_fadvise DONTNEED");
    }
  }

  if (strcmp(mode, "fadv_rand") == 0) {
    posix_fadvise(fd, 0, (off_t)file_bytes, POSIX_FADV_RANDOM);
  } else if (strcmp(mode, "fadv_will") == 0) {
    posix_fadvise(fd, 0, (off_t)file_bytes, POSIX_FADV_WILLNEED);
    // Give async readahead a brief head start.
    struct timespec ts = {.tv_sec = 0, .tv_nsec = 150000000};
    nanosleep(&ts, NULL);
  } else if (strcmp(mode, "seq") == 0) {
    posix_fadvise(fd, 0, (off_t)file_bytes, POSIX_FADV_SEQUENTIAL);
  }

  unsigned char buf[4096];
  uint64_t rng = 0x9e3779b97f4a7c15ULL;
  uint64_t checksum = 0;

  uint64_t t0 = now_ns();
  for (size_t i = 0; i < ops; ++i) {
    size_t page_idx;
    if (strcmp(mode, "rand") == 0 || strcmp(mode, "fadv_rand") == 0) {
      page_idx = (size_t)(xorshift64(&rng) % num_pages);
    } else {
      page_idx = i;
    }
    off_t offset = (off_t)(page_idx * block_size);
    ssize_t n = pread(fd, buf, block_size, offset);
    if (n != (ssize_t)block_size) {
      fprintf(stderr, "pread failed at page %zu: %s\n", page_idx, strerror(errno));
      close(fd);
      return 1;
    }
    checksum += buf[0];
  }
  uint64_t t1 = now_ns();
  double elapsed_ms = (double)(t1 - t0) / 1e6;
  double mb_s = ((double)ops * (double)block_size / (1024.0 * 1024.0)) / (elapsed_ms / 1000.0);

  printf("mode=%-10s ops=%zu elapsed_ms=%.2f throughput_mbs=%.1f checksum=%llu\n",
         mode, ops, elapsed_ms, mb_s, (unsigned long long)checksum);
  close(fd);
  return 0;
}
