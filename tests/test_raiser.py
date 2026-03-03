from typing import TypeAlias, cast

import pytest

from xdsl.ir import Region
from xdsl.tools.raiser import control


class TestOp:
    pass


class TestBlock:
    def __init__(self, name: str, last_op: TestOp | None = None) -> None:
        self.name = name
        self.last_op = last_op

    def __repr__(self) -> str:
        return f"B({self.name})"

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, value: object, /) -> bool:
        return isinstance(value, TestBlock) and value.name == self.name


class TestRegion:
    def __init__(self, blocks: list[TestBlock]) -> None:
        self.blocks = blocks


class TestCondJump(TestOp):
    def __init__(self, thenb: TestBlock, elseb: TestBlock) -> None:
        self.then_block = thenb
        self.else_block = elseb


TestSucc: TypeAlias = tuple[()] | tuple[TestBlock] | tuple[TestBlock, TestBlock]


def test_if_else(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = TestBlock("entry")
    thenb = TestBlock("then")
    elseb = TestBlock("else")
    exitb = TestBlock("exit")

    entry.last_op = TestCondJump(thenb, elseb)

    region: TestRegion = TestRegion([entry, thenb, elseb, exitb])

    adj_list: dict[TestBlock, TestSucc] = {
        entry: (thenb, elseb),
        thenb: (exitb,),
        elseb: (exitb,),
        exitb: (),
    }

    def build_adj(
        _: Region,
    ) -> dict[TestBlock, TestSucc]:
        return adj_list

    monkeypatch.setattr("xdsl.tools.raiser.control.build_adj", build_adj)
    monkeypatch.setattr(
        "xdsl.tools.raiser.control.ConditionalJumpOperation", TestCondJump
    )

    result: list[control.ControlBlock] = control.detect_control_blocks(
        cast(Region, region)
    )

    assert len(result) == 1

    b = result[0]
    assert isinstance(b, control.IfElseBlock)
    assert b.entry_block == entry
    assert b.then_block == thenb
    assert b.else_block == elseb
    assert b.exit_block == exitb


def test_while(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = TestBlock("entry")
    bodyb = TestBlock("body")
    exitb = TestBlock("exit")

    entry.last_op = TestCondJump(bodyb, exitb)

    region = TestRegion([entry, bodyb, exitb])

    adj_list: dict[TestBlock, TestSucc] = {
        entry: (bodyb, exitb),
        bodyb: (entry,),
        exitb: (),
    }

    def build_adj(_: Region) -> dict[TestBlock, TestSucc]:
        return adj_list

    monkeypatch.setattr("xdsl.tools.raiser.control.build_adj", build_adj)
    monkeypatch.setattr(
        "xdsl.tools.raiser.control.ConditionalJumpOperation", TestCondJump
    )

    result: list[control.ControlBlock] = control.detect_control_blocks(
        cast(Region, region)
    )

    assert len(result) == 1

    b = result[0]
    assert isinstance(b, control.WhileBlock)
    assert b.entry_block == entry
    assert b.body_block == bodyb
    assert b.exit_block == exitb
