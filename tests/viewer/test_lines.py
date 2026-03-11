from xdsl.tools.viewer.core import ProgramGraph


def test_add_line():
    p = ProgramGraph()

    line_no = p.add_line("add rax, rax")
    assert line_no == 0
    assert p.lines[0] == "add rax, rax"

    line_no = p.add_line("add rbx, rbx")
    assert line_no == 1
    assert p.lines[1] == "add rbx, rbx"

    assert p.lines


def test_add_jump():
    p = ProgramGraph()

    p.add_line("add rax, rax")
    p.add_line("add rbx, rbx")
    p.add_jump(0, 1)

    assert 0 in p.incoming[1]
    assert 1 in p.outgoing[0]
