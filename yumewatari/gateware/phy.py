from migen import *
from migen.genlib.fsm import *

from .protocol import *
from .phy_rx import *
from .phy_tx import *
from .debug import RingLog


__all__ = ["PCIePHY"]


class PCIePHY(Module):
    def __init__(self, lane, ms_cyc):
        self.submodules.rx = rx = PCIePHYRX(lane)
        self.submodules.tx = tx = PCIePHYTX(lane)

        self.link_up = Signal()

        self.submodules.ltssm_log = RingLog(timestamp_width=32, data_width=8, depth=16)

        ###

        self.comb += [
            tx.ts.rate.gen1.eq(1),
        ]

        rx_timer    = Signal(max=64 * ms_cyc + 1)
        rx_ts_count = Signal(max=16 + 1)
        tx_ts_count = Signal(max=1024 + 1)

        # LTSSM implemented according to PCIe Base Specification Revision 2.1.
        # The Specification must be read side to side with this code in order to understand it.
        # Unfortunately, the Specification is copyrighted and probably cannot be quoted here
        # directly at length.
        self.submodules.ltssm = ltssm = ResetInserter()(FSM())
        self.ltssm.act("Detect.Quiet",
            NextValue(tx.e_idle, 1),
            NextValue(self.link_up, 0),
            NextValue(rx_timer, 12 * ms_cyc),
            NextState("Detect.Quiet:Timeout")
        )
        self.ltssm.act("Detect.Quiet:Timeout",
            NextValue(rx_timer, rx_timer - 1),
            If(lane.rx_present | (rx_timer == 0),
                NextValue(lane.det_enable, 1),
                NextState("Detect.Active")
            )
        )
        self.ltssm.act("Detect.Active",
            If(lane.det_valid,
                NextValue(lane.det_enable, 0),
                If(lane.det_status,
                    NextState("Polling.Active")
                ).Else(
                    NextState("Detect.Quiet")
                )
            )
        )
        self.ltssm.act("Polling.Active",
            NextValue(tx.e_idle, 0),
            # Transmit TS1 Link=PAD Lane=PAD
            NextValue(tx.ts.valid, 1),
            NextValue(tx.ts.ts_id, 0),
            NextValue(tx.ts.link.valid, 0),
            NextValue(tx.ts.lane.valid, 0),
            NextValue(rx_timer, 24 * ms_cyc),
            NextValue(rx_ts_count, 0),
            NextValue(tx_ts_count, 0),
            NextState("Polling.Active:TS")
        )
        self.ltssm.act("Polling.Active:TS",
            If(tx.comma,
                If(tx_ts_count != 1024,
                    NextValue(tx_ts_count, tx_ts_count + 1)
                )
            ),
            If((tx_ts_count == 1024),
                If(rx.comma,
                    # Accept TS1 Link=PAD Lane=PAD Compliance=0
                    # Accept TS1 Link=PAD Lane=PAD Loopback=1
                    # Accept TS2 Link=PAD Lane=PAD
                    If(rx.ts.valid & ~rx.ts.lane.valid & ~rx.ts.link.valid &
                            (((rx.ts.ts_id == 0) & ~rx.ts.ctrl.compliance_receive) |
                             ((rx.ts.ts_id == 0) & rx.ts.ctrl.loopback) |
                              (rx.ts.ts_id == 1)),
                        NextValue(rx_ts_count, rx_ts_count + 1),
                        If(rx_ts_count == 8,
                            NextState("Polling.Configuration")
                        )
                    ).Else(
                        NextValue(rx_ts_count, 0)
                    )
                )
            ),
            NextValue(rx_timer, rx_timer - 1),
            If(rx_timer == 0,
                NextState("Detect.Quiet")
            )
        )
        self.ltssm.act("Polling.Configuration",
            # Transmit TS2 Link=PAD Lane=PAD
            NextValue(tx.ts.valid, 1),
            NextValue(tx.ts.ts_id, 1),
            NextValue(tx.ts.link.valid, 0),
            NextValue(tx.ts.lane.valid, 0),
            NextValue(rx_ts_count, 0),
            NextValue(tx_ts_count, 0),
            NextValue(rx_timer, 48 * ms_cyc),
            NextState("Polling.Configuration:TS")
        )
        self.ltssm.act("Polling.Configuration:TS",
            If(tx.comma,
                If(rx_ts_count == 0,
                    NextValue(tx_ts_count, 0)
                ).Else(
                    NextValue(tx_ts_count, tx_ts_count + 1)
                )
            ),
            If(rx.comma,
                # Accept TS2 Link=PAD Lane=PAD
                If(rx.ts.valid & (rx.ts.ts_id == 1) & ~rx.ts.link.valid & ~rx.ts.lane.valid,
                    If(rx_ts_count == 8,
                        If(tx_ts_count == 16,
                            NextValue(rx_timer, 24 * ms_cyc),
                            NextState("Configuration.Linkwidth.Start")
                        )
                    ).Else(
                        NextValue(rx_ts_count, rx_ts_count + 1)
                    )
                ).Else(
                    NextValue(rx_ts_count, 0)
                ),
            ),
            NextValue(rx_timer, rx_timer - 1),
            If(rx_timer == 0,
                NextState("Detect.Quiet")
            )
        )
        self.ltssm.act("Configuration.Linkwidth.Start",
            # Transmit TS1 Link=PAD Lane=PAD
            NextValue(tx.ts.valid, 1),
            NextValue(tx.ts.ts_id, 0),
            NextValue(tx.ts.link.valid, 0),
            NextValue(tx.ts.lane.valid, 0),
            # Accept TS1 Link=Upstream-Link Lane=PAD
            If(rx.ts.valid & (rx.ts.ts_id == 0) & rx.ts.link.valid & ~rx.ts.lane.valid,
                # Transmit TS1 Link=Upstream-Link Lane=PAD
                NextValue(tx.ts.link.valid, 1),
                NextValue(tx.ts.link.number, rx.ts.link.number),
                NextValue(rx_timer, 2 * ms_cyc),
                NextState("Configuration.Linkwidth.Accept")
            ),
            NextValue(rx_timer, rx_timer - 1),
            If(rx_timer == 0,
                NextState("Detect.Quiet")
            )
        )
        self.ltssm.act("Configuration.Linkwidth.Accept",
            # Accept TS1 Link=Upstream-Link Lane=Upstream-Lane
            If(rx.ts.valid & (rx.ts.ts_id == 0) & rx.ts.link.valid & rx.ts.lane.valid,
                # Accept Upstream-Lane=0
                If(rx.ts.lane.number == 0,
                    # Transmit TS1 Link=Upstream-Link Lane=Upstream-Lane
                    NextValue(tx.ts.lane.valid, 1),
                    NextValue(tx.ts.lane.number, rx.ts.lane.number),
                    NextValue(rx_timer, 2 * ms_cyc),
                    NextState("Configuration.Lanenum.Wait")
                )
            ),
            # Accept TS1 Link=PAD Lane=PAD
            If(rx.ts.valid & (rx.ts.ts_id == 0) & ~rx.ts.link.valid & ~rx.ts.lane.valid,
                NextState("Detect.Quiet")
            ),
            NextValue(rx_timer, rx_timer - 1),
            If(rx_timer == 0,
                NextState("Detect.Quiet")
            )
        )
        self.ltssm.act("Configuration.Lanenum.Wait",
            # Accept TS1 Link=Upstream-Link Lane=Upstream-Lane
            If(rx.ts.valid & (rx.ts.ts_id == 0) & rx.ts.link.valid & rx.ts.lane.valid,
                If(rx.ts.lane.number != tx.ts.lane.number,
                    NextState("Configuration.Lanenum.Accept")
                )
            ),
            # Accept TS2
            If(rx.ts.valid & (rx.ts.ts_id == 1),
                NextState("Configuration.Lanenum.Accept")
            ),
            # Accept TS1 Link=PAD Lane=PAD
            If(rx.ts.valid & (rx.ts.ts_id == 0) & ~rx.ts.link.valid & ~rx.ts.lane.valid,
                NextState("Detect.Quiet")
            ),
            NextValue(rx_timer, rx_timer - 1),
            If(rx_timer == 0,
                NextState("Detect.Quiet")
            )
        )
        self.ltssm.act("Configuration.Lanenum.Accept",
            # Accept TS2 Link=Upstream-Link Lane=Upstream-Lane
            If(rx.ts.valid & (rx.ts.ts_id == 1) & rx.ts.link.valid & rx.ts.lane.valid,
                If((rx.ts.link.number == tx.ts.link.number) &
                   (rx.ts.lane.number == tx.ts.lane.number),
                    NextState("Configuration.Complete")
                ).Else(
                    NextState("Detect.Quiet")
                )
            ),
            # Accept TS1 Link=PAD Lane=PAD
            If(rx.ts.valid & (rx.ts.ts_id == 0) & ~rx.ts.link.valid & ~rx.ts.lane.valid,
                NextState("Detect.Quiet")
            ),
        )
        self.ltssm.act("Configuration.Complete",
            # Transmit TS2 Link=Upstream-Link Lane=Upstream-Lane
            NextValue(tx.ts.ts_id, 1),
            NextValue(tx.ts.n_fts, 0xff),
            NextValue(rx_ts_count, 0),
            NextValue(tx_ts_count, 0),
            NextValue(rx_timer, 2 * ms_cyc),
            NextState("Configuration.Complete:TS")
        )
        self.ltssm.act("Configuration.Complete:TS",
            If(tx.comma,
                If(rx_ts_count == 0,
                    NextValue(tx_ts_count, 0)
                ).Else(
                    NextValue(tx_ts_count, tx_ts_count + 1)
                )
            ),
            If(rx.comma,
                # Accept TS2 Link=Upstream-Link Lane=Upstream-Lane
                If(rx.ts.valid & (rx.ts.ts_id == 1) & rx.ts.link.valid & rx.ts.lane.valid &
                        (rx.ts.link.number == tx.ts.link.number) &
                        (rx.ts.lane.number == tx.ts.lane.number),
                    If(rx_ts_count == 8,
                        If(tx_ts_count == 16,
                            NextState("Configuration.Idle")
                        )
                    ).Else(
                        NextValue(rx_ts_count, rx_ts_count + 1)
                    )
                ).Else(
                    NextValue(rx_ts_count, 0)
                ),
            ),
            NextValue(rx_timer, rx_timer - 1),
            If(rx_timer == 0,
                NextState("Detect.Quiet")
            )
        )
        self.ltssm.act("Configuration.Idle",
            NextValue(self.link_up, 1)
        )

    def do_finalize(self):
        self.comb += self.ltssm_log.data_i.eq(self.ltssm.state)
