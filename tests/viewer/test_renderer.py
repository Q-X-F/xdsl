from xdsl.viewer.core import Jump, ProgramGraph, Renderer


def is_disjoint(seq: list[Jump]) -> bool:
    if len(seq) == 0:
        return True

    prev = seq[0]

    for s in seq[1:]:
        if prev.end > s.start:
            return False
        prev = s

    return True


def test_disjoint():
    p = ProgramGraph()

    for i in range(9):
        p.add_line(str(i))

    p.add_jump(0, 8)
    p.add_jump(1, 2)
    p.add_jump(1, 3)
    p.add_jump(2, 4)

    renderer = Renderer(p)

    assert all(is_disjoint(col) for col in renderer.columns)


def test_can_share_column():
    p = ProgramGraph()

    for i in range(9):
        p.add_line(str(i))

    # Both incoming so acceptable
    p.add_jump(1, 2)
    p.add_jump(4, 2)

    view = Renderer(p)

    assert len(view.columns) == 1


def test_jumps_added():
    p = ProgramGraph()

    for i in range(9):
        p.add_line(str(i))

    p.add_jump(0, 8)
    p.add_jump(2, 1)

    renderer = Renderer(p)
    jumps = sum(renderer.columns, list[Jump]())

    assert Jump(0, 8, False) in jumps
    assert Jump(1, 2, True) in jumps
    assert len(jumps) == 2
