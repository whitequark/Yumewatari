__all__ = ["ts_layout"]


ts_layout = [
    ("valid",       1),
    ("link", [
        ("valid",       1),
        ("number",      8),
    ]),
    ("lane", [
        ("valid",       1),
        ("number",      5),
    ]),
    ("n_fts",       8),
    ("rate",  [
        ("reserved",    1),
        ("gen1",        1),
    ]),
    ("ctrl",  [
        ("reset",       1),
        ("disable",     1),
        ("loopback",    1),
        ("unscramble",  1)
    ]),
    ("ts_id",       1), # 0: TS1, 1: TS2
]
