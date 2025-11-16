; ----------------------------------------------------------------------------------------
; 控制台程序,将星号的小三角形写成标准输出
; nasm -felf64 t6_linux.asm -o t6_linux.o && ld -o t6_linux t6_linux.o && ./t6_linux
; ----------------------------------------------------------------------------------------

        global  _start

        section .bss
maxlines    equ     8
dataSize    equ     44
output:     resb    dataSize

        section .text
_start:
        mov     rdx, output         ; rdx holds address of next byte to write
        mov     r8, 1               ; initial line length
        mov     r9, 0               ; number of stars written on line so far
line:
        mov     byte [rdx], '*'     ; write single star
        inc     rdx                 ; advance pointer to next cell to write
        inc     r9                  ; "count" number so far on line
        cmp     r9, r8              ; did we reach the number of stars for this line?
        jne     line                ; not yet, keep writing on this line
lineDone:
        mov     byte [rdx], 10      ; write a new line char
        inc     rdx                 ; and move pointer to where next char goes
        inc     r8                  ; next line will be one char longer
        mov     r9, 0               ; reset count of stars written on this line
        cmp     r8, maxlines        ; wait, did we already finish the last line?
        jng     line                ; if not, begin writing this line

done:
        mov     rax, 1              ; sys_write
        mov     rdi, 1              ; file handle 1 is stdout
        mov     rsi, output         ; address of string to output
        mov     rdx, dataSize       ; number of bytes
        syscall                     ; invoke operating system to do the write

        ; exit(0)
        mov     rax, 60             ; sys_exit
        xor     rdi, rdi            ; exit code 0
        syscall
