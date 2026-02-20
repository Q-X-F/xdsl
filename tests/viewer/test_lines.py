from xdsl.viewer.core import Lines


def test_add_line():
    l = Lines()

    line_no = l.add_line("add rax, rax")
    assert line_no == 0
    assert l.lines[0] == "add rax, rax"

    line_no = l.add_line("add rbx, rbx")
    assert line_no == 1
    assert l.lines[1] == "add rbx, rbx"

    assert l.lines


def test_add_jump():
    l = Lines()

    l.add_line("add rax, rax")
    l.add_line("add rbx, rbx")
    l.add_jump(0, 1)

    assert 0 in l.prev[1]
    assert 1 in l.next[0]
