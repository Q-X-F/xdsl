from xdsl.dialects.arith import XOrIOp, ConstantOp
from xdsl.dialects.builtin import IntegerAttr, i32
from xdsl.ir import Operation
from xdsl.rewriter import Rewriter
from xdsl.pattern_rewriter import RewritePattern

# x XOR x = 0
class SelfXorPattern(RewritePattern):
    def match_and_rewrite(self, op: Operation, rewriter: Rewriter):
        if not isinstance(op, XOrIOp):
            return
        if op.lhs is not op.rhs:
            return
        # Replace x xor x with 0
        zero = ConstantOp.from_int_and_width(0, 32)
        rewriter.replace_op(op, [], new_results=[zero.results[0]])

