import argparse

from xdsl.viewer.core import Lines, Margin


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Input file with assembly")
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

    g = Lines()

    for i in instructions:
        g.add_line(i)

    # TODO: add edges from CFG
    g.add_jump(1, 4)
    g.add_jump(4, 3)
    g.add_jump(6, 6)
    g.add_jump(0, 8)

    m = Margin(g)
    m.print()


if __name__ == "__main__":
    main()
