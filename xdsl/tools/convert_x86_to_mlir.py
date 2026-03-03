from enum import Enum, auto

from lark import ParseTree, Token

from xdsl.dialects.builtin import Block, Region, SSAValue
from xdsl.dialects.x86 import *
from xdsl.dialects.x86.ops import ConditionalJumpOperation, X86Instruction
from xdsl.dialects.x86.registers import RFLAGS, X86_INDEX_BY_NAME
from xdsl.dialects.x86_func import *
from xdsl.ir import BlockArgument

from xdsl.tools.cfg import group_functions


class X86ConversionError(Exception):
    def __init__(self, *args: object):
        super().__init__(*args)


class OperandType(Enum):
    REG = auto()
    MEM = auto()
    IMM = auto()


CONDITIONAL_JUMP_OPS: dict[str, type[ConditionalJumpOperation]] = {
    "jae": C_JaeOp,
    "ja": C_JaOp,
    "jbe": C_JbeOp,
    "jb": C_JbOp,
    "jc": C_JcOp,
    "je": C_JeOp,
    "jge": C_JgeOp,
    "jg": C_JgOp,
    "jle": C_JleOp,
    "jl": C_JlOp,
    "jnae": C_JnaeOp,
    "jna": C_JnaOp,
    "jnbe": C_JnbeOp,
    "jnb": C_JnbOp,
    "jnc": C_JncOp,
    "jne": C_JneOp,
    "jnge": C_JngeOp,
    "jng": C_JngOp,
    "jnle": C_JnleOp,
    "jnl": C_JnlOp,
    "jno": C_JnoOp,
    "jnp": C_JnpOp,
    "jns": C_JnsOp,
    "jnz": C_JnzOp,
    "jo": C_JoOp,
    "jpe": C_JpeOp,
    "jpo": C_JpoOp,
    "jp": C_JpOp,
    "js": C_JsOp,
    "jz": C_JzOp,
}


def is_jump_instruction(tree: Token | ParseTree) -> bool:
    if isinstance(tree, Token) or not isinstance(tree.children[0], Token):
        return False
    opcode = tree.children[0].value.lower()
    return opcode == "jmp" or opcode in CONDITIONAL_JUMP_OPS.keys()


def is_terminating_instruction(tree: Token | ParseTree) -> bool:
    if is_jump_instruction(tree):
        return True
    if isinstance(tree, Token) or not isinstance(tree.children[0], Token):
        return False
    opcode = tree.children[0].value.lower()
    return opcode == "ret"


class X86Converter:
    def __init__(self):
        self.blocks: list[Block] = []
        self.block_register_inputs: list[dict[str, BlockArgument]] = []
        self.label_map: dict[str, int] = {}
        self.current_register_values: dict[str, SSAValue] = {}

    def get_basic_blocks(self, tree: ParseTree) -> list[list[Token | ParseTree]]:
        blocks: list[list[Token | ParseTree]] = [[]]
        self.label_map.clear()
        for instruction in tree.children:
            if isinstance(instruction, Token):
                raise X86ConversionError("Invalid code structure")
            if instruction.data == "label":
                if not isinstance(instruction.children[0], Token):
                    raise X86ConversionError("Invalid code structure")
                if len(blocks[-1]) == 0:  # don't add new block if last one was empty
                    blocks.pop()
                self.label_map[instruction.children[0].value] = len(blocks)
                blocks.append([])
            blocks[-1].append(instruction)
            if is_terminating_instruction(instruction):
                blocks.append([])
        if len(blocks[-1]) == 0:
            blocks.pop()
        return blocks

    def new_basic_block(self) -> None:
        block = Block()
        self.blocks.append(block)
        self.block_register_inputs.append({})
        for register, i in X86_INDEX_BY_NAME.items():
            self.block_register_inputs[-1][register] = block.insert_arg(
                GeneralRegisterType.from_name(register), i
            )
        self.block_register_inputs[-1]["rflags"] = block.insert_arg(RFLAGS, 16)

    def parse_jump(self, instruction: ParseTree, block_index: int) -> X86Instruction:
        opcode = instruction.children[0]
        if not isinstance(opcode, Token):
            raise X86ConversionError("Instruction should start with opcode token")
        opcode = opcode.lower()

        print(instruction)

        if len(instruction.children) != 2:
            raise X86ConversionError("Jump instruction must have one operand")

        label = instruction.children[1]
        if not isinstance(label, Token) or label.type != "LABELNAME":
            raise X86ConversionError("Jump instruction must have label operand")
        label = label.value
        if label not in self.label_map:
            raise X86ConversionError(f"Label {label} does not exist in the program")
        target_block = self.blocks[self.label_map[label]]
        regs = list(self.current_register_values.values())

        if opcode == "jmp":
            return C_JmpOp(block_values=regs, successor=target_block)

        if block_index == len(self.blocks) - 1:
            raise X86ConversionError(
                "Conditional jump at the end of program (has no successor)"
            )
        else_block = self.blocks[block_index + 1]
        return CONDITIONAL_JUMP_OPS[opcode](
            rflags=self.current_register_values["rflags"],
            then_values=regs,
            else_values=regs,
            then_block=target_block,
            else_block=else_block,
        )

    def parse_operand_types(
        self, operands: list[Token | ParseTree]
    ) -> list[OperandType]:
        types: list[OperandType] = []
        for operand in operands:
            if isinstance(operand, Token):
                if operand.type == "REG":
                    types.append(OperandType.REG)
                elif operand.type == "IMM":
                    types.append(OperandType.IMM)
                else:
                    raise X86ConversionError(
                        "Data instruction cannot have label operand"
                    )
            else:
                types.append(OperandType.MEM)
        return types

    def parse_instruction_type(
        self, opcode: str, operands: list[Token | ParseTree]
    ) -> str:
        match self.parse_operand_types(operands):
            case [OperandType.REG, OperandType.REG]:
                match opcode:
                    case "add" | "sub" | "and" | "xor" | "or" | "imul":
                        return "RS"
                    case "mov":
                        return "DS"
                    case "cmp":
                        return "SS"
                    case _:
                        raise X86ConversionError(
                            "Invalid combination of opcode and operands"
                        )
            case [OperandType.REG, OperandType.MEM]:
                match opcode:
                    case "add" | "sub" | "and" | "xor" | "or" | "imul":
                        return "RM"
                    case "lea" | "mov":
                        return "DM"
                    case "cmp":
                        return "SM"
                    case _:
                        raise X86ConversionError(
                            "Invalid combination of opcode and operands"
                        )
            case [OperandType.REG, OperandType.IMM]:
                match opcode:
                    case "add" | "sub" | "and" | "xor" | "or":
                        return "RI"
                    case "mov":
                        return "DI"
                    case "cmp":
                        return "SI"
                    case _:
                        raise X86ConversionError(
                            "Invalid combination of opcode and operands"
                        )
            case [OperandType.MEM, OperandType.REG]:
                match opcode:
                    case "add" | "sub" | "and" | "xor" | "or" | "cmp" | "mov":
                        return "MS"
                    case _:
                        raise X86ConversionError(
                            "Invalid combination of opcode and operands"
                        )
            case [OperandType.MEM, OperandType.IMM]:
                match opcode:
                    case "add" | "sub" | "and" | "xor" | "or" | "cmp" | "mov":
                        return "MI"
                    case _:
                        raise X86ConversionError(
                            "Invalid combination of opcode and operands"
                        )
            case [OperandType.REG]:
                match opcode:
                    case "dec" | "inc" | "neg" | "not":
                        return "R"
                    case "push" | "imul" | "idiv":
                        return "S"
                    case "pop":
                        return "D"
                    case _:
                        raise X86ConversionError(
                            "Invalid combination of opcode and operands"
                        )
            case [OperandType.MEM]:
                match opcode:
                    case "dec" | "inc" | "neg" | "not" | "push" | "pop" | "imul" | "idiv":
                        return "M"
                    case _:
                        raise X86ConversionError(
                            "Invalid combination of opcode and operands"
                        )
            case []:
                match opcode:
                    case "ret":
                        return "C"
                    case _:
                        raise X86ConversionError(
                            "Invalid combination of opcode and operands"
                        )
            case [OperandType.REG, OperandType.REG, OperandType.IMM]:
                match opcode:
                    case "imul":
                        return "DSI"
                    case _:
                        raise X86ConversionError(
                            "Invalid combination of opcode and operands"
                        )
            case [OperandType.REG, OperandType.MEM, OperandType.IMM]:
                match opcode:
                    case "imul":
                        return "DMI"
                    case _:
                        raise X86ConversionError(
                            "Invalid combination of opcode and operands"
                        )
            case _:
                raise X86ConversionError("Invalid combination of opcode and operands")

    def get_immediate_operand(self, operand: Token | ParseTree) -> int:
        if not isinstance(operand, Token):
            raise X86ConversionError("Invalid immediate operand")
        try:
            return int(operand)
        except ValueError:
            raise X86ConversionError(f"Invalid immediate operand {operand}") from None

    def get_memory_operand(self, operand: Token | ParseTree) -> tuple[SSAValue, int]:
        # assuming tokens are [reg] or [reg+offset]; other forms not supported by MLIR
        if isinstance(operand, Token) or len(operand.children) not in (1, 3):
            raise X86ConversionError("Invalid memory operand")
        if not isinstance(operand.children[0], Token):
            raise X86ConversionError("Invalid memory operand")
        register = self.current_register_values[operand.children[0].value.lower()]
        offset = 0
        if len(operand.children) == 3:
            if not isinstance(operand.children[1], Token) or not isinstance(
                operand.children[2], Token
            ):
                raise X86ConversionError("Invalid memory operand")
            try:
                if operand.children[1] == "+":
                    offset = int(operand.children[2])
                else:
                    offset = -int(operand.children[2])
            except ValueError:
                raise X86ConversionError(f"Invalid memory offset {offset}") from None
        return register, offset

    def get_dest_register_type(self, operand: Token | ParseTree) -> GeneralRegisterType:
        if (
            not isinstance(operand, Token)
            or operand.value.lower() not in X86_INDEX_BY_NAME
        ):
            raise X86ConversionError("Invalid register operand")
        return GeneralRegisterType.from_name(operand)

    def get_source_register(self, operand: Token | ParseTree) -> SSAValue:
        if (
            not isinstance(operand, Token)
            or operand.value.lower() not in X86_INDEX_BY_NAME
        ):
            raise X86ConversionError("Invalid register operand")
        return self.current_register_values[operand.value.lower()]

    def set_destination_register(
        self, operand: Token | ParseTree, value: SSAValue
    ) -> None:
        if (
            not isinstance(operand, Token)
            or operand.value.lower() not in X86_INDEX_BY_NAME
        ):
            raise X86ConversionError("Invalid register operand")
        self.current_register_values[operand.value.lower()] = value

    def parse_instruction(self, instruction: ParseTree) -> X86Instruction:
        opcode = instruction.children[0]
        if not isinstance(opcode, Token):
            raise X86ConversionError("Instruction should start with opcode token")
        opcode = opcode.lower()

        # TODO: fix clobbered registers...
        if opcode == "call":
            if (
                len(instruction.children) != 2
                or not isinstance(instruction.children[1], Token)
                or instruction.children[1].type != "LABELNAME"
            ):
                raise X86ConversionError("Call instruction should have exactly one label operand")
            return_types: list[Attribute] = []
            op = CallOp(
                callee=str(instruction.children[1]),
                arguments=list(self.current_register_values.values()),
                return_types=return_types
            )
            return op

        instruction_type = self.parse_instruction_type(opcode, instruction.children[1:])

        match instruction_type:
            case "RS":
                dest = self.get_source_register(instruction.children[1])
                source = self.get_source_register(instruction.children[2])
                match opcode:
                    case "add":
                        op = RS_AddOp(register_in=dest, source=source)
                    case "sub":
                        op = RS_SubOp(register_in=dest, source=source)
                    case "and":
                        op = RS_AndOp(register_in=dest, source=source)
                    case "xor":
                        op = RS_XorOp(register_in=dest, source=source)
                    case "or":
                        op = RS_OrOp(register_in=dest, source=source)
                    case "imul":
                        op = RS_ImulOp(register_in=dest, source=source)
                    case _:
                        raise X86ConversionError(f"Invalid opcode {opcode}")
                self.set_destination_register(instruction.children[1], op.results[0])

            case "DS":
                dest = self.get_dest_register_type(instruction.children[1])
                source = self.get_source_register(instruction.children[2])
                op = DS_MovOp(source=source, destination=dest)
                self.set_destination_register(instruction.children[1], op.results[0])

            case "SS":
                source1 = self.get_source_register(instruction.children[1])
                source2 = self.get_source_register(instruction.children[2])
                op = SS_CmpOp(source1=source1, source2=source2, result=RFLAGS)
                self.current_register_values["rflags"] = op.results[0]

            case "RM":
                dest = self.get_source_register(instruction.children[1])
                memory, offset = self.get_memory_operand(instruction.children[2])
                match opcode:
                    case "add":
                        op = RM_AddOp(
                            register_in=dest, memory=memory, memory_offset=offset
                        )
                    case "sub":
                        op = RM_SubOp(
                            register_in=dest, memory=memory, memory_offset=offset
                        )
                    case "and":
                        op = RM_AndOp(
                            register_in=dest, memory=memory, memory_offset=offset
                        )
                    case "xor":
                        op = RM_XorOp(
                            register_in=dest, memory=memory, memory_offset=offset
                        )
                    case "or":
                        op = RM_OrOp(
                            register_in=dest, memory=memory, memory_offset=offset
                        )
                    case "imul":
                        op = RM_ImulOp(
                            register_in=dest, memory=memory, memory_offset=offset
                        )
                    case _:
                        raise X86ConversionError(f"Invalid opcode {opcode}")
                self.set_destination_register(instruction.children[1], op.results[0])

            case "DM":
                dest = self.get_dest_register_type(instruction.children[1])
                memory, offset = self.get_memory_operand(instruction.children[2])
                match opcode:
                    case "mov":
                        op = DM_MovOp(
                            memory=memory, memory_offset=offset, destination=dest
                        )
                    case "lea":
                        op = DM_LeaOp(
                            memory=memory, memory_offset=offset, destination=dest
                        )
                    case _:
                        raise X86ConversionError(f"Invalid opcode {opcode}")
                self.set_destination_register(instruction.children[1], op.results[0])

            case "SM":
                source = self.get_source_register(instruction.children[1])
                memory, offset = self.get_memory_operand(instruction.children[2])
                op = SM_CmpOp(
                    source=source, memory=memory, memory_offset=offset, result=RFLAGS
                )
                self.current_register_values["rflags"] = op.results[0]

            case "RI":
                dest = self.get_source_register(instruction.children[1])
                immediate = self.get_immediate_operand(instruction.children[2])
                match opcode:
                    case "add":
                        op = RI_AddOp(register_in=dest, immediate=immediate)
                    case "sub":
                        op = RI_SubOp(register_in=dest, immediate=immediate)
                    case "and":
                        op = RI_AndOp(register_in=dest, immediate=immediate)
                    case "xor":
                        op = RI_XorOp(register_in=dest, immediate=immediate)
                    case "or":
                        op = RI_OrOp(register_in=dest, immediate=immediate)
                    case _:
                        raise X86ConversionError(f"Invalid opcode {opcode}")
                self.set_destination_register(instruction.children[1], op.results[0])

            case "DI":
                dest = self.get_dest_register_type(instruction.children[1])
                immediate = self.get_immediate_operand(instruction.children[2])
                op = DI_MovOp(immediate=immediate, destination=dest)
                self.set_destination_register(instruction.children[1], op.results[0])

            case "SI":
                source = self.get_source_register(instruction.children[1])
                immediate = self.get_immediate_operand(instruction.children[2])
                op = SI_CmpOp(source=source, immediate=immediate)
                self.current_register_values["rflags"] = op.results[0]

            case "MS":
                memory, offset = self.get_memory_operand(instruction.children[1])
                source = self.get_source_register(instruction.children[2])
                match opcode:
                    case "add":
                        op = MS_AddOp(
                            source=source, memory=memory, memory_offset=offset
                        )
                    case "sub":
                        op = MS_SubOp(
                            source=source, memory=memory, memory_offset=offset
                        )
                    case "and":
                        op = MS_AndOp(
                            source=source, memory=memory, memory_offset=offset
                        )
                    case "xor":
                        op = MS_XorOp(
                            source=source, memory=memory, memory_offset=offset
                        )
                    case "or":
                        op = MS_OrOp(source=source, memory=memory, memory_offset=offset)
                    case "mov":
                        op = MS_MovOp(
                            source=source, memory=memory, memory_offset=offset
                        )
                    case "cmp":
                        op = MS_CmpOp(
                            source=source,
                            memory=memory,
                            memory_offset=offset,
                            result=RFLAGS,
                        )
                    case _:
                        raise X86ConversionError(f"Invalid opcode {opcode}")
                if opcode == "cmp":
                    self.current_register_values["rflags"] = op.results[0]
                else:
                    self.set_destination_register(
                        instruction.children[1], op.results[0]
                    )

            case "MI":
                memory, offset = self.get_memory_operand(instruction.children[1])
                immediate = self.get_immediate_operand(instruction.children[2])
                match opcode:
                    case "add":
                        op = MI_AddOp(
                            memory=memory, memory_offset=offset, immediate=immediate
                        )
                    case "sub":
                        op = MI_SubOp(
                            memory=memory, memory_offset=offset, immediate=immediate
                        )
                    case "and":
                        op = MI_AndOp(
                            memory=memory, memory_offset=offset, immediate=immediate
                        )
                    case "xor":
                        op = MI_XorOp(
                            memory=memory, memory_offset=offset, immediate=immediate
                        )
                    case "or":
                        op = MI_OrOp(
                            memory=memory, memory_offset=offset, immediate=immediate
                        )
                    case "mov":
                        op = MI_MovOp(
                            memory=memory, memory_offset=offset, immediate=immediate
                        )
                    case "cmp":
                        op = MI_CmpOp(
                            memory=memory,
                            memory_offset=offset,
                            immediate=immediate,
                            result=RFLAGS,
                        )
                    case _:
                        raise X86ConversionError(f"Invalid opcode {opcode}")
                if opcode == "cmp":
                    self.current_register_values["rflags"] = op.results[0]

            case "R":
                dest = self.get_source_register(instruction.children[1])
                match opcode:
                    # NOTE: idk why pylance complains about the types here...
                    case "dec":
                        op = R_DecOp(register_in=dest)  # pyright: ignore[reportArgumentType]
                    case "inc":
                        op = R_IncOp(register_in=dest)  # pyright: ignore[reportArgumentType]
                    case "neg":
                        op = R_NegOp(register_in=dest)  # pyright: ignore[reportArgumentType]
                    case "not":
                        op = R_NotOp(register_in=dest)  # pyright: ignore[reportArgumentType]
                    case _:
                        raise X86ConversionError(f"Invalid opcode {opcode}")
                self.set_destination_register(instruction.children[1], op.results[0])

            case "D":
                rsp_in = self.current_register_values["rsp"]
                dest = self.get_dest_register_type(instruction.children[1])
                op = D_PopOp(rsp_in=rsp_in, destination=dest)
                self.current_register_values["rsp"] = op.results[0]
                self.set_destination_register(instruction.children[1], op.results[1])

            case "S":
                source = self.get_source_register(instruction.children[1])
                match opcode:
                    case "push":
                        op = S_PushOp(
                            rsp_in=self.current_register_values["rsp"], source=source
                        )
                    case "imul":
                        op = S_ImulOp(
                            rax_input=self.current_register_values["rax"], source=source,
                            rax_output=GeneralRegisterType.from_name("rax"),
                            rdx_output=GeneralRegisterType.from_name("rdx")
                        )
                    case "idiv":
                        op = S_IDivOp(
                            rdx_input=self.current_register_values["rdx"],
                            rax_input=self.current_register_values["rax"],
                            source=source,
                            rax_output=GeneralRegisterType.from_name("rax"),
                            rdx_output=GeneralRegisterType.from_name("rdx")
                        )
                    case _:
                        raise X86ConversionError(f"Invalid opcode {opcode}")
                if opcode == "push":
                    self.current_register_values["rsp"] = op.results[0]
                if opcode in ("imul", "idiv"):
                    self.current_register_values["rdx"] = op.results[0]
                    self.current_register_values["rax"] = op.results[1]

            case "M":
                memory, offset = self.get_memory_operand(instruction.children[1])
                rsp_in = self.current_register_values["rsp"]
                match opcode:
                    case "dec":
                        op = M_DecOp(memory=memory, memory_offset=offset)
                    case "inc":
                        op = M_IncOp(memory=memory, memory_offset=offset)
                    case "neg":
                        op = M_NegOp(memory=memory, memory_offset=offset)
                    case "not":
                        op = M_NotOp(memory=memory, memory_offset=offset)
                    case "imul":
                        op = M_ImulOp(
                            rax_in=self.current_register_values["rax"],
                            memory=memory, memory_offset=offset,
                            rax_out=GeneralRegisterType.from_name("rax"),
                            rdx_out=GeneralRegisterType.from_name("rdx")
                        )
                    case "idiv":
                        op = M_IDivOp(
                            rdx_in=self.current_register_values["rdx"],
                            rax_in=self.current_register_values["rax"],
                            memory=memory, memory_offset=offset,
                            rax_out=GeneralRegisterType.from_name("rax"),
                            rdx_out=GeneralRegisterType.from_name("rdx")
                        )
                    case "push":
                        op = M_PushOp(
                            rsp_in=rsp_in,
                            memory=memory,
                            memory_offset=offset,
                            rsp_out=GeneralRegisterType.from_name("rsp"),
                        )
                    case "pop":
                        op = M_PopOp(
                            rsp_in=rsp_in,
                            memory=memory,
                            memory_offset=offset,
                            rsp_out=GeneralRegisterType.from_name("rsp"),
                        )
                    case _:
                        raise X86ConversionError(f"Invalid opcode {opcode}")
                if opcode in ("pop", "push"):
                    self.current_register_values["rsp"] = op.results[0]
                if opcode in ("imul", "idiv"):
                    self.current_register_values["rdx"] = op.results[0]
                    self.current_register_values["rax"] = op.results[1]

            case "C":
                match opcode:
                    case "ret":
                        op = RetOp()
                    case _:
                        raise X86ConversionError(f"Invalid opcode {opcode}")
                        
            case "DSI":
                dest = self.get_dest_register_type(instruction.children[1])
                source = self.get_source_register(instruction.children[2])
                immediate = self.get_immediate_operand(instruction.children[3])
                op = DSI_ImulOp(source=source, destination=dest, immediate=immediate)
                self.set_destination_register(instruction.children[1], op.results[0])

            case "DMI":
                dest = self.get_dest_register_type(instruction.children[1])
                memory, offset = self.get_memory_operand(instruction.children[2])
                immediate = self.get_immediate_operand(instruction.children[3])
                op = DMI_ImulOp(
                    memory=memory, memory_offset=offset,
                    destination=dest, immediate=immediate
                )
                self.set_destination_register(instruction.children[1], op.results[0])

            case _:
                raise X86ConversionError(f"Invalid opcode {opcode}")

        return op

    def convert_blocks(self, instructions: list[list[Token | ParseTree]]) -> None:
        self.blocks.clear()
        self.block_register_inputs.clear()
        for _ in instructions:
            self.new_basic_block()

        for index, block in enumerate(instructions):
            self.current_register_values.clear()
            self.current_register_values["rflags"] = self.block_register_inputs[
                index
            ]["rflags"]
            for register in X86_INDEX_BY_NAME.keys():
                self.current_register_values[register] = self.block_register_inputs[
                    index
                ][register]

            ended_with_jump = False
            for instruction in block:
                # label
                if isinstance(instruction, Token):
                    raise X86ConversionError("Invalid code structure")

                if instruction.data == "label":
                    if not isinstance(instruction.children[0], Token):
                        raise X86ConversionError("Invalid code structure")
                    self.blocks[index].add_op(LabelOp(instruction.children[0].value))
                    continue
            
                if is_terminating_instruction(instruction):
                    ended_with_jump = True

                if is_jump_instruction(instruction):
                    self.blocks[index].add_op(self.parse_jump(instruction, index))
                else:
                    self.blocks[index].add_op(self.parse_instruction(instruction))

            if not ended_with_jump:
                if index != len(instructions) - 1:
                    self.blocks[index].add_op(
                        FallthroughOp(
                            list(self.current_register_values.values()),
                            self.blocks[index + 1],
                        )
                    )

    def convert(self, tree: ParseTree) -> Region:
        blocks = self.get_basic_blocks(tree)
        self.convert_blocks(blocks)

        grouped_blocks = group_functions(self.blocks, self.label_map)
        final_blocks: list[Block] = []
        for block in grouped_blocks:
            if isinstance(block, Block):
                final_blocks.append(block)
            else:
                region = Region(block)
                assert(isinstance(block[0].first_op, LabelOp))
                name = str(block[0].first_op.label)
                register_args: list[Attribute] = []
                for register in X86_INDEX_BY_NAME.keys():
                    register_args.append(GeneralRegisterType.from_name(register))
                register_args.append(RFLAGS)
                func = FuncOp(
                    name, region, (register_args, [])
                )
                final_blocks.append(Block([func]))
        
        region = Region(final_blocks)
        return region


if __name__ == "__main__":
    from xdsl.tools.lark_parser import parse

    program2 = """
            
        
        test_func_3:
            cmp rax, rbx
            jnz func_3_label
            imul rax
            ret
        
        test_func:
            pop rbx
            add rbx, [rax+3]
            ret

        func_3_label:
            imul rbx
            ret
        
        test_func_2:
            push rax
            call test_func
            ret

            
    """

    program = """
        _start:
            push rbx           ; save callee-saved register

            xor rax, rax       ; fib_a = 0
            mov rbx, 1         ; fib_b = 1
            mov rcx, 12        ; print first 12 numbers

        print_loop:
            ; print current fib (rax) using printf

            ; mov rdi, fmt

            mov rsi, rax
            xor rax, rax       ; varargs count
            ; call printf        ; (external, linked via ld -dynamic-linker /lib64/ld-linux-x86-64.so.2 ... or gcc fib.o)

            ; update fib: temp = a + b; a = b; b = temp
            mov rdx, [rax-5]       ; rdx = old a
            mov rax, [rbx+3]       ; a = old b
            add rax, [rdx]       ; a += old a

            dec rcx

            ; TODO: support conditional jumps
            jnz print_loop
            jmp print_loop

            pop rbx            ; restore

            ; exit(0)
            mov rax, 60
            xor rdi, rdi
            ; TODO: support syscalls
            ; syscall
    """

    jambloat = parse(program2)
    print(jambloat)

    converter = X86Converter()
    res = converter.convert(jambloat)

    # TODO: what are we doing about this?
    # are we ignoring it or explicitly requiring a return/jump instruction at the end?
    try:
        res.verify()
    except Exception:
        # print(e)
        pass

    from xdsl.printer import Printer

    printer = Printer()
    printer.print_region(res)
    print()

    from xdsl.dialects.builtin import ModuleOp
    from xdsl.dialects.x86.ops import x86_code

    jambloat = x86_code(ModuleOp(res))
    print(jambloat)

    # TODO: implement function calls
