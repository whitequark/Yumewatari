import os
from collections import defaultdict, namedtuple
from migen import *
from migen.fhdl.structure import _Value, _Statement
from migen.genlib.fsm import _LowerNext, FSM


__all__ = ["Parser", "Memory", "NextMemory"]


_DEBUG = os.getenv("DEBUG_PARSER")


class Memory(_Value):
    def __init__(self, target):
        self.target = target


class NextMemory(_Statement):
    def __init__(self, target, value):
        self.target = target
        self.value  = value


class _LowerMemory(_LowerNext):
    def __init__(self, *args):
        super().__init__(*args)
        # (target, next_value_ce, next_value)
        self.memories = []

    def _get_memory_control(self, memory):
        for target, next_value_ce, next_value in self.memories:
            if target is memory:
                break
        else:
            next_value_ce = Signal(related=memory)
            next_value    = Signal(memory.nbits, related=memory)
            self.memories.append((memory, next_value_ce, next_value))
        return next_value_ce, next_value

    def visit_unknown(self, node):
        if isinstance(node, Memory):
            next_value_ce, next_value = self._get_memory_control(node.target)
            return Mux(next_value_ce, next_value, node.target)
        elif isinstance(node, NextMemory):
            next_value_ce, next_value = self._get_memory_control(node.target)
            return next_value_ce.eq(1), next_value.eq(node.value)
        else:
            return super().visit_unknown(node)


class _ParserFSM(FSM):
    def _lower_controls(self):
        return _LowerMemory(self.next_state, self.encoding, self.state_aliases)

    def _finalize_sync(self, ls):
        super()._finalize_sync(ls)
        for memory, next_value_ce, next_value in ls.memories:
            self.sync += If(next_value_ce, memory.eq(next_value))


_Rule = namedtuple("_Rule", ("name", "cond", "succ", "action"))


class Parser(Module):
    def __init__(self, symbol_size, word_size, reset_rule):
        self.reset = Signal()
        self.error = Signal()
        self.i     = Signal(symbol_size * word_size)

        ###

        self._symbol_size = symbol_size
        self._word_size   = word_size
        self._reset_rule  = reset_rule
        # name -> [(cond, succ, action)]
        self._grammar = defaultdict(lambda: [])

    def rule(self, name, cond, succ, action=lambda symbol: []):
        self._grammar[name].append(_Rule(name, cond, succ, action))

    def _get_rule_tuples(self, rule_name, rule_tuples, rule_path=()):
        if len(rule_path) == self._word_size:
            rule_tuples.add(rule_path)
            return

        for rule in self._grammar[rule_name]:
            self._get_rule_tuples(rule.succ, rule_tuples, rule_path + (rule,))

    def do_finalize(self):
        self.submodules.fsm = ResetInserter()(_ParserFSM())
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

            conds   = []
            actions = []
            for i, rule_tuple in enumerate(rule_tuples):
                if _DEBUG:
                    print("    Input #%d %s -> %s" %
                          (i, rule_name, " -> ".join(rule.succ for rule in rule_tuple)))

                succ = rule_tuple[-1].succ
                cond   = 1
                action = [
                    self.error.eq(0),
                    NextState(succ)
                ]
                for j, rule in enumerate(reversed(rule_tuple)):
                    symbol = self.i.part((self._word_size - j - 1) * self._symbol_size,
                                         self._symbol_size)
                    action = [
                        If(rule.cond(symbol),
                            rule.action(symbol),
                            *action
                        ),
                    ]

                conds.append(cond)
                actions.append(action)
                if succ not in processed:
                    worklist.add(succ)

            self.fsm.act(rule_name, [
                self.error.eq(1),
                *actions
            ])
