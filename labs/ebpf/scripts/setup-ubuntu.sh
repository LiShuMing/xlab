#!/usr/bin/env bash
# Install eBPF toolchain packages on Ubuntu (tested on Ubuntu with Linux 7.0 + sched_ext).

set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "error: labs/ebpf requires Linux with BTF support." >&2
  exit 1
fi

sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  bpftrace \
  clang \
  llvm \
  libbpf-dev \
  libelf-dev \
  pkg-config \
  iproute2 \
  linux-libc-dev

echo "Installed versions:"
clang --version | head -n 1
bpftrace --version
bpftool --version
pkg-config --modversion libbpf
