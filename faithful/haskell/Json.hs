module Json where

import Text.Parsec
import Text.Parsec.String (Parser)
import Numeric (showHex)
import Data.Char (chr, ord)
import Data.List (intercalate)

data J = Obj [(String,J)] | Arr [J] | Str String | Num Double | Boolean Bool | Null deriving (Eq,Show)

parseJSON :: String -> Either String J
parseJSON s = either (Left . show) Right (parse (spaces *> value <* eof) "json" s)
  where
    lexeme p = p <* spaces
    stringP = char '"' *> many character <* char '"'
    character = noneOf "\"\\" <|> (char '\\' *> escaped)
    escaped = choice [char '"' >> pure '"', char '\\' >> pure '\\', char '/' >> pure '/', char 'b' >> pure '\b', char 'f' >> pure '\f', char 'n' >> pure '\n', char 'r' >> pure '\r', char 't' >> pure '\t', char 'u' *> (chr . foldl (\a c -> 16*a + digit c) 0 <$> count 4 hexDigit)]
    digit c | c >= '0' && c <= '9' = ord c - ord '0'
            | otherwise = ord (if c >= 'a' then c else chr (ord c+32)) - ord 'a' + 10
    value :: Parser J
    value = lexeme $ choice
      [ Obj <$> between (char '{' *> spaces) (char '}') (pair `sepBy` lexeme (char ','))
      , Arr <$> between (char '[' *> spaces) (char ']') (value `sepBy` lexeme (char ','))
      , Str <$> stringP
      , string "true" >> pure (Boolean True), string "false" >> pure (Boolean False), string "null" >> pure Null
      , Num . read <$> ((++) <$> option "" (string "-") <*> ((++) <$> many1 digitChar <*> ((++) <$> option "" ((:) <$> char '.' <*> many1 digitChar) <*> option "" ((:) <$> oneOf "eE" <*> ((++) <$> option "" ((:[]) <$> oneOf "+-") <*> many1 digitChar))))) ]
    digitChar = oneOf "0123456789"
    pair = (,) <$> lexeme stringP <* lexeme (char ':') <*> value

render :: J -> String
render (Obj xs) = "{" ++ intercalate "," [quote k ++ ":" ++ render v | (k,v)<-xs] ++ "}"
render (Arr xs) = "[" ++ intercalate "," (map render xs) ++ "]"
render (Str s) = quote s
render (Num x) | isInfinite x || isNaN x = "null"
               | x == fromInteger (round x) = show (round x :: Integer)
               | otherwise = show x
render (Boolean b) = if b then "true" else "false"
render Null = "null"
quote s = '"' : concatMap esc s ++ "\"" where
  esc '"' = "\\\""
  esc '\\' = "\\\\"
  esc c | ord c < 32 = "\\u" ++ replicate (4-length h) '0' ++ h where h=showHex (ord c) ""
  esc c = [c]
field k (Obj xs) = maybe Null id (lookup k xs)
field _ _ = Null
str (Str s) = s
str x = error ("Expected string: " ++ show x)
num (Num n) = n
num x = error ("Expected number: " ++ show x)
arr (Arr xs) = xs
arr Null = []
arr x = error ("Expected array: " ++ show x)
integer :: J -> Int
integer = round . num
fallback d Null = d
fallback _ v = v
