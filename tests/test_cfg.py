from xdsl.dialects.x86 import C_JmpOp, FallthroughOp
from xdsl.dialects.x86.ops import C_JgeOp, SI_CmpOp
from xdsl.dialects.x86.registers import GeneralRegisterType
from xdsl.dialects.x86_func import CallOp, RetOp
from xdsl.ir import Block, Region
from xdsl.tools.cfg import build_adj, group_functions


def test_build_adj():
    # Setup blocks
    b_entry = Block()
    b_then = Block()
    b_else = Block()
    b_exit = Block()
    b_final = Block()

    # Populate blocks

    # b_entry -> b_then
    #        \-> b_else
    b_entry.add_op(
        C_JgeOp(
            SI_CmpOp(b_entry.insert_arg(GeneralRegisterType.from_name("rax"), 0), 0),
            [],
            [],
            b_then,
            b_else,
        )
    )

    # b_then -> b_exit
    b_then.add_op(FallthroughOp([], b_exit))

    # b_else -> b_exit
    b_else.add_op(C_JmpOp([], b_exit))

    # b_exit -> b_final
    b_exit.add_op(FallthroughOp([], b_final))

    # b_final, ret
    b_final.add_op(RetOp())

    region = Region([b_entry, b_then, b_else, b_exit, b_final])
    adj = build_adj(region)

    assert adj[b_entry] == (b_then, b_else)
    assert adj[b_then] == (b_exit,)
    assert adj[b_else] == (b_exit,)
    assert adj[b_exit] == (b_final,)
    assert adj[b_final] == ()


def test_group_functions():
    # Setup blocks
    b_main = Block()  # Entry 0
    b_orphan_1 = Block()  # Unreachable
    b_helper = Block()  # Entry 2 (called by main)
    b_helper_cont = Block()  # Reachable from helper
    b_orphan_2 = Block()  # Unreachable

    label_map = {"main": 0, "orphan_1": 1, "helper": 2, "orphan_2": 3, "helper_cont": 4}
    all_blocks = [b_main, b_orphan_1, b_helper, b_orphan_2, b_helper_cont]

    # Populate blocks

    # main (entry point)
    # Calls 'helper'
    b_main.add_op(CallOp("helper", [], []))
    b_main.add_op(RetOp())

    # orphan_1 (unreachable)
    # Nothing points here, and it doesn't point anywhere
    b_orphan_1.add_op(RetOp())

    # helper (entry point)
    # Points to Block 3
    b_helper.add_op(FallthroughOp([], b_helper_cont))

    # helper_cont (reachable by helper)
    b_helper_cont.add_op(RetOp())

    # orphan_2 (unreachable)
    b_orphan_2.add_op(RetOp())

    result = group_functions(all_blocks, label_map)

    assert result == [[b_main], b_orphan_1, [b_helper, b_helper_cont], b_orphan_2]
