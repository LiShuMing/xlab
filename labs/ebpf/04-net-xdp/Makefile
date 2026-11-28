CLANG ?= clang
CC ?= gcc
BPFTOOL ?= bpftool
ARCH := $(shell uname -m | sed 's/x86_64/x86/;s/aarch64/arm64/')
VMLINUX_H := ../common/vmlinux.h
BIN_DIR := bin

BPF_CFLAGS := -g -O2 -target bpf -D__TARGET_ARCH_$(ARCH) -I../common -I/usr/include/$(shell uname -m)-linux-gnu
USER_CFLAGS := -O2 -Wall -Wextra -I$(BIN_DIR)
USER_LDFLAGS := -lbpf -lelf -lz

.PHONY: all clean run

all: $(BIN_DIR)/xdp_udp_guard

$(BIN_DIR):
	mkdir -p $(BIN_DIR)

$(VMLINUX_H):
	mkdir -p ../common
	sudo $(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > $@

$(BIN_DIR)/xdp_udp_guard.bpf.o: xdp_udp_guard.bpf.c $(VMLINUX_H) | $(BIN_DIR)
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@

$(BIN_DIR)/xdp_udp_guard.skel.h: $(BIN_DIR)/xdp_udp_guard.bpf.o
	$(BPFTOOL) gen skeleton $< > $@

$(BIN_DIR)/xdp_udp_guard: xdp_udp_guard.c $(BIN_DIR)/xdp_udp_guard.skel.h | $(BIN_DIR)
	$(CC) $(USER_CFLAGS) $< -o $@ $(USER_LDFLAGS)

run: all
	./run_net_lab.sh

clean:
	rm -rf $(BIN_DIR)
