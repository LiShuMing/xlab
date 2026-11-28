#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
make -s all

ARCH="$(uname -m | sed 's/x86_64/x86/;s/aarch64/arm64/')"
BPF_CFLAGS="-g -O2 -target bpf -D__TARGET_ARCH_${ARCH} -I../common -I/usr/include/$(uname -m)-linux-gnu"

cat <<'EOF' > bin/inspect_helper.c
#include <bpf/bpf.h>
#include <bpf/libbpf.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int dump_verifier(const char *obj_path) {
  char log[32768] = {0};
  struct bpf_object *obj = bpf_object__open(obj_path);
  if (!obj) return 1;
  struct bpf_program *prog = bpf_object__next_program(obj, NULL);
  bpf_program__set_log_level(prog, 2);
  bpf_program__set_log_buf(prog, log, sizeof(log));
  int err = bpf_object__load(obj);
  printf("load_err=%d\n%s\n", err, log);
  bpf_object__close(obj);
  return 0;
}

static int dump_jit_bin(uint32_t prog_id, const char *out_path) {
  int fd = bpf_prog_get_fd_by_id(prog_id);
  if (fd < 0) {
    perror("bpf_prog_get_fd_by_id");
    return 1;
  }
  struct bpf_prog_info info = {};
  uint32_t len = sizeof(info);
  if (bpf_prog_get_info_by_fd(fd, &info, &len)) {
    perror("bpf_prog_get_info_by_fd");
    close(fd);
    return 1;
  }
  uint32_t jlen = info.jited_prog_len;
  unsigned char *buf = calloc(1, jlen);
  if (!buf) {
    close(fd);
    return 1;
  }
  memset(&info, 0, sizeof(info));
  info.jited_prog_len = jlen;
  info.jited_prog_insns = (uintptr_t)buf;
  if (bpf_prog_get_info_by_fd(fd, &info, &len)) {
    perror("bpf_prog_get_info_by_fd(insns)");
    free(buf);
    close(fd);
    return 1;
  }
  FILE *f = fopen(out_path, "wb");
  if (f) {
    fwrite(buf, 1, info.jited_prog_len, f);
    fclose(f);
  }
  printf("jited_prog_len=%u bytes (xlated_prog_len=%u bytes)\n",
         info.jited_prog_len, info.xlated_prog_len);
  free(buf);
  close(fd);
  return 0;
}

int main(int argc, char **argv) {
  if (argc == 3 && strcmp(argv[1], "verif") == 0) {
    return dump_verifier(argv[2]);
  }
  if (argc == 4 && strcmp(argv[1], "jit") == 0) {
    return dump_jit_bin((uint32_t)strtoul(argv[2], NULL, 10), argv[3]);
  }
  return 1;
}
EOF
gcc -O2 bin/inspect_helper.c -o bin/inspect_helper -lbpf

echo "================================================================"
echo "STAGE 1: Compiled BPF ELF Bytecode (pre-CO-RE relocation)"
echo "================================================================"
llvm-objdump -d --source --disassemble-symbols=handle_exec bin/exec_rw_trace.bpf.o | head -n 65

echo ""
echo "================================================================"
echo "STAGE 2 & 3: Loaded xlated (post-CO-RE) + Native x86-64 JIT"
echo "================================================================"
sudo ./bin/exec_rw_trace --duration 3 --max-print 0 >/dev/null 2>&1 &
TR_PID=$!
sleep 0.5

PROG_ID=$(sudo bpftool prog show name handle_exec | awk -F: 'NR==1{print $1}')
echo "Loaded handle_exec prog_id=${PROG_ID}"

echo ""
echo "--- Stage 2: bpftool prog dump xlated id ${PROG_ID} linum ---"
sudo bpftool prog dump xlated id "$PROG_ID" linum | head -n 65

echo ""
echo "--- Stage 3: Native x86-64 JIT disassembly (from kernel jited_prog_insns) ---"
sudo rm -f /tmp/xlab_handle_exec_jit.bin
sudo ./bin/inspect_helper jit "$PROG_ID" /tmp/xlab_handle_exec_jit.bin
objdump -D -b binary -m i386:x86-64 -M intel /tmp/xlab_handle_exec_jit.bin | head -n 45
sudo rm -f /tmp/xlab_handle_exec_jit.bin

wait "$TR_PID" || true

echo ""
echo "================================================================"
echo "VERIFIER REGISTER-STATE TRACE: ARRAY (const key) vs XDP bounds"
echo "================================================================"
mkdir -p verifier_cases/bin

clang $BPF_CFLAGS -c verifier_cases/case1b_array_const_ok.bpf.c -o verifier_cases/bin/case1b_array_const_ok.bpf.o
clang $BPF_CFLAGS -c verifier_cases/case3_pkt_oob_fixed.bpf.c -o verifier_cases/bin/case3_pkt_oob_fixed.bpf.o

echo ""
echo "--- Case 1b: ARRAY const key=0 (static non-null proof) ---"
sudo ./bin/inspect_helper verif verifier_cases/bin/case1b_array_const_ok.bpf.o

echo ""
echo "--- Case 3 (fixed): XDP data_end range tracking pkt(r=0) -> pkt(r=14) ---"
sudo ./bin/inspect_helper verif verifier_cases/bin/case3_pkt_oob_fixed.bpf.o
