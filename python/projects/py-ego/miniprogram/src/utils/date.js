export function todayLabel() {
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
}

export function currentMonth() {
  const today = new Date();
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
}

export function greeting() {
  const hour = new Date().getHours();
  if (hour < 11) {
    return "早上好，今天先记录一个小片段。";
  }
  if (hour < 18) {
    return "下午好，把脑中的线索落下来。";
  }
  return "晚上好，今天想记录什么？";
}
