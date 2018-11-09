from migen import *
from migen.genlib.fsm import *
from migen.genlib.cdc import MultiReg


__all__ = ['UART', 'uart_bit_cyc']


class UARTBus(Module):
    """
    UART bus.

    Provides synchronization.
    """
    def __init__(self, pads):
        self.has_rx = hasattr(pads, "rx_t")
        if self.has_rx:
            self.rx_t = pads.rx_t
            self.rx_i = Signal()

        self.has_tx = hasattr(pads, "tx_t")
        if self.has_tx:
            self.tx_t = pads.tx_t
            self.tx_o = Signal(reset=1)

        ###

        if self.has_tx:
            self.comb += [
                self.tx_t.oe.eq(1),
                self.tx_t.o.eq(self.tx_o)
            ]

        if self.has_rx:
            self.specials += [
                MultiReg(self.rx_t.i, self.rx_i, reset=1)
            ]


def uart_bit_cyc(clk_freq, baud_rate, max_deviation=50000):
    """
    Calculate bit time from clock frequency and baud rate.

    :param clk_freq:
        Input clock frequency, in Hz.
    :type clk_freq: int or float
    :param baud_rate:
        Baud rate, in bits per second.
    :type baud_rate: int or float
    :param max_deviation:
        Maximum deviation of actual baud rate from ``baud_rate``, in parts per million.
    :type max_deviation: int or float

    :returns: (int, int or float) -- bit time as a multiple of clock period, and actual baud rate
    as calculated based on bit time.
    :raises: ValueError -- if the baud rate is too high for the specified clock frequency,
    or if actual baud rate deviates from requested baud rate by more than a specified amount.
    """

    bit_cyc = round(clk_freq // baud_rate)
    if bit_cyc <= 0:
        raise ValueError("baud rate {} is too high for input clock frequency {}"
                         .format(baud_rate, clk_freq))

    actual_baud_rate = round(clk_freq // bit_cyc)
    deviation = round(1000000 * (actual_baud_rate - baud_rate) // baud_rate)
    if deviation > max_deviation:
        raise ValueError("baud rate {} deviation from {} ({} ppm) is higher than {} ppm"
                         .format(actual_baud_rate, baud_rate, deviation, max_deviation))

    return bit_cyc + 1, actual_baud_rate


class UART(Module):
    """
    Asynchronous serial receiver-transmitter.

    Any number of data bits, any parity, and 1 stop bit are supported.

    :param bit_cyc:
        Bit time expressed as a multiple of system clock periods. Use :func:`uart_bit_cyc`
        to calculate bit time from system clock frequency and baud rate.
    :type bit_cyc: int
    :param data_bits:
        Data bit count.
    :type data_bits: int
    :param parity:
        Parity, one of ``"none"`` (default), ``"zero"``, ``"one"``, ``"even"``, ``"odd"``.
    :type parity: str

    :attr rx_data:
        Received data. Valid when ``rx_rdy`` is active.
    :attr rx_rdy:
        Receive ready flag. Becomes active after a stop bit of a valid frame is received.
    :attr rx_ack:
        Receive acknowledgement. If active when ``rx_rdy`` is active, ``rx_rdy`` is reset,
        and the receive state machine becomes ready for another frame.
    :attr rx_ferr:
        Receive frame error flag. Active for one cycle when a frame error is detected.
    :attr rx_ovf:
        Receive overflow flag. Active for one cycle when a new frame is started while ``rx_rdy``
        is still active. Afterwards, the receive state machine is reset and starts receiving
        the new frame.
    :attr rx_err:
        Receive error flag. Logical OR of all other error flags.

    :attr tx_data:
        Data to transmit. Sampled when ``tx_rdy`` is active.
    :attr tx_rdy:
        Transmit ready flag. Active while the transmit state machine is idle, and can accept
        data to transmit.
    :attr tx_ack:
        Transmit acknowledgement. If active when ``tx_rdy`` is active, ``tx_rdy`` is reset,
        ``tx_data`` is sampled, and the transmit state machine starts transmitting a frame.
    """
    def __init__(self, pads, bit_cyc, data_bits=8, parity="none"):
        self.rx_data = Signal(data_bits)
        self.rx_rdy  = Signal()
        self.rx_ack  = Signal()
        self.rx_ferr = Signal()
        self.rx_ovf  = Signal()
        self.rx_perr = Signal()
        self.rx_err  = Signal()

        self.tx_data = Signal(data_bits)
        self.tx_rdy  = Signal()
        self.tx_ack  = Signal()

        self.submodules.bus = bus = UARTBus(pads)

        ###

        bit_cyc = int(bit_cyc)

        def calc_parity(sig, kind):
            if kind in ("zero", "none"):
                return C(0, 1)
            elif kind == "one":
                return C(1, 1)
            else:
                bits, _ = value_bits_sign(sig)
                even_parity = sum([sig[b] for b in range(bits)]) & 1
                if kind == "odd":
                    return ~even_parity
                elif kind == "even":
                    return even_parity
                else:
                    assert False

        if bus.has_rx:
            rx_timer = Signal(max=bit_cyc)
            rx_stb   = Signal()
            rx_shreg = Signal(data_bits)
            rx_bitno = Signal(max=rx_shreg.nbits)

            self.comb += self.rx_err.eq(self.rx_ferr | self.rx_ovf | self.rx_perr)

            self.sync += [
                If(rx_timer == 0,
                    rx_timer.eq(bit_cyc - 1)
                ).Else(
                    rx_timer.eq(rx_timer - 1)
                )
            ]
            self.comb += rx_stb.eq(rx_timer == 0)

            self.submodules.rx_fsm = FSM(reset_state="IDLE")
            self.rx_fsm.act("IDLE",
                NextValue(self.rx_rdy, 0),
                If(~bus.rx_i,
                    NextValue(rx_timer, bit_cyc // 2),
                    NextState("START")
                )
            )
            self.rx_fsm.act("START",
                If(rx_stb,
                    NextState("DATA")
                )
            )
            self.rx_fsm.act("DATA",
                If(rx_stb,
                    NextValue(rx_shreg, Cat(rx_shreg[1:8], bus.rx_i)),
                    NextValue(rx_bitno, rx_bitno + 1),
                    If(rx_bitno == rx_shreg.nbits - 1,
                        If(parity == "none",
                            NextState("STOP")
                        ).Else(
                            NextState("PARITY")
                        )
                    )
                )
            )
            self.rx_fsm.act("PARITY",
                If(rx_stb,
                    If(bus.rx_i == calc_parity(rx_shreg, parity),
                        NextState("STOP")
                    ).Else(
                        self.rx_perr.eq(1),
                        NextState("IDLE")
                    )
                )
            )
            self.rx_fsm.act("STOP",
                If(rx_stb,
                    If(~bus.rx_i,
                        self.rx_ferr.eq(1),
                        NextState("IDLE")
                    ).Else(
                        NextValue(self.rx_data, rx_shreg),
                        NextState("READY")
                    )
                )
            )
            self.rx_fsm.act("READY",
                NextValue(self.rx_rdy, 1),
                If(self.rx_ack,
                    NextState("IDLE")
                ).Elif(~bus.rx_i,
                    self.rx_ovf.eq(1),
                    NextState("IDLE")
                )
            )

        ###

        if bus.has_tx:
            tx_timer  = Signal(max=bit_cyc)
            tx_stb    = Signal()
            tx_shreg  = Signal(data_bits)
            tx_bitno  = Signal(max=tx_shreg.nbits)
            tx_parity = Signal()

            self.sync += [
                If(tx_timer == 0,
                    tx_timer.eq(bit_cyc - 1)
                ).Else(
                    tx_timer.eq(tx_timer - 1)
                )
            ]
            self.comb += tx_stb.eq(tx_timer == 0)

            self.submodules.tx_fsm = FSM(reset_state="IDLE")
            self.tx_fsm.act("IDLE",
                self.tx_rdy.eq(1),
                If(self.tx_ack,
                    NextValue(tx_shreg, self.tx_data),
                    If(parity != "none",
                        NextValue(tx_parity, calc_parity(self.tx_data, parity))
                    ),
                    NextValue(tx_timer, bit_cyc - 1),
                    NextValue(bus.tx_o, 0),
                    NextState("START")
                ).Else(
                    NextValue(bus.tx_o, 1)
                )
            )
            self.tx_fsm.act("START",
                If(tx_stb,
                    NextValue(bus.tx_o, tx_shreg[0]),
                    NextValue(tx_shreg, Cat(tx_shreg[1:8], 0)),
                    NextState("DATA")
                )
            )
            self.tx_fsm.act("DATA",
                If(tx_stb,
                    NextValue(tx_bitno, tx_bitno + 1),
                    If(tx_bitno != tx_shreg.nbits - 1,
                        NextValue(bus.tx_o, tx_shreg[0]),
                        NextValue(tx_shreg, Cat(tx_shreg[1:8], 0)),
                    ).Else(
                        If(parity == "none",
                            NextValue(bus.tx_o, 1),
                            NextState("STOP")
                        ).Else(
                            NextValue(bus.tx_o, tx_parity),
                            NextState("PARITY")
                        )
                    )
                )
            )
            self.tx_fsm.act("PARITY",
                If(tx_stb,
                    NextValue(bus.tx_o, 1),
                    NextState("STOP")
                )
            )
            self.tx_fsm.act("STOP",
                If(tx_stb,
                    NextState("IDLE")
                )
            )
