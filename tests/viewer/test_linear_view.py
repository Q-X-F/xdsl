from xdsl.viewer.core import Jmp, LinearView, Lines


def is_disjoint(seq: list[Jmp]) -> bool:
    if len(seq) == 0:
        return True

    prev = seq[0]

    for s in seq[1:]:
        if prev.end > s.start:
            return False
        prev = s

    return True


def test_disjoint():
    l = Lines()

    for i in range(9):
        l.add_line(str(i))

    l.add_jump(0, 8)
    l.add_jump(1, 2)
    l.add_jump(1, 3)
    l.add_jump(2, 4)

    view = LinearView(l)

    assert all(is_disjoint(col) for col in view.columns)


def test_can_share_column():
    l = Lines()

    for i in range(9):
        l.add_line(str(i))

    l.add_jump(1, 2)
    l.add_jump(2, 4)

    view = LinearView(l)

    assert len(view.columns) == 1


def test_jumps_added():
    l = Lines()

    for i in range(9):
        l.add_line(str(i))

    l.add_jump(0, 8)
    l.add_jump(2, 1)

    view = LinearView(l)
    jumps = sum(view.columns, list[Jmp]())

    assert Jmp(0, 8, False) in jumps
    assert Jmp(1, 2, True) in jumps
    assert len(jumps) == 2
