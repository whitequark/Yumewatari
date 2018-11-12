from migen import *


__all__ = ["SymbolSlip"]


class SymbolSlip(Module):
    """
    Symbol slip based comma aligner. Accepts and emits a sequence of words, shifting it such
    that if a comma symbol is encountered, it is always placed at the start of a word.

    If the input word contains multiple commas, the behavior is undefined.

    Parameters
    ----------
    symbol_size : int
        Symbol width, in bits.
    word_size : int
        Word size, in symbols.
    comma : int
        Comma symbol, ``symbol_size`` bit wide.

    Attributes
    ----------
    i : Signal(symbol_size * word_size)
        Input word.
    o : Signal(symbol_size * word_size)
        Output word.
    en : Signal
        Enable input. If asserted (the default), comma symbol affects alignment. Otherwise,
        comma symbol does nothing.
    """
    def __init__(self, symbol_size, word_size, comma):
        width = symbol_size * word_size

        self.i = Signal(width)
        self.o = Signal(width)
        self.en = Signal(reset=1)

        ###

        shreg  = Signal(width * 2)
        offset = Signal(max=symbol_size * (word_size - 1))
        self.sync += shreg.eq(Cat(shreg[width:], self.i))
        self.comb += self.o.eq(shreg.part(offset, width))

        commas = Signal(word_size)
        self.sync += [
            commas[n].eq(self.i.part(symbol_size * n, symbol_size) == comma)
            for n in range(word_size)
        ]

        self.sync += [
            If(self.en,
                Case(commas, {
                    (1 << n): offset.eq(symbol_size * n)
                    for n in range(word_size)
                })
            )
        ]
