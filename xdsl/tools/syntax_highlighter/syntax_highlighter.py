import json
import os

ansi_colors = {
    "black": "\033[30m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    # Bright variants
    "bright_black": "\033[90m",
    "bright_red": "\033[91m",
    "bright_green": "\033[92m",
    "bright_yellow": "\033[93m",
    "bright_blue": "\033[94m",
    "bright_magenta": "\033[95m",
    "bright_cyan": "\033[96m",
    "bright_white": "\033[97m",
    # Backgrounds
    "black_bg": "\033[40m",
    "red_bg": "\033[41m",
    "green_bg": "\033[42m",
    "yellow_bg": "\033[43m",
    "blue_bg": "\033[44m",
    "magenta_bg": "\033[45m",
    "cyan_bg": "\033[46m",
    "white_bg": "\033[47m",
    # Bright variants
    "bright_black_bg": "\033[100m",
    "bright_red_bg": "\033[101m",
    "bright_green_bg": "\033[102m",
    "bright_yellow_bg": "\033[103m",
    "bright_blue_bg": "\033[104m",
    "bright_magenta_bg": "\033[105m",
    "bright_cyan_bg": "\033[106m",
    "bright_white_bg": "\033[107m",
    # Reset
    "reset": "\033[0m",
}

INSTRUCTIONS = [
    "add",
    "sub",
    "mul",
    "div",
    "inc",
    "dec",
    "and",
    "or",
    "xor",
    "not",
    "neg",
    "push",
    "pop",
    "mov",
    "cmp",
    "lea",
    "jmp",
    "ja",
    "jae",
    "jb",
    "jbe",
    "jc",
    "je",
    "jg",
    "jge",
    "jl",
    "jle",
    "jna",
    "jnae",
    "jnb",
    "jnbe",
    "jnc",
    "jne",
    "jng",
    "jnge",
    "jnl",
    "jnle",
    "jno",
    "jnp",
    "jns",
    "jnz",
    "jo",
    "jp",
    "jpe",
    "jpo",
    "js",
    "jz",
    "call",
    "ret",
    "syscall",
]

REGISTERS = [
    "eax",
    "ebx",
    "ecx",
    "edx",
    "esi",
    "edi",
    "ebp",
    "esp",
    "eip",
    "eflags",
    "cs",
    "ds",
    "ss",
    "es",
    "fs",
    "gs",
    "rax",
    "rbx",
    "rcx",
    "rdx",
    "rsi",
    "rdi",
    "rbp",
    "rsp",
    "rip",
    "rflags",
    "r8",
    "r9",
    "r10",
    "r11",
    "r12",
    "r13",
    "r14",
    "r15",
]


def highlight_x86(code: str) -> str:
    # Initialize config
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            "config.json not found in the same directory as the script."
        )
    with open(config_path) as f:
        config = json.load(f)

    def color(text: str, syntax_type: str) -> str:
        color_name = config.get(syntax_type, "white")
        return ansi_colors[color_name] + text + ansi_colors["reset"]

    highlighted_lines: list[str] = []

    for line in code.splitlines():
        # Handle comments
        comment_part = ""
        if ";" in line:
            line, comment = line.split(";", 1)
            comment_part = color(";" + comment, "comment")
        if "#" in line:
            line, comment = line.split("#", 1)
            comment_part = color("#" + comment, "comment")

        stripped = line.lstrip()
        indent = line[: len(line) - len(stripped)]

        # Handle labels
        if stripped.endswith(":") or stripped.startswith("."):
            highlighted_lines.append(indent + color(stripped, "label") + comment_part)
            continue

        tokens = stripped.split(" ")
        new_tokens: list[str] = []

        for token in tokens:
            clean = token.strip(",")
            lower = clean.lower()

            if lower in INSTRUCTIONS:
                token = token.replace(clean, color(clean, "instruction"))

            elif lower in REGISTERS:
                token = token.replace(clean, color(clean, "register"))

            elif clean.isdigit() or (
                clean.startswith("0x")
                and all(c in "0123456789abcdefABCDEF" for c in clean[2:])
            ):
                token = token.replace(clean, color(clean, "number"))

            new_tokens.append(token)

        highlighted_lines.append(indent + " ".join(new_tokens) + comment_part)

    return "\n".join(highlighted_lines)
