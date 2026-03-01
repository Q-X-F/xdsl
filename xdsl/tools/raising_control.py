from dataclasses import dataclass
from xdsl.dialects.x86.ops import ConditionalJumpOperation
from xdsl.ir.core import Block, Region
from cfg import build_adj

@dataclass
class ifElseBlock:
    entry_Block: Block
    then_block: Block
    else_block: Block
    exit_block: Block

def detect_if_blocks(region: Region) -> list[ifElseBlock]:
    result: list[ifElseBlock] = []

    parents: dict[Block, set[Block]] = {block: set() for block in region.blocks}
    adj_list = build_adj(region)

    # Populate parent dictionary
    for block, children in adj_list.items():
        for child in children:
            parents[child].add(block)

    # Find potential entry blocks
    for entry, children in adj_list.items():
        lastop = entry.last_op

        if not isinstance(lastop, ConditionalJumpOperation):
            continue

        then_block = lastop.then_block
        else_block = lastop.else_block
        
        if then_block == else_block:
            continue

        fchild = adj_list[then_block]
        schild = adj_list[else_block]

        if len(fchild) != 1 or len(schild) != 1: continue
        if fchild[0] is not schild[0]: continue
        if len(parents[then_block]) != 1 or len(parents[else_block]) != 1: continue
        if len(parents[fchild[0]]) != 1: continue
        
        result.append(ifElseBlock(entry, then_block, else_block, fchild[0]))

    return result
