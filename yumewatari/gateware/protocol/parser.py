import os
from migen import *

from .engine import _ProtocolFSM, _ProtocolEngine


_DEBUG = os.getenv("DEBUG_PARSER")


class Parser(_ProtocolEngine):
    def __init__(self, symbol_size, word_size, reset_rule, layout=None):
        super().__init__(symbol_size, word_size, reset_rule)

        self.reset = Signal()
        self.error = Signal()
        self.i     = Signal(symbol_size * word_size)

        ###

        self._i = [self.i.part(n * symbol_size, symbol_size) for n in range(word_size)]
        if layout is not None:
            for n in range(word_size):
                irec = Record(layout)
                self.comb += irec.raw_bits().eq(self._i[n])
                self._i[n] = irec

    def do_finalize(self):
        self.submodules.fsm = ResetInserter()(_ProtocolFSM())
        self.comb += self.fsm.reset.eq(self.reset | self.error)

        if _DEBUG:
            print("Parser layout:")
        worklist  = {self._reset_rule}
        processed = set()
        while worklist:
            rule_name = worklist.pop()
            processed.add(rule_name)

            if _DEBUG:
                print("  State %s" % rule_name)

            rule_tuples = set()
            self._get_rule_tuples(rule_name, rule_tuples)

            actions = []
            for i, rule_tuple in enumerate(rule_tuples):
                if _DEBUG:
                    print("    Input #%d %s -> %s" %
                          (i, rule_name, " -> ".join(rule.succ for rule in rule_tuple)))

                succ = rule_tuple[-1].succ
                action = [
                    self.error.eq(0),
                    NextState(succ)
                ]
                for j, rule in enumerate(reversed(rule_tuple)):
                    symbol = self._i[self._word_size - j - 1]
                    action = [
                        If(rule.cond(symbol),
                            rule.action(symbol),
                            *action
                        ),
                    ]

                actions.append(action)
                if succ not in processed:
                    worklist.add(succ)

            self.fsm.act(rule_name, [
                self.error.eq(1),
                *actions
            ])
