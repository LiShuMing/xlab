lucky :: (Integral a) => a -> String
lucky 7 = "Lucky number seven!"
lucky x = "Sorry, you're out of luck, pal!"

main :: IO ()
main = putStrLn "Hello, Haskell!"