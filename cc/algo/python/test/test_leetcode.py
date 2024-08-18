import pytest

class GrayCode:
    def __init__(self):
        pass

    def gray_to_binary(self, g: int) -> int:
        n = 0
        while g:
            n ^= g
            g >>= 1
        return n

    def binary_to_gray(self, n: int) -> int:
        return n ^ (n >> 1)

def test_gray_code():
    gray_code = GrayCode()
    for i in range(16):
        g = gray_code.binary_to_gray(i)
        b = gray_code.gray_to_binary(g)
        print(f"i: {i}, binary: {bin(i)}, gray: {bin(g)}, binary_back: {bin(b)}")
        assert b == i
