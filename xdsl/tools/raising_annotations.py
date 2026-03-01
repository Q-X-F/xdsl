from xdsl.dialects.arith import AddiOp, ConstantOp, SubiOp, XOrIOp
from xdsl.dialects.builtin import IntegerAttr, StringAttr
from xdsl.ir import Operation

def annoXor(op: Operation) -> None:
    if not isinstance(op, XOrIOp):
        return
    if op.lhs != op.rhs:
        return
    op.attributes["label"] = StringAttr(f"{op.lhs.name_hint} = 0")
    op.attributes["description"] = StringAttr("XORs the register with itself, setting it to 0")

def annoSub(op: Operation) -> None:
    if not isinstance(op, SubiOp):
        return
    if op.lhs != op.rhs:
        return
    op.attributes["label"] = StringAttr(f"{op.lhs.name_hint} = 0")
    op.attributes["description"] = StringAttr("Subtracts the register from itself, setting it to 0")

def annoAddConst(op: Operation) -> None:
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
        op.attributes["label"] = StringAttr(f"{op.lhs.name_hint} += {c.value.value.data}")
        op.attributes["description"] = StringAttr("Adds a constant to the register")
