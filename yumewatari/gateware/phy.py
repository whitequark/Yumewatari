from migen import *
from migen.genlib.fsm import *

from .parser import *


__all__ = ["PCIeRXPHY", "PCIeTXPHY"]


def K(x, y): return (1 << 8) | (y << 5) | x
def D(x, y): return (0 << 8) | (y << 5) | x


_ts_layout = [
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


class PCIeRXPHY(Module):
    def __init__(self, lane):
        self.ts    = Record(_ts_layout)
        self.error = Signal()

        ###

        self.comb += lane.rx_align.eq(1)

        self._tsY  = Record(_ts_layout) # previous TS received
        self._tsZ  = Record(_ts_layout) # TS being received
        self.sync += If(self.error, self._tsZ.valid.eq(0))

        ts_id  = Signal(9)
        ts_inv = Signal()

        self.submodules.parser = Parser(symbol_size=9, word_size=lane.ratio, reset_rule="COMMA")
        self.comb += [
            self.parser.reset.eq(~lane.rx_valid),
            self.parser.i.eq(lane.rx_symbol),
            self.error.eq(self.parser.error)
        ]
        self.parser.rule(
            name="COMMA",
            cond=lambda symbol: symbol == K(28,5),
            succ="TSn-LINK/SKP-0",
            action=lambda symbol: [
                NextValue(self._tsZ.valid, 1),
                NextValue(self._tsY.raw_bits(), self._tsZ.raw_bits()),
            ]
        )
        self.parser.rule(
            name="TSn-LINK/SKP-0",
            cond=lambda symbol: symbol == K(28,0),
            succ="SKP-1"
        )
        self.parser.rule(
            name="TSn-LINK/SKP-0",
            cond=lambda symbol: symbol == K(23,7),
            succ="TSn-LANE",
            action=lambda symbol: [
                NextValue(self._tsZ.link.valid,  0)
            ]
        )
        self.parser.rule(
            name="TSn-LINK/SKP-0",
            cond=lambda symbol: ~symbol[8],
            succ="TSn-LANE",
            action=lambda symbol: [
                NextValue(self._tsZ.link.number, symbol),
                NextValue(self._tsZ.link.valid,  1)
            ]
        )
        for n in range(1, 3):
            self.parser.rule(
                name="SKP-%d" % n,
                cond=lambda symbol: symbol == K(28,0),
                succ="COMMA" if n == 2 else "SKP-%d" % (n + 1),
            )
        self.parser.rule(
            name="TSn-LANE",
            cond=lambda symbol: symbol == K(23,7),
            succ="TSn-FTS",
            action=lambda symbol: [
                NextValue(self._tsZ.lane.valid,  0)
            ]
        )
        self.parser.rule(
            name="TSn-LANE",
            cond=lambda symbol: ~symbol[8],
            succ="TSn-FTS",
            action=lambda symbol: [
                NextValue(self._tsZ.lane.number, symbol),
                NextValue(self._tsZ.lane.valid,  1)
            ]
        )
        self.parser.rule(
            name="TSn-FTS",
            cond=lambda symbol: ~symbol[8],
            succ="TSn-RATE",
            action=lambda symbol: [
                NextValue(self._tsZ.n_fts, symbol)
            ]
        )
        self.parser.rule(
            name="TSn-RATE",
            cond=lambda symbol: ~symbol[8],
            succ="TSn-CTRL",
            action=lambda symbol: [
                NextValue(self._tsZ.rate.raw_bits(), symbol)
            ]
        )
        self.parser.rule(
            name="TSn-CTRL",
            cond=lambda symbol: ~symbol[8],
            succ="TSn-ID0",
            action=lambda symbol: [
                NextValue(self._tsZ.ctrl.raw_bits(), symbol)
            ]
        )
        self.parser.rule(
            name="TSn-ID0",
            cond=lambda symbol: symbol == D(10,2),
            succ="TSn-ID1",
            action=lambda symbol: [
                NextMemory(ts_id, symbol),
                NextValue(ts_inv, 0),
                NextValue(self._tsZ.ts_id, 0),
            ]
        )
        self.parser.rule(
            name="TSn-ID0",
            cond=lambda symbol: symbol == D(5,2),
            succ="TSn-ID1",
            action=lambda symbol: [
                NextMemory(ts_id, symbol),
                NextValue(ts_inv, 0),
                NextValue(self._tsZ.ts_id, 1),
            ]
        )
        self.parser.rule(
            name="TSn-ID0",
            cond=lambda symbol: symbol == D(21,5),
            succ="TSn-ID1",
            action=lambda symbol: [
                NextMemory(ts_id, symbol),
                NextValue(ts_inv, 1),
            ]
        )
        self.parser.rule(
            name="TSn-ID0",
            cond=lambda symbol: symbol == D(26,5),
            succ="TSn-ID1",
            action=lambda symbol: [
                NextMemory(ts_id, symbol),
                NextValue(ts_inv, 1),
            ]
        )
        for n in range(1, 9):
            self.parser.rule(
                name="TSn-ID%d" % n,
                cond=lambda symbol: symbol == Memory(ts_id),
                succ="TSn-ID%d" % (n + 1)
            )
        self.parser.rule(
            name="TSn-ID9",
            cond=lambda symbol: symbol == Memory(ts_id),
            succ="COMMA",
            action=lambda symbol: [
                NextValue(self.ts.valid, 0),
                If(ts_inv,
                    NextValue(lane.rx_invert, ~lane.rx_invert)
                ).Elif(self._tsZ.raw_bits() == self._tsY.raw_bits(),
                    NextValue(self.ts.raw_bits(), self._tsY.raw_bits())
                ),
                NextState("COMMA")
            ]
        )


class PCIeTXPHY(Module):
    def __init__(self, lane):
        self.ts = Record(_ts_layout)

        ###

        self.submodules.fsm = ResetInserter()(FSM(reset_state="IDLE"))
        self.fsm.act("IDLE",
            lane.tx_set_disp.eq(1),
            lane.tx_symbol.eq(K(28,5)),
            NextState("TSn-LINK")
        )
        self.fsm.act("TSn-LINK",
            If(self.ts.link.valid,
                lane.tx_symbol.eq(self.ts.link.number)
            ).Else(
                lane.tx_symbol.eq(K(23,7))
            ),
            NextState("TSn-LANE")
        )
        self.fsm.act("TSn-LANE",
            If(self.ts.lane.valid,
                lane.tx_symbol.eq(self.ts.lane.number)
            ).Else(
                lane.tx_symbol.eq(K(23,7))
            ),
            NextState("TSn-FTS")
        )
        self.fsm.act("TSn-FTS",
            lane.tx_symbol.eq(self.ts.n_fts),
            NextState("TSn-RATE")
        )
        self.fsm.act("TSn-RATE",
            lane.tx_symbol.eq(self.ts.rate.raw_bits()),
            NextState("TSn-CTRL")
        )
        self.fsm.act("TSn-CTRL",
            lane.tx_symbol.eq(self.ts.ctrl.raw_bits()),
            NextState("TSn-ID0")
        )
        for n in range(0, 10):
            self.fsm.act("TSn-ID%d" % n,
                If(self.ts.ts_id == 0,
                    lane.tx_symbol.eq(D(10,2))
                ).Else(
                    lane.tx_symbol.eq(D(5,2))
                ),
                NextState("IDLE" if n == 9 else "TSn-ID%d" % (n + 1))
            )
