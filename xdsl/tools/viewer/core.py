from bisect import bisect_right
from dataclasses import dataclass
from io import StringIO

from lark import ParseTree, Token, Tree

from xdsl.dialects.builtin import ModuleOp
from xdsl.dialects.x86.ops import (
    C_JmpOp,
    ConditionalJumpOperation,
    FallthroughOp,
    x86_code,
)
from xdsl.dialects.x86_func import FuncOp
from xdsl.ir import Block, Region
from xdsl.syntax_printer import SyntaxPrinter
from xdsl.tools.convert_x86_to_mlir import X86Converter
from xdsl.tools.lark_parser import parse
from xdsl.tools.syntax_highlighter.syntax_highlighter import highlight_x86
from xdsl.utils.colors import RESET, Colors


@dataclass
class Jump:
    start: int
    end: int
    reversed: bool
    color: Colors = Colors.BLUE


class ProgramGraph:
    """
    Consists of lines connected by jumps.

    Lines are strings that do not have any newlines or control characters.
    """

    def __init__(self) -> None:
        self.outgoing: list[set[int]] = []
        self.incoming: list[set[int]] = []
        self.lines: list[str] = []
        self.colors: dict[tuple[int, int], Colors] = {}

    def add_line(self, line: str) -> int:
        """
        Insert line and return line number
        """
        new_id = len(self)

        self.outgoing.append(set())
        self.incoming.append(set())
        self.lines.append(line)

        return new_id

    def add_jump(self, start_id: int, end_id: int, color: Colors = Colors.BLUE) -> None:
        """
        Add arrow with specified color
        """
        self.outgoing[start_id].add(end_id)
        self.incoming[end_id].add(start_id)
        self.colors[(start_id, end_id)] = color

    def __len__(self) -> int:
        return len(self.outgoing)


ASCII_BORDER = {
    "h": "-",
    "v": "|",
    "tr": "+",
    "tl": "+",
    "br": "+",
    "bl": "+",
    "hv": "-",
}

UNICODE_BORDER = {
    "h": "─",
    "v": "│",
    "tr": "╮",
    "tl": "╭",
    "br": "╯",
    "bl": "╰",
    "hv": "─",
}


def insertable(col: list[Jump], jmp: Jump) -> bool:
    """
    Check if a Jump can be inserted into a list of Jumps without overlap
    """
    if len(col) == 0:
        return True

    last = col[-1]

    if last.end < jmp.start:
        return True

    if last.end == jmp.start and not last.reversed and jmp.reversed:
        return True

    return False


class Renderer:
    def __init__(
        self, program: ProgramGraph, unicode: bool = False, color: bool = False
    ) -> None:
        self.columns: list[list[Jump]] = []
        self.program = program
        self.border = UNICODE_BORDER if unicode else ASCII_BORDER
        self.color = color

        for line_no in range(len(program)):
            # Process forward jumps
            for end in program.outgoing[line_no]:
                # Will be handled by adj_t case
                if end <= line_no:
                    continue

                jmp = Jump(line_no, end, False, program.colors[(line_no, end)])
                self._insert(jmp)

            # Process backward jumps
            for start in program.incoming[line_no]:
                if start < line_no:
                    continue

                jmp = Jump(line_no, start, True, program.colors[(start, line_no)])
                self._insert(jmp)

    def _insert(self, jmp: Jump) -> None:
        for col in self.columns:
            if insertable(col, jmp):
                col.append(jmp)
                break
        else:
            # Create new column if current ones are all full
            self.columns.append([jmp])

    def _display(
        self, line_no: int, outgoing: bool = False, line_width: int = 8
    ) -> str:
        line_width -= 2
        out: list[str] = [" "] * (line_width - len(self.columns))
        active_jmp: Jump | None = None

        def output(text: str, jmp: Jump | None = None):
            if self.color:
                j = active_jmp or jmp

                if j is not None:
                    out.append(j.color)

            out.append(text)

            if self.color:
                out.append(RESET)

        for col in self.columns[:line_width]:
            # bisect_right gets line_no < x.start
            # subtract 1 to get x.start <= line_no (our lower bound)
            index = bisect_right(col, line_no, key=lambda x: x.start) - 1

            if index < 0 or len(col) <= index:
                output(" " if not active_jmp else self.border["h"])
                continue

            jmp = col[index]

            if outgoing:
                if [jmp.start, jmp.end][jmp.reversed] == line_no:
                    active_jmp = jmp
                    output(
                        self.border["bl"] if jmp.reversed else self.border["tl"], jmp
                    )
                    continue

                if jmp.start <= line_no and line_no < jmp.end:
                    output(
                        self.border["v"] if not active_jmp else self.border["h"], jmp
                    )
                    continue
            else:
                if [jmp.end, jmp.start][jmp.reversed] == line_no:
                    active_jmp = jmp
                    output(
                        self.border["tl"] if jmp.reversed else self.border["bl"], jmp
                    )
                    continue

                if jmp.start < line_no and line_no <= jmp.end:
                    output(
                        self.border["v"] if not active_jmp else self.border["h"], jmp
                    )
                    continue

            output(" " if not active_jmp else self.border["h"])

        if outgoing:
            output(self.border["h"] * 2 if active_jmp else "  ")
        else:
            output(self.border["h"] + ">" if active_jmp else "  ")

        return "".join(out)

    def display_incoming(self, line_no: int, line_width: int = 8) -> str:
        return self._display(line_no, False, line_width)

    def display_outgoing(self, line_no: int, line_width: int = 8) -> str:
        return self._display(line_no, True, line_width)

    def print(self, *, file: StringIO | None = None, line_width: int = 16) -> None:
        for line_no in range(len(self.program)):
            row = self.display_incoming(line_no, line_width=line_width)

            if self.border["h"] not in row:
                row = self.display_outgoing(line_no, line_width=line_width)

            print(f"{row} {self.program.lines[line_no]}", file=file)


def convert_to_mlir(tree: ParseTree) -> Region:
    """
    Convert parse tree into Region
    """
    converter = X86Converter()
    res = converter.convert(tree)
    return res


def process_asm(text: str, color: bool) -> ProgramGraph:
    """
    Produce x86 ProgramGraph from x86 source code
    """
    program = ProgramGraph()
    tree = parse(text)

    if color:
        text = highlight_x86(text)

    for line in text.split("\n"):
        program.add_line(line)

    labels: dict[str, int] = {}
    jumps: list[tuple[int, str, Colors]] = []

    for t in tree.children:
        if not isinstance(t, Tree):
            raise ValueError

        t2 = t.children[0]

        if not isinstance(t2, Token):
            raise ValueError

        line_no = (t2.line or 0) - 1

        if t.data == "label":
            labels[str(t2)] = line_no

        jump_color = Colors.BLUE if t.children[0] == "jmp" else Colors.GREEN

        for operand in t.children[1:]:
            if isinstance(operand, Token) and operand.type == "LABELNAME":
                jumps.append((line_no, str(operand), jump_color))

    for line_no, label, jump_color in jumps:
        program.add_jump(line_no, labels[label], jump_color)

    return program


def process_asm_opt(text: str, color: bool):
    tree = parse(text)
    region = convert_to_mlir(tree)

    new_text = x86_code(ModuleOp(region))
    new_text = new_text[new_text.find("\n") :]

    return process_asm(new_text, color)


def get_blocks(region: Region) -> list[Block]:
    """
    Extract blocks from a Region, including ones inside FuncOp
    """
    blocks: list[Block] = []

    for block in region.blocks:
        op = block.last_op

        if isinstance(op, FuncOp):
            blocks.extend(get_blocks(op.body))
        else:
            blocks.append(block)

    return blocks


# Potentially move to utils/cfg module
def get_outgoing(block: Block) -> list[Block]:
    op = block.last_op

    if isinstance(op, (C_JmpOp, FallthroughOp)):
        return [op.successor]

    if isinstance(op, ConditionalJumpOperation):
        return [op.then_block, op.else_block]

    return []


class ViewerPrinter(SyntaxPrinter):
    blocks: dict[Block, tuple[int, int]] = {}

    def print_block(
        self,
        block: Block,
        print_block_args: bool = True,
        print_block_terminator: bool = True,
    ) -> None:
        start = 0
        end = 0

        self.print_string(" \n ")
        self.print_string(" \n ")

        if isinstance(self.stream, StringIO):
            start = len(self.stream.getvalue().splitlines())

        super().print_block(block, print_block_args, print_block_terminator)

        if isinstance(self.stream, StringIO):
            end = len(self.stream.getvalue().splitlines()) - 1

        self.blocks[block] = (start, end)


def process_mlir(text: str) -> ProgramGraph:
    """
    Produce MLIR x86 ProgramGraph from x86 source code
    """
    program = ProgramGraph()
    tree = parse(text)
    region = convert_to_mlir(tree)

    s = StringIO()
    p = ViewerPrinter(s)
    p.print_region(region)

    for line in s.getvalue().splitlines():
        program.add_line(line)

    for block, (start, end) in p.blocks.items():
        if isinstance(block.first_op, FuncOp):
            program.add_jump(start, end, Colors.YELLOW)

        next_blocks = get_outgoing(block)

        if len(next_blocks) == 1:
            dest = p.blocks[next_blocks[0]][0]

            if isinstance(block.last_op, FallthroughOp):
                program.add_jump(end, dest, Colors.BRIGHT_BLACK)
            else:
                program.add_jump(end, dest, Colors.BLUE)

        elif len(next_blocks) == 2:
            # If then block
            dest = p.blocks[next_blocks[0]][0]
            program.add_jump(end, dest, Colors.GREEN)

            # Else block
            dest = p.blocks[next_blocks[1]][0]
            program.add_jump(end, dest, Colors.RED)

    return program
