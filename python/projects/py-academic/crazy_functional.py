from toolbox import HotReload  # HotReload enables live plugin reloading without restart
from toolbox import trimmed_format_exc
from loguru import logger

def get_crazy_functions():
    from crazy_functions.Paper_Abstract_Writer import Paper_Abstract_Writer
    from crazy_functions.Program_Comment_Gen import 批量Program_Comment_Gen
    from crazy_functions.SourceCode_Analyse import 解析项目本身
    from crazy_functions.SourceCode_Analyse import 解析一个Python项目
    from crazy_functions.SourceCode_Analyse import 解析一个Matlab项目
    from crazy_functions.SourceCode_Analyse import 解析一个C项目的头文件
    from crazy_functions.SourceCode_Analyse import 解析一个C项目
    from crazy_functions.SourceCode_Analyse import 解析一个Golang项目
    from crazy_functions.SourceCode_Analyse import 解析一个Rust项目
    from crazy_functions.SourceCode_Analyse import 解析一个Java项目
    from crazy_functions.SourceCode_Analyse import 解析一个前端项目
    from crazy_functions.高级功能函数模板 import 高阶功能模板函数
    from crazy_functions.高级功能函数模板 import Demo_Wrap
    from crazy_functions.Latex_Project_Polish import Latex英文润色
    from crazy_functions.Multi_LLM_Query import 同时问询
    from crazy_functions.SourceCode_Analyse import 解析一个Lua项目
    from crazy_functions.SourceCode_Analyse import 解析一个CSharp项目
    from crazy_functions.Word_Summary import Word_Summary
    from crazy_functions.SourceCode_Analyse_JupyterNotebook import 解析ipynb文件
    from crazy_functions.Conversation_To_File import 载入对话历史存档
    from crazy_functions.Conversation_To_File import 对话历史存档
    from crazy_functions.Conversation_To_File import Conversation_To_File_Wrap
    from crazy_functions.Conversation_To_File import 删除所有本地对话历史记录
    from crazy_functions.Helpers import 清除缓存
    from crazy_functions.Markdown_Translate import Markdown英译中
    from crazy_functions.PDF_Summary import PDF_Summary
    from crazy_functions.PDF_Translate import 批量翻译PDF文档
    from crazy_functions.Google_Scholar_Assistant_Legacy import Google_Scholar_Assistant_Legacy
    from crazy_functions.PDF_QA import PDF_QA标准文件输入
    from crazy_functions.Latex_Project_Polish import Latex中文润色
    from crazy_functions.Latex_Project_Polish import Latex英文纠错
    from crazy_functions.Markdown_Translate import Markdown中译英
    from crazy_functions.Void_Terminal import Void_Terminal
    from crazy_functions.Mermaid_Figure_Gen import Mermaid_Gen
    from crazy_functions.PDF_Translate_Wrap import PDF_Tran
    from crazy_functions.Latex_Function import Latex英文纠错加PDF对比
    from crazy_functions.Latex_Function import Latex翻译中文并重新编译PDF
    from crazy_functions.Latex_Function import PDF翻译中文并重新编译PDF
    from crazy_functions.Latex_Function_Wrap import Arxiv_Localize
    from crazy_functions.Latex_Function_Wrap import PDF_Localize
    from crazy_functions.Internet_GPT import 连接网络回答问题
    from crazy_functions.Internet_GPT_Wrap import NetworkGPT_Wrap
    from crazy_functions.Image_Generate import 图片生成_DALLE2, 图片生成_DALLE3, 图片修改_DALLE2
    from crazy_functions.Image_Generate_Wrap import ImageGen_Wrap
    from crazy_functions.SourceCode_Comment import 注释Python项目
    from crazy_functions.SourceCode_Comment_Wrap import SourceCodeComment_Wrap
    from crazy_functions.VideoResource_GPT import 多媒体任务
    from crazy_functions.Document_Conversation import 批量文件询问
    from crazy_functions.Document_Conversation_Wrap import Document_Conversation_Wrap


    function_plugins = {
        "Multimedia Agent": {
            "Group": "agent",
            "Color": "stop",
            "AsButton": False,
            "Info": "[Test only] Multimedia task agent",
            "Function": HotReload(多媒体任务),
        },
        "Void Terminal": {
            "Group": "chat|coding|academic|agent",
            "Color": "stop",
            "AsButton": True,
            "Info": "Describe your idea in natural language and let the terminal handle it",
            "Function": HotReload(Void_Terminal),
        },
        "Analyse Python Project": {
            "Group": "coding",
            "Color": "stop",
            "AsButton": True,
            "Info": "Analyse all source files (.py) in a Python project | Input: project path",
            "Function": HotReload(解析一个Python项目),
        },
        "Add Docstrings to Python Project": {
            "Group": "coding",
            "Color": "stop",
            "AsButton": False,
            "Info": "Upload Python source files (or zip), add docstrings to all functions | Input: path",
            "Function": HotReload(注释Python项目),
            "Class": SourceCodeComment_Wrap,
        },
        "Load Conversation Archive (upload or enter path)": {
            "Group": "chat",
            "Color": "stop",
            "AsButton": False,
            "Info": "Load a saved conversation archive | Input: file path",
            "Function": HotReload(载入对话历史存档),
        },
        "Delete All Local Conversation History (caution)": {
            "Group": "chat",
            "AsButton": False,
            "Info": "Delete all local conversation history files (irreversible) | No input required",
            "Function": HotReload(删除所有本地对话历史记录),
        },
        "Clear All Cache Files (caution)": {
            "Group": "chat",
            "Color": "stop",
            "AsButton": False,
            "Info": "Clear all cache files (irreversible) | No input required",
            "Function": HotReload(清除缓存),
        },
        "Generate Mermaid Diagrams (from conversation or file)": {
            "Group": "chat",
            "Color": "stop",
            "AsButton": False,
            "Info": "Generate multiple Mermaid diagram types from the current conversation or a file (.pdf/.md/.docx)",
            "Function": None,
            "Class": Mermaid_Gen,
        },
        "Translate ArXiv Paper": {
            "Group": "academic",
            "Color": "stop",
            "AsButton": True,
            "Info": "Precisely translate an ArXiv paper | Input: ArXiv paper ID, e.g. 1812.10695",
            "Function": HotReload(Latex翻译中文并重新编译PDF),
            "Class": Arxiv_Localize,
        },
        "Summarise Word Documents (batch)": {
            "Group": "academic",
            "Color": "stop",
            "AsButton": False,
            "Info": "Batch summarise Word documents | Input: directory path",
            "Function": HotReload(Word_Summary),
        },
        "Analyse Matlab Project": {
            "Group": "coding",
            "Color": "stop",
            "AsButton": False,
            "Info": "Analyse all source files (.m) in a Matlab project | Input: project path",
            "Function": HotReload(解析一个Matlab项目),
        },
        "Analyse C++ Project Headers": {
            "Group": "coding",
            "Color": "stop",
            "AsButton": False,
            "Info": "Analyse all header files (.h/.hpp) in a C++ project | Input: project path",
            "Function": HotReload(解析一个C项目的头文件),
        },
        "Analyse C++ Project": {
            "Group": "coding",
            "Color": "stop",
            "AsButton": False,
            "Info": "Analyse all source files (.cpp/.hpp/.c/.h) in a C++ project | Input: project path",
            "Function": HotReload(解析一个C项目),
        },
        "Analyse Go Project": {
            "Group": "coding",
            "Color": "stop",
            "AsButton": False,
            "Info": "Analyse all source files in a Go project | Input: project path",
            "Function": HotReload(解析一个Golang项目),
        },
        "Analyse Rust Project": {
            "Group": "coding",
            "Color": "stop",
            "AsButton": False,
            "Info": "Analyse all source files in a Rust project | Input: project path",
            "Function": HotReload(解析一个Rust项目),
        },
        "Analyse Java Project": {
            "Group": "coding",
            "Color": "stop",
            "AsButton": False,
            "Info": "Analyse all source files in a Java project | Input: project path",
            "Function": HotReload(解析一个Java项目),
        },
        "Analyse Frontend Project (js/ts/css)": {
            "Group": "coding",
            "Color": "stop",
            "AsButton": False,
            "Info": "Analyse all frontend source files (js, ts, css, etc.) | Input: project path",
            "Function": HotReload(解析一个前端项目),
        },
        "Analyse Lua Project": {
            "Group": "coding",
            "Color": "stop",
            "AsButton": False,
            "Info": "Analyse all source files in a Lua project | Input: project path",
            "Function": HotReload(解析一个Lua项目),
        },
        "Analyse CSharp Project": {
            "Group": "coding",
            "Color": "stop",
            "AsButton": False,
            "Info": "Analyse all source files in a CSharp project | Input: project path",
            "Function": HotReload(解析一个CSharp项目),
        },
        "Analyse Jupyter Notebook": {
            "Group": "coding",
            "Color": "stop",
            "AsButton": False,
            "Info": "Analyse a Jupyter Notebook file | Input: file path",
            "Function": HotReload(解析ipynb文件),
            "AdvancedArgs": True,
            "ArgsReminder": "Enter 0 to skip Markdown cells in the notebook",
        },
        "Write Abstract from LaTeX Paper": {
            "Group": "academic",
            "Color": "stop",
            "AsButton": False,
            "Info": "Read a LaTeX paper and write an abstract | Input: project path",
            "Function": HotReload(Paper_Abstract_Writer),
        },
        "Translate README / Markdown": {
            "Group": "coding",
            "Color": "stop",
            "AsButton": True,
            "Info": "Translate a Markdown file to Chinese | Input: file path or URL",
            "Function": HotReload(Markdown英译中),
        },
        "Translate Markdown (GitHub link supported)": {
            "Group": "coding",
            "Color": "stop",
            "AsButton": False,
            "Info": "Translate a Markdown/README to Chinese | Input: file path or URL",
            "Function": HotReload(Markdown英译中),
        },
        "Generate Function Comments (batch)": {
            "Group": "coding",
            "Color": "stop",
            "AsButton": False,
            "Info": "Generate function-level comments in batch | Input: project path",
            "Function": HotReload(批量Program_Comment_Gen),
        },
        "Save Current Conversation": {
            "Group": "chat",
            "Color": "stop",
            "AsButton": True,
            "Info": "Save the current conversation to a file | No input required",
            "Function": HotReload(对话历史存档),
            "Class": Conversation_To_File_Wrap,
        },
        "[Multi-thread Demo] Analyse This Project (self-analysis)": {
            "Group": "chat|coding",
            "Color": "stop",
            "AsButton": False,
            "Info": "Multi-threaded analysis and translation of this project's source code | No input required",
            "Function": HotReload(解析项目本身),
        },
        "Web Search then Answer": {
            "Group": "chat",
            "Color": "stop",
            "AsButton": True,
            "Function": HotReload(连接网络回答问题),
            "Class": NetworkGPT_Wrap,
        },
        "Today in History": {
            "Group": "chat",
            "Color": "stop",
            "AsButton": False,
            "Info": "Show what happened today in history (developer demo plugin) | No input required",
            "Function": None,
            "Class": Demo_Wrap,
        },
        "Translate PDF Paper": {
            "Group": "academic",
            "Color": "stop",
            "AsButton": True,
            "Info": "Precisely translate a PDF paper | Input: file path",
            "Function": HotReload(批量翻译PDF文档),
            "Class": PDF_Tran,
        },
        "Query Multiple LLM Models": {
            "Group": "chat",
            "Color": "stop",
            "AsButton": True,
            "Function": HotReload(同时问询),
        },
        "Summarise PDF Documents (batch)": {
            "Group": "academic",
            "Color": "stop",
            "AsButton": False,
            "Info": "Batch summarise PDF documents | Input: directory path",
            "Function": HotReload(PDF_Summary),
        },
        "Google Scholar Assistant (enter search page URL)": {
            "Group": "academic",
            "Color": "stop",
            "AsButton": False,
            "Info": "Search Google Scholar results at a given URL | Input: Google Scholar search URL",
            "Function": HotReload(Google_Scholar_Assistant_Legacy),
        },
        "Chat with PDF Document (ChatPDF style)": {
            "Group": "academic",
            "Color": "stop",
            "AsButton": False,
            "Info": "Understand and answer questions about a PDF | Input: file path",
            "Function": HotReload(PDF_QA标准文件输入),
        },
        "Polish English LaTeX Project": {
            "Group": "academic",
            "Color": "stop",
            "AsButton": False,
            "Info": "Polish the full text of an English LaTeX project | Input: path or zip upload",
            "Function": HotReload(Latex英文润色),
        },
        "Polish Chinese LaTeX Project": {
            "Group": "academic",
            "Color": "stop",
            "AsButton": False,
            "Info": "Polish the full text of a Chinese LaTeX project | Input: path or zip upload",
            "Function": HotReload(Latex中文润色),
        },
        "Translate Markdown ZH→EN (batch)": {
            "Group": "coding",
            "Color": "stop",
            "AsButton": False,
            "Info": "Batch translate Markdown files from Chinese to English | Input: path or zip upload",
            "Function": HotReload(Markdown中译英),
        },
        "LaTeX English Proofreading + Diff Highlight [requires LaTeX]": {
            "Group": "academic",
            "Color": "stop",
            "AsButton": False,
            "AdvancedArgs": True,
            "ArgsReminder": "Optionally add more detailed correction instructions here (in English).",
            "Function": HotReload(Latex英文纠错加PDF对比),
        },
        "📚 Precise ArXiv Paper Translation (enter arXiv ID) [requires LaTeX]": {
            "Group": "academic",
            "Color": "stop",
            "AsButton": False,
            "AdvancedArgs": True,
            "ArgsReminder":
                r"Optionally provide custom translation instructions to fix specific term translations. "
                r'Example: If "agent" is mistranslated, paste: '
                r'If the term "agent" is used in this section, it should be translated to "智能体".',
            "Info": "Precisely translate an ArXiv paper | Input: arXiv paper ID, e.g. 1812.10695",
            "Function": HotReload(Latex翻译中文并重新编译PDF),
            "Class": Arxiv_Localize,
        },
        "📚 Translate Local LaTeX Paper (upload zip) [requires LaTeX]": {
            "Group": "academic",
            "Color": "stop",
            "AsButton": False,
            "AdvancedArgs": True,
            "ArgsReminder":
                r"Optionally provide custom translation instructions to fix specific term translations. "
                r'Example: If "agent" is mistranslated, paste: '
                r'If the term "agent" is used in this section, it should be translated to "智能体".',
            "Info": "Precisely translate a local LaTeX paper | Input: project path",
            "Function": HotReload(Latex翻译中文并重新编译PDF),
        },
        "Translate PDF and Recompile (upload PDF) [requires LaTeX]": {
            "Group": "academic",
            "Color": "stop",
            "AsButton": False,
            "AdvancedArgs": True,
            "ArgsReminder":
                r"Optionally provide custom translation instructions to fix specific term translations. "
                r'Example: If "agent" is mistranslated, paste: '
                r'If the term "agent" is used in this section, it should be translated to "智能体".',
            "Info": "Translate PDF to Chinese and recompile | Input: file path",
            "Function": HotReload(PDF翻译中文并重新编译PDF),
            "Class": PDF_Localize,
        },
        "Batch Document Q&A (supports various file types)": {
            "Group": "academic",
            "Color": "stop",
            "AsButton": False,
            "AdvancedArgs": False,
            "Info": "Upload files then click this button to ask questions about them",
            "Function": HotReload(批量文件询问),
            "Class": Document_Conversation_Wrap,
        },
    }

    function_plugins.update(
        {
            "🎨 Image Generation (DALLE2/DALLE3, switch to GPT model first)": {
                "Group": "chat",
                "Color": "stop",
                "AsButton": False,
                "Info": "Generate images using DALLE2/DALLE3 | Input: image description",
                "Function": HotReload(图片生成_DALLE2),
                "Class": ImageGen_Wrap,
            },
        }
    )

    function_plugins.update(
        {
            "🎨 Edit Image with DALLE2 (switch to GPT model first)": {
                "Group": "chat",
                "Color": "stop",
                "AsButton": False,
                "Function": HotReload(图片修改_DALLE2),
            },
        }
    )

    try:
        from crazy_functions.Arxiv_Downloader import 下载arxiv论文并翻译摘要

        function_plugins.update(
            {
                "Download ArXiv Paper and Translate Abstract (enter ID, e.g. 1812.10695)": {
                    "Group": "academic",
                    "Color": "stop",
                    "AsButton": False,
                    "Function": HotReload(下载arxiv论文并翻译摘要),
                }
            }
        )
    except:
        logger.error(trimmed_format_exc())
        logger.error("Load function plugin failed")

    try:
        from crazy_functions.SourceCode_Analyse import 解析任意code项目

        function_plugins.update(
            {
                "Analyse Project (custom file type filter)": {
                    "Group": "coding",
                    "Color": "stop",
                    "AsButton": False,
                    "AdvancedArgs": True,
                    "ArgsReminder":
                        'Comma-separated globs; * is a wildcard; prefix ^ to exclude. '
                        'Leave empty to match all. Example: "*.c, ^*.cpp, config.toml, ^*.toml"',
                    "Function": HotReload(解析任意code项目),
                },
            }
        )
    except:
        logger.error(trimmed_format_exc())
        logger.error("Load function plugin failed")

    try:
        from crazy_functions.Multi_LLM_Query import 同时问询_指定模型

        function_plugins.update(
            {
                "Query Multiple LLM Models (specify models manually)": {
                    "Group": "chat",
                    "Color": "stop",
                    "AsButton": False,
                    "AdvancedArgs": True,
                    "ArgsReminder": "Any number of LLM interfaces separated by &. Example: gpt-3.5-turbo&gpt-4",
                    "Function": HotReload(同时问询_指定模型),
                },
            }
        )
    except:
        logger.error(trimmed_format_exc())
        logger.error("Load function plugin failed")

    try:
        from crazy_functions.Audio_Summary import Audio_Summary

        function_plugins.update(
            {
                "Summarise Audio / Video (batch)": {
                    "Group": "chat",
                    "Color": "stop",
                    "AsButton": False,
                    "AdvancedArgs": True,
                    "ArgsReminder":
                        "Uses OpenAI Whisper-1. Supported formats: mp4, m4a, wav, mpga, mpeg, mp3. "
                        "Optionally enter a transcription hint here.",
                    "Info": "Batch summarise audio or video files | Input: directory path",
                    "Function": HotReload(Audio_Summary),
                }
            }
        )
    except:
        logger.error(trimmed_format_exc())
        logger.error("Load function plugin failed")

    try:
        from crazy_functions.Math_Animation_Gen import 动画生成

        function_plugins.update(
            {
                "Math Animation Generator (Manim)": {
                    "Group": "chat",
                    "Color": "stop",
                    "AsButton": False,
                    "Info": "Generate an animation from a natural language description | Input: description text",
                    "Function": HotReload(动画生成),
                }
            }
        )
    except:
        logger.error(trimmed_format_exc())
        logger.error("Load function plugin failed")

    try:
        from crazy_functions.Markdown_Translate import Markdown翻译指定语言

        function_plugins.update(
            {
                "Translate Markdown (specify target language)": {
                    "Group": "coding",
                    "Color": "stop",
                    "AsButton": False,
                    "AdvancedArgs": True,
                    "ArgsReminder": "Enter the target language. Default: Chinese.",
                    "Function": HotReload(Markdown翻译指定语言),
                }
            }
        )
    except:
        logger.error(trimmed_format_exc())
        logger.error("Load function plugin failed")

    try:
        from crazy_functions.Vectorstore_QA import 知识库文件注入

        function_plugins.update(
            {
                "Build Knowledge Base (upload files first, then run)": {
                    "Group": "chat",
                    "Color": "stop",
                    "AsButton": False,
                    "AdvancedArgs": True,
                    "ArgsReminder":
                        "Knowledge base ID (default: 'default'). "
                        "Files are stored persistently. Run again to append more documents.",
                    "Function": HotReload(知识库文件注入),
                }
            }
        )
    except:
        logger.error(trimmed_format_exc())
        logger.error("Load function plugin failed")

    try:
        from crazy_functions.Vectorstore_QA import 读取知识库作答

        function_plugins.update(
            {
                "Query Knowledge Base (build it first, then run)": {
                    "Group": "chat",
                    "Color": "stop",
                    "AsButton": False,
                    "AdvancedArgs": True,
                    "ArgsReminder":
                        "Knowledge base ID to query (default: 'default'). "
                        "You must build the knowledge base before querying it.",
                    "Function": HotReload(读取知识库作答),
                }
            }
        )
    except:
        logger.error(trimmed_format_exc())
        logger.error("Load function plugin failed")

    try:
        from toolbox import get_conf

        ENABLE_AUDIO = get_conf("ENABLE_AUDIO")
        if ENABLE_AUDIO:
            from crazy_functions.Audio_Assistant import Audio_Assistant

            function_plugins.update(
                {
                    "Real-time Voice Chat": {
                        "Group": "chat",
                        "Color": "stop",
                        "AsButton": True,
                        "Info": "A voice conversation assistant that listens in real-time | No input required",
                        "Function": HotReload(Audio_Assistant),
                    }
                }
            )
    except:
        logger.error(trimmed_format_exc())
        logger.error("Load function plugin failed")

    try:
        from crazy_functions.PDF_Translate_Nougat import 批量翻译PDF文档

        function_plugins.update(
            {
                "Translate PDF Document (NOUGAT)": {
                    "Group": "academic",
                    "Color": "stop",
                    "AsButton": False,
                    "Function": HotReload(批量翻译PDF文档),
                }
            }
        )
    except:
        logger.error(trimmed_format_exc())
        logger.error("Load function plugin failed")

    try:
        from crazy_functions.Dynamic_Function_Generate import Dynamic_Function_Generate

        function_plugins.update(
            {
                "Dynamic Code Interpreter (CodeInterpreter)": {
                    "Group": "agent",
                    "Color": "stop",
                    "AsButton": False,
                    "Function": HotReload(Dynamic_Function_Generate),
                }
            }
        )
    except:
        logger.error(trimmed_format_exc())
        logger.error("Load function plugin failed")

    try:
        from crazy_functions.Rag_Interface import Rag问答

        function_plugins.update(
            {
                "RAG Smart Recall": {
                    "Group": "chat",
                    "Color": "stop",
                    "AsButton": False,
                    "Info": "Record Q&A data into a vector store for long-term reference.",
                    "Function": HotReload(Rag问答),
                },
            }
        )
    except:
        logger.error(trimmed_format_exc())
        logger.error("Load function plugin failed")

    try:
        from crazy_functions.Paper_Reading import 快速论文解读
        function_plugins.update(
            {
                "Quick Paper Reading": {
                    "Group": "academic",
                    "Color": "stop",
                    "AsButton": False,
                    "Info": "Upload a paper for fast analysis and reading | Input: paper path or DOI/arXiv ID",
                    "Function": HotReload(快速论文解读),
                },
            }
        )
    except:
        logger.error(trimmed_format_exc())
        logger.error("Load function plugin failed")

    # Apply defaults:
    # - Default Group  = "chat"
    # - Default AsButton = True
    # - Default AdvancedArgs = False
    # - Default Color = "secondary"
    for name, function_meta in function_plugins.items():
        if "Group" not in function_meta:
            function_plugins[name]["Group"] = "chat"
        if "AsButton" not in function_meta:
            function_plugins[name]["AsButton"] = True
        if "AdvancedArgs" not in function_meta:
            function_plugins[name]["AdvancedArgs"] = False
        if "Color" not in function_meta:
            function_plugins[name]["Color"] = "secondary"

    return function_plugins


def get_multiplex_button_functions():
    """Mapping for the multi-mode main submit button."""
    return {
        "Regular Chat":
            "",

        "Web Search then Answer":
            "Web Search then Answer",

        "Multi-model Chat":
            "Query Multiple LLM Models",

        "RAG Smart Recall":
            "RAG Smart Recall",

        "Multimedia Query":
            "Multimedia Agent",
    }
