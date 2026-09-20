import SwiftUI
import DayLogCore

struct InspectorView: View {
    @Bindable var store: AppStore
    var body: some View {
        VStack(spacing:0) {
            Picker("详情",selection:$store.inspector) { Text("任务详情").tag("task"); Text("AI 回顾").tag("review") }.pickerStyle(.segmented).padding(18)
            Divider()
            if store.inspector == "review" { ReviewView(store:store) }
            else if let task = store.selectedTask { TaskEditor(store:store,task:task).id(task.id) }
            else { ContentUnavailableView("留一点空间给专注",systemImage:"rectangle.and.pencil.and.ellipsis",description:Text("选择一个任务，记录步骤和进展。")).frame(maxHeight:.infinity) }
        }.background(Design.panel)
    }
}

struct TaskEditor: View {
    @Bindable var store: AppStore
    let task: WorkTask
    @FocusState private var focusedDraft: DraftID?
    var buffer: TaskBuffer { store.taskBuffers[task.id] ?? TaskBuffer(task) }
    private func field(_ path: WritableKeyPath<TaskBuffer,String>) -> Binding<String> {
        Binding(get:{buffer[keyPath:path]},set:{ value in
            var next = buffer; next[keyPath:path] = value
            store.taskBuffers[task.id] = next; store.dirtyEditors.insert(task.id)
        })
    }
    var body: some View {
        ScrollViewReader { proxy in
        ScrollView {
            VStack(alignment:.leading,spacing:21) {
                HStack { Text("TASK DETAILS").font(.caption2.monospaced()).foregroundStyle(.tertiary); Spacer(); Text(store.dirtyEditors.contains(task.id) ? "正在编辑" : store.saves.failure != nil ? "保存失败" : store.saves.hasPendingWrites ? "保存中" : "已保存").font(.caption).foregroundStyle(.secondary) }
                TextField("任务标题",text:field(\.title),axis:.vertical).font(.system(size:21,weight:.medium)).textFieldStyle(.plain).focused($focusedDraft,equals:.task(task.id)).id(DraftID.task(task.id))
                HStack {
                    Picker("状态",selection:Binding(get:{task.status},set:{store.changeStatus(task,to:$0)})) { ForEach(TaskStatus.allCases,id:\.self) { Text($0.label).tag($0) } }
                    Spacer()
                }
                if let plan = store.today?.plans.first(where:{$0.taskID == task.id}) {
                    Picker("安排",selection:Binding(get:{plan.section},set:{ section in _ = store.commit { try $0.setSection(taskID:task.id,section:section,now:Date()) } })) { ForEach(DaySection.allCases,id:\.self) { Text($0.label).tag($0) } }
                }
                VStack(alignment:.leading,spacing:8) {
                    Text("说明").font(.caption).foregroundStyle(.secondary)
                    TextEditor(text:field(\.notes)).font(.system(size:12)).scrollContentBackground(.hidden).frame(minHeight:95).padding(8).background(Design.canvas,in:RoundedRectangle(cornerRadius:7))
                    HStack { Text("停笔后自动保存").font(.caption2).foregroundStyle(.tertiary); Spacer(); Button("保存") {store.saveBuffer(task.id)}.font(.caption).disabled(!store.dirtyEditors.contains(task.id)) }
                    if store.dirtyEditors.contains(task.id) && buffer.revision != task.revision {
                        Text("任务已从另一个入口更新。文字仍保留，请复制后重新载入。").font(.caption).foregroundStyle(.orange)
                        Button("放弃文字编辑并重新载入") { store.taskBuffers.removeValue(forKey:task.id); store.dirtyEditors.remove(task.id) }.font(.caption)
                    }
                }
                Divider()
                HStack { Text("步骤").fontWeight(.medium); Spacer(); Text("\(task.steps.filter(\.done).count) / \(task.steps.count)").font(.caption).foregroundStyle(.secondary) }
                ForEach(task.steps) { item in
                    HStack {
                        Button { mutate("更新步骤") { value in if let i = value.steps.firstIndex(where:{$0.id == item.id}) {value.steps[i].done.toggle()} } } label: {Image(systemName:item.done ? "checkmark.circle.fill" : "circle")}.buttonStyle(.plain).accessibilityLabel("切换步骤 \(item.text)")
                        Text(item.text).font(.system(size:12)).strikethrough(item.done); Spacer()
                        Button { mutate("移除步骤") { $0.steps.removeAll {$0.id == item.id} } } label: {Image(systemName:"minus.circle")}.buttonStyle(.plain).foregroundStyle(.secondary).accessibilityLabel("移除步骤")
                    }
                }
                TextField("添加一个步骤，回车确认",text:Binding(get:{store.stepDrafts[task.id] ?? ""},set:{store.stepDrafts[task.id]=$0})).focused($focusedDraft,equals:.step(task.id)).id(DraftID.step(task.id)).onSubmit {
                    let value = (store.stepDrafts[task.id] ?? "").trimmingCharacters(in:.whitespacesAndNewlines)
                    guard !value.isEmpty else {return}
                    if mutate("添加步骤",change:{$0.steps.append(TaskStep(text:value))}) {store.stepDrafts.removeValue(forKey:task.id)}
                }
                Text("步骤全部完成后，仍可继续记录任务进展。").font(.caption2).foregroundStyle(.tertiary)
                Divider()
                Text("进展").fontWeight(.medium)
                TextField("记一条进展…",text:Binding(get:{store.progressDrafts[task.id] ?? ""},set:{store.progressDrafts[task.id]=$0}),axis:.vertical).lineLimit(2...5).focused($focusedDraft,equals:.progress(task.id)).id(DraftID.progress(task.id))
                Button("记录进展") { if store.append(store.progressDrafts[task.id] ?? "",kind:.progress,taskID:task.id) {store.progressDrafts.removeValue(forKey:task.id)} }.buttonStyle(.bordered)
                ForEach(store.state.entries.filter {$0.taskID == task.id}.reversed()) { entry in
                    VStack(alignment:.leading,spacing:4) { Text(entry.time,style:.date).font(.caption2).foregroundStyle(.secondary); Text(entry.body).font(.system(size:12)).textSelection(.enabled) }
                }
                DisclosureGroup("操作记录") {
                    ForEach(store.state.events.filter {$0.taskID == task.id}.reversed()) { event in
                        HStack { Text(event.message); Spacer(); Text(event.time,style:.time) }.font(.caption2).foregroundStyle(.secondary).padding(.vertical,4)
                    }
                }.font(.caption)
            }.padding(21)
        }.task(id:buffer) {
            guard store.dirtyEditors.contains(task.id) else {return}
            do {try await Task.sleep(for:.milliseconds(650))} catch {return}
            store.saveBuffer(task.id)
        }
        .onDisappear {store.saveBuffer(task.id)}
        .task(id:store.draftNavigation?.id) {
            if let target=store.draftNavigation?.target, target.taskID == task.id {focusedDraft=target; proxy.scrollTo(target,anchor:.center)}
        }
        }
    }
    @discardableResult private func mutate(_ message: String,change:(inout WorkTask)->Void) -> Bool {
        store.saveBuffer(task.id)
        guard !store.dirtyEditors.contains(task.id), let latest = store.state.task(task.id) else {return false}
        return store.commit {try $0.updateTask(task.id,expectedRevision:latest.revision,now:Date(),message:message,change:change)}
    }
}

struct ReviewView: View {
    @Bindable var store: AppStore
    var body: some View {
        ScrollView {
            VStack(alignment:.leading,spacing:18) {
                Label("给今天一个清晰的收尾",systemImage:"sparkles").font(.headline)
                Text("整理事实，留出下一步。").font(.caption).foregroundStyle(.secondary)
                Picker("范围",selection:$store.reviewRange) {Text("今天").tag(1); Text("近 7 天").tag(7)}.pickerStyle(.segmented)
                Text("点击生成后，将所选日期的任务、说明、步骤和工作记录发送到你配置的模型服务。个人日记不包含在内。").font(.caption).foregroundStyle(.secondary)
                if store.config == nil { Button("配置模型") {store.route="settings"} }
                HStack {
                    Button(action:store.generateReview) {Label(store.llmBusy ? "整理中…" : "生成回顾",systemImage:"sparkles")}.buttonStyle(.borderedProminent).disabled(store.llmBusy || store.config == nil)
                    if store.llmBusy {ProgressView().controlSize(.small); Button("取消",action:store.cancelRequest)}
                }
                if !store.state.reviews.isEmpty {
                    Divider()
                    Picker("草稿",selection:Binding(get:{store.selectedReviewID ?? store.state.reviews.last!.id},set:{store.selectedReviewID=$0})) {
                        ForEach(store.state.reviews.reversed()) { draft in Text("\(draft.dayIDs.last ?? "") · \(draft.createdAt.formatted(date:.omitted,time:.shortened))").tag(draft.id) }
                    }
                }
                if let draft = store.selectedReview {
                    Text("来源：\(draft.dayIDs.joined(separator:"、"))").font(.caption2).foregroundStyle(.secondary)
                    if draft.acceptedEntryID != nil { Label("已保存为工作记录",systemImage:"checkmark.seal").font(.caption).foregroundStyle(.secondary) }
                    else if store.reviewStale {
                        Label("来源或编辑已变化，请重新生成",systemImage:"arrow.clockwise").font(.caption).foregroundStyle(.orange)
                        if !store.reviewBlockingDrafts(dayIDs:draft.dayIDs).isEmpty {Button("查看未保存的工作输入") {store.presentDrafts(.review(draft.dayIDs))}}
                    }
                    ReviewDraftContent(store:store,draft:draft).id(draft.id)
                    Text("模型生成的内容可能有误，请核对后采纳。").font(.caption2).foregroundStyle(.tertiary)
                    Button("采纳到工作记录") {store.saveReviewText(draft.id); guard store.reviewTextDrafts[draft.id] == nil else {return}; _ = store.commit { _ = try $0.acceptReview(draft.id,now:Date()) } }.disabled(draft.acceptedEntryID != nil || store.reviewStale)
                } else if !store.llmBusy {
                    Image(systemName:"text.alignleft").font(.system(size:36,weight:.ultraLight)).foregroundStyle(.quaternary).frame(maxWidth:.infinity).padding(.top,40)
                    Text("回顾草稿会出现在这里。\n由你决定哪些内容进入日记。").font(.caption).foregroundStyle(.secondary).frame(maxWidth:.infinity).multilineTextAlignment(.center)
                }
            }.padding(21)
        }
    }
}
