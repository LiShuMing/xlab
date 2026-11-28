SUBDIRS := 01-bpftrace 02-sched-ext 03-core-ringbuf 04-net-xdp
BPFTOOL ?= bpftool

.PHONY: all clean vmlinux run-01 run-02 run-03 run-04

vmlinux:
	mkdir -p common
	sudo $(BPFTOOL) btf dump file /sys/kernel/btf/vmlinux format c > common/vmlinux.h

all: vmlinux
	for d in $(SUBDIRS); do $(MAKE) -C $$d all; done

run-01:
	$(MAKE) -C 01-bpftrace run

run-02: vmlinux
	$(MAKE) -C 02-sched-ext run

run-03: vmlinux
	$(MAKE) -C 03-core-ringbuf run

run-04: vmlinux
	$(MAKE) -C 04-net-xdp run

clean:
	for d in $(SUBDIRS); do $(MAKE) -C $$d clean; done
	rm -f common/vmlinux.h
