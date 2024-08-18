import clang.cindex as CX

import pytest

def traverse(node: CX.Cursor, prefix="", is_last=True):
    branch = "└──" if is_last else "├──"
    text = f"{str(node.kind).removeprefix('CursorKind.')}: {node.spelling}"

    if node.kind == CX.CursorKind.INTEGER_LITERAL:
        value = list(node.get_tokens())[0].spelling
        text = f"{text}{value}"

    print(f"{prefix}{branch} {text}")
    new_prefix = prefix + ("    " if is_last else "│   ")
    children = list(node.get_children())
    for child in children:
        traverse(child, new_prefix, child is children[-1])

def traverse_my(node: CX.Cursor):
    if node.kind == CX.CursorKind.NAMESPACE:
        if node.spelling == "local":
            traverse(node) # forward to the previous function

    for child in node.get_children():
        traverse_my(child)

def traverse_class(node: CX.Cursor):
    match node.kind:
        case CX.CursorKind.STRUCT_DECL | CX.CursorKind.CLASS_DECL:
            print(f"Class: {node.spelling}:")
        case CX.CursorKind.FIELD_DECL:
            print(f"    Field: {node.spelling}: {node.type.spelling}")
        case CX.CursorKind.CXX_METHOD:
            print(f"    Method: {node.spelling}: {node.type.spelling}")
            for arg in node.get_arguments():
                print(f"        Param: {arg.spelling}: {arg.type.spelling}")

    for child in node.get_children():
        traverse_class(child)
def traverse_comment(node: CX.Cursor):
    if node.brief_comment:
        print(f"brief_comment => {node.brief_comment}")
    if node.raw_comment:
        print(f"raw_comment => {node.raw_comment}")
    for child in node.get_children():
        traverse_comment(child)

def traverse_macro(node: CX.Cursor):
    if node.kind == CX.CursorKind.MACRO_DEFINITION:
        if not node.spelling.startswith('_'):  # Exclude internal macros
            print(f"MACRO: {node.spelling}")
            print([token.spelling for token in node.get_tokens()])
    elif node.kind == CX.CursorKind.MACRO_INSTANTIATION:
        print(f"MACRO_INSTANTIATION: {node.spelling}")
        print([token.spelling for token in node.get_tokens()])

    for child in node.get_children():
        traverse_macro(child)

# def rewrite(node: CX.Cursor, rewriter: CX.Rewriter):
#     if node.kind == CX.CursorKind.VAR_DECL:
#         if node.spelling == "a":
#             rewriter.replace_text(node.extent, "int a = 100")
#         elif node.spelling == "b":
#             rewriter.remove_text(node.extent)
#         elif node.spelling == "c":
#             rewriter.insert_text_before(node.extent.start, "[[maybe_unused]]")

#     for child in node.get_children():
#         rewrite(child, rewriter)

def test_traverse():
    index = CX.Index.create(excludeDecls=True)
    tu = index.parse('main1.cpp', args=['-std=c++20'])
    traverse(tu.cursor)

def test_traverse_my():
    index = CX.Index.create(excludeDecls=True)
    tu = index.parse('main2.cpp', args=['-std=c++20'])
    # traverse_my(tu.cursor)
    # traverse_class(tu.cursor)
    traverse_comment(tu.cursor)

def test_rewrite():
    index = CX.Index.create()
    tu = index.parse('main3.cpp', args=['-std=c++20'])
    # rewriter = CX.Rewriter.create(tu)
    # rewrite(tu.cursor, rewriter)
    # rewriter.overwrite_changed_files()
