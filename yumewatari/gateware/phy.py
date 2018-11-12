from migen import *
from migen.genlib.fsm import *

from .serdes import K, D
from .protocol import *


__all__ = ["PCIeRXPHY", "PCIeTXPHY"]


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

        self.submodules.parser = Parser(
            symbol_size=9,
            word_size=lane.ratio,
            reset_rule="COMMA",
            layout=[
                ("data", 8),
                ("ctrl", 1),
            ])
        self.comb += [
            self.parser.reset.eq(~lane.rx_valid),
            self.parser.i.eq(lane.rx_symbol),
            self.error.eq(self.parser.error)
        ]
        self.parser.rule(
            name="COMMA",
            cond=lambda symbol: symbol.raw_bits() == K(28,5),
            succ="TSn-LINK/SKP-0",
            action=lambda symbol: [
                NextValue(self._tsZ.valid, 1),
                NextValue(self._tsY.raw_bits(), self._tsZ.raw_bits()),
            ]
        )
        self.parser.rule(
            name="TSn-LINK/SKP-0",
            cond=lambda symbol: symbol.raw_bits() == K(28,0),
            succ="SKP-1"
        )
        self.parser.rule(
            name="TSn-LINK/SKP-0",
            cond=lambda symbol: symbol.raw_bits() == K(23,7),
            succ="TSn-LANE",
            action=lambda symbol: [
                NextValue(self._tsZ.link.valid,  0)
            ]
        )
        self.parser.rule(
            name="TSn-LINK/SKP-0",
            cond=lambda symbol: ~symbol.ctrl,
            succ="TSn-LANE",
            action=lambda symbol: [
                NextValue(self._tsZ.link.number, symbol.data),
                NextValue(self._tsZ.link.valid,  1)
            ]
        )
        for n in range(1, 3):
            self.parser.rule(
                name="SKP-%d" % n,
                cond=lambda symbol: symbol.raw_bits() == K(28,0),
                succ="COMMA" if n == 2 else "SKP-%d" % (n + 1),
            )
        self.parser.rule(
            name="TSn-LANE",
            cond=lambda symbol: symbol.raw_bits() == K(23,7),
            succ="TSn-FTS",
            action=lambda symbol: [
                NextValue(self._tsZ.lane.valid,  0)
            ]
        )
        self.parser.rule(
            name="TSn-LANE",
            cond=lambda symbol: ~symbol.ctrl,
            succ="TSn-FTS",
            action=lambda symbol: [
                NextValue(self._tsZ.lane.number, symbol.data),
                NextValue(self._tsZ.lane.valid,  1)
            ]
        )
        self.parser.rule(
            name="TSn-FTS",
            cond=lambda symbol: ~symbol.ctrl,
            succ="TSn-RATE",
            action=lambda symbol: [
                NextValue(self._tsZ.n_fts, symbol.data)
            ]
        )
        self.parser.rule(
            name="TSn-RATE",
            cond=lambda symbol: ~symbol.ctrl,
            succ="TSn-CTRL",
            action=lambda symbol: [
                NextValue(self._tsZ.rate.raw_bits(), symbol.data)
            ]
        )
        self.parser.rule(
            name="TSn-CTRL",
            cond=lambda symbol: ~symbol.ctrl,
            succ="TSn-ID0",
            action=lambda symbol: [
                NextValue(self._tsZ.ctrl.raw_bits(), symbol.data)
            ]
        )
        self.parser.rule(
            name="TSn-ID0",
            cond=lambda symbol: symbol.raw_bits() == D(10,2),
            succ="TSn-ID1",
            action=lambda symbol: [
                NextMemory(ts_id, symbol.raw_bits()),
                NextValue(ts_inv, 0),
                NextValue(self._tsZ.ts_id, 0),
            ]
        )
        self.parser.rule(
            name="TSn-ID0",
            cond=lambda symbol: symbol.raw_bits() == D(5,2),
            succ="TSn-ID1",
            action=lambda symbol: [
                NextMemory(ts_id, symbol.raw_bits()),
                NextValue(ts_inv, 0),
                NextValue(self._tsZ.ts_id, 1),
            ]
        )
        self.parser.rule(
            name="TSn-ID0",
            cond=lambda symbol: symbol.raw_bits() == D(21,5),
            succ="TSn-ID1",
            action=lambda symbol: [
                NextMemory(ts_id, symbol.raw_bits()),
                NextValue(ts_inv, 1),
            ]
        )
        self.parser.rule(
            name="TSn-ID0",
            cond=lambda symbol: symbol.raw_bits() == D(26,5),
            succ="TSn-ID1",
            action=lambda symbol: [
                NextMemory(ts_id, symbol.raw_bits()),
                NextValue(ts_inv, 1),
            ]
        )
        for n in range(1, 9):
            self.parser.rule(
                name="TSn-ID%d" % n,
                cond=lambda symbol: symbol.raw_bits() == Memory(ts_id),
                succ="TSn-ID%d" % (n + 1)
            )
        self.parser.rule(
            name="TSn-ID9",
            cond=lambda symbol: symbol.raw_bits() == Memory(ts_id),
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

        self.submodules.emitter = Emitter(
            symbol_size=12,
            word_size=lane.ratio,
            reset_rule="IDLE",
            layout=[
                ("data",     8),
                ("ctrl",     1),
                ("set_disp", 1),
                ("disp",     1),
                ("e_idle",   1),
            ])
        self.comb += [
            lane.tx_symbol.eq(Cat(
                (self.emitter._o[n].data, self.emitter._o[n].ctrl)
                for n in range(lane.ratio)
            )),
            lane.tx_set_disp.eq(Cat(self.emitter._o[n].set_disp for n in range(lane.ratio))),
            lane.tx_disp    .eq(Cat(self.emitter._o[n].disp     for n in range(lane.ratio))),
            lane.tx_e_idle  .eq(Cat(self.emitter._o[n].e_idle   for n in range(lane.ratio))),
        ]
        self.emitter.rule(
            name="IDLE",
            succ="TSn-LINK",
            action=lambda symbol: [
                symbol.raw_bits().eq(K(28,5)),
                symbol.set_disp.eq(1),
                symbol.disp.eq(0)
            ]
        )
        self.emitter.rule(
            name="TSn-LINK",
            succ="TSn-LANE",
            action=lambda symbol: [
                If(self.ts.link.valid,
                    symbol.data.eq(self.ts.link.number)
                ).Else(
                    symbol.raw_bits().eq(K(23,7))
                ),
            ]
        )
        self.emitter.rule(
            name="TSn-LANE",
            succ="TSn-FTS",
            action=lambda symbol: [
                If(self.ts.lane.valid,
                    symbol.data.eq(self.ts.lane.number)
                ).Else(
                    symbol.raw_bits().eq(K(23,7))
                ),
            ]
        )
        self.emitter.rule(
            name="TSn-FTS",
            succ="TSn-RATE",
            action=lambda symbol: [
                symbol.data.eq(self.ts.n_fts),
            ]
        )
        self.emitter.rule(
            name="TSn-RATE",
            succ="TSn-CTRL",
            action=lambda symbol: [
                symbol.data.eq(self.ts.rate.raw_bits()),
            ]
        )
        self.emitter.rule(
            name="TSn-CTRL",
            succ="TSn-ID0",
            action=lambda symbol: [
                symbol.data.eq(self.ts.ctrl.raw_bits()),
            ]
        )
        for n in range(0, 10):
            self.emitter.rule(
                name="TSn-ID%d" % n,
                succ="IDLE" if n == 9 else "TSn-ID%d" % (n + 1),
                action=lambda symbol: [
                    If(self.ts.ts_id == 0,
                        symbol.raw_bits().eq(D(10,2))
                    ).Else(
                        symbol.raw_bits().eq(D(5,2))
                    )
                ]
            )
