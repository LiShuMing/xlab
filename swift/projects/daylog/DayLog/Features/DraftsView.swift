import SwiftUI

struct DraftsView: View {
    @Bindable var store: AppStore
    private var exporting: Bool {if case .export=store.draftPurpose {true} else {false}}
    var body: some View {
        VStack(alignment:.leading,spacing:16) {
            Text(exporting ? "选择导出内容" : "未保存内容").font(.title2.bold())
            Text(exporting ? "以下输入尚未提交。仅导出已提交内容时，它们不会进入备份。" : "选择一项前往编辑，或直接保存。工作回顾只列出影响其来源的输入。").font(.callout).foregroundStyle(.secondary)
            ScrollView {
                VStack(spacing:12) {
                    ForEach(store.visibleDrafts) {draft in
                        HStack(alignment:.top) {
                            VStack(alignment:.leading,spacing:4) {
                                Text(draft.title).fontWeight(.medium)
                                Text(draft.detail).font(.caption).foregroundStyle(.secondary).lineLimit(2)
                            }
                            Spacer()
                            Button("前往") {store.revealDraft(draft.id)}.accessibilityLabel("前往 \(draft.title)")
                            Button("保存") {_ = store.saveDrafts([draft.id])}.accessibilityLabel("保存 \(draft.title)")
                        }.padding(12).background(Design.canvas,in:RoundedRectangle(cornerRadius:8))
                    }
                    if store.visibleDrafts.isEmpty {Text("这些输入已全部保存，可以返回继续操作。").foregroundStyle(.secondary)}
                }
            }.frame(maxHeight:330)
            if let error=store.error {Text(error).foregroundStyle(.red).font(.callout)}
            if exporting || store.draftPurpose == .manage {
                Text("保存全部会提交私人日记；回顾文字只保存为草稿，不会自动采纳。").font(.caption).foregroundStyle(.secondary)
            }
            HStack {
                Button("关闭") {store.dismissDrafts()}.keyboardShortcut(.cancelAction)
                Spacer()
                if exporting {
                    Button("仅导出已提交内容") {store.confirmExport(saveDrafts:false)}
                    Button("保存全部并导出") {store.confirmExport(saveDrafts:true)}.buttonStyle(.borderedProminent)
                } else {
                    Button(store.draftPurpose == .manage ? "保存全部" : "保存这些工作输入") {_ = store.saveDrafts(Set(store.visibleDrafts.map(\.id)))}.buttonStyle(.borderedProminent).disabled(store.visibleDrafts.isEmpty)
                }
            }
        }.padding(24).background(Design.panel).modifier(BrandAppearance()).frame(width:600).fixedSize(horizontal:false,vertical:true)
    }
}
