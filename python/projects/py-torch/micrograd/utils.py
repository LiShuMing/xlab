"""
Visualization utilities for micrograd.

This module provides functions for visualizing the computational graph
built during forward passes.
"""

from typing import Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from micrograd.engine import Value


def trace(root: "Value") -> Tuple[Set["Value"], Set[Tuple["Value", "Value"]]]:
    """
    Trace all nodes and edges in the computational graph.

    Performs a depth-first traversal of the computational graph starting
    from the root node, collecting all nodes and edges.

    Args:
        root: Root Value node (output of computation)

    Returns:
        Tuple of (nodes, edges) where:
            - nodes: Set of all Value objects in the graph
            - edges: Set of (parent, child) tuples representing dependencies
    """
    nodes: Set[Value] = set()
    edges: Set[Tuple[Value, Value]] = set()

    def build(v: "Value") -> None:
        if v not in nodes:
            nodes.add(v)
            for child in v._prev:
                edges.add((child, v))
                build(child)

    build(root)
    return nodes, edges


def draw_dot(root: "Value", format: str = 'svg', rankdir: str = 'LR') -> "Digraph":
    """
    Draw the computation graph using graphviz.

    Creates a visual representation of the computational graph showing
    values, gradients, and operations.

    Args:
        root: Root Value node
        format: Output format ('svg', 'png', 'pdf', etc.)
        rankdir: Graph direction ('LR' for left-to-right, 'TB' for top-to-bottom)

    Returns:
        graphviz.Digraph object

    Raises:
        ImportError: If graphviz package is not installed
    """
    try:
        from graphviz import Digraph
    except ImportError:
        raise ImportError(
            "graphviz package required. Install with: pip install graphviz"
        )

    dot = Digraph(format=format, graph_attr={'rankdir': rankdir})
    nodes, edges = trace(root)

    for n in nodes:
        uid = str(id(n))
        # Create node label with data and grad
        label = f"{{ {n.label or 'Value'} | data {n.data:.4f} | grad {n.grad:.4f} }}"
        dot.node(name=uid, label=label, shape='record')

        # Add operation node if this was created by an operation
        if n._op:
            dot.node(name=uid + n._op, label=n._op, shape='circle')
            dot.edge(uid + n._op, uid)

    for n1, n2 in edges:
        dot.edge(str(id(n1)), str(id(n2)) + n2._op)

    return dot


def print_graph(root: "Value") -> None:
    """
    Print the computation graph in text format.

    Displays all nodes in the computational graph with their
    data values and gradients.

    Args:
        root: Root Value node
    """
    nodes, edges = trace(root)
    print(f"Computation Graph ({len(nodes)} nodes, {len(edges)} edges)")
    print("=" * 50)
    for n in sorted(nodes, key=lambda x: id(x)):
        op_str = f" [op={n._op}]" if n._op else ""
        print(f"  {n.label or 'Value'}: data={n.data:.4f}, grad={n.grad:.4f}{op_str}")
