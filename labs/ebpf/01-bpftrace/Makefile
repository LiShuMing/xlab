CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra -pthread
BIN_DIR := bin

.PHONY: all clean run

all: $(BIN_DIR)/pagecache_bench $(BIN_DIR)/futex_bench

$(BIN_DIR):
	mkdir -p $(BIN_DIR)

$(BIN_DIR)/pagecache_bench: pagecache_bench.c | $(BIN_DIR)
	$(CC) $(CFLAGS) $< -o $@

$(BIN_DIR)/futex_bench: futex_bench.c | $(BIN_DIR)
	$(CC) $(CFLAGS) $< -o $@

run: all
	./run_all.sh

clean:
	rm -rf $(BIN_DIR) /tmp/ebpf_pagecache.dat
