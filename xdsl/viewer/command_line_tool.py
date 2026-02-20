import argparse
import locale
import sys

from xdsl.viewer.core import LinearView, Lines


def supports_utf8() -> bool:
    encoding = sys.stdout.encoding or locale.getpreferredencoding(False)
    return isinstance(encoding, str) and encoding.lower().startswith("utf")


def is_safe() -> bool:
    """
    Detects if safe to display unicode and colors.
    """
    return sys.stdout.isatty() and supports_utf8()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Input file with assembly")
    parser.add_argument(
        "-u",
        "--unicode",
        help="Display with unicode",
        choices=["auto", "always", "never"],
        default="auto",
    )
    parser.add_argument(
        "-c",
        "--color",
        help="Display with color",
        choices=["auto", "always", "never"],
        default="auto",
    )
    args = parser.parse_args()

    # TODO: pass file to other components
    _file = args.file

    # Use temporary output for now
    instructions = """\
jmp 0x8
jmp 0x4
add rax, 1
mul rbx, 2
jmp 0x3
xor rcx, rcx
jmp 0x6
xor rcx, rcx
xor rcx, rcx
xor rcx, rcx
""".splitlines()

    lines = Lines()

    for i in instructions:
        lines.add_line(i)

    # TODO: add edges from CFG
    lines.add_jump(1, 4)
    lines.add_jump(4, 3)
    lines.add_jump(6, 6)
    lines.add_jump(0, 8)

    unicode = args.unicode == "always" or args.unicode == "auto" and is_safe()
    color = args.color == "always" or args.color == "auto" and is_safe()
    view = LinearView(lines, unicode, color)
    view.print()


if __name__ == "__main__":
    main()
