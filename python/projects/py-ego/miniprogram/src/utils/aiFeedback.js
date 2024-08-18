function pickSignal(text) {
  if (/(累|疲惫|焦虑|压力|难受|崩|烦|失眠)/.test(text)) {
    return {
      kind: "tired",
      response: "你刚才记录里有明显的消耗感。先不用急着解释原因，可以把身体状态、触发事件、最想被理解的一句话分开看。",
    };
  }

  if (/(开心|顺利|完成|不错|喜欢|高兴|期待)/.test(text)) {
    return {
      kind: "positive",
      response: "这条记录里有一点能量回升的迹象。建议把这个时刻具体化：是什么让它变好、你做对了什么、下次能不能复用。",
    };
  }

  if (/(会议|项目|方案|工作|代码|问题|排查)/.test(text)) {
    return {
      kind: "work",
      response: "这更像一条工作线索。可以继续补两点：当前卡点是什么，以及下一步最小动作是什么。这样它会更容易进入长期记忆。",
    };
  }

  return {
    kind: "open",
    response: "我读到的是一个还没有完全展开的片段。它不需要马上变成结论，先保留现场感就够了。",
  };
}

function therapistResponse(signal) {
  const responses = {
    tired:
      "我先接住这一点：你现在的累不是小题大做，它像是身体和注意力都在提醒你，今天已经撑过不少东西了。可以先不用急着把它分析清楚，也不用马上变得积极。我们可以慢一点，把这份疲惫放在桌面上看：它来自事情本身，还是来自你一直在逼自己保持稳定？如果愿意，先给自己一个很小的缓冲，比如喝水、站起来活动一下，或者只是承认一句“我今天确实不容易”。",
    positive:
      "我能感觉到这条记录里有一点亮起来的地方。它不一定要很大，但它值得被认真保存。你可以稍微停一下，看看这份顺利或开心里，哪些是外部发生的好事，哪些是你自己做出的努力。很多时候，人会很快跳到下一个任务，却忘了把这种微小的确定感收回来。今天这部分，是可以被你带走的。",
    work:
      "我听到的是一种很真实的工作消耗：你在处理问题，也在努力把混乱变得可理解。先肯定一下，这种排查、定位、推进，本身就需要很多耐心。现在不必马上把所有事都安排好，可以先问自己：这件事里最耗你的部分是什么？是问题本身，还是反复不确定带来的紧绷？把这两者分开，你会更容易恢复一点掌控感。",
    open:
      "我在这里。这个片段现在可能还没有完整形状，但它已经足够被记录了。有些感受一开始不会直接说出自己的名字，只会以一句话、一个画面、一个隐约的念头出现。你可以不用急着解释它，我们先陪它待一会儿。等你愿意的时候，再慢慢看看它真正指向哪里。",
  };

  return responses[signal.kind] || responses.open;
}

export function generateRecordFeedback(text, roleId = "therapist") {
  const trimmed = text.trim();
  const summary = trimmed.length > 42 ? `${trimmed.slice(0, 42)}...` : trimmed;
  const signal = pickSignal(trimmed);
  const response = roleId === "therapist" ? therapistResponse(signal) : signal.response;

  return {
    summary: summary || "空白记录",
    response,
    prompts: [
      roleId === "therapist" ? "此刻最需要被理解的那一部分是什么？" : "这件事对你最重要的部分是什么？",
      roleId === "therapist" ? "如果不要求自己马上解决，你会想先照顾哪一点？" : "如果给今天的自己一句反馈，会是什么？",
      roleId === "therapist" ? "有没有一个很小、很温和的下一步？" : "下一步有一个很小的动作吗？",
    ],
  };
}

export function generateChatReply(text, roleId = "therapist") {
  const feedback = generateRecordFeedback(text, roleId);

  if (roleId === "researcher") {
    return `我先把它拆成一个可研究的问题：${feedback.summary}\n\n初步判断：${feedback.response}\n\n你可以补充变量、证据和反例，我会继续帮你收束。`;
  }

  return `${feedback.response}\n\n如果你愿意，我们可以不用急着找答案，先从一个很小的问题开始：${feedback.prompts[0]}`;
}
