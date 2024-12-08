object Main {
  def main(args: Array[String]): Unit = {
    val arr = Array(1, 2, 3, 4)
    arr.filter { p =>
     if (p % 2 == 0) {
       true
     } else {
       false
     }
    }. foreach(println(_))
  }
}