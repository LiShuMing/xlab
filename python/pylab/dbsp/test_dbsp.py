
from dbsp import *
import math

def test_integer_addition_is_commutative():
    a = 5
    b = 10
    integer_addition_group = IntegerAddition()

    
    print(f"{a} + {b} = {integer_addition_group.add(a, b)}\n")

    print(integer_addition_group.is_commutative(a, b))
    print(integer_addition_group.is_associative(a, b, integer_addition_group.add(a, b)))
    print(integer_addition_group.has_identity(a))
    print(integer_addition_group.has_inverse(a))

def create_integer_identity_stream(to: int) -> Stream[int]:
    stream = Stream(IntegerAddition())
    for i in range(to):
        stream.send(i)

    return stream

def test_integer_identity_stream():
    n = 10
    integer_identity_stream = create_integer_identity_stream(n)
    zero_to_ten = StreamHandle(lambda: integer_identity_stream)
    print(f"Stream of integers from 0 to {n}: {zero_to_ten.get().to_list()}\n")

    delayed_zero_to_ten = Delay(zero_to_ten)
    step_until_fixpoint(delayed_zero_to_ten)
    print(f"Delayed stream of integers: \n{delayed_zero_to_ten.output().to_list()}\n")

    diff_zero_to_ten = Differentiate(zero_to_ten)
    step_until_fixpoint(diff_zero_to_ten)
    print(f"Diff stream of integers: \n{diff_zero_to_ten.output().to_list()}\n")

def test_zset():
    A: ZSet[str] = ZSet({"apple": 1, "orange": 3})
    B: ZSet[str] = ZSet({"apple": 3, "banana": 2})

    zset_addition_group = ZSetAddition()

    C = zset_addition_group.add(A, B)
    print(f"{A} + {B} = {C}\n")

    D = zset_addition_group.neg(A)
    print(f"neg({A}) = {D}\n")

    print(zset_addition_group.is_commutative(A, B))
    print(zset_addition_group.is_associative(A, B, zset_addition_group.add(A, B)))
    print(zset_addition_group.has_identity(A))
    print(zset_addition_group.has_inverse(A))

def test_stream_addition():
    A = ZSet({"apple": 1, "orange": 3})
    B = ZSet({"apple": -2, "orange": 3})
    C = ZSet({"apple": 2, "bananas": -2})

    zset_stream = Stream(ZSetAddition())
    zset_stream.send(A)
    zset_stream.send(B)
    zset_stream.send(C)

    zset_addition_group = ZSetAddition()
    zset_stream_addition_group = StreamAddition(zset_addition_group)
    zset_stream_sum = zset_stream_addition_group.add(zset_stream, zset_stream)

    print(f"zset_stream: {zset_stream}\n")
    print(f"zset_stream + zset_stream:\n{zset_stream_sum}\n")
    print(zset_stream_addition_group.is_commutative(zset_stream, zset_stream))
    print(
        zset_stream_addition_group.is_associative(zset_stream, zset_stream, zset_stream_sum)
    )
    print(zset_stream_addition_group.has_identity(zset_stream))
    print(zset_stream_addition_group.has_inverse(zset_stream))

def test_join():
    some_zset: ZSet[int] = ZSet({1: 1, 2: 1, 3: 1, 4: 1})
    other_zset: ZSet[int] = ZSet({4: 1, 9: 1})
    some_join_cmp = lambda left, right: left == math.isqrt(right)
    some_post_join_projection = lambda left, right: left
    print(join(some_zset, other_zset, some_join_cmp, some_post_join_projection))
