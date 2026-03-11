import argparse
from io import StringIO

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, ScrollableContainer
from textual.visual import VisualType
from textual.widgets import Footer, Static

from xdsl.viewer.core import ProgramGraph, Renderer, process_asm, process_mlir


class Line(Static):
    def __init__(self, content: VisualType, action: str = "") -> None:
        super().__init__(content)
        self.action = action

    async def on_click(self) -> None:
        if self.action:
            await self.run_action(self.action)


def bind_scrolls(program: ProgramGraph, text: str, container_id: str) -> list[Line]:
    """
    Bind scroll actions to each jump in the program
    """
    lines = Text.from_ansi(text).split(allow_blank=True)
    new_lines: list[Line] = []

    for i, line in enumerate(lines):
        if len(program.outgoing[i]) == 0:
            new_lines.append(Line(line))
            continue

        dest = max(program.outgoing[i])
        m = min(program.outgoing[i])
        if m < i:
            dest = m

        action = f"app.scroll('{container_id}', {dest})"
        new_lines.append(Line(line, action))

    return new_lines


class AsmApp(App):
    CSS = """
    .t {
        overflow: auto auto;
        border: round ansi_bright_black;
    }

    Line {
        text-wrap: nowrap;
        text-overflow: clip;
    }

    Footer {
        background: transparent;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self, text: str):
        super().__init__()

        program = process_asm(text, True)
        s = StringIO()
        Renderer(program, True, True).print(file=s)
        asm = bind_scrolls(program, s.getvalue(), "#asm")

        program = process_mlir(text)
        s = StringIO()
        Renderer(program, True, True).print(file=s)
        mlir = bind_scrolls(program, s.getvalue(), "#mlir")

        self.asm = asm
        self.mlir = mlir

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield ScrollableContainer(*self.asm, classes="t", id="asm")
            yield ScrollableContainer(*self.mlir, classes="t", id="mlir")
        yield Footer()

    async def action_scroll(self, container_id: str, line_no: int):
        container = self.query_one(container_id, ScrollableContainer)
        container.scroll_to(None, line_no)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="input file with assembly")
    args = parser.parse_args()

    try:
        with open(args.file) as f:
            text = f.read()
    except FileNotFoundError:
        print(f"error: the file '{args.file}' was not found")
        exit(1)

    AsmApp(text).run()


if __name__ == "__main__":
    main()
