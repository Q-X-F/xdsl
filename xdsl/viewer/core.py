from bisect import bisect_right
from dataclasses import dataclass

from xdsl.utils.colors import RESET, Colors


class Lines:
    """
    Lines with jumps.

    Lines are strings that do not have any newlines or control characters.
    """

    def __init__(self) -> None:
        self.next: list[set[int]] = []
        self.prev: list[set[int]] = []
        self.lines: list[str] = []

    def add_line(self, line: str) -> int:
        """
        Insert line and return line number
        """
        new_id = len(self)

        self.next.append(set())
        self.prev.append(set())
        self.lines.append(line)

        return new_id

    def add_jump(self, start_id: int, end_id: int) -> None:
        self.next[start_id].add(end_id)
        self.prev[end_id].add(start_id)

    def __len__(self) -> int:
        return len(self.next)


@dataclass
class Jmp:
    start: int
    end: int
    reversed: bool


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


def blue(x: str) -> str:
    return Colors.BLUE + x + RESET


class LinearView:
    def __init__(
        self, lines: Lines, unicode: bool = False, color: bool = False
    ) -> None:
        self.columns: list[list[Jmp]] = []
        self.lines = lines
        self.border = UNICODE_BORDER if unicode else ASCII_BORDER
        self.color = color

        for line_no in range(len(lines)):
            # Process forward jumps
            for end in lines.next[line_no]:
                # Will be handled by adj_t case
                if end <= line_no:
                    continue

                jmp = Jmp(line_no, end, False)
                self._insert(jmp)

            # Process backward jumps
            for start in lines.prev[line_no]:
                if start < line_no:
                    continue

                jmp = Jmp(line_no, start, True)
                self._insert(jmp)

    def _insert(self, jmp: Jmp) -> None:
        for col in self.columns:
            if len(col) == 0 or col[-1].end <= jmp.start:
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
        horizontal = False

        for col in self.columns[:line_width]:
            # bisect_right gets line_no < x.start
            # subtract 1 to get x.start <= line_no (our lower bound)
            index = bisect_right(col, line_no, key=lambda x: x.start) - 1

            if index < 0 or len(col) <= index:
                out.append(" " if not horizontal else self.border["h"])
                continue

            value = col[index]

            if outgoing:
                if [value.start, value.end][value.reversed] == line_no:
                    out.append(
                        self.border["bl"] if value.reversed else self.border["tl"]
                    )
                    horizontal = True
                    continue

                if value.start <= line_no and line_no < value.end:
                    out.append(self.border["v"] if not horizontal else self.border["h"])
                    continue
            else:
                if [value.end, value.start][value.reversed] == line_no:
                    out.append(
                        self.border["tl"] if value.reversed else self.border["bl"]
                    )
                    horizontal = True
                    continue

                if value.start < line_no and line_no <= value.end:
                    out.append(self.border["v"] if not horizontal else self.border["h"])
                    continue

            out.append(" " if not horizontal else self.border["h"])

        if outgoing:
            out.append(self.border["h"] * 2 if horizontal else "  ")
        else:
            out.append(self.border["h"] + ">" if horizontal else "  ")

        return "".join(out)

    def display_incoming(self, line_no: int, line_width: int = 8) -> str:
        return self._display(line_no, False, line_width)

    def display_outgoing(self, line_no: int, line_width: int = 8) -> str:
        return self._display(line_no, True, line_width)

    def print(self) -> None:
        for line_no in range(len(self.lines)):
            row = self.display_incoming(line_no)

            # Don't display label if nothing jumps to it
            if row[-1] != " ":
                if self.color:
                    row = blue(row)

                print(f"{row} LINE_{line_no}:")

            row = self.display_outgoing(line_no)
            if self.color:
                row = blue(row)

            print(f"{row}   {self.lines.lines[line_no]}")
