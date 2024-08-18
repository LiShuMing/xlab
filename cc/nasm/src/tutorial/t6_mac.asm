; ----------------------------------------------------------------------------------------
; 这是一个OSX控制台程序,将星号的小三角形写成标准
; 输出。仅在macOS上运行。
;
; nasm -fmacho64 triangle.asm && gcc hola.o && ./a.out
; ----------------------------------------------------------------------------------------

          global    _main
          default  rel

          section   .text
_main:
          push      rbx                     ; OSX必须，保存栈，Linux下删除该行
          mov       rdx, output             ; rdx holds address of next byte to write
          mov       r8, 1                   ; initial line length
          mov       r9, 0                   ; number of stars written on line so far
line:
          mov       byte [rdx], '*'         ; write single star
          inc       rdx                     ; advance pointer to next cell to write
          inc       r9                      ; "count" number so far on line
          cmp       r9, r8                  ; did we reach the number of stars for this line?
          jne       line                    ; not yet, keep writing on this line
lineDone:
          mov       byte [rdx], 10          ; write a new line char
          inc       rdx                     ; and move pointer to where next char goes
          inc       r8                      ; next line will be one char longer
          mov       r9, 0                   ; reset count of stars written on this line
          cmp       r8, maxlines            ; wait, did we already finish the last line?
          jng       line                    ; if not, begin writing this line
done:
          mov       rax, 0x02000004         ; system call for write
          mov       rdi, 1                  ; file handle 1 is stdout
          mov       rsi, output             ; address of string to output
          mov       rdx, dataSize           ; number of bytes
          syscall                           ; invoke operating system to do the write

          ;exit(0)
          pop rbx                           ; OSX必须，弹出开头保存的栈，Linux下删除该行
          ;mov       rax, 0x02000001         ; system call for exit
          ;xor       rdi, rdi                ; exit code 0
          ;syscall                           ; invoke operating system to exit
          ret

          section   .bss
maxlines  equ       8
dataSize  equ       44
output:   resb      dataSize

