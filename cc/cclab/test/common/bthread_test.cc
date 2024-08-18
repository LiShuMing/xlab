#include <gtest/gtest.h>

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

#include <iostream>

typedef void *bthread_fcontext_t;

extern "C" bthread_fcontext_t bthread_make_fcontext(void *sp, size_t size,
                                                    void (*fn)(intptr_t));
__asm(
    ".text\n"
    ".globl bthread_make_fcontext\n"
    ".type bthread_make_fcontext,@function\n"
    ".align 16\n"
    "bthread_make_fcontext:\n"
    "    movq  %rdi, %rax\n"
    "    andq  $-16, %rax\n"
    "    leaq  -0x48(%rax), %rax\n"
    "    movq  %rdx, 0x38(%rax)\n"
    "    stmxcsr  (%rax)\n"
    "    fnstcw   0x4(%rax)\n"
    "    leaq  finish(%rip), %rcx\n"
    "    movq  %rcx, 0x40(%rax)\n"
    "    ret \n"
    "finish:\n"
    "    xorq  %rdi, %rdi\n"
    "    call  _exit@PLT\n"
    "    hlt\n"
    ".size bthread_make_fcontext,.-bthread_make_fcontext\n"
    ".section .note.GNU-stack,\"\",%progbits\n"
    ".previous\n");

extern "C" intptr_t bthread_jump_fcontext(bthread_fcontext_t *ofc,
                                          bthread_fcontext_t nfc, intptr_t vp);
__asm(
    ".text\n"
    ".globl bthread_jump_fcontext\n"
    ".type bthread_jump_fcontext,@function\n"
    ".align 16\n"
    "bthread_jump_fcontext:\n"
    "    pushq  %rbp  \n"
    "    pushq  %rbx  \n"
    "    pushq  %r15  \n"
    "    pushq  %r14  \n"
    "    pushq  %r13  \n"
    "    pushq  %r12  \n"
    "    leaq  -0x8(%rsp), %rsp\n"
    "    movq  %rsp, (%rdi)\n"
    "    movq  %rsi, %rsp\n"
    "    leaq  0x8(%rsp), %rsp\n"
    "    popq  %r12  \n"
    "    popq  %r13  \n"
    "    popq  %r14  \n"
    "    popq  %r15  \n"
    "    popq  %rbx  \n"
    "    popq  %rbp  \n"
    "    popq  %r8\n"
    "    movq  %rdx, %rax\n"
    "    movq  %rdx, %rdi\n"
    "    jmp  *%r8\n"
    ".size bthread_jump_fcontext,.-bthread_jump_fcontext\n"
    ".section .note.GNU-stack,\"\",%progbits\n"
    ".previous\n");

bthread_fcontext_t fcm;
bthread_fcontext_t fc;

typedef std::pair<int, int> pair_t;
static void f(intptr_t param) {
  pair_t *p = (pair_t *)param;
  printf("In Routine: fcm %p fc %p\n", fcm, fc);

  p = (pair_t *)bthread_jump_fcontext(&fc, fcm,
                                      (intptr_t)(p->first + p->second));

  printf("In Routine Again: fcm %p fc %p\n", fcm, fc);
  bthread_jump_fcontext(&fc, fcm, (intptr_t)(p->first + p->second));
}
class BThreadTest : public testing::Test {};

TEST_F(BThreadTest, BasicTest) {
  fcm = NULL;
  std::size_t size(8192);
  void *sp = malloc(size);

  pair_t p(std::make_pair(2, 7));
  fc = bthread_make_fcontext((char *)sp + size, size, f);

  printf("Start Routine: fcm %p fc %p\n", fcm, fc);
  int res = (int)bthread_jump_fcontext(&fcm, fc, (intptr_t)&p);
  printf("Back to Main: %d + %d = %d\n", p.first, p.second, res);

  p = std::make_pair(5, 6);
  printf("Resume Routine: fcm %p fc %p\n", fcm, fc);
  res = (int)bthread_jump_fcontext(&fcm, fc, (intptr_t)&p);
  printf("Back to Main Again: %d + %d = %d\n", p.first, p.second, res);
}