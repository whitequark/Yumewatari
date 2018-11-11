from migen import *
from migen.genlib.fsm import *


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
        self.ts       = Record(_ts_layout)
        self.ts_error = Signal()

        ###

        self.comb += lane.rx_align.eq(1)

        self._tsZ = Record(_ts_layout) # TS being received
        self._tsY = Record(_ts_layout) # previous TS received

        id_ctr = Signal(max=10)
        ts_idx = Signal(2) # bit 0: TS1/TS2, bit 1: noninverted/inverted
        ts_id  = Signal(9)

        self.submodules.fsm = ResetInserter()(FSM(reset_state="IDLE"))
        self.comb += self.fsm.reset.eq(~lane.rx_valid)
        self.fsm.act("IDLE",
            If(lane.rx_symbol == K(28,5),
                NextValue(self._tsZ.valid, 1),
                NextValue(self._tsY.raw_bits(), self._tsZ.raw_bits()),
                NextState("TSn-LINK")
            )
        )
        self.fsm.act("TSn-LINK",
            NextValue(self._tsZ.link.number, lane.rx_symbol),
            If(lane.rx_symbol == K(23,7),
                NextValue(self._tsZ.link.valid,  0),
                NextState("TSn-LANE")
            ).Elif(~lane.rx_symbol[8],
                NextValue(self._tsZ.link.valid,  1),
                NextState("TSn-LANE")
            ).Else(
                self.ts_error.eq(1),
                NextValue(self._tsZ.valid, 0),
                NextState("IDLE")
            )
        )
        self.fsm.act("TSn-LANE",
            NextValue(self._tsZ.lane.number, lane.rx_symbol),
            If(lane.rx_symbol == K(23,7),
                NextValue(self._tsZ.lane.valid,  0),
                NextState("TSn-FTS")
            ).Elif(~lane.rx_symbol[8],
                NextValue(self._tsZ.lane.valid,  1),
                NextState("TSn-FTS")
            ).Else(
                self.ts_error.eq(1),
                NextValue(self._tsZ.valid, 0),
                NextState("IDLE")
            )
        )
        self.fsm.act("TSn-FTS",
            NextValue(self._tsZ.n_fts, lane.rx_symbol),
            If(~lane.rx_symbol[8],
                NextState("TSn-RATE")
            ).Else(
                self.ts_error.eq(1),
                NextValue(self._tsZ.valid, 0),
                NextState("IDLE")
            )
        )
        self.fsm.act("TSn-RATE",
            NextValue(self._tsZ.rate.raw_bits(), lane.rx_symbol),
            If(~lane.rx_symbol[8],
                NextState("TSn-CTRL")
            ).Else(
                self.ts_error.eq(1),
                NextValue(self._tsZ.valid, 0),
                NextState("IDLE")
            )
        )
        self.fsm.act("TSn-CTRL",
            NextValue(self._tsZ.ctrl.raw_bits(), lane.rx_symbol),
            If(~lane.rx_symbol[8],
                NextState("TSn-ID0")
            ).Else(
                self.ts_error.eq(1),
                NextValue(self._tsZ.valid, 0),
                NextState("IDLE")
            )
        )
        self.fsm.act("TSn-ID0",
            NextValue(id_ctr, 1),
            NextValue(ts_id, lane.rx_symbol),
            If(lane.rx_symbol == D(10,2),
                NextValue(ts_idx, 0),
                NextValue(self._tsZ.ts_id, 0),
                NextState("TSn-IDn")
            ).Elif(lane.rx_symbol == D(5,2),
                NextValue(ts_idx, 1),
                NextValue(self._tsZ.ts_id, 1),
                NextState("TSn-IDn")
            ).Elif(lane.rx_symbol == D(21,5),
                NextValue(ts_idx, 2),
                NextValue(self._tsZ.valid, 0),
                NextState("TSn-IDn")
            ).Elif(lane.rx_symbol == D(26,5),
                NextValue(ts_idx, 3),
                NextValue(self._tsZ.valid, 0),
                NextState("TSn-IDn")
            ).Else(
                self.ts_error.eq(1),
                NextValue(self._tsZ.valid, 0),
                NextState("IDLE")
            )
        )
        self.fsm.act("TSn-IDn",
            NextValue(id_ctr, id_ctr + 1),
            If(lane.rx_symbol == ts_id,
                If(id_ctr == 9,
                    If(self._tsZ.raw_bits() == self._tsY.raw_bits(),
                        NextValue(self.ts.raw_bits(), self._tsY.raw_bits())
                    ).Else(
                        NextValue(self.ts.valid, 0)
                    ),
                    If(ts_idx[1],
                        NextValue(lane.rx_invert, ~lane.rx_invert)
                    ),
                    NextState("IDLE")
                )
            ).Else(
                self.ts_error.eq(1),
                NextValue(self._tsZ.valid, 0),
                NextState("IDLE")
            )
        )


class PCIeTXPHY(Module):
    def __init__(self, lane):
        self.ts = Record(_ts_layout)

        ###

        id_ctr = Signal(max=10)

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
            NextValue(id_ctr, 0),
            NextState("TSn-IDn")
        )
        self.fsm.act("TSn-IDn",
            NextValue(id_ctr, id_ctr + 1),
            If(self.ts.ts_id == 0,
                lane.tx_symbol.eq(D(10,2))
            ).Else(
                lane.tx_symbol.eq(D(5,2))
            ),
            If(id_ctr == 9,
                NextState("IDLE")
            )
        )
