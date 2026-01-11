UNAME := $(shell uname)

TUTORIAL_DIR := src/tutorial
# Detect OS and set appropriate flags
ifeq ($(UNAME),Darwin)
    # macOS: Use clang with assembly + C wrapper
    CC := clang
    ASMSRC := $(TUTORIAL_DIR)/t1_macos.asm
    CSRC := $(TUTORIAL_DIR)/t1_main.c
    SUFFIX := _macos
else
    # Linux: Use nasm + ld (x86_64)
    CC := nasm
    ASMSRC := $(TUTORIAL_DIR)/t1_linux.asm
    LDFLAGS := -o
    SUFFIX := _linux
endif

all: t1 t2 t3

t1:
	@echo "Building for $(UNAME)..."
ifeq ($(UNAME),Darwin)
	$(CC) -o t1 $(ASMSRC) $(CSRC) && ./t1 || true
else
	nasm -f elf64 -o t1.o $(ASMSRC) && ld $(LDFLAGS) t1 t1.o && ./t1 || true
endif

t2:
ifeq ($(UNAME),Darwin)
	$(CC) -o t2 $(TUTORIAL_DIR)/t2.asm && ./t2 || true
else
	nasm -f elf64 -o t2.o $(TUTORIAL_DIR)/t2.asm && ld -o t2 t2.o && ./t2 || true
endif

t3:
ifeq ($(UNAME),Darwin)
	$(CC) -o t3 $(TUTORIAL_DIR)/t3.asm && ./t3 || true
else
	nasm -f elf64 -o t3.o $(TUTORIAL_DIR)/t3.asm && ld -o t3 t3.o && ./t3 || true
endif

clean:
	rm -f $(TUTORIAL_DIR)/*.o t1 t2 t3

.PHONY: all t1 t2 t3 clean
