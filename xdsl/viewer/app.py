import argparse
from enum import Enum, auto


class Graph:
    """
    Directed graph, using adjacency list. Nodes have ordering.
    """

    def __init__(self) -> None:
        self.adj: list[set[int]] = []
        self.adj_t: list[set[int]] = []
        self.nodes: list[str] = []

    def add_node(self, data: str) -> int:
        new_id = self.num_of_nodes()

        self.adj.append(set())
        self.adj_t.append(set())
        self.nodes.append(data)

        return new_id

    def add_edge(self, start_id: int, end_id: int) -> None:
        self.adj[start_id].add(end_id)
        self.adj_t[end_id].add(start_id)

    def num_of_nodes(self) -> int:
        return len(self.adj)


class ArrowEnum(Enum):
    Normal = auto()
    Outgoing = auto()
    Incoming = auto()


def format_slots(
    slots: list[int | None], arrow: ArrowEnum, indexes: list[int] = []
) -> str:
    out: list[str] = []

    discovered = False

    for i, slot in enumerate(slots):
        if i in indexes:
            discovered = True
            out.append("+")

        elif discovered:
            out.append("-")

        elif slot is None:
            out.append(" ")

        else:
            out.append("|")

    if not discovered:
        out.append(" ")

    elif arrow == ArrowEnum.Outgoing:
        out.append("<")

    elif arrow == ArrowEnum.Incoming:
        out.append(">")

    else:
        out.append(" ")

    return "".join(out)


class LineView:
    def __init__(self, graph: Graph) -> None:
        """
        NOTE: Strings in graph should not have any newlines or other control characters
        """
        self.graph = graph

    def print(self, margin: int = 8) -> None:
        slots: list[int | None] = [None] * margin

        for id in range(self.graph.num_of_nodes()):
            line = self.graph.nodes[id]

            # jmp TO this instruction
            ptr = 0
            to_remove: list[int] = []
            incoming = list(self.graph.adj_t[id])
            indexes: list[int] = []

            for i in incoming:
                if i < id:
                    s = slots.index(id, ptr)
                    indexes.append(s)
                    to_remove.append(s)
                    ptr += 1
                else:
                    s = slots.index(None)
                    slots[s] = i
                    indexes.append(s)

            if len(incoming) > 0:
                print(format_slots(slots, ArrowEnum.Incoming, indexes), f"LABEL_{id}:")

            for i in to_remove:
                slots[i] = None

            # jmp FROM this instruction
            ptr = 0
            to_remove: list[int] = []
            outgoing = list(self.graph.adj[id])
            indexes: list[int] = []

            for i in outgoing:
                if i < id:
                    s = slots.index(id, ptr)
                    indexes.append(s)
                    to_remove.append(s)
                    ptr += 1
                else:
                    s = slots.index(None)
                    slots[s] = i
                    indexes.append(s)

            if len(outgoing) > 0:
                print(format_slots(slots, ArrowEnum.Outgoing, indexes), " ", line)
            else:
                print(format_slots(slots, ArrowEnum.Normal), " ", line)

            for i in to_remove:
                slots[i] = None

        return


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
xor rcx, rcx
xor rcx, rcx
xor rcx, rcx
xor rcx, rcx
""".splitlines()

    g = Graph()

    for i in instructions:
        g.add_node(i)

    # TODO: add edges from CFG
    g.add_edge(1, 4)
    g.add_edge(4, 3)
    g.add_edge(0, 8)

    LineView(g).print()


if __name__ == "__main__":
    main()
