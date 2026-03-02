from dataclasses import dataclass

from cfg import build_adj

from xdsl.dialects.x86.ops import ConditionalJumpOperation
from xdsl.ir import Block, Region


@dataclass
class ifElseBlock:
    entry_block: Block
    then_block: Block
    else_block: Block
    exit_block: Block


@dataclass
class whileBlock:
    entry_block: Block
    body_block: Block
    exit_block: Block


def get_descendants(
    block: Block,
    adj_list: dict[Block, tuple[()] | tuple[Block] | tuple[Block, Block]],
    visited: set[Block] = set(),
) -> set[Block]:
    if block in visited:
        return {block}
    visited.add(block)

    children: tuple[()] | tuple[Block] | tuple[Block, Block] = adj_list[block]

    result: set[Block] = set()

    for child in children:
        result |= get_descendants(child, adj_list, visited.copy())

    return result | set(children)


def detect_control_blocks(region: Region) -> list[ifElseBlock | whileBlock]:
    result: list[ifElseBlock | whileBlock] = []

    # Get blocks in order to determine merge points
    block_order: dict[Block, int] = {b: i for i, b in enumerate(region.blocks)}

    # dictionary from a block to its parent blocks
    parents: dict[Block, set[Block]] = {block: set() for block in region.blocks}

    # get CFG representation and populate dict
    adj_list: dict[Block, tuple[()] | tuple[Block] | tuple[Block, Block]] = build_adj(
        region
    )
    descendants: dict[Block, set[Block]] = {
        block: get_descendants(block, adj_list) for block in region.blocks
    }

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

        # Detect loop using ancestors
        if entry in descendants[bthen]:
            result.append(whileBlock(entry, bthen, belse))
            continue
        elif entry in descendants[belse]:
            result.append(whileBlock(entry, belse, bthen))
            continue

        common_descendents = descendants[bthen] & descendants[belse]
        if len(common_descendents) == 0:
            continue
        if len(parents[bthen]) != 1 or len(parents[belse]) != 1:
            continue

        exit_block = min(common_descendents, key=lambda b: block_order[b])

        result.append(ifElseBlock(entry, bthen, belse, exit_block))
    return result
