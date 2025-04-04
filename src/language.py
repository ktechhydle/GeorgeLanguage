from src.nodes import NumberNode, BinaryOperatorNode, UnaryOperatorNode
from src.errors import IllegalCharError, InvalidSyntaxError

DIGITS = '0123456789'
TT_INT = 'INT'
TT_FLOAT = 'FLOAT'
TT_PLUS = 'PLUS'
TT_MINUS = 'MINUS'
TT_MUL = 'MUL'
TT_DIV = 'DIV'
TT_LPAREN = 'LPAREN'
TT_RPAREN = 'RPAREN'
TT_EOF = 'EOF'


class Token:
    def __init__(self, type, value=None, pos_start=None, pos_end=None):
        self.type = type
        self.value = value

        if pos_start:
            self.pos_start = pos_start.copy()
            self.pos_end = pos_start.copy()
            self.pos_end.advance()

        if pos_end:
            self.pos_end = pos_end

    def __repr__(self):
        if self.value:
            return f'{self.type}:{self.value}'

        return f'{self.type}'


class Position:
    def __init__(self, index: int, line_num: int, column_num: int, file_name: str, file_text: str):
        self.index = index
        self.line_num = line_num
        self.column_num = column_num
        self.file_name = file_name
        self.file_text = file_text

    def advance(self, current_char=None):
        self.index += 1
        self.column_num += 1

        if current_char == '\n':
            self.line_num += 1
            self.column_num = 0

        return self

    def copy(self):
        return Position(self.index, self.line_num, self.column_num, self.file_name, self.file_text)


class Lexer:
    def __init__(self, file_name: str, text: str):
        self.file_name = file_name
        self.text = text
        self.pos = Position(-1, 0, -1, file_name, text)
        self.current_char = None

        self.advance()

    def advance(self):
        self.pos.advance(self.current_char)
        self.current_char = self.text[self.pos.index] if self.pos.index < len(self.text) else None

    def makeTokens(self) -> tuple[list, None]:
        tokens = []

        while self.current_char is not None:
            if self.current_char in ' \t':
                self.advance()

            elif self.current_char in DIGITS:
                tokens.append(self.makeNumber())

            elif self.current_char == '+':
                tokens.append(Token(TT_PLUS, pos_start=self.pos))
                self.advance()

            elif self.current_char == '-':
                tokens.append(Token(TT_MINUS, pos_start=self.pos))
                self.advance()

            elif self.current_char == '*':
                tokens.append(Token(TT_MUL, pos_start=self.pos))
                self.advance()

            elif self.current_char == '/':
                tokens.append(Token(TT_DIV, pos_start=self.pos))
                self.advance()

            elif self.current_char == '(':
                tokens.append(Token(TT_LPAREN, pos_start=self.pos))
                self.advance()

            elif self.current_char == ')':
                tokens.append(Token(TT_RPAREN, pos_start=self.pos))
                self.advance()

            else:
                pos_start = self.pos.copy()
                char = self.current_char
                self.advance()
                return [], IllegalCharError(pos_start, self.pos, f'"{char}" is not defined')

        tokens.append(Token(TT_EOF, pos_start=self.pos))
        return tokens, None

    def makeNumber(self) -> Token:
        num_str = ''
        dot_count = 0
        pos_start = self.pos.copy()

        while self.current_char is not None and self.current_char in DIGITS + '.':
            if self.current_char == '.':
                if dot_count == 1:
                    break

                dot_count += 1
                num_str += '.'

            else:
                num_str += self.current_char

            self.advance()

        if dot_count == 0:
            return Token(TT_INT, int(num_str), pos_start, self.pos)

        else:
            return Token(TT_FLOAT, float(num_str), pos_start, self.pos)


class ParseResult:
    def __init__(self):
        self.error = None
        self.node = None

    def register(self, result):
        if isinstance(result, ParseResult):
            if result.error:
                self.error = result.error

            return result.node

        return result

    def success(self, node):
        self.node = node
        return self

    def failure(self, error):
        self.error = error
        return self


class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.token_index = -1

        self.advance()

    def advance(self):
        self.token_index += 1

        if self.token_index < len(self.tokens):
            self.current_token = self.tokens[self.token_index]

        return self.current_token

    def parse(self):
        result = self.expr()

        if not result.error and self.current_token.type is not TT_EOF:
            return result.failure(InvalidSyntaxError(
                self.current_token.pos_start, self.current_token.pos_end,
                'Expected operators "+", "-", "*" or "/"'
            ))

        return result

    def factor(self) -> ParseResult:
        result = ParseResult()
        token = self.current_token

        if token.type in (TT_PLUS, TT_MINUS):
            result.register(self.advance())
            factor = result.register(self.factor())

            if result.error:
                return result

            return result.success(UnaryOperatorNode(token, factor))

        elif token.type in (TT_INT, TT_FLOAT):
            result.register(self.advance())
            return result.success(NumberNode(token))

        elif token.type in (TT_LPAREN, TT_RPAREN):
            result.register(self.advance())
            expr = result.register(self.expr())

            if result.error:
                return result

            if self.current_token.type == TT_RPAREN:
                result.register(self.advance())
                return result.success(expr)

            else:
                return result.failure(InvalidSyntaxError(
                    self.current_token.pos_start, self.current_token.pos_end,
                    'Expected ")"'
                ))

        return result.failure(InvalidSyntaxError(
            token.pos_start, token.pos_end, 'Expected type int or float'
        ))

    def term(self):
        return self.binaryOperator(self.factor, (TT_MUL, TT_DIV))

    def expr(self):
        return self.binaryOperator(self.term, (TT_PLUS, TT_MINUS))

    def binaryOperator(self, func, op_tokens):
        result = ParseResult()
        left = result.register(func())

        if result.error:
            return result

        while self.current_token.type in op_tokens:
            op_token = self.current_token
            result.register(self.advance())
            right = result.register(func())

            if result.error:
                return result

            left = BinaryOperatorNode(left, op_token, right)

        return result.success(left)


def run(file_name: str, text: str):
    lexer = Lexer(file_name, text)
    tokens, error = lexer.makeTokens()

    if error:
        return None, error

    parser = Parser(tokens)
    ast = parser.parse()

    return ast.node, ast.error