from src.tokens_and_keywords import *
from src.context import Context
from src.runtime_result import RuntimeResult
from src.symbol_table import SymbolTable
from src.nodes import NumberNode, VariableAccessNode, VariableAssignNode, BinaryOperatorNode, UnaryOperatorNode, \
    StringNode
from src.errors import RunTimeError


class Interpreter:
    def visit(self, node, context):
        method_name = f'visit_{type(node).__name__}'
        method = getattr(self, method_name, self.noVisitMethod)

        return method(node, context)

    def noVisitMethod(self, node, context):
        raise Exception(f'No visit_{type(node).__name__} method defined')

    def visit_NumberNode(self, node: NumberNode, context):
        return RuntimeResult().success(
            Number(node.token.value).setContext(context).setPos(node.pos_start, node.pos_end))

    def visit_StringNode(self, node: StringNode, context):
        return RuntimeResult().success(String(node.token.value).setContext(context).setPos(node.pos_start, node.pos_end))

    def visit_VariableAccessNode(self, node: VariableAccessNode, context):
        result = RuntimeResult()
        var_name = node.var_name_token.value
        value = context.symbol_table.get(var_name)

        if not value:
            return result.failure(
                RunTimeError(node.pos_start,
                             node.pos_end,
                             f'"{var_name}" is not defined',
                             context))

        value = value.copy().setPos(node.pos_start, node.pos_end)
        return result.success(value)

    def visit_VariableAssignNode(self, node: VariableAssignNode, context):
        result = RuntimeResult()
        var_name = node.var_name_token.value
        value = result.register(self.visit(node.value_node, context))

        if result.error:
            return result

        context.symbol_table.set(var_name, value)
        return result.success(value)

    def visit_BinaryOperatorNode(self, node: BinaryOperatorNode, context):
        result = RuntimeResult()
        left = result.register(self.visit(node.left_node, context))

        if result.error:
            return result

        right = result.register(self.visit(node.right_node, context))

        if result.error:
            return result

        if node.op_token.type == TT_PLUS:
            number, error = left.addedTo(right)
        elif node.op_token.type == TT_MINUS:
            number, error = left.subtractedBy(right)
        elif node.op_token.type == TT_MUL:
            number, error = left.multipliedBy(right)
        elif node.op_token.type == TT_DIV:
            number, error = left.dividedBy(right)
        elif node.op_token.type == TT_POW:
            number, error = left.poweredBy(right)
        elif node.op_token.type == TT_EE:
            number, error = left.getComparisonEq(right)
        elif node.op_token.type == TT_NE:
            number, error = left.getComparisonNe(right)
        elif node.op_token.type == TT_LT:
            number, error = left.getComparisonLt(right)
        elif node.op_token.type == TT_GT:
            number, error = left.getComparisonGt(right)
        elif node.op_token.type == TT_LTE:
            number, error = left.getComparisonLte(right)
        elif node.op_token.type == TT_GTE:
            number, error = left.getComparisonGte(right)
        elif node.op_token.matches(TT_KEYWORD, 'and'):
            number, error = left.andedBy(right)
        elif node.op_token.matches(TT_KEYWORD, 'or'):
            number, error = left.oredBy(right)

        if error:
            return result.failure(error)

        else:
            return result.success(number.setPos(node.pos_start, node.pos_end))

    def visit_UnaryOperatorNode(self, node: UnaryOperatorNode, context):
        result = RuntimeResult()
        number = result.register(self.visit(node.node, context))

        if result.error:
            return result

        error = None

        if node.op_token.type == TT_MINUS:
            number, error = number.multipliedBy(Number(-1))

        elif node.op_token.matches(TT_KEYWORD, 'oppositeof'):
            number, error = number.notted()

        if error:
            return result.failure(error)

        else:
            return result.success(number.setPos(node.pos_start, node.pos_end))

    def visit_IfNode(self, node, context):
        result = RuntimeResult()

        for condition, expr in node.cases:
            condition_value = result.register(self.visit(condition, context))

            if result.error:
                return result

            if condition_value.isTrue():
                expr_value = result.register(self.visit(expr, context))

                if result.error:
                    return result

                return result.success(expr_value)

        if node.else_case:
            else_value = result.register(self.visit(node.else_case, context))

            if result.error:
                return result

            return result.success(else_value)

        return result.success(None)

    def visit_ForNode(self, node, context):
        result = RuntimeResult()

        start_value = result.register(self.visit(node.start_value_node, context))

        if result.error:
            return result

        end_value = result.register(self.visit(node.end_value_node, context))

        if result.error:
            return result

        if node.step_value_node:
            step_value = result.register(self.visit(node.step_value_node, context))

            if result.error:
                return result

        else:
            step_value = Number(1)

        i = start_value.value

        if step_value.value >= 0:
            condition = lambda: i < end_value.value

        else:
            condition = lambda: i > end_value.value

        while condition():
            context.symbol_table.set(node.var_name_token.value, Number(i))
            i += step_value.value

            result.register(self.visit(node.body_node, context))

            if result.error:
                return result

        return result.success(None)

    def visit_WhileNode(self, node, context):
        result = RuntimeResult()

        while True:
            condition = result.register(self.visit(node.condition_node, context))

            if result.error:
                return result

            if not condition.isTrue():
                break

            result.register(self.visit(node.body_node, context))

            if result.error:
                return result

        return result.success(None)

    def visit_FunctionDefinitionNode(self, node, context):
        result = RuntimeResult()

        func_name = node.var_name_token.value if node.var_name_token else None
        body_node = node.body_node
        arg_names = [arg_name.value for arg_name in node.arg_name_tokens]
        func_value = Function(func_name, body_node, arg_names).setContext(context).setPos(node.pos_start,
                                                                                            node.pos_end)

        if node.var_name_token:
            context.symbol_table.set(func_name, func_value)

        return result.success(func_value)

    def visit_CallNode(self, node, context):
        result = RuntimeResult()
        args = []

        value_to_call = result.register(self.visit(node.node_to_call, context))

        if result.error:
            return result

        value_to_call = value_to_call.copy().setPos(node.pos_start, node.pos_end)

        for arg_node in node.arg_nodes:
            args.append(result.register(self.visit(arg_node, context)))

            if result.error:
                return result

        return_value = result.register(value_to_call.execute(args))

        if result.error:
            return result

        return result.success(return_value)


class Value:
    def __init__(self):
        self.setPos()
        self.setContext()

    def setPos(self, pos_start=None, pos_end=None):
        self.pos_start = pos_start
        self.pos_end = pos_end
        return self

    def setContext(self, context=None):
        self.context = context
        return self

    def addedTo(self, other):
        return None, self.illegalOperation(other)

    def subtractedBy(self, other):
        return None, self.illegalOperation(other)

    def multipliedBy(self, other):
        return None, self.illegalOperation(other)

    def dividedBy(self, other):
        return None, self.illegalOperation(other)

    def poweredBy(self, other):
        return None, self.illegalOperation(other)

    def getComparisonEq(self, other):
        return None, self.illegalOperation(other)

    def getComparisonNe(self, other):
        return None, self.illegalOperation(other)

    def getComparisonLt(self, other):
        return None, self.illegalOperation(other)

    def getComparisonGt(self, other):
        return None, self.illegalOperation(other)

    def getComparisonLte(self, other):
        return None, self.illegalOperation(other)

    def getComparisonGte(self, other):
        return None, self.illegalOperation(other)

    def andedBy(self, other):
        return None, self.illegalOperation(other)

    def oredBy(self, other):
        return None, self.illegalOperation(other)

    def notted(self):
        return None, self.illegalOperation()

    def copy(self):
        raise Exception('No copy method defined')

    def isTrue(self):
        return False

    def execute(self, args):
        return RuntimeResult().failure(self.illegalOperation())

    def illegalOperation(self, other=None):
        if not other:
            other = self

        return RunTimeError(
            self.pos_start, other.pos_end,
            'Illegal operation',
            self.context
        )


class Number(Value):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def addedTo(self, other):
        if isinstance(other, Number):
            return Number(self.value + other.value).setContext(self.context), None

        else:
            return None, Value.illegalOperation(self, other)

    def subtractedBy(self, other):
        if isinstance(other, Number):
            return Number(self.value - other.value).setContext(self.context), None

        else:
            return None, Value.illegalOperation(self, other)

    def multipliedBy(self, other):
        if isinstance(other, Number):
            return Number(self.value * other.value).setContext(self.context), None

        else:
            return None, Value.illegalOperation(self, other)

    def dividedBy(self, other):
        if isinstance(other, Number):
            if other.value == 0:
                return None, RunTimeError(
                    other.pos_start, other.pos_end, 'Division by zero',
                    self.context
                )

            return Number(self.value / other.value).setContext(self.context), None

        else:
            return None, Value.illegalOperation(self, other)

    def poweredBy(self, other):
        if isinstance(other, Number):
            return Number(self.value ** other.value).setContext(self.context), None

        else:
            return None, Value.illegalOperation(self, other)

    def getComparisonEq(self, other):
        if isinstance(other, Number):
            return Number(int(self.value == other.value)).setContext(self.context), None

        else:
            return None, Value.illegalOperation(self, other)

    def getComparisonNe(self, other):
        if isinstance(other, Number):
            return Number(int(self.value != other.value)).setContext(self.context), None

        else:
            return None, Value.illegalOperation(self, other)

    def getComparisonLt(self, other):
        if isinstance(other, Number):
            return Number(int(self.value < other.value)).setContext(self.context), None

        else:
            return None, Value.illegalOperation(self, other)

    def getComparisonGt(self, other):
        if isinstance(other, Number):
            return Number(int(self.value > other.value)).setContext(self.context), None

        else:
            return None, Value.illegalOperation(self, other)

    def getComparisonLte(self, other):
        if isinstance(other, Number):
            return Number(int(self.value <= other.value)).setContext(self.context), None

        else:
            return None, Value.illegalOperation(self, other)

    def getComparisonGte(self, other):
        if isinstance(other, Number):
            return Number(int(self.value >= other.value)).setContext(self.context), None

        else:
            return None, Value.illegalOperation(self, other)

    def andedBy(self, other):
        if isinstance(other, Number):
            return Number(int(self.value and other.value)).setContext(self.context), None

        else:
            return None, Value.illegalOperation(self, other)

    def oredBy(self, other):
        if isinstance(other, Number):
            return Number(int(self.value or other.value)).setContext(self.context), None

        else:
            return None, Value.illegalOperation(self, other)

    def notted(self):
        return Number(1 if self.value == 0 else 0).setContext(self.context), None

    def copy(self):
        copy = Number(self.value)
        copy.setPos(self.pos_start, self.pos_end)
        copy.setContext(self.context)
        return copy

    def isTrue(self):
        return self.value != 0

    def __repr__(self):
        return f'<number: {self.value}>'


class String(Value):
    def __init__(self, value):
        super().__init__()
        self.value = value

    def addedTo(self, other):
        if isinstance(other, String):
            return String(self.value + other.value).setContext(self.context), None

        else:
            return None, Value.illegalOperation(self, other)

    def multipliedBy(self, other):
        if isinstance(other, Number):
            return String(self.value * other.value).setContext(self.context), None

        else:
            return None, Value.illegalOperation(self, other)

    def subtractedBy(self, other):
        if isinstance(other, String):
            return String(other.value).setContext(self.context), None

        else:
            return None, Value.illegalOperation(self, other)

    def isTrue(self):
        return len(self.value) > 0

    def copy(self):
        copy = String(self.value)
        copy.setPos(self.pos_start, self.pos_end)
        copy.setContext(self.context)
        return copy

    def __repr__(self):
        return f'<string: {self.value}>'


class Function(Value):
    def __init__(self, name, body_node, arg_names):
        super().__init__()
        self.name = name or '<anonymous>'
        self.body_node = body_node
        self.arg_names = arg_names

    def execute(self, args):
        result = RuntimeResult()
        interpreter = Interpreter()
        new_context = Context(self.name, self.context, self.pos_start)
        new_context.symbol_table = SymbolTable(new_context.parent.symbol_table)

        if len(args) > len(self.arg_names) or len(args) < len(self.arg_names):
            return result.failure(RunTimeError(
                self.pos_start, self.pos_end,
                f'{self.name} takes {len(self.arg_names)} positional argument(s) but the program gave {len(args)}',
                self.context
            ))

        for i in range(len(args)):
            arg_name = self.arg_names[i]
            arg_value = args[i]
            arg_value.setContext(new_context)
            new_context.symbol_table.set(arg_name, arg_value)

        value = result.register(interpreter.visit(self.body_node, new_context))

        if result.error:
            return result

        return result.success(value)

    def copy(self):
        copy = Function(self.name, self.body_node, self.arg_names)
        copy.setPos(self.pos_start, self.pos_end)
        copy.setContext(self.context)
        return copy

    def __repr__(self):
        return f'<function: {self.name}>'
