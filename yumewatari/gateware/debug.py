from migen import *


__all__ = ["RingLog"]


class RingLog(Module):
    def __init__(self, timestamp_width, data_width, depth):
        self.width     = timestamp_width + data_width
        self.depth     = depth

        self.data_i    = Signal(data_width)
        self.trigger   = Signal()

        self.time_o    = Signal(timestamp_width)
        self.data_o    = Signal(data_width)
        self.next      = Signal()

        ###

        timestamp = Signal(timestamp_width)
        self.sync += timestamp.eq(timestamp + 1)

        data_i_l = Signal.like(self.data_i)
        self.sync += data_i_l.eq(self.data_i)

        storage = Memory(width=self.width, depth=self.depth)
        self.specials += storage

        wrport = storage.get_port(write_capable=True)
        self.specials += wrport
        self.comb += [
            wrport.we.eq(~self.trigger & (self.data_i != data_i_l)),
            wrport.dat_w.eq(Cat(timestamp, self.data_i))
        ]
        self.sync += [
            If(~self.trigger,
                If(self.data_i != data_i_l,
                    wrport.adr.eq(wrport.adr + 1)
                )
            )
        ]

        trigger_s = Signal.like(self.trigger)
        self.sync += trigger_s.eq(self.trigger)

        rdport = storage.get_port()
        self.specials += rdport
        self.comb += [
            Cat(self.time_o, self.data_o).eq(rdport.dat_r),
        ]
        self.sync += [
            If(~self.trigger,
                rdport.adr.eq(wrport.adr + 1)
            ).Elif(self.next,
                rdport.adr.eq(rdport.adr + 1)
            )
        ]
