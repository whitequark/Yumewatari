from migen import *


__all__ = ["PCIeSERDESInterface"]


class PCIeSERDESInterface(Module):
    """
    Interface of a single PCIe SERDES pair, connected to a single lane. Uses 1:**ratio** gearing
    for configurable **ratio**, i.e. **ratio** symbols are transmitted per clock cycle.

    Parameters
    ----------
    ratio : int
        Gearbox ratio.

    rx_invert : Signal
        Assert to invert the received bits before 8b10b decoder.
    rx_align : Signal
        Assert to enable comma alignment state machine, deassert to lock alignment.
    rx_present : Signal
        Asserted if the receiver has detected signal.
    rx_locked : Signal
        Asserted if the receiver has recovered a valid clock.
    rx_aligned : Signal
        Asserted if the receiver has aligned to the comma symbol.

    rx_symbol : Signal(9 * ratio)
        Two 8b10b-decoded received symbols, with 9th bit indicating a control symbol.
    rx_valid : Signal(ratio)
        Asserted if the received symbol has no coding errors. If not asserted, ``rx_data`` and
        ``rx_control`` must be ignored, and may contain symbols that do not exist in 8b10b coding
        space.

    tx_locked : Signal
        Asserted if the transmitter is generating a valid clock.

    tx_symbol : Signal(9 * ratio)
        Symbol to 8b10b-encode and transmit, with 9th bit indicating a control symbol.
    tx_set_disp : Signal(ratio)
        Assert to indicate that the 8b10b encoder should choose an encoding with a specific
        running disparity instead of using its state, specified by ``tx_disp``.
    tx_disp : Signal(ratio)
        Assert to transmit a symbol with positive running disparity, deassert for negative
        running disparity.
    tx_e_idle : Signal(ratio)
        Assert to transmit Electrical Idle for that symbol.
    """
    def __init__(self, ratio=1):
        self.ratio        = ratio

        self.rx_invert    = Signal()
        self.rx_align     = Signal()
        self.rx_present   = Signal()
        self.rx_locked    = Signal()
        self.rx_aligned   = Signal()

        self.rx_symbol    = Signal(ratio * 9)
        self.rx_valid     = Signal(ratio)

        self.tx_symbol    = Signal(ratio * 9)
        self.tx_set_disp  = Signal(ratio)
        self.tx_disp      = Signal(ratio)
        self.tx_e_idle    = Signal(ratio)
