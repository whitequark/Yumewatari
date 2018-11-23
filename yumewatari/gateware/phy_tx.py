from migen import *

from .serdes import K, D
from .protocol import *
from .struct import *


__all__ = ["PCIePHYTX"]


class PCIePHYTX(Module):
    def __init__(self, lane):
        self.e_idle = Signal()
        self.comma  = Signal()
        self.ts     = Record(ts_layout)

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
            cond=lambda: self.e_idle,
            succ="IDLE",
            action=lambda symbol: [
                symbol.e_idle.eq(1)
            ]
        )
        self.emitter.rule(
            name="IDLE",
            cond=lambda: self.ts.valid,
            succ="TSn-LINK",
            action=lambda symbol: [
                self.comma.eq(1),
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
