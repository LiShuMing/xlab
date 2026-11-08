# lowlevel 主题的统一构建入口，只做调度，不写编译细节。
.PHONY: all simd nasm llvm clean

all: simd nasm llvm

simd:
	$(MAKE) -C simd

nasm:
	$(MAKE) -C nasm

llvm:
	$(MAKE) -C llvm

clean:
	$(MAKE) -C simd clean
	$(MAKE) -C nasm clean
	$(MAKE) -C llvm clean
