import numpy as np

def test_basic():
    print(np.__version__)
    print(np.__config__.show())

def test_array():
    a = np.array([1, 2, 3])
    print(a)
    print(a.shape)
    print(a.dtype)
    print(a.ndim)
    print(a.size)

    b = np.arange(15).reshape(3, 5)
    print(b)
    print(b.T)
