CLANG ?= clang
CC ?= gcc
BPFTOOL ?= bpftool
ARCH := $(shell uname -m | sed 's/x86_64/x86/;s/aarch64/arm64/')
VMLINUX_H := ../common/vmlinux.h
BIN_DIR := bin

BPF_CFLAGS := -g -O2 -target bpf -D__TARGET_ARCH_$(ARCH) -I../common -I. -I/usr/include/$(shell uname -m)-linux-gnu
USER_CFLAGS := -O2 -Wall -Wextra -I$(BIN_DIR) -I.
USER_LDFLAGS := -lbpf -lelf -lz

VERIFIER_SRCS := $(wildcard verifier_cases/*.bpf.c)
VERIFIER_OBJS := $(patsubst verifier_cases/%.bpf.c,$(BIN_DIR)/%.bpf.o,$(VERIFIER_SRCS))

.PHONY: all clean run verifier

all: $(BIN_DIR)/exec_rw_trace $(VERIFIER_OBJS)

$(BIN_DIR):
	mkdir -p $(BIN_DIR)

$(VMLINUX_H):
	mkdir -p ../common
	sudo $(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > $@

$(BIN_DIR)/exec_rw_trace.bpf.o: exec_rw_trace.bpf.c common.h $(VMLINUX_H) | $(BIN_DIR)
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@

$(BIN_DIR)/exec_rw_trace.skel.h: $(BIN_DIR)/exec_rw_trace.bpf.o
	$(BPFTOOL) gen skeleton $< > $@

$(BIN_DIR)/exec_rw_trace: exec_rw_trace.c $(BIN_DIR)/exec_rw_trace.skel.h common.h | $(BIN_DIR)
	$(CC) $(USER_CFLAGS) $< -o $@ $(USER_LDFLAGS)

$(BIN_DIR)/%.bpf.o: verifier_cases/%.bpf.c $(VMLINUX_H) | $(BIN_DIR)
	$(CLANG) $(BPF_CFLAGS) -c $< -o $@

verifier: $(VERIFIER_OBJS)
	./verifier_cases/run_verifier_gallery.sh

run: all
	./run_demo.sh

clean:
	rm -rf $(BIN_DIR)
