; macOS ARM64 assembly - sum 1 to 10, export as function
    .text
    .global _sum_1_to_10
    .align 2

_sum_1_to_10:
    mov x1, #10      // counter
    mov x0, #0       // sum = 0

.loop:
    add x0, x0, x1
    subs x1, x1, #1  // x1--, set flags
    b.ne .loop       // if x1 != 0, jump

    ret              // return sum in x0
