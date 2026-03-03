import re

from lark import Lark, Token, Tree
from lark.tree import Branch


def string_to_case_insensitive_regex(s: str) -> str:
    parts: list[str] = []
    parts.append("")
    for char in s:
        upper = char.upper()
        lower = char.lower()
        if upper == lower:
            parts.append(re.escape(char))  # Non-letter: escape literally
        else:
            parts.append(f"[{upper}{lower}]")

    parts.append("")
    return "".join(parts)


# Turns a list of strings into a regex body that case-insensitively matches any string
def list_string_to_case_insensitive_regex(l: list[str]) -> str:
    l = sorted(l)[::-1]
    res = ""
    for s in l:
        res = res + string_to_case_insensitive_regex(s) + "|"
    return res[0:-1]


# All instruction mnemonics
ops = [
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

ops_re = list_string_to_case_insensitive_regex(ops)

# All register mnemonics
regs = [
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

regs_re = list_string_to_case_insensitive_regex(regs)

# grammar for the Lark parser
grammar = f"""
    program : line*
    line : label
         | instruction
    instruction : OPCODE [operand ("," operand)*]
    operand : LABELNAME
            | REG
            | IMM
            | mem
    label : LABELNAME ":"
    mem : "[" REG [/[+-]/ OFFSET] "]"
    COMMENT.3 : /;[^\\n]*/
    %ignore COMMENT
    OPCODE.2 : /{ops_re}/
    REG.2 : /{regs_re}/
    %import common.SIGNED_NUMBER -> IMM
    %import common.NUMBER -> OFFSET
    LABELNAME.1 : /[._a-zA-Z][._a-zA-Z0-9]*/
    %import common.WS
    %ignore WS
"""
# MEM.1 : "[" /[^\]]*/ "]"

# Lark parser
x86_parser = Lark(grammar, start="program")


def transform_operand(b: Branch[Token]) -> Branch[Token]:
    if not isinstance(b, Tree):
        raise ValueError

    return b.children[0]


def transform_instruction(t: Tree[Token]) -> Tree[Token]:
    opcode = t.children[0]

    # Can contain None so be careful
    operands = [transform_operand(b) for b in t.children[1:] if b is not None]
    return Tree("instruction", [opcode] + operands)


def transform_label(t: Tree[Token]) -> Tree[Token]:
    return t


def transform_lines(b: Branch[Token]) -> Branch[Token]:
    if not isinstance(b, Tree):
        raise ValueError

    b2 = b.children[0]

    if not isinstance(b2, Tree):
        raise ValueError

    if b2.data == "instruction":
        return transform_instruction(b2)
    elif b2.data == "label":
        return transform_label(b2)
    else:
        raise ValueError


def transform(t: Tree[Token]) -> Tree[Token]:
    lines = [transform_lines(b) for b in t.children]
    return Tree("program", lines)


def parse(text: str) -> Tree[Token]:
    tree = x86_parser.parse(text)
    return transform(tree)


if __name__ == "__main__":
    # tests
    test_comment = (
        "xor rax, rax       ; fib_a = 0\n"
        "mov rbx, 1         ; fib_b = 1\n"
        "mov rcx, 12        ; print first 12 numbers\n"
    )

    test_mem = """
        mov rax, [rdx]
        mov rbx, [rdx + 4]
        mov rcx, [rdx - 4]
        mov [rdx], rcx
        mov [rdx + 4], rax
        mov [rdx - 4], rbx
    """

    test_label = """
        .done:
        jge .done
    """

    test_no_newline = "mov rax, rbx add rbx, rax"

    test_fib = """
        _start:
            push rbx           ; save callee-saved register

            xor rax, rax       ; fib_a = 0
            mov rbx, 1         ; fib_b = 1
            mov rcx, 12        ; print first 12 numbers

        print_loop:
            ; print current fib (rax) using printf
            mov rdi, fmt
            mov rsi, rax
            xor rax, rax       ; varargs count
            call printf        ; (external, linked via ld -dynamic-linker /lib64/ld-linux-x86-64.so.2 ... or gcc fib.o)

            ; update fib: temp = a + b; a = b; b = temp
            mov rdx, rax       ; rdx = old a
            mov rax, rbx       ; a = old b
            add rax, rdx       ; a += old a

            dec rcx
            jnz print_loop

            pop rbx            ; restore

            ; exit(0)
            mov rax, 60
            xor rdi, rdi
            syscall
    """

    # pretty printed test
    print(x86_parser.parse(test_fib).pretty())
