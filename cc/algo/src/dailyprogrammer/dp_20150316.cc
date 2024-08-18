#ifdef __APPLE__
#include <mach/mach.h>
#else
#include <sys/mman.h>
#include <sys/types.h>
#endif

#include "../include/fwd.h"

#define BUF_PAGE_SIZE 4088
#define CODE_SIZE BUF_PAGE_SIZE

/**
* See: https://www.reddit.com/r/dailyprogrammer/comments/2z68di/20150316_challenge_206_easy_recurrence_relations/
* - https://nullprogram.com/blog/2015/03/19/
*/
struct asmbuf {
    uint8_t code[CODE_SIZE];
    uint64_t count;
};

struct asmbuf *
asmbuf_create(void)
{
#ifdef __APPLE__
    mach_port_t task = mach_task_self();
    vm_address_t address = 0;
    kern_return_t result = vm_allocate(task, &address, BUF_PAGE_SIZE, VM_FLAGS_ANYWHERE);
    if (result != KERN_SUCCESS) {
        return NULL;
    }
    return (struct asmbuf *)address;
#else
    int prot = PROT_READ | PROT_WRITE;
    int flags = MAP_ANONYMOUS | MAP_PRIVATE;
    return (struct asmbuf *)mmap(NULL, BUF_PAGE_SIZE, prot, flags, -1, 0);
#endif
}

void
asmbuf_free(struct asmbuf *buf)
{
#ifdef __APPLE__
    mach_port_t task = mach_task_self();
    vm_deallocate(task, (vm_address_t)buf, BUF_PAGE_SIZE);
#else
    munmap(buf, BUF_PAGE_SIZE);
#endif
}

void
asmbuf_finalize(struct asmbuf *buf)
{
#ifdef __APPLE__
    mach_port_t task = mach_task_self();
    vm_protect(task, (vm_address_t)buf, BUF_PAGE_SIZE, FALSE, VM_PROT_READ | VM_PROT_EXECUTE);
#else
    mprotect(buf, BUF_PAGE_SIZE, PROT_READ | PROT_EXEC);
#endif
}

void
asmbuf_ins(struct asmbuf *buf, int size, uint64_t ins)
{
    for (int i = size - 1; i >= 0; i--)
        buf->code[buf->count++] = (ins >> (i * 8)) & 0xff;
}

void
asmbuf_immediate(struct asmbuf *buf, int size, const void *value)
{
    memcpy(buf->code + buf->count, value, size);
    buf->count += size;
}

int main(void)
{
    /* Compile input program */
    struct asmbuf *buf = asmbuf_create();
    asmbuf_ins(buf, 3, 0x4889f8); // mov %rdi, %rax
    int c;
    while ((c = fgetc(stdin)) != '\n' && c != EOF) {
        if (c == ' ')
            continue;
        char op = c;
        long operand;
        scanf("%ld", &operand);
        asmbuf_ins(buf, 2, 0x48bf);         // movq  operand, %rdi
        asmbuf_immediate(buf, 8, &operand);
        switch (op) {
        case '+':
            asmbuf_ins(buf, 3, 0x4801f8);   // add   %rdi, %rax
            break;
        case '-':
            asmbuf_ins(buf, 3, 0x4829f8);   // sub   %rdi, %rax
            break;
        case '*':
            asmbuf_ins(buf, 4, 0x480fafc7); // imul  %rdi, %rax
            break;
        case '/':
            asmbuf_ins(buf, 3, 0x4831d2);   // xor   %rdx, %rdx
            asmbuf_ins(buf, 3, 0x48f7ff);   // idiv  %rdi
            break;
        }
    }
    asmbuf_ins(buf,  1, 0xc3); // retq
    asmbuf_finalize(buf);

    long init;
    unsigned long term;
    scanf("%ld %lu", &init, &term);
    long (*recurrence)(long) = (long (*)(long))(void *)buf->code;
    for (unsigned long i = 0, x = init; i <= term; i++, x = recurrence(x))
        fprintf(stderr, "Term %lu: %ld\n", i, x);

    asmbuf_free(buf);
    return 0;
}
