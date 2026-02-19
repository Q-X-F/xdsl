from typing import Union
from enum import Enum, auto

from lark import Token, ParseTree

from xdsl.dialects.x86 import *
from xdsl.dialects.x86.ops import X86Instruction, ConditionalJumpOperation
from xdsl.dialects.x86.registers import X86_INDEX_BY_NAME, RFLAGS
from xdsl.dialects.x86_func import *

from xdsl.dialects.builtin import Region, Block, SSAValue
from xdsl.ir import BlockArgument

class X86ConversionError(Exception):
    def __init__(self, *args: object):
        super().__init__(*args)

class OperandType(Enum):
    REG = auto()
    MEM = auto()
    IMM = auto()

CONDITIONAL_JUMP_OPS : dict[str, type[ConditionalJumpOperation]] = {
    "jae":      C_JaeOp,
    "ja":       C_JaOp,
    "jbe":      C_JbeOp,
    "jb":       C_JbOp,
    "jc":       C_JcOp,
    "je":       C_JeOp,
    "jge":      C_JgeOp,
    "jg":       C_JgOp,
    "jle":      C_JleOp,
    "jl":       C_JlOp,
    "jnae":     C_JnaeOp,
    "jna":      C_JnaOp,
    "jnbe":     C_JnbeOp,
    "jnb":      C_JnbOp,
    "jnc":      C_JncOp,
    "jne":      C_JneOp,
    "jnge":     C_JngeOp,
    "jng":      C_JngOp,
    "jnle":     C_JnleOp,
    "jnl":      C_JnlOp,
    "jno":      C_JnoOp,
    "jnp":      C_JnpOp,
    "jns":      C_JnsOp,
    "jnz":      C_JnzOp,
    "jo":       C_JoOp,
    "jpe":      C_JpeOp,
    "jpo":      C_JpoOp,
    "jp":       C_JpOp,
    "js":       C_JsOp,
    "jz":       C_JzOp,
}


def is_jump_instruction(tree: Union[Token, ParseTree]) -> bool:
    if isinstance(tree, Token) or not isinstance(tree.children[0], Token):
        return False
    opcode = tree.children[0].value.lower()
    return opcode == "jmp" or opcode in CONDITIONAL_JUMP_OPS.keys()

def is_terminating_instruction(tree: Union[Token, ParseTree]) -> bool:
    if is_jump_instruction(tree):
        return True
    if isinstance(tree, Token) or not isinstance(tree.children[0], Token):
        return False
    opcode = tree.children[0].value.lower()
    return opcode == "ret"


class X86Converter:
    def __init__(self):
        self.blocks : list[Block] = []
        self.block_register_inputs : list[dict[str, BlockArgument]] = []
        self.label_map : dict[str, int] = {}
        self.current_register_values : dict[str, SSAValue] = {}

    def get_basic_blocks(self, tree: ParseTree) -> list[list[Union[Token, ParseTree]]]:
        blocks : list[list[Union[Token, ParseTree]]] = [[]]
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
            raise X86ConversionError("Conditional jump at the end of program (has no successor)")
        else_block = self.blocks[block_index + 1]
        return CONDITIONAL_JUMP_OPS[opcode](
            rflags=self.current_register_values["rflags"],
            then_values=regs,
            else_values=regs,
            then_block=target_block,
            else_block=else_block
        )
    
    def parse_operand_types(self, operands: list[Union[Token, ParseTree]]) -> list[OperandType]:
        types : list[OperandType] = []
        for operand in operands:
            if isinstance(operand, Token):
                if operand.type == "REG":
                    types.append(OperandType.REG)
                elif operand.type == "IMM":
                    types.append(OperandType.IMM)
                else:
                    raise X86ConversionError("Data instruction cannot have label operand")
            else:
                types.append(OperandType.MEM)
        return types

    def parse_instruction_type(self, opcode: str, operands: list[Union[Token, ParseTree]]) -> str:
        match self.parse_operand_types(operands):
            case [OperandType.REG, OperandType.REG]:
                match opcode:
                    case "add" | "sub" | "and" | "xor" | "or": return "RS"
                    case "mov": return "DS"
                    case "cmp": return "SS"
                    case _: raise X86ConversionError(f"Invalid combination of opcode and operands")
            case [OperandType.REG, OperandType.MEM]:
                match opcode:
                    case "add" | "sub" | "and" | "xor" | "or": return "RM"
                    case "lea" | "mov": return "DM"
                    case "cmp": return "SM"
                    case _: raise X86ConversionError(f"Invalid combination of opcode and operands")
            case [OperandType.REG, OperandType.IMM]:
                match opcode:
                    case "add" | "sub" | "and" | "xor" | "or": return "RI"
                    case "mov": return "DI"
                    case "cmp": return "SI"
                    case _: raise X86ConversionError(f"Invalid combination of opcode and operands")
            case [OperandType.MEM, OperandType.REG]:
                match opcode:
                    case "add" | "sub" | "and" | "xor" | "or" | "cmp" | "mov": return "MS"
                    case _: raise X86ConversionError(f"Invalid combination of opcode and operands")
            case [OperandType.MEM, OperandType.IMM]:
                match opcode:
                    case "add" | "sub" | "and" | "xor" | "or" | "cmp" | "mov": return "MI"
                    case _: raise X86ConversionError(f"Invalid combination of opcode and operands")
            case [OperandType.REG]:
                match opcode:
                    case "dec" | "inc" | "neg" | "not": return "R"
                    case "push": return "S"
                    case "pop": return "D"
                    case _: raise X86ConversionError(f"Invalid combination of opcode and operands")
            case [OperandType.MEM]:
                match opcode:
                    case "dec" | "inc" | "neg" | "not" | "push" | "pop": return "M"
                    case _: raise X86ConversionError(f"Invalid combination of opcode and operands")
            case []:
                match opcode:
                    case "ret": return "C"
                    case _: raise X86ConversionError(f"Invalid combination of opcode and operands")
            case _: raise X86ConversionError(f"Invalid combination of opcode and operands")
    
    def get_immediate_operand(self, operand: Union[Token, ParseTree]) -> int:
        if not isinstance(operand, Token):
            raise X86ConversionError("Invalid immediate operand")
        try:
            return int(operand)
        except ValueError:
            raise X86ConversionError(f"Invalid immediate operand {operand}") from None

    def get_memory_operand(self, operand: Union[Token, ParseTree]) -> tuple[SSAValue, int]:
        # assuming tokens are [reg] or [reg+offset]; other forms not supported by MLIR
        if isinstance(operand, Token) or len(operand.children) not in (1, 3):
            raise X86ConversionError("Invalid memory operand")
        if not isinstance(operand.children[0], Token):
            raise X86ConversionError("Invalid memory operand")
        register = self.current_register_values[operand.children[0].value.lower()]
        offset = 0
        if len(operand.children) == 3:
            if not isinstance(operand.children[1], Token) or not isinstance(operand.children[2], Token):
                raise X86ConversionError("Invalid memory operand")
            try:
                if operand.children[1] == "+":
                    offset = int(operand.children[2])
                else:
                    offset = -int(operand.children[2])
            except ValueError:
                raise X86ConversionError(f"Invalid memory offset {offset}") from None
        return register, offset

    def get_dest_register_type(self, operand: Union[Token, ParseTree]) -> GeneralRegisterType:
        if not isinstance(operand, Token) or operand.value.lower() not in X86_INDEX_BY_NAME:
            raise X86ConversionError("Invalid register operand")
        return GeneralRegisterType.from_name(operand)
    
    def get_source_register(self, operand: Union[Token, ParseTree]) -> SSAValue:
        if not isinstance(operand, Token) or operand.value.lower() not in X86_INDEX_BY_NAME:
            raise X86ConversionError("Invalid register operand")
        return self.current_register_values[operand.value.lower()]

    def set_destination_register(self, operand: Union[Token, ParseTree], value: SSAValue) -> None:
        if not isinstance(operand, Token) or operand.value.lower() not in X86_INDEX_BY_NAME:
            raise X86ConversionError("Invalid register operand")
        self.current_register_values[operand.value.lower()] = value
        
    def parse_instruction(self, instruction: ParseTree) -> X86Instruction:
        opcode = instruction.children[0]
        if not isinstance(opcode, Token):
            raise X86ConversionError("Instruction should start with opcode token")
        opcode = opcode.lower()

        instruction_type = self.parse_instruction_type(opcode, instruction.children[1:])
        
        match instruction_type:
            case "RS":
                dest = self.get_source_register(instruction.children[1])
                source = self.get_source_register(instruction.children[2])
                match opcode:
                    case "add": op = RS_AddOp(register_in=dest, source=source)
                    case "sub": op = RS_SubOp(register_in=dest, source=source)
                    case "and": op = RS_AndOp(register_in=dest, source=source)
                    case "xor": op = RS_XorOp(register_in=dest, source=source)
                    case "or": op = RS_OrOp(register_in=dest, source=source)
                    case _: raise X86ConversionError(f"Invalid opcode {opcode}")
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
                    case "add": op = RM_AddOp(register_in=dest, memory=memory, memory_offset=offset)
                    case "sub": op = RM_SubOp(register_in=dest, memory=memory, memory_offset=offset)
                    case "and": op = RM_AndOp(register_in=dest, memory=memory, memory_offset=offset)
                    case "xor": op = RM_XorOp(register_in=dest, memory=memory, memory_offset=offset)
                    case "or": op = RM_OrOp(register_in=dest, memory=memory, memory_offset=offset)
                    case _: raise X86ConversionError(f"Invalid opcode {opcode}")
                self.set_destination_register(instruction.children[1], op.results[0])

            case "DM":
                dest = self.get_dest_register_type(instruction.children[1])
                memory, offset = self.get_memory_operand(instruction.children[2])
                match opcode:
                    case "mov": op = DM_MovOp(memory=memory, memory_offset=offset, destination=dest)
                    case "lea": op = DM_LeaOp(memory=memory, memory_offset=offset, destination=dest)
                    case _: raise X86ConversionError(f"Invalid opcode {opcode}")
                self.set_destination_register(instruction.children[1], op.results[0])

            case "SM":
                source = self.get_source_register(instruction.children[1])
                memory, offset = self.get_memory_operand(instruction.children[2])
                op = SM_CmpOp(source=source, memory=memory, memory_offset=offset, result=RFLAGS)
                self.current_register_values["rflags"] = op.results[0]

            case "RI":
                dest = self.get_source_register(instruction.children[1])
                immediate = self.get_immediate_operand(instruction.children[2])
                match opcode:
                    case "add": op = RI_AddOp(register_in=dest, immediate=immediate)
                    case "sub": op = RI_SubOp(register_in=dest, immediate=immediate)
                    case "and": op = RI_AndOp(register_in=dest, immediate=immediate)
                    case "xor": op = RI_XorOp(register_in=dest, immediate=immediate)
                    case "or": op = RI_OrOp(register_in=dest, immediate=immediate)
                    case _: raise X86ConversionError(f"Invalid opcode {opcode}")
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
                    case "add": op = MS_AddOp(source=source, memory=memory, memory_offset=offset)
                    case "sub": op = MS_SubOp(source=source, memory=memory, memory_offset=offset)
                    case "and": op = MS_AndOp(source=source, memory=memory, memory_offset=offset)
                    case "xor": op = MS_XorOp(source=source, memory=memory, memory_offset=offset)
                    case "or": op = MS_OrOp(source=source, memory=memory, memory_offset=offset)
                    case "mov": op = MS_MovOp(source=source, memory=memory, memory_offset=offset)
                    case "cmp": op = MS_CmpOp(source=source, memory=memory, memory_offset=offset, result=RFLAGS)
                    case _: raise X86ConversionError(f"Invalid opcode {opcode}")
                if opcode == "cmp":
                    self.current_register_values["rflags"] = op.results[0]
                else:
                    self.set_destination_register(instruction.children[1], op.results[0])
                    
            case "MI":
                memory, offset = self.get_memory_operand(instruction.children[1])
                immediate = self.get_immediate_operand(instruction.children[2])
                match opcode:
                    case "add": op = MI_AddOp(memory=memory, memory_offset=offset, immediate=immediate)
                    case "sub": op = MI_SubOp(memory=memory, memory_offset=offset, immediate=immediate)
                    case "and": op = MI_AndOp(memory=memory, memory_offset=offset, immediate=immediate)
                    case "xor": op = MI_XorOp(memory=memory, memory_offset=offset, immediate=immediate)
                    case "or": op = MI_OrOp(memory=memory, memory_offset=offset, immediate=immediate)
                    case "mov": op = MI_MovOp(memory=memory, memory_offset=offset, immediate=immediate)
                    case "cmp": op = MI_CmpOp(memory=memory, memory_offset=offset, immediate=immediate, result=RFLAGS)
                    case _: raise X86ConversionError(f"Invalid opcode {opcode}")
                if opcode == "cmp":
                    self.current_register_values["rflags"] = op.results[0]
            
            case "R":
                dest = self.get_source_register(instruction.children[1])
                match opcode:
                    # NOTE: idk why pylance complains about the types here...
                    case "dec": op = R_DecOp(register_in=dest) # pyright: ignore[reportArgumentType]
                    case "inc": op = R_IncOp(register_in=dest) # pyright: ignore[reportArgumentType]
                    case "neg": op = R_NegOp(register_in=dest) # pyright: ignore[reportArgumentType]
                    case "not": op = R_NotOp(register_in=dest) # pyright: ignore[reportArgumentType]
                    case _: raise X86ConversionError(f"Invalid opcode {opcode}")
                self.set_destination_register(instruction.children[1], op.results[0])
                
            case "D":
                rsp_in = self.current_register_values["rsp"]
                dest = self.get_dest_register_type(instruction.children[1])
                op = D_PopOp(rsp_in=rsp_in, destination=dest)
                self.current_register_values["rsp"] = op.results[0]
                self.set_destination_register(instruction.children[1], op.results[1])
                
            case "S":
                rsp_in = self.current_register_values["rsp"]
                source = self.get_source_register(instruction.children[1])
                op = S_PushOp(rsp_in=rsp_in, source=source)
                self.current_register_values["rsp"] = op.results[0]
                
            case "M":
                memory, offset = self.get_memory_operand(instruction.children[1])
                rsp_in = self.current_register_values["rsp"]
                match opcode:
                    case "dec": op = M_DecOp(memory=memory, memory_offset=offset)
                    case "inc": op = M_IncOp(memory=memory, memory_offset=offset)
                    case "neg": op = M_NegOp(memory=memory, memory_offset=offset)
                    case "not": op = M_NotOp(memory=memory, memory_offset=offset)
                    case "push": op = M_PushOp(
                        rsp_in=rsp_in, memory=memory, memory_offset=offset,
                        rsp_out=GeneralRegisterType.from_name("rsp")
                    )
                    case "pop": op = M_PopOp(
                        rsp_in=rsp_in, memory=memory, memory_offset=offset,
                        rsp_out=GeneralRegisterType.from_name("rsp")
                    )
                    case _: raise X86ConversionError(f"Invalid opcode {opcode}")
                if opcode in ("pop", "push"):
                    self.current_register_values["rsp"] = op.results[0]
            
            case "C":
                match opcode:
                    case "ret": op = RetOp()
                    case _: raise X86ConversionError(f"Invalid opcode {opcode}")

            case _: raise X86ConversionError(f"Invalid opcode {opcode}")

        return op
                    

    def convert_blocks(self, instructions: list[list[Union[Token, ParseTree]]]) -> None:
        self.blocks.clear()
        self.block_register_inputs.clear()
        for _ in instructions:
            self.new_basic_block()

        for index, block in enumerate(instructions):
            self.current_register_values.clear()
            for register in X86_INDEX_BY_NAME.keys():
                self.current_register_values[register] = self.block_register_inputs[index][register]
            
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

                if is_jump_instruction(instruction):
                    ended_with_jump = True
                    self.blocks[index].add_op(self.parse_jump(instruction, index))
                else:
                    self.blocks[index].add_op(self.parse_instruction(instruction))
            
            if not ended_with_jump:
                if index != len(instructions) - 1:
                    self.blocks[index].add_op(FallthroughOp(
                        list(self.current_register_values.values()),
                        self.blocks[index + 1]
                    ))
        
    
    def convert(self, tree: ParseTree) -> Region:
        blocks = self.get_basic_blocks(tree)
        self.convert_blocks(blocks)

        region = Region(self.blocks)
        return region
    




if __name__ == "__main__":
    jambloat = ParseTree(
        "program", [
            ParseTree(
                "label", [
                    Token("LABELNAME", "jambloat"), Token(":", ":")
                ]
            ),
            ParseTree(
                "instruction", [
                    Token("opcode", "add"), Token("REG", "rax"), Token("REG", "rbx")
                ]
            ),
            ParseTree(
                "instruction", [
                    Token("opcode", "mov"), Token("REG", "rcx"), Token("REG", "rax")
                ]
            ),
            ParseTree(
                "instruction", [
                    Token("opcode", "cmp"), Token("REG", "rbx"), Token("REG", "rcx")
                ]
            ),
            ParseTree(
                "instruction", [
                    Token("opcode", "lea"), Token("REG", "rbx"), ParseTree("mem", [
                        Token("REG", "rax")
                    ])
                ]
            ),
            ParseTree(
                "instruction", [
                    Token("opcode", "mov"), Token("REG", "rsp"), ParseTree("mem", [
                        Token("REG", "rbx"), Token("+", "+"), Token("IMM", "3")
                    ])
                ]
            ),
            ParseTree(
                "label", [
                    Token("LABELNAME", "jambloat2"), Token(":", ":")
                ]
            ),
            ParseTree(
                "instruction", [
                    Token("opcode", "add"), Token("REG", "r8"), ParseTree("mem", [
                        Token("REG", "rsp"), Token("-", "-"), Token("IMM", "10")
                    ])
                ]
            ),
            ParseTree(
                "instruction", [
                    Token("opcode", "cmp"), ParseTree("mem", [
                        Token("REG", "rsp"), Token("-", "-"), Token("IMM", "10")
                    ]), Token("IMM", "100")
                ]
            ),
            ParseTree(
                "instruction", [
                    Token("opcode", "inc"), Token("REG", "rsp")
                ]
            ),
            ParseTree(
                "instruction", [
                    Token("opcode", "push"), Token("REG", "rbp")
                ]
            ),
            ParseTree(
                "instruction", [
                    Token("opcode", "pop"), Token("REG", "r15")
                ]
            ),
            ParseTree(
                "instruction", [
                    Token("opcode", "push"), Token("REG", "rsp")
                ]
            ),
            
            ParseTree(
                "instruction", [
                    Token("opcode", "neg"), ParseTree("mem", [
                        Token("REG", "rax")
                    ])
                ]
            ),
            ParseTree(
                "instruction", [
                    Token("opcode", "push"), ParseTree("mem", [
                        Token("REG", "r15"), Token("-", "-"), Token("IMM", "10")
                    ])
                ]
            ),
            ParseTree(
                "instruction", [
                    Token("opcode", "jne"), Token("LABELNAME", "jambloat3")
                ]
            ),
            ParseTree(
                "instruction", [
                    Token("opcode", "pop"), ParseTree("mem", [
                        Token("REG", "rbp"), Token("+", "+"), Token("IMM", "10")
                    ])
                ]
            ),
            ParseTree(
                "instruction", [
                    Token("opcode", "jmp"), Token("LABELNAME", "jambloat2")
                ]
            ),
            ParseTree(
                "label", [
                    Token("LABELNAME", "jambloat3"), Token(":", ":")
                ]
            ),
            ParseTree(
                "instruction", [
                    Token("opcode", "ret")
                ]
            ),
        ]
    )

    converter = X86Converter()
    res = converter.convert(jambloat)


    # TODO: what are we doing about this?
    # are we ignoring it or explicitly requiring a return/jump instruction at the end?
    try:
        res.verify()
    except Exception as e:
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