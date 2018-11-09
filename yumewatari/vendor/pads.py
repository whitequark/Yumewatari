from migen import *


__all__ = ['Pads']


class Pads(Module):
    """
    Pad adapter.

    Provides a common interface to device pads, wrapping either a Migen platform request,
    or a Glasgow I/O port slice.

    Construct a pad adapter providing signals, records, or tristate triples; name may
    be specified explicitly with keyword arguments. For each signal, record field, or
    triple with name ``n``, the pad adapter will have an attribute ``n_t`` containing
    a tristate triple. ``None`` may also be provided, and is ignored; no attribute
    is added to the adapter.

    For example, if a Migen platform file contains the definitions ::

        _io = [
            ("i2c", 0,
                Subsignal("scl", Pins("39")),
                Subsignal("sda", Pins("40")),
            ),
            # ...
        ]

    then a pad adapter constructed as ``Pads(platform.request("i2c"))`` will have
    attributes ``scl_t`` and ``sda_t`` containing tristate triples for their respective
    pins.

    If a Glasgow applet contains the code ::

        port = target.get_port(args.port)
        pads = Pads(tx=port[args.pin_tx], rx=port[args.pin_rx])
        target.submodules += pads

    then the pad adapter ``pads`` will have attributes ``tx_t`` and ``rx_t`` containing
    tristate triples for their respective pins; since Glasgow I/O ports return tristate
    triples when slicing, the results of slicing are unchanged.
    """
    def __init__(self, *args, **kwargs):
        for (i, elem) in enumerate(args):
            self._add_elem(elem, index=i)
        for name, elem in kwargs.items():
            self._add_elem(elem, name)

    def _add_elem(self, elem, name=None, index=None):
        if elem is None:
            return
        elif isinstance(elem, Record):
            for field in elem.layout:
                if name is None:
                    field_name = field[0]
                else:
                    field_name = "{}_{}".format(name, field[0])
                self._add_elem(getattr(elem, field[0]), field_name)
            return
        elif isinstance(elem, Signal):
            triple = TSTriple()
            self.specials += triple.get_tristate(elem)

            if name is None:
                name = elem.backtrace[-1][0]
        elif isinstance(elem, TSTriple):
            triple = elem

        if name is None and index is None:
            raise ValueError("Name must be provided for {!r}".format(elem))
        elif name is None:
            raise ValueError("Name must be provided for {!r} (argument {})"
                             .format(elem, index + 1))

        triple_name = "{}_t".format(name)
        if hasattr(self, triple_name):
            raise ValueError("Cannot add {!r} as attribute {}; attribute already exists")

        setattr(self, triple_name, triple)
