from migen import *
from migen.genlib.fsm import *

from .serdes import K, D
from .protocol import *
from .struct import *


__all__ = ["PCIePHYRX"]


class PCIePHYRX(Module):
    def __init__(self, lane):
        self.ts    = Record(ts_layout)
        self.comma = Signal()
        self.error = Signal()

        ###

        self.comb += lane.rx_align.eq(1)

        self._tsY  = Record(ts_layout) # previous TS received
        self._tsZ  = Record(ts_layout) # TS being received
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
                self.comma.eq(1),
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
