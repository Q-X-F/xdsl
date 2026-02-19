from __future__ import annotations

from collections.abc import Sequence

from xdsl.backend.assembly_printer import AssemblyPrintable, AssemblyPrinter
from xdsl.dialects.builtin import (
    FunctionType,
    StringAttr,
    SymbolNameConstraint,
    FlatSymbolRefAttrConstr,
    SymbolRefAttr
)
from xdsl.dialects.utils import (
    parse_func_op_like,
    print_func_op_like,
)
from xdsl.dialects.x86.ops import X86Instruction
from xdsl.ir import Attribute, Dialect, Operation, Region, SSAValue
from xdsl.irdl import (
    IRDLOperation,
    irdl_op_definition,
    attr_def,
    opt_attr_def,
    prop_def,
    region_def,
    traits_def,
    var_operand_def,
    var_result_def,
)
from xdsl.parser import Parser
from xdsl.printer import Printer
from xdsl.traits import (
    SymbolUserOpInterface,
    CallableOpInterface,
    HasParent,
    IsolatedFromAbove,
    IsTerminator,
    SymbolTable,
    SymbolOpInterface,
)
from xdsl.utils.exceptions import DiagnosticException, VerifyException


class FuncOpCallableInterface(CallableOpInterface):
    @classmethod
    def get_callable_region(cls, op: Operation) -> Region:
        assert isinstance(op, FuncOp)
        return op.body

    @classmethod
    def get_argument_types(cls, op: Operation) -> tuple[Attribute, ...]:
        assert isinstance(op, FuncOp)
        return op.function_type.inputs.data

    @classmethod
    def get_result_types(cls, op: Operation) -> tuple[Attribute, ...]:
        assert isinstance(op, FuncOp)
        return op.function_type.outputs.data

        
class CallOpSymbolUserOpInterface(SymbolUserOpInterface):
    def verify(self, op: Operation) -> None:
        assert isinstance(op, CallOp)

        found_callee = SymbolTable.lookup_symbol(op, op.callee)
        if not found_callee:
            raise VerifyException(f"'{op.callee}' could not be found in symbol table")

        if not isinstance(found_callee, FuncOp):
            raise VerifyException(f"'{op.callee}' does not reference a valid function")

        if len(found_callee.function_type.inputs) != len(op.arguments):
            raise VerifyException("incorrect number of operands for callee")

        if len(found_callee.function_type.outputs) != len(op.result_types):
            raise VerifyException("incorrect number of results for callee")

        for idx, (found_operand, operand) in enumerate(
            zip(found_callee.function_type.inputs, (arg.type for arg in op.arguments))
        ):
            if found_operand != operand:
                raise VerifyException(
                    f"operand type mismatch: expected operand type {found_operand}, "
                    f"but provided {operand} for operand number {idx}"
                )

        for idx, (found_res, res) in enumerate(
            zip(found_callee.function_type.outputs, op.result_types)
        ):
            if found_res != res:
                raise VerifyException(
                    f"result type mismatch: expected result type {found_res}, but "
                    f"provided {res} for result number {idx}"
                )

        return



@irdl_op_definition
class FuncOp(IRDLOperation, AssemblyPrintable):
    """x86 function definition operation"""

    name = "x86_func.func"
    sym_name = attr_def(SymbolNameConstraint())
    body = region_def()
    function_type = attr_def(FunctionType)
    sym_visibility = opt_attr_def(StringAttr)

    traits = traits_def(
        SymbolOpInterface(),
        FuncOpCallableInterface(),
        IsolatedFromAbove(),
    )

    def __init__(
        self,
        name: str,
        region: Region,
        function_type: FunctionType | tuple[Sequence[Attribute], Sequence[Attribute]],
        visibility: StringAttr | str | None = None,
    ):
        if isinstance(function_type, tuple):
            inputs, outputs = function_type
            function_type = FunctionType.from_lists(inputs, outputs)
        if isinstance(visibility, str):
            visibility = StringAttr(visibility)
        attributes: dict[str, Attribute | None] = {
            "sym_name": StringAttr(name),
            "function_type": function_type,
            "sym_visibility": visibility,
        }

        super().__init__(attributes=attributes, regions=[region])

    @classmethod
    def parse(cls, parser: Parser) -> FuncOp:
        visibility = parser.parse_optional_visibility_keyword()
        (name, input_types, return_types, region, extra_attrs, arg_attrs, res_attrs) = (
            parse_func_op_like(
                parser,
                reserved_attr_names=("sym_name", "function_type", "sym_visibility"),
            )
        )
        if arg_attrs:
            raise NotImplementedError("arg_attrs not implemented in x86_func")
        if res_attrs:
            raise NotImplementedError("res_attrs not implemented in x86_func")
        func = FuncOp(name, region, (input_types, return_types), visibility)
        if extra_attrs is not None:
            func.attributes |= extra_attrs.data
        return func

    def print(self, printer: Printer):
        if self.sym_visibility:
            visibility = self.sym_visibility.data
            printer.print_string(f" {visibility}")

        print_func_op_like(
            printer,
            self.sym_name,
            self.function_type,
            self.body,
            self.attributes,
            reserved_attr_names=("sym_name", "function_type", "sym_visibility"),
        )

    def print_assembly(self, printer: AssemblyPrinter) -> None:
        if not self.body.blocks:
            # Print nothing for function declaration
            return

        printer.emit_section(".text")

        if self.sym_visibility is not None:
            match self.sym_visibility.data:
                case "public":
                    printer.print_string(f".globl {self.sym_name.data}\n", indent=0)
                case "private":
                    printer.print_string(f".local {self.sym_name.data}\n", indent=0)
                case _:
                    raise DiagnosticException(
                        f"Unexpected visibility {self.sym_visibility.data} for function {self.sym_name}"
                    )

        printer.print_string(f"{self.sym_name.data}:\n")



@irdl_op_definition
class CallOp(X86Instruction):
    """x86 function call operation"""

    name = "x86_func.call"
    arguments = var_operand_def()
    callee = prop_def(FlatSymbolRefAttrConstr)
    res = var_result_def()

    traits = traits_def(
        CallOpSymbolUserOpInterface(),
    )

    assembly_format = (
        "$callee `(` $arguments `)` attr-dict `:` functional-type($arguments, $res)"
    )

    def __init__(
        self,
        callee: str | SymbolRefAttr,
        arguments: Sequence[SSAValue | Operation],
        return_types: Sequence[Attribute],
    ):
        if isinstance(callee, str):
            callee = SymbolRefAttr(callee)
        super().__init__(
            operands=[arguments],
            result_types=[return_types],
            properties={"callee": callee},
        )

    def assembly_line_args(self):
        return (self.callee.string_value(),)


@irdl_op_definition
class RetOp(X86Instruction):
    """
    Return from subroutine.
    """

    name = "x86_func.ret"

    assembly_format = "attr-dict"

    traits = traits_def(IsTerminator(), HasParent(FuncOp))

    def __init__(
        self,
        *,
        comment: str | StringAttr | None = None,
    ):
        if isinstance(comment, str):
            comment = StringAttr(comment)

        super().__init__(
            attributes={
                "comment": comment,
            },
        )

    def assembly_line_args(self):
        return ()


X86_FUNC = Dialect(
    "x86_func",
    [
        FuncOp,
        CallOp,
        RetOp,
    ],
)
