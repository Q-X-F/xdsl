from bisect import bisect_right
from dataclasses import dataclass
from io import StringIO

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
        self.colors: dict[int, Colors] = {}

    def add_line(self, line: str) -> int:
        """
        Insert line and return line number
        """
        new_id = len(self)

        self.next.append(set())
        self.prev.append(set())
        self.lines.append(line)

        return new_id

    def add_jump(self, start_id: int, end_id: int, color: Colors = Colors.BLUE) -> None:
        self.next[start_id].add(end_id)
        self.prev[end_id].add(start_id)
        self.colors[start_id] = color

    def __len__(self) -> int:
        return len(self.next)


@dataclass
class Jmp:
    start: int
    end: int
    reversed: bool
    color: Colors = Colors.BLUE


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


def insertable(col: list[Jmp], jmp: Jmp) -> bool:
    if len(col) == 0:
        return True

    last = col[-1]

    if last.end < jmp.start:
        return True

    if last.end == jmp.start and not last.reversed and jmp.reversed:
        return True

    return False


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

                jmp = Jmp(line_no, end, False, lines.colors[line_no])
                self._insert(jmp)

            # Process backward jumps
            for start in lines.prev[line_no]:
                if start < line_no:
                    continue

                jmp = Jmp(line_no, start, True, lines.colors[start])
                self._insert(jmp)

    def _insert(self, jmp: Jmp) -> None:
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
        active_jmp: Jmp | None = None

        def output(text: str, jmp: Jmp | None = None):
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

    def print(self, *, file: StringIO | None = None, line_width: int = 8) -> None:
        for line_no in range(len(self.lines)):
            row = self.display_incoming(line_no, line_width=line_width)

            if self.border["h"] not in row:
                row = self.display_outgoing(line_no, line_width=line_width)

            print(f"{row} {self.lines.lines[line_no]}", file=file)
