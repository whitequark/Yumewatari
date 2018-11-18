from migen import *
from migen.genlib.fsm import *

from .protocol import *
from .phy_rx import *
from .phy_tx import *


__all__ = ["PCIePHY"]


class PCIePHY(Module):
    def __init__(self, lane):
        self.submodules.rx = rx = PCIePHYRX(lane)
        self.submodules.tx = tx = PCIePHYTX(lane)

        ###

        self.comb += [
            tx.ts.n_fts.eq(0xff),
            tx.ts.rate.gen1.eq(1),
        ]

        rx_ts_count = Signal(max=8)

        self.submodules.ltssm = ltssm = ResetInserter()(FSM())
        self.comb += self.ltssm.reset.eq(self.rx.error)
        self.ltssm.act("Reset",
            NextValue(rx_ts_count, 7),
            # Send TS1 Link=PAD Lane=PAD
            NextValue(tx.ts.ts_id, 0),
            NextValue(tx.ts.link.valid, 0),
            NextValue(tx.ts.lane.valid, 0),
            NextState("Polling.Active")
        )
        self.ltssm.act("Polling.Active",
            # Expect TS1 Link=PAD Lane=PAD
            If(rx.ts.valid & (rx.ts.ts_id == 0) & ~rx.ts.link.valid & ~rx.ts.lane.valid,
                NextValue(rx_ts_count, rx_ts_count - 1),
                If(rx_ts_count == 0,
                    NextValue(rx_ts_count, 7),
                    # Send TS2 Link=PAD Lane=PAD
                    NextValue(tx.ts.ts_id, 1),
                    NextState("Polling.Configuration")
                )
            )
        )
        self.ltssm.act("Polling.Configuration",
            # Expect TS2 Link=PAD Lane=PAD
            If(rx.ts.valid & (rx.ts.ts_id == 1) & ~rx.ts.link.valid & ~rx.ts.lane.valid,
                NextValue(rx_ts_count, rx_ts_count - 1),
                If(rx_ts_count == 0,
                    NextValue(rx_ts_count, 7),
                    # Send TS1 Link=PAD Lane=PAD
                    NextValue(tx.ts.ts_id, 0),
                    NextState("Configuration.Linkwidth.Start")
                )
            )
        )
        self.ltssm.act("Configuration.Linkwidth.Start",
            # Expect TS1 Link<>PAD Lane=PAD
            If(rx.ts.valid & (rx.ts.ts_id == 0) & rx.ts.link.valid & ~rx.ts.lane.valid,
                NextValue(rx_ts_count, rx_ts_count - 1),
                If(rx_ts_count == 0,
                    NextValue(rx_ts_count, 7),
                    # Send TS1 Link=Upstream-Link Lane=PAD
                    NextValue(tx.ts.link.raw_bits(), rx.ts.link.raw_bits()),
                    NextState("Configuration.Linkwidth.Accept")
                )
            )
        )
        self.ltssm.act("Configuration.Linkwidth.Accept",
            # Expect TS1 Link<>PAD Lane=PAD
            If(rx.ts.valid & (rx.ts.ts_id == 0) & rx.ts.link.valid &
                    (rx.ts.link.number == tx.ts.link.number) & ~rx.ts.lane.valid,
                NextValue(rx_ts_count, rx_ts_count - 1),
                If(rx_ts_count == 0,
                    NextValue(rx_ts_count, 7),
                    # Send TS1 Link=Upstream-Link Lane=Upstream-Lane
                    NextValue(tx.ts.lane.raw_bits(), rx.ts.lane.raw_bits()),
                    NextState("Configuration.Lanenum.Wait")
                )
            )
        )
        self.ltssm.act("Configuration.Lanenum.Wait",
            NextState("Configuration.Lanenum.Wait")
        )
