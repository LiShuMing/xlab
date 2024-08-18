
hello:
	nasm -felf64 hello.asm -o hello.o
	ld -o hello hello.o
	./hello

hello2:
	nasm -felf64 hello2.asm -o hello2.o
	ld -o hello2 hello2.o
	./hello2

clean:
	rm -f hello.o hello hello2.o hello2

.PHONY: clean hello hello2