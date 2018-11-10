from migen import *
from migen.genlib.fsm import *


__all__ = ["PCIePHY"]


K28_5 = 0b1_101_11100
K23_7 = 0b1_111_10111
D10_2 = 0b0_010_01010
D21_5 = 0b0_101_10101
D05_2 = 0b0_010_00101
D26_5 = 0b0_101_11010


class PCIePHY(Module):
    def __init__(self, lane):
        self.lane = lane

        ###

        rx_link   = Signal(8)
        rx_lane   = Signal(5)
        rx_n_fts  = Signal(8)
        rx_rate   = Signal(8)
        rx_ctrl   = Record([
            ("reset",      1),
            ("disable",    1),
            ("loopback",   1),
            ("unscramble", 1)
        ])

        rx_id_ctr = Signal(max=10)
        rx_ts_idx = Signal(2) # bit 0: TS1/TS2, bit 1: noninverted/inverted
        rx_ts_id  = Array([D10_2, D05_2, D21_5, D26_5])[rx_ts_idx]

        self.submodules.rx_fsm = ResetInserter()(FSM(reset_state="TSn-COM"))
        self.comb += self.rx_fsm.reset.eq(~lane.rx_valid)
        self.rx_fsm.act("TSn-COM",
            If(lane.rx_symbol == K28_5,
                NextState("TSn-LINK")
            )
        )
        self.rx_fsm.act("TSn-LINK",
            If(lane.rx_symbol == K23_7,
                NextState("TSn-LANE")
            ).Elif(~lane.rx_symbol[8:],
                NextValue(rx_link, lane.rx_symbol),
                NextState("TSn-LANE")
            ).Else(
                NextState("TSn-COM")
            )
        )
        self.rx_fsm.act("TSn-LANE",
            If(lane.rx_symbol == K23_7,
                NextState("TSn-FTS")
            ).Elif(~lane.rx_symbol[4:],
                NextValue(rx_lane, lane.rx_symbol),
                NextState("TSn-FTS")
            ).Else(
                NextState("TSn-COM")
            )
        )
        self.rx_fsm.act("TSn-FTS",
            If(~lane.rx_symbol[8:],
                NextValue(rx_n_fts, lane.rx_symbol),
                NextState("TSn-RATE")
            ).Else(
                NextState("TSn-COM")
            )
        )
        self.rx_fsm.act("TSn-RATE",
            If(~lane.rx_symbol[8:],
                NextValue(rx_rate, lane.rx_symbol),
                NextState("TSn-CTRL")
            ).Else(
                NextState("TSn-COM")
            )
        )
        self.rx_fsm.act("TSn-CTRL",
            If(~lane.rx_symbol[8:],
                NextValue(rx_ctrl.raw_bits(), lane.rx_symbol),
                NextState("TSn-ID0")
            ).Else(
                NextState("TSn-COM")
            )
        )
        self.rx_fsm.act("TSn-ID0",
            NextValue(rx_id_ctr, 1),
            If(lane.rx_symbol == D10_2,
                NextValue(rx_ts_idx, 0),
                NextState("TSn-IDn")
            ).Elif(lane.rx_symbol == D05_2,
                NextValue(rx_ts_idx, 1),
                NextState("TSn-IDn")
            ).Elif(lane.rx_symbol == D26_5,
                NextValue(rx_ts_idx, 2),
                NextState("TSn-IDn")
            ).Elif(lane.rx_symbol == D21_5,
                NextValue(rx_ts_idx, 3),
                NextState("TSn-IDn")
            ).Else(
                NextState("TSn-COM")
            )
        )
        self.rx_fsm.act("TSn-IDn",
            NextValue(rx_id_ctr, rx_id_ctr + 1),
            If(lane.rx_symbol == rx_ts_id,
                If(rx_id_ctr == 9,
                    NextState("TS-FOUND")
                )
            ).Else(
                NextState("TSn-COM")
            )
        )
        self.rx_fsm.act("TS-FOUND",
            NextState("TS-FOUND")
        )
