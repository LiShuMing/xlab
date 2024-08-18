# 'primary' color corresponds to primary_hue in theme.py
# 'secondary' color corresponds to neutral_hue in theme.py
# 'stop' color corresponds to color_er in theme.py
import importlib
from toolbox import clear_line_break
from toolbox import apply_gpt_academic_string_mask_langbased
from toolbox import build_gpt_academic_masked_string_langbased
from textwrap import dedent

def get_core_functions():
    return {

        "Academic Polish": {
            # [1*] Prefix string prepended to the user input.
            #      Uses language-detection to build the right prompt for English vs Chinese input.
            "Prefix": build_gpt_academic_masked_string_langbased(
                text_show_english=
                    r"Below is a paragraph from an academic paper. Polish the writing to meet the academic style, "
                    r"improve the spelling, grammar, clarity, concision and overall readability. When necessary, rewrite the whole sentence. "
                    r"Firstly, you should provide the polished paragraph (in English). "
                    r"Secondly, you should list all your modification and explain the reasons to do so in markdown table.",
                text_show_chinese=
                    r"作为一名中文学术论文写作改进助理，你的任务是改进所提供文本的拼写、语法、清晰、简洁和整体可读性，"
                    r"同时分解长句，减少重复，并提供改进建议。请先提供文本的更正版本，然后在markdown表格中列出修改的内容，并给出修改的理由:"
            ) + "\n\n",
            # [2*] Suffix string appended to the user input.
            "Suffix": r"",
            # [3] Button color (optional, default: secondary)
            "Color": r"secondary",
            # [4] Whether the button is visible (optional, default: True)
            "Visible": True,
            # [5] Whether to clear history on trigger (optional, default: False)
            "AutoClearHistory": False,
            # [6] Pre-processing function applied to input (optional, default: None)
            "PreProcess": None,
        },


        "Summarize as Mind Map": {
            "Prefix": '"""\n\n',
            "Suffix": dedent("\n\n" + r'''
                    """

                    Summarize the above text using a mermaid flowchart that captures the main ideas
                    and their logical relationships. Example format:

                    ```mermaid
                    flowchart LR
                        A["Node 1"] --> B("Node 2")
                        B --> C{"Node 3"}
                        C --> D["Node 4"]
                        C --> |"edge label"| E["Node 5"]
                    ```

                    Notes:
                    (1) Use the same language as the source text
                    (2) Wrap node labels in quotes, e.g. ["Laptop"]
                    (3) No spaces between `|` and `"`
                    (4) Choose flowchart LR (left-to-right) or TD (top-down) as appropriate
                '''),
        },


        "Grammar Check": {
            "Prefix":
                r"Help me ensure that the grammar and the spelling is correct. "
                r"Do not try to polish the text, if no mistake is found, tell me that this paragraph is good. "
                r"If you find grammar or spelling mistakes, please list mistakes you find in a two-column markdown table, "
                r"put the original text the first column, "
                r"put the corrected text in the second column and highlight the key words you fixed. "
                r"Finally, please provide the proofreaded text." "\n\n"
                r"Example:" "\n"
                r"Paragraph: How is you? Do you knows what is it?" "\n"
                r"| Original sentence | Corrected sentence |" "\n"
                r"| :--- | :--- |" "\n"
                r"| How **is** you? | How **are** you? |" "\n"
                r"| Do you **knows** what **is** **it**? | Do you **know** what **it** **is** ? |" "\n\n"
                r"Below is a paragraph from an academic paper. "
                r"You need to report all grammar and spelling mistakes as the example before."
                + "\n\n",
            "Suffix": r"",
            "PreProcess": clear_line_break,
        },


        "Chinese to English": {
            "Prefix": r"Please translate following sentence to English:" + "\n\n",
            "Suffix": r"",
        },


        "Academic EN<->ZH Translation": {
            "Prefix": build_gpt_academic_masked_string_langbased(
                text_show_chinese=
                    r"I want you to act as a scientific English-Chinese translator, "
                    r"I will provide you with some paragraphs in one language "
                    r"and your task is to accurately and academically translate the paragraphs only into the other language. "
                    r"Do not repeat the original provided paragraphs after translation. "
                    r"You should use artificial intelligence tools, "
                    r"such as natural language processing, and rhetorical knowledge "
                    r"and experience about effective writing techniques to reply. "
                    r"I'll give you my paragraphs as follows, tell me what language it is written in, and then translate:",
                text_show_english=
                    r"你是经验丰富的翻译，请把以下学术文章段落翻译成中文，"
                    r"并同时充分考虑中文的语法、清晰、简洁和整体可读性，"
                    r"必要时，你可以修改整个句子的顺序以确保翻译后的段落符合中文的语言习惯。"
                    r"你需要翻译的文本如下："
            ) + "\n\n",
            "Suffix": r"",
        },


        "English to Chinese": {
            "Prefix": r"翻译成地道的中文：" + "\n\n",
            "Suffix": r"",
            "Visible": False,
        },


        "Find Image": {
            "Prefix":
                r"Find an image from the web. Use the Unsplash API "
                r"(https://source.unsplash.com/960x640/?<English-keywords>) to get the image URL, "
                r"then embed it using Markdown format without backslashes or code blocks. "
                r"Now send me an image matching this description:" + "\n\n",
            "Suffix": r"",
            "Visible": False,
        },


        "Explain Code": {
            "Prefix": r"Please explain the following code:" + "\n```\n",
            "Suffix": "\n```\n",
        },


        "References to BibTeX": {
            "Prefix":
                r"Here are some bibliography items, please transform them into bibtex style."
                r"Note that, reference styles maybe more than one kind, you should transform each item correctly."
                r"Items need to be transformed:" + "\n\n",
            "Visible": False,
            "Suffix": r"",
        },
    }


def handle_core_functionality(additional_fn, inputs, history, chatbot):
    import core_functional
    importlib.reload(core_functional)    # Hot-reload prompt definitions
    core_functional = core_functional.get_core_functions()
    addition = chatbot._cookies['customize_fn_overwrite']
    if additional_fn in addition:
        # Custom user-defined function
        inputs = addition[additional_fn]["Prefix"] + inputs + addition[additional_fn]["Suffix"]
        return inputs, history
    else:
        # Built-in function
        if "PreProcess" in core_functional[additional_fn]:
            if core_functional[additional_fn]["PreProcess"] is not None:
                inputs = core_functional[additional_fn]["PreProcess"](inputs)
        inputs = apply_gpt_academic_string_mask_langbased(
            string=core_functional[additional_fn]["Prefix"] + inputs + core_functional[additional_fn]["Suffix"],
            lang_reference=inputs,
        )
        if core_functional[additional_fn].get("AutoClearHistory", False):
            history = []
        return inputs, history


if __name__ == "__main__":
    t = get_core_functions()["Summarize as Mind Map"]
    print(t["Prefix"] + t["Suffix"])
