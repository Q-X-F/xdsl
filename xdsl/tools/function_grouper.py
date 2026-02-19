import lark

class Instr:
    def __init__(self, Opcode: str, Operands: List[str], Index: int) -> None:
        self.opcode = Opcode
        self.operands = Operands
        self.index = Index
    opcode: str
    operands: List[str]
    index: int

class Label:
    def __init__(self, Name: str, Index: int) -> None:
        self.name = Name
        self.index = Index
    name: str
    index: int

returntype: List[List[Instr]]

def group_functions(tree: lark.tree.Tree[Any]) -> int:
    curr_line: int = 1

    labels: List[Label] = []
    lines: List[Instr] = []

    for line in tree.children:
        assert line.data == "line"
        if line.children[0].data == "label":
        # TODO: Add label



