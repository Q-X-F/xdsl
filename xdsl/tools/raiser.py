from xdsl.dialects.arith import XOrIOp, ConstantOp, AddiOp, IntegerAttr, FloatAttr,
from xdsl.dialects.builtin import StringAttr
from xdsl.ir import Operation
from xdsl.pattern_rewriter import RewritePattern, PatternRewriter

def selfXor(op: Operation) -> None:
    if not isinstance(op, XOrIOp):
        return
    if op.lhs != op.rhs:
        return
    op.attributes["label"] = StringAttr(f"{op.lhs.name_hint} = 0")
    op.attributes["description"] = StringAttr("XORs the register with itself, setting it to 0")

# x + 0 = x
class AddZeroPattern(RewritePattern):
    def match_and_rewrite(self, op: Operation, rewriter: PatternRewriter) -> None:
        if not isinstance(op, AddiOp):
            return
        if not isinstance(cst := op.rhs.owner, ConstantOp):
            return
        if not isinstance(cst.value, IntegerAttr) and not isinstance(cst.value, FloatAttr):
            return
        if cst.value.value.data != 0:
            return
        rewriter.replace_op(op, [], new_results=[op.lhs])




