from collections import namedtuple, defaultdict
from migen import *
from migen.fhdl.structure import _Value, _Statement
from migen.genlib.fsm import _LowerNext, FSM


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


class _ProtocolFSM(FSM):
    def _lower_controls(self):
        return _LowerMemory(self.next_state, self.encoding, self.state_aliases)

    def _finalize_sync(self, ls):
        super()._finalize_sync(ls)
        for memory, next_value_ce, next_value in ls.memories:
            self.sync += If(next_value_ce, memory.eq(next_value))


_Rule = namedtuple("_Rule", ("name", "cond", "succ", "action"))


class _ProtocolEngine(Module):
    def __init__(self, symbol_size, word_size, reset_rule):
        self._symbol_size = symbol_size
        self._word_size   = word_size
        self._reset_rule  = reset_rule
        # name -> [(cond, succ, action)]
        self._grammar = defaultdict(lambda: [])

    def rule(self, name, succ, cond=lambda *_: True, action=lambda symbol: []):
        self._grammar[name].append(_Rule(name, cond, succ, action))

    def _get_rule_tuples(self, rule_name, rule_tuples, rule_path=()):
        if len(rule_path) == self._word_size:
            rule_tuples.add(rule_path)
            return

        for rule in self._grammar[rule_name]:
            self._get_rule_tuples(rule.succ, rule_tuples, rule_path + (rule,))
