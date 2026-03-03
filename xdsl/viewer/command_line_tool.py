import argparse
import locale
import re
import sys
from io import StringIO

from lark import ParseTree, Token, Tree

from xdsl.ir import Region
from xdsl.syntax_printer import SyntaxPrinter
from xdsl.tools.convert_x86_to_mlir import X86Converter
from xdsl.tools.lark_parser import parse
from xdsl.tools.syntax_highlighter.syntax_highlighter import highlight_x86
from xdsl.utils.colors import Colors
from xdsl.viewer.core import LinearView, Lines

# from xdsl.tools.cfg import group_functions


def supports_utf8() -> bool:
    encoding = sys.stdout.encoding or locale.getpreferredencoding(False)
    return isinstance(encoding, str) and encoding.lower().startswith("utf")


def is_safe() -> bool:
    """
    Detects if safe to display Unicode and colors.
    """
    return sys.stdout.isatty() and supports_utf8()


def convert_to_mlir(ast: ParseTree) -> Region:
    converter = X86Converter()
    res = converter.convert(ast)
    return res


def process_asm(text: str, color: bool) -> Lines:
    lines = Lines()
    tree = parse(text)

    if color:
        text = highlight_x86(text)

    for line in text.split("\n"):
        lines.add_line(line)

    labels: dict[str, int] = {}
    jumps: list[tuple[int, str]] = []

    for t in tree.children:
        if not isinstance(t, Tree):
            raise ValueError

        t2 = t.children[0]

        if not isinstance(t2, Token):
            raise ValueError

        line_no = (t2.line or 0) - 1

        if t.data == "label":
            labels[str(t2)] = line_no

        for operand in t.children[1:]:
            if isinstance(operand, Token) and operand.type == "LABELNAME":
                jumps.append((line_no, str(operand)))

    for line_no, label in jumps:
        lines.add_jump(line_no, labels[label])

    return lines


def process_mlir(text: str, color: bool) -> Lines:
    lines = Lines()
    tree = parse(text)
    region = convert_to_mlir(tree)

    s = StringIO()
    SyntaxPrinter(s).print_region(region)

    block_line_nos: list[int] = []
    block_names: list[str] = []

    indents: list[int] = []

    for line in s.getvalue().split("\n"):
        line = line.lstrip()
        if line.startswith("^bb") or line.startswith("x86_func"):
            block_names.append(line.split("(")[0].lstrip())

            if len(block_line_nos) > 0:
                block_line_nos.append(len(lines) - 1)
                lines.add_line("")
                lines.add_line("")
                lines.add_line("")
            block_line_nos.append(len(lines))

        lines.add_line("    " * len(indents[1:]) + line)

        if "}" in line:
            last = indents.pop()

            if last == 0:
                continue

            lines.add_jump(last, len(lines) - 1, Colors.RED)

        if "{" in line:
            indents.append(len(lines) - 1)

    if len(block_line_nos) > 0:
        block_line_nos.append(len(lines) - 1)

        lines.add_line("")
        lines.add_line("")
        lines.add_line("")

    for pos in block_line_nos[1::2]:
        line = lines.lines[pos]
        bbs = re.findall("(\\^bb\\d+)", line)

        if len(bbs) == 0:
            continue

        bb = bbs[0]
        color2 = Colors.BLUE if "fallthrough" not in line else Colors.WHITE
        lines.add_jump(pos, block_line_nos[2 * block_names.index(bb)], color2)

    return lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="input file with assembly")
    parser.add_argument(
        "-u",
        "--unicode",
        help="display with unicode",
        choices=["auto", "always", "never"],
        default="auto",
    )
    parser.add_argument("-x", "--x86", help="use raw x86", action="store_true")
    parser.add_argument(
        "-c",
        "--color",
        help="display with color",
        choices=["auto", "always", "never"],
        default="auto",
    )
    args = parser.parse_args()

    try:
        with open(args.file) as f:
            text = f.read()
    except FileNotFoundError:
        print(f"error: the file '{args.file}' was not found")
        exit(1)

    unicode = args.unicode == "always" or args.unicode == "auto" and is_safe()
    color = args.color == "always" or args.color == "auto" and is_safe()

    if args.x86:
        lines = process_asm(text, color)

    else:
        lines = process_mlir(text, color)

    view = LinearView(lines, unicode, color)
    view.print()


if __name__ == "__main__":
    main()
