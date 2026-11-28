CLANG ?= clang
CC ?= gcc
BPFTOOL ?= bpftool
ARCH := $(shell uname -m | sed 's/x86_64/x86/;s/aarch64/arm64/')
VMLINUX_H := ../common/vmlinux.h
BIN_DIR := bin

BPF_CFLAGS := -g -O2 -target bpf -D__TARGET_ARCH_$(ARCH) -I../common -I/usr/include/$(shell uname -m)-linux-gnu
USER_CFLAGS := -O2 -Wall -Wextra -I$(BIN_DIR)
USER_LDFLAGS := -lbpf -lelf -lz

.PHONY: all clean run vmlinux

all: $(BIN_DIR)/scx_prio_fifo $(BIN_DIR)/cpu_compete

$(BIN_DIR):
	mkdir -p $(BIN_DIR)

$(VMLINUX_H):
	mkdir -p ../common
	sudo $(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > $@

$(BIN_DIR)/scx_prio_fifo.bpf.o: scx_prio_fifo.bpf.c $(VMLINUX_H) | $(BIN_DIR)
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@

$(BIN_DIR)/scx_prio_fifo.skel.h: $(BIN_DIR)/scx_prio_fifo.bpf.o
	$(BPFTOOL) gen skeleton $< > $@

$(BIN_DIR)/scx_prio_fifo: scx_prio_fifo.c $(BIN_DIR)/scx_prio_fifo.skel.h | $(BIN_DIR)
	$(CC) $(USER_CFLAGS) $< -o $@ $(USER_LDFLAGS)

$(BIN_DIR)/cpu_compete: cpu_compete.c | $(BIN_DIR)
	$(CC) -O2 -Wall -Wextra $< -o $@

run: all
	./run_bench.sh

clean:
	rm -rf $(BIN_DIR)
