from collections import defaultdict, namedtuple
from migen import *
from migen.fhdl.structure import _Value, _Statement
from migen.genlib.fsm import _LowerNext, FSM


__all__ = ["Parser", "Memory", "NextMemory"]


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
            next_value    = Signal.like(memory)
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


_Rule = namedtuple("_Rule", ("cond", "succ", "action"))


class Parser(Module):
    def __init__(self, symbol_width, reset_rule):
        self.reset = Signal()
        self.error = Signal()
        self.i     = Signal(symbol_width)

        ###

        self._reset_rule = reset_rule
        # name -> [(cond, succ, action)]
        self._grammar = defaultdict(lambda: [])

    def rule(self, name, cond, succ, action=lambda symbol: []):
        self._grammar[name].append(_Rule(cond, succ, action))

    def do_finalize(self):
        self.submodules.fsm = ResetInserter()(_ParserFSM(reset_state=self._reset_rule))
        self.comb += self.fsm.reset.eq(self.reset | self.error)

        for (name, rules) in self._grammar.items():
            conds = Cat(rule.cond(self.i) for rule in rules)
            self.fsm.act(name, [
                self.error.eq(1),
                Case(conds, {
                    (1 << n): [
                        NextState(rule.succ),
                        *rule.action(self.i),
                        self.error.eq(0),
                    ]
                    for n, rule in enumerate(rules)
                })
            ])
