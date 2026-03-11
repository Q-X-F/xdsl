from collections.abc import Callable

from xdsl.dialects.arith import AddiOp, ConstantOp, SubiOp, XOrIOp
from xdsl.dialects.builtin import IntegerAttr, StringAttr
from xdsl.ir import Operation


def _annoXor(op: Operation) -> None:
    """Annotates the x XOR x = 0 pattern"""

    if not isinstance(op, XOrIOp):
        return
    if op.lhs != op.rhs:
        return

    op.attributes["label"] = StringAttr(f"{op.lhs.name_hint} = 0")
    op.attributes["description"] = StringAttr(
        "XORs the register with itself, setting it to 0"
    )


def _annoSub(op: Operation) -> None:
    """Annotates the x - x = 0 pattern"""

    if not isinstance(op, SubiOp):
        return
    if op.lhs != op.rhs:
        return

    op.attributes["label"] = StringAttr(f"{op.lhs.name_hint} = 0")
    op.attributes["description"] = StringAttr(
        "Subtracts the register from itself, setting it to 0"
    )


def _annoAddConst(op: Operation) -> None:
    """Annotates the x++ and x += i patterns"""

    if not isinstance(op, AddiOp):
        return
    if not isinstance(c := op.rhs.owner, ConstantOp):
        return
    if not isinstance(c.value, IntegerAttr):
        return

    if c.value.value.data == 1:
        op.attributes["label"] = StringAttr(f"{op.lhs.name_hint}++")
        op.attributes["description"] = StringAttr("Increments the register")
    else:
        op.attributes["label"] = StringAttr(
            f"{op.lhs.name_hint} += {c.value.value.data}"
        )
        op.attributes["description"] = StringAttr("Adds a constant to the register")


def _annoSubConst(op: Operation) -> None:
    """Annotates the x-- and x -= i patterns"""

    if not isinstance(op, AddiOp):
        return
    if not isinstance(c := op.rhs.owner, ConstantOp):
        return
    if not isinstance(c.value, IntegerAttr):
        return

    if c.value.value.data == 1:
        op.attributes["label"] = StringAttr(f"{op.lhs.name_hint}--")
        op.attributes["description"] = StringAttr("Decrements the register")
    else:
        op.attributes["label"] = StringAttr(
            f"{op.lhs.name_hint} -= {c.value.value.data}"
        )
        op.attributes["description"] = StringAttr(
            "Subtracts a constant from the register"
        )


annoFunctions: list[Callable[[Operation], None]] = [
    _annoXor,
    _annoSub,
    _annoAddConst,
    _annoSubConst,
]


def annoOperation(op: Operation) -> None:
    """Adds annotations for an operation depending on idiomatic patterns.

    Args:
        op: The xDSL operation to annotate."""
    for f in annoFunctions:
        f(op)
