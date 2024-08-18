package leetcode;

/**
 * @author shuming.lsm
 * @version 2019/12/14
 */
public class _013 {
    public int romanToInt(String s) {
        if (s == null) return 0;

        int i = 0, len = s.length(), r = 0;
        while (i < len) {
            switch (s.charAt(i)) {
                case 'I':
                    if (i + 1 < len && (s.charAt(i + 1) == 'V' || s.charAt(i + 1) == 'X')) {
                        if (s.charAt(i + 1) == 'V') {
                            r += 4;
                        } else {
                            r += 9;
                        }
                        i += 2;
                        continue;
                    }
                    r += 1;
                    i += 1;
                    break;
                case 'V':
                    r += 5;
                    i += 1;
                    break;
                case 'X':
                    if (i + 1 < len && (s.charAt(i + 1) == 'L' || s.charAt(i + 1) == 'C')) {
                        if (s.charAt(i + 1) == 'L') {
                            r += 40;
                        } else {
                            r += 90;
                        }
                        i += 2;
                        continue;
                    }
                    r += 10;
                    i += 1;
                    break;
                case 'L':
                    r += 50;
                    i += 1;
                    break;
                case 'C':
                    if (i + 1 < len && (s.charAt(i + 1) == 'D' || s.charAt(i + 1) == 'M')) {
                        if (s.charAt(i + 1) == 'D') {
                            r += 400;
                        } else {
                            r += 900;
                        }
                        i += 2;
                        continue;
                    }
                    r += 100;
                    i += 1;
                    break;
                case 'D':
                    r += 500;
                    i += 1;
                    break;
                case 'M':
                    r += 1000;
                    i += 1;
                    break;
                default:
                    i+=1;
                    break;
            }
        }
        return r;
    }

    public static void main(String[] args) {
        int r = new _013().romanToInt("DCXXI");
        System.out.println(r);
    }
}
