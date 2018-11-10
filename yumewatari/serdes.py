from migen import *
from migen.genlib.cdc import *


__all__ = ["PCIeSERDESInterface"]


class PCIeSERDESInterface(Module):
    """
    Interface of a single PCIe SERDES pair, connected to a single lane. Assumes 1:1 gearing,
    i.e. one symbol is transmitted each clock cycle.

    Parameters
    ----------
    rx_invert : Signal
        Assert to invert the received bits before 8b10b decoder.
    rx_align : Signal
        Assert to enable comma alignment state machine, deassert to lock bit alignment.
    rx_present : Signal
        Asserted if the receiver has detected signal.
    rx_locked : Signal
        Asserted if the receiver has recovered a valid clock.
    rx_aligned : Signal
        Asserted if the receiver has aligned to the comma symbol.

    rx_data : Signal(8)
        8b10b-decoded received symbol.
    rx_control : Signal
        Asserted if the received symbol is a control symbol.
    rx_valid : Signal
        Asserted if the received symbol has no coding errors. If not asserted, ``rx_data`` and
        ``rx_control`` must be ignored, and may contain symbols that do not exist in 8b10b coding
        space.

    tx_locked : Signal
        Asserted if the transmitter is generating a valid clock.

    tx_data : Signal(8)
        Symbol to 8b10b-encode and transmit.
    tx_control : Signal
        Assert if the symbol to transmit is a comma.
    tx_set_disp : Signal
        Assert to indicate that the 8b10b encoder should choose an encoding with a specific
        running disparity instead of using its state, specified by ``tx_disp``.
    tx_disp : Signal
        Assert to transmit a symbol with positive running disparity, deassert for negative
        running disparity.
    """
    def __init__(self):
        self.rx_invert    = Signal()
        self.rx_align     = Signal()
        self.rx_present   = Signal()
        self.rx_locked    = Signal()
        self.rx_aligned   = Signal()

        self.rx_data      = Signal(8)
        self.rx_control   = Signal()
        self.rx_valid     = Signal()

        self.tx_data      = Signal(8)
        self.tx_control   = Signal()
        self.tx_set_disp  = Signal()
        self.tx_disp      = Signal()
