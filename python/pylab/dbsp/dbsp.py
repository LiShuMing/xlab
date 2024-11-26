from abc import abstractmethod
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

class AbelianGroupOperation(Protocol[T]):
    @abstractmethod
    def add(self, a: T, b: T) -> T:
        raise NotImplementedError

    @abstractmethod
    def neg(self, a: T) -> T:
        raise NotImplementedError

    @abstractmethod
    def identity(self) -> T:
        raise NotImplementedError

    def is_commutative(self, a: T, b: T) -> bool:
        test = self.add(a, b) == self.add(b, a)
        if not test:
            print(f"Failed commutativity assertion: {self.add(a, b)} == {self.add(b, a)}")

        return test

    def is_associative(self, a: T, b: T, c: T) -> bool:
        test = self.add(self.add(a, b), c) == self.add(a, self.add(b, c))
        if not test:
            print(f"Failed associativity assertion: {self.add(self.add(a, b), c)} == {self.add(a, self.add(b, c))}")

        return test

    def has_identity(self, a: T) -> bool:
        identity = self.identity()
        test = self.add(a, identity) == a and self.add(identity, a) == a
        if not test:
            print(f"Failed identity assertion: {self.add(a, identity)} == {self.add(identity, a)}")

        return test

    def has_inverse(self, a: T) -> bool:
        identity = self.identity()
        inv_a = self.neg(a)
        test = self.add(a, inv_a) == identity and self.add(inv_a, a) == identity
        if not test:
            print(f"Failed inverse assertion: {self.add(a, inv_a)} == {self.add(inv_a, a)}")

        return test

class IntegerAddition(AbelianGroupOperation[int]):
    def add(self, a: int, b: int) -> int:
        return a + b

    def neg(self, a: int) -> int:
        return -a

    def identity(self) -> int:
        return 0

class Stream(Generic[T]):
    """
    Represents a stream of elements from an Abelian group.
    """
    timestamp: int
    inner: OrderedDict[int, T]
    group_op: AbelianGroupOperation[T]
    identity: bool
    default: T
    default_changes: OrderedDict[int, T]

    def __init__(self, group_op: AbelianGroupOperation[T]) -> None:
        self.inner = OrderedDict()
        self.group_op = group_op
        self.timestamp = -1
        self.identity = True
        self.default = group_op.identity()
        self.default_changes = OrderedDict()
        self.default_changes[0] = group_op.identity()
        self.send(group_op.identity())

    def send(self, element: T) -> None:
        """Adds an element to the stream and increments the timestamp."""
        if element != self.default:
            self.inner[self.timestamp + 1] = element
            self.identity = False

        self.timestamp += 1

    def group(self) -> AbelianGroupOperation[T]:
        """Returns the Abelian group operation associated with this stream."""
        return self.group_op

    def current_time(self) -> int:
        """Returns the timestamp of the most recently arrived element."""
        return self.timestamp

    def __iter__(self) -> Iterator[T]:
        for t in range(self.current_time() + 1):
            yield self[t]

    def __repr__(self) -> str:
        return self.inner.__repr__()

    def set_default(self, new_default: T):
        """
        Warning! changing this can break causality. Stay clear of this function unless you REALLY know what you are
        doing.

        This function effectively "freezes" the stream to strictly return a not-identity value when a timestamp
        beyond its frontier is requested.

        This is used in very specific scenarios. See the `LiftedIntegrate` implementation.
        """
        self.default = new_default
        self.default_changes[self.timestamp] = new_default

    def __getitem__(self, timestamp: int) -> T:
        """Returns the element at the given timestamp."""
        if timestamp < 0:
            raise ValueError("Timestamp cannot be negative")

        if timestamp <= self.current_time():
            default_timestamp = max((t for t in self.default_changes if t < timestamp), default=0)
            return self.inner.get(timestamp, self.default_changes[default_timestamp])

        elif timestamp > self.current_time():
            while timestamp > self.current_time():
                self.send(self.default)

        return self.__getitem__(timestamp)

    def latest(self) -> T:
        """Returns the most recent element."""
        return self.__getitem__(self.current_time())

    def is_identity(self) -> bool:
        return self.identity

    def to_list(self) -> List[T]:
        return list(iter(self))

    def __eq__(self, other: object) -> bool | NotImplementedType:
        """
        Compares this stream with another, considering all timestamps up to the latest.
        """
        if not isinstance(other, Stream):
            return NotImplemented

        if self.is_identity() and other.is_identity():
            return True

        cast(Stream[T], other)

        self_timestamp = self.current_time()
        other_timestamp = other.current_time()

        if self_timestamp != other_timestamp:
            return False

        return self.inner == other.inner  # type: ignore

StreamReference = Callable[[], Stream[T]]
class StreamHandle(Generic[T]):
    """A handle to a stream, allowing lazy access."""

    ref: StreamReference[T]

    def __init__(self, stream_reference: StreamReference[T]) -> None:
        self.ref = stream_reference

    def get(self) -> Stream[T]:
        """Returns the referenced stream."""
        return self.ref()


class Operator(Protocol[T]):
    @abstractmethod
    def step(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def output_handle(self) -> StreamHandle[T]:
        raise NotImplementedError

def step_until_fixpoint(operator: Operator[T]) -> None:
    while not operator.step():
        pass

def step_until_fixpoint_and_return(operator: Operator[T]) -> Stream[T]:
    step_until_fixpoint(operator)
    return operator.output_handle().get()


class UnaryOperator(Operator[R], Protocol[T, R]):
    """Base class for stream operators with a single input and output."""

    input_stream_handle: StreamHandle[T]
    output_stream_handle: StreamHandle[R]

    def __init__(
        self,
        stream_handle: Optional[StreamHandle[T]],
        output_stream_group: Optional[AbelianGroupOperation[R]],
    ) -> None:
        print(f"Stream handle: {stream_handle}")
        if stream_handle is not None:
            #print(f"Setting input stream: {stream_handle.get().to_list()}")
            self.set_input(stream_handle, output_stream_group)

    def set_input(
        self,
        stream_handle: StreamHandle[T],
        output_stream_group: Optional[AbelianGroupOperation[R]],
    ) -> None:
        """Sets the input stream and initializes the output stream."""
        self.input_stream_handle = stream_handle
        if output_stream_group is not None:
            output = Stream(output_stream_group)
            self.output_stream_handle = StreamHandle(lambda: output)
        else:
            print(f"Output stream:")
            output = cast(Stream[R], Stream(self.input_a().group()))
            self.output_stream_handle = StreamHandle(lambda: output)

    def output(self) -> Stream[R]:
        return self.output_stream_handle.get()

    def input_a(self) -> Stream[T]:
        return self.input_stream_handle.get()

    def output_handle(self) -> StreamHandle[R]:
        handle = StreamHandle(lambda: self.output())

        return handle


class BinaryOperator(Operator[S], Protocol[T, R, S]):
    """Base class for stream operators with two inputs and one output."""

    input_stream_handle_a: StreamHandle[T]
    input_stream_handle_b: StreamHandle[R]
    output_stream_handle: StreamHandle[S]

    def __init__(
        self,
        stream_a: Optional[StreamHandle[T]],
        stream_b: Optional[StreamHandle[R]],
        output_stream_group: Optional[AbelianGroupOperation[S]],
    ) -> None:
        if stream_a is not None:
            self.set_input_a(stream_a)

        if stream_b is not None:
            self.set_input_b(stream_b)

        if output_stream_group is not None:
            output = Stream(output_stream_group)

            self.set_output_stream(StreamHandle(lambda: output))

    def set_input_a(self, stream_handle_a: StreamHandle[T]) -> None:
        """Sets the first input stream and initializes the output stream."""
        self.input_stream_handle_a = stream_handle_a
        output = cast(Stream[S], Stream(self.input_a().group()))

        self.set_output_stream(StreamHandle(lambda: output))

    def set_input_b(self, stream_handle_b: StreamHandle[R]) -> None:
        """Sets the second input stream."""
        self.input_stream_handle_b = stream_handle_b

    def set_output_stream(self, output_stream_handle: StreamHandle[S]) -> None:
        """Sets the output stream handle."""
        self.output_stream_handle = output_stream_handle

    def output(self) -> Stream[S]:
        return self.output_stream_handle.get()

    def input_a(self) -> Stream[T]:
        return self.input_stream_handle_a.get()

    def input_b(self) -> Stream[R]:
        return self.input_stream_handle_b.get()

    def output_handle(self) -> StreamHandle[S]:
        handle = StreamHandle(lambda: self.output())

        return handle


class Delay(UnaryOperator[T, T]):
    """
    Delays the input stream by one timestamp.
    """

    def __init__(self, stream: Optional[StreamHandle[T]]) -> None:
        print(f"Delaying stream: {stream.get().to_list()}")
        super().__init__(stream, None)

    def step(self) -> bool:
        """
        Outputs the previous value from the input stream.
        """
        output_timestamp = self.output().current_time()
        input_timestamp = self.input_a().current_time()
        if output_timestamp <= input_timestamp:
            self.output().send(self.input_a()[output_timestamp])
            return False
        return True

F1 = Callable[[T], R]
class Lift1(UnaryOperator[T, R]):
    """Lifts a unary function to operate on a stream"""

    f1: F1[T, R]
    frontier: int

    def __init__(
        self,
        stream: Optional[StreamHandle[T]],
        f1: F1[T, R],
        output_stream_group: Optional[AbelianGroupOperation[R]],
    ):
        self.f1 = f1
        self.frontier = 0
        super().__init__(stream, output_stream_group)

    def step(self) -> bool:
        """Applies the lifted function to the next element in the input stream."""
        output_timestamp = self.output().current_time()
        input_timestamp = self.input_a().current_time()
        join = max(input_timestamp, output_timestamp, self.frontier)
        meet = min(input_timestamp, output_timestamp, self.frontier)

        if join == meet:
            return True

        next_frontier = self.frontier + 1
        self.output().send(self.f1(self.input_a()[next_frontier]))
        self.frontier = next_frontier

        return False


F2 = Callable[[T, R], S]
class Lift2(BinaryOperator[T, R, S]):
    """Lifts a binary function to operate on two streams"""

    f2: F2[T, R, S]
    frontier_a: int
    frontier_b: int

    def __init__(
        self,
        stream_a: Optional[StreamHandle[T]],
        stream_b: Optional[StreamHandle[R]],
        f2: F2[T, R, S],
        output_stream_group: Optional[AbelianGroupOperation[S]],
    ) -> None:
        self.f2 = f2
        self.frontier_a = 0
        self.frontier_b = 0

        super().__init__(stream_a, stream_b, output_stream_group)

    def step(self) -> bool:
        """Applies the lifted function to the most recently arrived elements in both input streams."""
        a_timestamp = self.input_a().current_time()
        b_timestamp = self.input_b().current_time()
        output_timestamp = self.output().current_time()

        join = max(a_timestamp, b_timestamp, output_timestamp, self.frontier_a, self.frontier_b)
        meet = min(a_timestamp, b_timestamp, output_timestamp, self.frontier_a, self.frontier_b)
        if join == meet:
            return True

        next_frontier_a = self.frontier_a + 1
        next_frontier_b = self.frontier_b + 1
        a = self.input_a()[next_frontier_a]
        b = self.input_b()[next_frontier_b]

        application = self.f2(a, b)
        self.output().send(application)

        self.frontier_a = next_frontier_a
        self.frontier_b = next_frontier_b

        return False


class LiftedGroupAdd(Lift2[T, T, T]):
    def __init__(self, stream_a: StreamHandle[T], stream_b: Optional[StreamHandle[T]]):
        super().__init__(
            stream_a,
            stream_b,
            lambda x, y: stream_a.get().group().add(x, y),
            None,
        )


class LiftedGroupNegate(Lift1[T, T]):
    def __init__(self, stream: StreamHandle[T]):
        super().__init__(stream, lambda x: stream.get().group().neg(x), None)

class Differentiate(UnaryOperator[T, T]):
    """
    Computes the difference between consecutive elements in the input stream.
    """

    delayed_stream: Delay[T]
    delayed_negated_stream: LiftedGroupNegate[T]
    differentiation_stream: LiftedGroupAdd[T]

    def __init__(self, stream: StreamHandle[T]) -> None:
        self.input_stream_handle = stream
        self.delayed_stream = Delay(self.input_stream_handle)
        self.delayed_negated_stream = LiftedGroupNegate(self.delayed_stream.output_handle())
        self.differentiation_stream = LiftedGroupAdd(
            self.input_stream_handle, self.delayed_negated_stream.output_handle()
        )
        self.output_stream_handle = self.differentiation_stream.output_handle()

    def step(self) -> bool:
        """
        Outputs the difference between the latest element from the input stream with the one before
        """
        self.delayed_stream.step()
        self.delayed_negated_stream.step()
        self.differentiation_stream.step()

        return self.output().current_time() == self.input_a().current_time()


class Integrate(UnaryOperator[T, T]):
    """
    Computes the running sum of the input stream.
    """

    delayed_stream: Delay[T]
    integration_stream: LiftedGroupAdd[T]

    def __init__(self, stream: StreamHandle[T]) -> None:
        self.input_stream_handle = stream
        self.integration_stream = LiftedGroupAdd(self.input_stream_handle, None)
        self.delayed_stream = Delay(self.integration_stream.output_handle())
        self.integration_stream.set_input_b(self.delayed_stream.output_handle())

        self.output_stream_handle = self.integration_stream.output_handle()

    def step(self) -> bool:
        """
        Adds the latest element from the input stream to the running sum
        """
        self.delayed_stream.step()
        self.integration_stream.step()

        return self.output().current_time() == self.input_a().current_time()


class ZSet(Generic[T]):
    """
    Represents a Z-set, a generalization of multisets with integer weights.
    Elements can have positive, negative, or zero weights.

    A Z-Set whose elements have all weight one can be interpreted as a set. One where
    all are strictly positive is a bag, and one where they are either one or -1 is a diff.
    """

    inner: Dict[T, int]

    def __init__(self, values: Dict[T, int]) -> None:
        self.inner = values

    def items(self) -> Iterable[Tuple[T, int]]:
        """Returns an iterable of (element, weight) pairs."""
        return self.inner.items()

    def __repr__(self) -> str:
        return self.inner.__repr__()

    def __eq__(self, other: object) -> bool:
        """
        Two Z-sets are equal if they have the same elements with the same weight.
        """
        if not isinstance(other, ZSet):
            return False

        return self.inner == other.inner  # type: ignore

    def __contains__(self, item: T) -> bool:
        """An item is in the Z-set if it has non-zero weight."""
        return self.inner.__contains__(item)

    def __getitem__(self, item: T) -> int:
        """Returns the weight of an item (0 if not present)."""
        if item not in self:
            return 0

        return self.inner[item]

    def is_identity(self) -> bool:
        return len(self.inner) == 0

    def __setitem__(self, key: T, value: int) -> None:
        self.inner[key] = value


class ZSetAddition(Generic[T], AbelianGroupOperation[ZSet[T]]):
    """
    Defines addition operation for Z-sets, forming an Abelian group.
    """

    def add(self, a: ZSet[T], b: ZSet[T]) -> ZSet[T]:
        """
        Adds two Z-sets by summing weights of common elements.
        Elements with resulting zero weight are removed.
        """
        result = a.inner | b.inner

        for k, v in b.inner.items():
            if k in a.inner:
                new_weight = a.inner[k] + v
                if new_weight == 0:
                    del result[k]
                else:
                    result[k] = new_weight

        return ZSet(result)

    def neg(self, a: ZSet[T]) -> ZSet[T]:
        """Returns the inverse of a Z-set by negating all weights."""
        return ZSet({k: v * -1 for k, v in a.inner.items()})

    def identity(self) -> ZSet[T]:
        """Returns the empty Z-set."""
        return ZSet({})

class StreamAddition(AbelianGroupOperation[Stream[T]]):
    """Defines addition for streams by lifting their underlying group's addition."""

    group: AbelianGroupOperation[T]

    def __init__(self, group: AbelianGroupOperation[T]) -> None:
        self.group = group

    def add(self, a: Stream[T], b: Stream[T]) -> Stream[T]:
        """Adds two streams element-wise."""
        handle_a = StreamHandle(lambda: a)
        handle_b = StreamHandle(lambda: b)

        lifted_group_add = LiftedGroupAdd(handle_a, handle_b)
        out = step_until_fixpoint_and_return(lifted_group_add)
        if a.is_identity():
            out.default = b.default

        if b.is_identity():
            out.default = a.default

        return out

    def inner_group(self) -> AbelianGroupOperation[T]:
        """Returns the underlying group operation."""
        return self.group

    def neg(self, a: Stream[T]) -> Stream[T]:
        """Negates a stream element-wise."""
        handle_a = StreamHandle(lambda: a)
        lifted_group_neg = LiftedGroupNegate(handle_a)

        return step_until_fixpoint_and_return(lifted_group_neg)

    def identity(self) -> Stream[T]:
        """
        Returns an identity stream for the addition operation.
        """
        identity_stream = Stream(self.group)

        return identity_stream

JoinCmp = Callable[[T, R], bool]
PostJoinProjection = Callable[[T, R], S]
def join(
    left_zset: ZSet[T],
    right_zset: ZSet[R],
    p: JoinCmp[T, R],
    f: PostJoinProjection[T, R, S],
) -> ZSet[S]:
    output: Dict[S, int] = {}
    for left_value, left_weight in left_zset.items():
        for right_value, right_weight in right_zset.items():
            if p(left_value, right_value):
                projected_value = f(left_value, right_value)
                new_weight = left_weight * right_weight

                if projected_value in output:
                    output[projected_value] += new_weight
                else:
                    output[projected_value] = new_weight
    return ZSet(output)
