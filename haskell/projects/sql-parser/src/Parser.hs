{-# LANGUAGE LambdaCase #-}
{-# LANGUAGE OverloadedStrings #-}

{- |
Module      : Parser
Description : Megaparsec-based SQL Parser

This module implements a pure, combinator-based SQL parser using Megaparsec.

Design Philosophy:
- **Pure Functions**: The parser is a pure function from 'Text' to 'Either ParseError AST'.
  No side effects, no IO, making it trivially testable and composable.
- **Composability**: Small parsers are combined to build larger ones. This mirrors
  the recursive structure of SQL grammar itself.
- **Clear Error Messages**: Megaparsec provides detailed parse errors with source
  locations, crucial for user-facing tools.
-}
module Parser
    ( parseSQL
    , module Text.Megaparsec
    ) where

import Control.Monad.Combinators (sepBy1, optional)
import Data.Text (Text)
import qualified Data.Text as T
import qualified Data.List.NonEmpty as NE
import Data.Void (Void)
import Text.Megaparsec
import Text.Megaparsec.Char
import qualified Text.Megaparsec.Char.Lexer as L
import Control.Applicative ((<$>), (<|>), (*>), (<*), (<$))
import Data.Functor (($>))

import AST

-- | Custom error type for SQL parsing.
-- Currently we use Megaparsec's default, but this allows future extension.
type Parser = Parsec Void Text

-- | Top-level parser: raw SQL string to AST.
-- 
-- This is the public API for parsing. It's a pure function that returns
-- either a parse error or a valid Statement. The purity guarantees that
-- the same input always produces the same output.
parseSQL :: Text -> Either (ParseErrorBundle Text Void) Statement
parseSQL = parse (statement <* eof) ""

-- | Parse a complete SQL statement.
statement :: Parser Statement
statement = do
    stmt <- selectStmt
    optional $ char ';'  -- Optional trailing semicolon
    pure stmt

-- | Parse a SELECT statement.
selectStmt :: Parser Statement
selectStmt = StmtSelect <$> selectStmt'

selectStmt' :: Parser SelectStmt
selectStmt' = do
    _ <- keyword "SELECT"
    items <- selectList
    from <- optional fromClause
    where_ <- optional whereClause
    pure SelectStmt
        { ssSelect = items
        , ssFrom   = from
        , ssWhere  = where_
        }

-- | Parse the SELECT projection list.
-- At least one item is required; multiple items are comma-separated.
selectList :: Parser (NE.NonEmpty SelectItem)
selectList = do
    first <- selectItem
    rest <- many (char ',' *> skipSpace *> selectItem)
    pure $ NE.fromList (first : rest)

-- | Parse a single SELECT item (expression or *).
selectItem :: Parser SelectItem
selectItem = skipSpace *> (
    (char '*' $> SelectAll <* skipSpace) <|>
    (SelectExpr <$> (expr <* skipSpace) <*> optional alias)
    )
  where
    alias :: Parser Text
    alias = skipSpace *> (keyword "AS" *> identifier <|> identifier)

-- | Parse the FROM clause.
fromClause :: Parser FromClause
fromClause = do
    _ <- keyword "FROM"
    first <- skipSpace *> tableRef
    rest <- many (char ',' *> skipSpace *> tableRef)
    skipSpace
    pure $ FromClause $ NE.fromList (first : rest)

-- | Parse a table reference.
tableRef :: Parser TableRef
tableRef = TableRef <$> identifier

-- | Parse the WHERE clause.
whereClause :: Parser WhereClause
whereClause = WhereClause <$> (keyword "WHERE" *> skipSpace *> expr)

-- | Parse an expression.
-- Expressions are built from terms combined with OR operators.
expr :: Parser Expr
expr = orExpr `chainl` orOp

-- | Parse OR expressions.
orExpr :: Parser Expr
orExpr = andExpr `chainl` andOp

andExpr :: Parser Expr
andExpr = comparisonExpr `chainl` comparisonOp

comparisonExpr :: Parser Expr
comparisonExpr = addExpr `chainl` comparisonOp

addExpr :: Parser Expr
addExpr = mulExpr `chainl` addOp

mulExpr :: Parser Expr
mulExpr = term `chainl` mulOp

-- | Helper: chainl for zero or more left-associative operators.
-- This is like chainl1 but allows a single term without operators.
chainl :: Parser a -> Parser (a -> a -> a) -> Parser a
chainl p op = do
    x <- p
    xs <- many (try (do
        f <- op
        y <- p
        pure (f, y)
        ))
    pure $ foldl (\acc (f, y) -> f acc y) x xs

-- | Parse OR operator.
orOp :: Parser (Expr -> Expr -> Expr)
orOp = keyword "OR" $> EBin OpOr

-- | Parse AND operator.
andOp :: Parser (Expr -> Expr -> Expr)
andOp = keyword "AND" $> EBin OpAnd

-- | Parse comparison operators (=, <>, <, <=, >, >=).
comparisonOp :: Parser (Expr -> Expr -> Expr)
comparisonOp = do
    op <- choice
        [ string "<>" $> OpNe
        , string "<=" $> OpLe
        , string ">=" $> OpGe
        , char '=' $> OpEq
        , char '<' $> OpLt
        , char '>' $> OpGt
        ]
    skipSpace
    pure $ EBin op

-- | Parse additive operator (+, -).
addOp :: Parser (Expr -> Expr -> Expr)
addOp = do
    op <- char '+' $> OpAdd <|> char '-' $> OpSub
    skipSpace
    pure $ EBin op

-- | Parse multiplicative operator (*, /).
mulOp :: Parser (Expr -> Expr -> Expr)
mulOp = try $ do
    op <- char '*' $> OpMul <|> char '/' $> OpDiv
    skipSpace
    pure $ EBin op

-- | Parse a term: literal, column reference, function call, or parenthesized expr.
term :: Parser Expr
term = choice
    [ ELit <$> literal
    , try (EFunc <$> identifier <* char '(' <*> (expr `sepBy` char ',') <* char ')')
    , ECol <$> columnRef
    , between (char '(') (char ')') expr
    ]
  where
    expr `sepBy` sep = sepBy1 expr (skipSpace *> sep <* skipSpace)

-- | Parse a literal value (integer, string, boolean, NULL).
literal :: Parser Literal
literal = choice
    [ LitBool True  <$ keyword "TRUE"
    , LitBool False <$ keyword "FALSE"
    , LitNull       <$ keyword "NULL"
    , LitString     <$> stringLiteral
    , LitInt        <$> L.decimal
    ]

-- | Parse a column reference (optionally qualified: table.column).
columnRef :: Parser ColumnRef
columnRef = do
    first <- identifier
    second <- optional (char '.' *> identifier)
    pure $ case second of
        Just col -> ColumnRef (Just first) col
        Nothing  -> ColumnRef Nothing first

-- | Parse a string literal (single-quoted).
stringLiteral :: Parser Text
stringLiteral = between (char '\'') (char '\'') $ T.concat <$> many stringChar
  where
    stringChar = T.singleton <$> escapedChar <|> T.singleton <$> satisfy (/= '\'')
    escapedChar = char '\\' *> anySingle

-- | Parse an identifier (unquoted name).
identifier :: Parser Text
identifier = lexeme ident <?> "identifier"
  where
    ident = do
        first <- startChar
        rest <- many letterChar
        pure $ T.pack (first : rest)
    startChar = letterChar <|> char '_'

-- | Parse a reserved keyword (case-insensitive).
keyword :: Text -> Parser Text
keyword = L.symbol skipSpace

-- | Helper: lexeme that trims trailing whitespace.
lexeme :: Parser a -> Parser a
lexeme = L.lexeme skipSpace

-- | Skip whitespace and comments.
skipSpace :: Parser ()
skipSpace = L.space space1 lineComment blockComment
  where
    lineComment  = L.skipLineComment "--"
    blockComment = L.skipBlockComment "/*" "*/"

-- | Helper: chainl1 for left-associative operator parsing.
-- This is a standard combinator for expression parsing.
chainl1 :: Parser a -> Parser (a -> a -> a) -> Parser a
chainl1 p op = scan
  where
    scan = do
        x <- p
        rest x
      where
        rest x = do
            f <- op
            y <- p
            rest (f x y)
                <|> pure x
