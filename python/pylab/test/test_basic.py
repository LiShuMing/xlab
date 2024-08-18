from abc import ABC, abstractmethod
from typing import Protocol, TypeVar
from typing import Callable, Generic, Iterator, List, Optional, cast
from types import NotImplementedType
from typing import Callable
from abc import abstractmethod
from types import NotImplementedType
from typing import Callable, Dict, Iterable, Tuple, Iterator, List, Optional, OrderedDict, Protocol, TypeVar, cast

T = TypeVar("T")
R = TypeVar("R")
S = TypeVar("S")

class A:
    def __init__(self):
        print("A initialized")

class B(A):
    def __init__(self):
        print("B initialized")
        print("super().__init__" + str(super()))
        super().__init__() 


class Operator(ABC, Generic[T]):

    @abstractmethod
    def step(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def output_handle(self) -> None:
        raise NotImplementedError

class UnaryOperator(Operator[T], ABC, Generic[T, R]):
        def __init__(self) -> None:
            print("UnaryOperator initialized")
        
        def output_handle(self):
            print("UnaryOperator output_handle")

class Delay(UnaryOperator[T, T]):
    def __init__(self):
        print("Delay initialized")
        super().__init__()

    def step(self) -> bool:
        print("Delay step")
        return True

def test_basic1():
    b = B()

def test_basic2():
    delay = Delay()