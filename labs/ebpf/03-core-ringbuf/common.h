#ifndef XLAB_EBPF_CORE_COMMON_H
#define XLAB_EBPF_CORE_COMMON_H

#define TASK_COMM_LEN 16
#define MAX_FILENAME_LEN 128

enum event_kind {
  EVT_EXEC = 1,
  EVT_EXIT = 2,
  EVT_READ = 3,
  EVT_WRITE = 4,
};

struct rb_event {
  unsigned int kind;
  unsigned int pid;
  unsigned int ppid;
  unsigned int fd;
  long long ret;
  unsigned long long duration_ns;
  char comm[TASK_COMM_LEN];
  char filename[MAX_FILENAME_LEN];
};

#define HIST_SLOTS 32

#endif
