import os
from migen import *

from .engine import _ProtocolFSM, _ProtocolEngine


_DEBUG = os.getenv("DEBUG_EMITTER")


class Emitter(_ProtocolEngine):
    def __init__(self, symbol_size, word_size, reset_rule, layout=None):
        super().__init__(symbol_size, word_size, reset_rule)

        self.o = Signal(symbol_size * word_size)

        ###

        self._o = [Signal(symbol_size) for n in range(word_size)]
        self.comb += self.o.eq(Cat(self._o))
        if layout is not None:
            for n in range(word_size):
                irec = Record(layout)
                self.comb += self._o[n].eq(irec.raw_bits())
                self._o[n] = irec

    def do_finalize(self):
        self.submodules.fsm = _ProtocolFSM()

        if _DEBUG:
            print("Emitter layout:")
        worklist  = {self._reset_rule}
        processed = set()
        while worklist:
            rule_name = worklist.pop()
            processed.add(rule_name)

            if _DEBUG:
                print("  State %s" % rule_name)

            rule_tuples = set()
            self._get_rule_tuples(rule_name, rule_tuples)

            conds   = []
            actions = []
            for i, rule_tuple in enumerate(rule_tuples):
                if _DEBUG:
                    print("    Output #%d %s -> %s" %
                          (i, rule_name, " -> ".join(rule.succ for rule in rule_tuple)))

                succ = rule_tuple[-1].succ
                action = [NextState(succ)]
                for j, rule in enumerate(reversed(rule_tuple)):
                    symbol = self._o[self._word_size - j - 1]
                    action = [
                        If(rule.cond(),
                            rule.action(symbol),
                            *action
                        ),
                    ]

                actions.append(action)
                if succ not in processed:
                    worklist.add(succ)

            self.fsm.act(rule_name, actions)
