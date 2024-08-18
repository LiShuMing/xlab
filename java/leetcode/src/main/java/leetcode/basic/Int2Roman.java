package leetcode.basic;

/**
 * @author : lishuming
 */
public class Int2Roman {
    public String solution(int i) {
        String I[] = {"", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "VIIII"};
        String X[] = {"", "X", "XX", "XXX", "XXXX", "L", "LX", "LXX", "LXXX", "LXXXX"};
        return X[i / 10] + I[i % 10];
    }
}
