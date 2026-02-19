import argparse
from bisect import bisect_right
from dataclasses import dataclass


class Lines:
    """
    Lines with jumps.

    Lines are strings that do not have any newlines or control characters.
    """

    def __init__(self) -> None:
        self.adj: list[set[int]] = []
        self.adj_t: list[set[int]] = []
        self.nodes: list[str] = []

    def add_line(self, line: str) -> int:
        new_id = len(self)

        self.adj.append(set())
        self.adj_t.append(set())
        self.nodes.append(line)

        return new_id

    def add_jump(self, start_id: int, end_id: int) -> None:
        self.adj[start_id].add(end_id)
        self.adj_t[end_id].add(start_id)

    def __len__(self) -> int:
        return len(self.adj)


@dataclass
class Jmp:
    start: int
    end: int
    reversed: bool


class Margin:
    def __init__(self, lines: Lines) -> None:
        self.columns: list[list[Jmp]] = []
        self.lines = lines

        for line_no in range(len(lines)):
            for dest in lines.adj[line_no]:
                # Will be handled by adj_t case
                if dest < line_no:
                    continue

                jmp = Jmp(line_no, dest, False)
                self._insert(jmp)

            for dest in lines.adj_t[line_no]:
                if dest <= line_no:
                    continue

                jmp = Jmp(line_no, dest, True)
                self._insert(jmp)

    def _insert(self, jmp: Jmp) -> None:
        for col in self.columns:
            if len(col) == 0 or col[-1].end <= jmp.start:
                col.append(jmp)
                break
        else:
            self.columns.append([jmp])

    def display_outgoing(self, line_no: int, line_width: int = 8) -> str:
        line_width -= 2
        out: list[str] = [" "] * (line_width - len(self.columns))
        horizontal = False

        for col in self.columns[:line_width]:
            # bisect_right gets line_no < x.start
            # subtract 1 to get x.start <= line_no (our lower bound)
            index = bisect_right(col, line_no, key=lambda x: x.start) - 1

            if index < 0 or len(col) <= index:
                out.append(" " if not horizontal else "-")
                continue

            value = col[index]

            if [value.start, value.end][value.reversed] == line_no:
                out.append("+")
                horizontal = True
                continue

            if value.start <= line_no and line_no < value.end:
                out.append("|" if not horizontal else "-")
                continue

            out.append(" " if not horizontal else "-")

        out.append("-<" if horizontal else "  ")

        return "".join(out)

    def display_incoming(self, line_no: int, line_width: int = 8) -> str:
        line_width -= 2
        out: list[str] = [" "] * (line_width - len(self.columns))
        horizontal = False

        for col in self.columns[:line_width]:
            # bisect_right gets line_no < x.start
            # subtract 1 to get x.start <= line_no (our lower bound)
            index = bisect_right(col, line_no, key=lambda x: x.start) - 1

            if index < 0 or len(col) <= index:
                out.append(" " if not horizontal else "-")
                continue

            value = col[index]

            if [value.end, value.start][value.reversed] == line_no:
                out.append("+")
                horizontal = True
                continue

            if value.start < line_no and line_no <= value.end:
                out.append("|" if not horizontal else "-")
                continue

            out.append(" " if not horizontal else "-")

        out.append("->" if horizontal else "  ")
        return "".join(out)

    def print(self) -> None:
        for line_no in range(len(self.lines)):
            s = self.display_incoming(line_no)

            if s[-1] != " ":
                print(s, f"LINE_{line_no}:")

            print(self.display_outgoing(line_no), " ", self.lines.nodes[line_no])


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
