all: t1 t2 t3 t4 t5 t6_linux fib power average

t1:
	nasm -felf64 t1.asm -o t1.o
	ld -o t1 t1.o
	./t1

t2:
	nasm -felf64 t2.asm -o t2.o
	ld -o t2 t2.o
	./t2

t3:
	nasm -felf64 t3.asm -o t3.o
	ld -o t3 t3.o
	./t3

t4:
	nasm -f elf64 square.asm -o square.o
	nasm -f elf64 mywrite.asm -o mywrite.o
	gcc main.c mywrite.o square.o -o t4
	./t4

t5:
	nasm -f elf64 t5.asm -o t5.o
	ld -o t5 t5.o
	./t5

t6_linux:
	nasm -f elf64 t6_linux.asm -o t6_linux.o
	ld -o t6_linux t6_linux.o
	./t6_linux

fib:
	nasm -f elf64 fib.asm -o fib.o
	gcc -no-pie fib.o -o fib
	./fib

power:
	nasm -f elf64 power.asm -o power.o
	gcc -no-pie power.o -o power
	./power 2 8

average:
	nasm -f elf64 average.asm -o average.o
	gcc -no-pie average.o -o average
	./average 1 2 3 4 5 6 7 8 9 10

clean:
	rm -f t1.o t1
	rm -f t2.o t2
	rm -f t3.o t3
	rm -f t4.o t4
	rm -f t5.o t5
	rm -f mywrite.o mywrite
	rm -f square.o square
	rm -f t6_linux.o t6_linux
	rm -f fib.o fib
	rm -f power.o power
	rm -f average.o average

.PHONY: clean t1 t2 t3 t4 t5 t6_linux fib power average