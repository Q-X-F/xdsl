import argparse
import locale
import sys

from xdsl.viewer.core import Renderer, process_asm, process_mlir


def supports_utf() -> bool:
    """
    Checks if current environemnt supports UTF
    """
    encoding = sys.stdout.encoding or locale.getpreferredencoding(False)
    return isinstance(encoding, str) and encoding.lower().startswith("utf")


def is_safe() -> bool:
    """
    Detects if safe to display Unicode and colors.
    """
    return sys.stdout.isatty() and supports_utf()


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
    parser.add_argument(
        "-m", "--mlir", help="use mlir representation", action="store_true"
    )
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

    if args.mlir:
        program = process_mlir(text)

    else:
        program = process_asm(text, color)

    Renderer(program, unicode, color).print()


if __name__ == "__main__":
    main()
