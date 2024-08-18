import unittest

class TestStringMethods(unittest.TestCase):
    def test_basic(self):
        d = {}
        d[1] = "1"
        print(d)
        for i in d.items():
            print(i)
        for k, v in d.items():
            print(str(k) + ":" + v)