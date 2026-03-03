from dataclasses import dataclass

from xdsl.dialects.x86.ops import ConditionalJumpOperation
from xdsl.ir import Block, Region
from xdsl.tools.cfg import SuccBlock, build_adj


@dataclass
class IfElseBlock:
    """Represents an if/else statement in control-flow."""

    entry_block: Block
    then_block: Block
    else_block: Block
    exit_block: Block


@dataclass
class WhileBlock:
    """Represents a conditional loop in control-flow."""

    entry_block: Block
    body_block: Block
    exit_block: Block


ControlBlock = IfElseBlock | WhileBlock


def get_descendants(
    block: Block,
    adj_list: dict[Block, SuccBlock],
    visited: set[Block] | None = None,
) -> set[Block]:
    """Finds the set of all blocks within a region that can be reached in execution from a given block.

    Args:
        block: The block to find descendants of.
        adj_list: An adjacency list of the region.
        visited: A set of already-visited blocks, used for cycle detection.

    Returns:
        A set of blocks that can be reached from the input block."""
    if visited is None:
        visited = set()

    # Detect cycles and returns early.
    if block in visited:
        return {block}
    visited.add(block)

    children: SuccBlock = adj_list[block]

    result: set[Block] = set()

    # Use DFS to find all visitable descendants.
    for child in children:
        result |= get_descendants(child, adj_list, visited.copy())

    return result | set(children)


def detect_control_blocks(region: Region) -> list[ControlBlock]:
    """Finds all the control flow structures within a region.

    Analyses the control-flow graph to detect blocks in this region that correspond to either an if statement (with suitable
    'else' block), or a while loop (with condition and body).

    Args:
        region: The xDSL region to detect control flow within.

    Returns:
        A list of blocks that represent either if/else control flow or while loops. Note that for loops are encoded as while
        loops."""

    result: list[ControlBlock] = []

    block_order: dict[Block, int] = {
        b: i for i, b in enumerate(region.blocks)
    }  # A dictionary mapping blocks to its order in the region

    # Build the CFG adjacency list
    adj_list: dict[Block, SuccBlock] = build_adj(region)

    # Maps blocks to a set of all reachable blocks
    descendants: dict[Block, set[Block]] = {
        block: get_descendants(block, adj_list) for block in region.blocks
    }

    # Maps blocks to a set of all immediate parents
    parents: dict[Block, set[Block]] = {block: set() for block in region.blocks}
    for block, children in adj_list.items():
        for child in children:
            parents[child].add(block)

    # Find suitable entry blocks
    for entry, children in adj_list.items():
        lastop = entry.last_op
        if not isinstance(lastop, ConditionalJumpOperation):
            continue

        # Get children
        bthen = lastop.then_block
        belse = lastop.else_block

        if bthen == belse:
            continue

        # Detect loop via cycles in adjacency graph
        if entry in descendants[bthen]:
            result.append(WhileBlock(entry, bthen, belse))
            continue
        elif entry in descendants[belse]:
            result.append(WhileBlock(entry, belse, bthen))
            continue

        common_descendents = descendants[bthen] & descendants[belse]
        if len(common_descendents) == 0:
            continue
        if len(parents[bthen]) != 1 or len(parents[belse]) != 1:
            continue

        exit_block = min(
            common_descendents, key=lambda b: block_order[b]
        )  # Get the first common descendant
        result.append(IfElseBlock(entry, bthen, belse, exit_block))

    return result
