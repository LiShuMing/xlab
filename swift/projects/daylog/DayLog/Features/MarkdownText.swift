import SwiftUI
import DayLogCore

struct MarkdownText: View {
    let source: String
    var collapsible = false
    @State private var expanded = false
    private var blocks: [ReviewMarkdownBlock] {ReviewMarkdown.blocks(source)}
    private var long: Bool {source.count > 420 || blocks.count > 6}
    private var collapsed: Bool {collapsible && long && !expanded}
    var body: some View {
        VStack(alignment:.leading,spacing:10) {
            ForEach(Array((collapsed ? Array(blocks.prefix(4)) : blocks).enumerated()),id:\.offset) {_,block in
                switch block.kind {
                case .heading(let level): Text(ReviewMarkdown.inline(block.text)).font(level < 3 ? .headline : .subheadline).fontWeight(.semibold)
                case .item(let marker):
                    HStack(alignment:.top,spacing:8) {Text(marker).foregroundStyle(.secondary); Text(ReviewMarkdown.inline(block.text)).lineLimit(collapsed ? 3 : nil)}
                case .code: Text(block.text).font(.system(.caption,design:.monospaced)).lineLimit(collapsed ? 3 : nil).padding(8).background(Design.canvas,in:RoundedRectangle(cornerRadius:6))
                case .paragraph: Text(ReviewMarkdown.inline(block.text)).lineLimit(collapsed ? 3 : nil)
                }
            }
            if collapsible && long {Button(expanded ? "收起回顾" : "展开完整回顾") {expanded.toggle()}.font(.caption)}
        }.font(.system(size:13)).lineSpacing(4).textSelection(.enabled).frame(maxWidth:.infinity,alignment:.leading)
    }
}

struct ReviewDraftContent: View {
    @Bindable var store: AppStore
    let draft: ReviewDraft
    @State private var editing = false
    @FocusState private var focused: Bool
    var body: some View {
        VStack(alignment:.leading,spacing:10) {
            if draft.acceptedEntryID != nil {MarkdownText(source:draft.text,collapsible:true)}
            else {
                Button(editing ? "预览排版" : "编辑草稿") {editing.toggle()}
                if editing {
                    TextEditor(text:Binding(get:{store.reviewTextDrafts[draft.id] ?? draft.text},set:{store.reviewTextDrafts[draft.id]=$0})).focused($focused).font(.system(size:13)).frame(minHeight:280)
                } else {MarkdownText(source:store.reviewTextDrafts[draft.id] ?? draft.text)}
                if store.reviewTextDrafts[draft.id] != nil {Button("保存草稿修改") {store.saveReviewText(draft.id)}}
            }
        }.task(id:store.draftNavigation?.id) {
            if store.draftNavigation?.target == .review(draft.id) {editing=true; focused=true}
        }
    }
}
