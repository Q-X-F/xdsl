import argparse
from io import StringIO

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, ScrollableContainer
from textual.widgets import Footer, Static

from xdsl.viewer.core import LinearView, process_asm, process_mlir


class AsmApp(App):
    CSS = """
    .t {
        overflow: auto;
        border: solid green;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self, asm: str, mlir: str):
        super().__init__()
        self.asm = Text.from_ansi(asm)
        self.mlir = Text.from_ansi(mlir)

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield ScrollableContainer(Static(self.asm), classes="t")
            yield ScrollableContainer(Static(self.mlir), classes="t")
        yield Footer()


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

    lines = process_asm(text, True)
    s = StringIO()
    LinearView(lines, True, True).print(file=s)

    lines = process_mlir(text, True)
    s2 = StringIO()
    LinearView(lines, True, True).print(file=s2)

    AsmApp(s.getvalue(), s2.getvalue()).run()


if __name__ == "__main__":
    main()
