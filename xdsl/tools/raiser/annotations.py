from collections.abc import Callable
from typing import TypeAlias

from xdsl.dialects.builtin import StringAttr
from xdsl.dialects.x86.assembly import AssemblyInstructionArg
from xdsl.dialects.x86.ops import (
    RI_AddOp,
    RI_SubOp,
    RS_AddOp,
    RS_SubOp,
    RS_XorOp,
    X86Instruction,
)
from xdsl.dialects.x86.registers import GeneralRegisterType
from xdsl.ir import Operation

OpArgs: TypeAlias = tuple[AssemblyInstructionArg | None, ...]


def _is_same_register(args: OpArgs) -> GeneralRegisterType | None:
    """Determines whether the source and destination for a RS-type operation
    are the same register.

    Args:
        args: Assembly-line arguments for the operation

    Returns:
        The shared register if both operands are the same, otherwise None
    """

    if len(args) != 2:
        return None
    if not isinstance(args[0], GeneralRegisterType) or not isinstance(
        args[1], GeneralRegisterType
    ):
        return None
    if args[0] != args[1]:
        return None
    return args[0]


def _anno_xor(op: Operation, args: OpArgs) -> bool:
    """Annotates the idiom of a self-XORed register."""

    if not isinstance(op, RS_XorOp):
        return False

    reg = _is_same_register(args)
    if reg is None:
        return False

    op.attributes["label"] = StringAttr(f"{reg.register_name} = 0")
    op.attributes["description"] = StringAttr(
        "XORs the register with itself, setting it to 0"
    )
    return True


def _anno_sub_self(op: Operation, args: OpArgs) -> bool:
    """Annotates the idiom of a self-subtracted register"""

    if not isinstance(op, RS_SubOp):
        return False

    reg = _is_same_register(args)
    if reg is None:
        return False

    op.attributes["label"] = StringAttr(f"{reg.register_name} = 0")
    op.attributes["description"] = StringAttr(
        "Subtracts the register from itself, setting it to 0"
    )
    return True


def _anno_add_self(op: Operation, args: OpArgs) -> bool:
    """Annotates the idiom of a self-added register"""

    if not isinstance(op, RS_AddOp):
        return False

    reg = _is_same_register(args)
    if reg is None:
        return False

    op.attributes["label"] = StringAttr(f"{reg.register_name} *= 2")
    op.attributes["description"] = StringAttr(
        "Adds the register with itself, doubling it"
    )
    return True


def _anno_add_const(op: Operation, args: OpArgs) -> bool:
    """Annotates registers being added by immediates."""

    if not isinstance(op, RI_AddOp):
        return False

    if len(args) != 2:
        return False
    if not isinstance(args[0], GeneralRegisterType):
        return False

    if op.immediate.value.data == 1:
        op.attributes["label"] = StringAttr(f"{args[0].register_name}++")
        op.attributes["description"] = StringAttr("Increments the register")
    else:
        op.attributes["label"] = StringAttr(
            f"{args[0].register_name} += {op.immediate.value.data}"
        )
        op.attributes["description"] = StringAttr("Adds a constant to the register")
    return True


def _anno_sub_const(op: Operation, args: OpArgs) -> bool:
    """Annotates registers being subtracted by immediates."""

    if not isinstance(op, RI_SubOp):
        return False

    if len(args) != 2:
        return False
    if not isinstance(args[0], GeneralRegisterType):
        return False

    if op.immediate.value.data == 1:
        op.attributes["label"] = StringAttr(f"{args[0].register_name}--")
        op.attributes["description"] = StringAttr("Decrements the register")
    else:
        op.attributes["label"] = StringAttr(
            f"{args[0].register_name} -= {op.immediate.value.data}"
        )
        op.attributes["description"] = StringAttr(
            "Subtracts a constant from the register"
        )
    return True


anno_functions: list[Callable[[Operation, OpArgs], bool]] = [
    _anno_xor,
    _anno_sub_self,
    _anno_add_self,
    _anno_add_const,
    _anno_sub_const,
]


def anno_operation(op: Operation) -> None:
    """Adds annotations for an operation depending on idiomatic patterns.
    The annotations are in the op.attributes field, with the following:
    attributes["label"]: the idiomatic pattern (e.g. "eax++")
    attributes["description"]: an explanation of the pattern (e.g.
        "increments the register")

    Args:
        op: The xDSL operation to annotate."""
    if not isinstance(op, X86Instruction):
        return

    args: OpArgs = op.assembly_line_args()

    for f in anno_functions:
        if f(op, args):
            break
