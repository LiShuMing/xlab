import SwiftUI
import DayLogCore

struct WorkspaceView: View {
    @Bindable var store: AppStore
    @Environment(\.openWindow) private var openWindow
    @AppStorage("appearance") private var appearance = "system"
    var body: some View {
        Group {
            if store.isLoading {
                ProgressView("正在打开工作空间…").frame(maxWidth:.infinity,maxHeight:.infinity)
            } else if let fatal = store.fatalError {
                ContentUnavailableView("无法打开日记",systemImage:"externaldrive.badge.exclamationmark",description:Text(fatal)).padding(40)
            } else {
                HStack(spacing:0) {
                    VStack(spacing:18) {
                        KebaiBadge().padding(.bottom,8)
                        nav("今天","sun.max",route:"today")
                        nav("历史","clock.arrow.circlepath",route:"history")
                        nav("日记","book.closed",route:"journal")
                        Spacer()
                        nav("设置","slider.horizontal.3",route:"settings")
                    }.padding(.vertical,22).frame(width:68).background(Design.sidebar)
                    Divider()
                    VStack(spacing:0) {
                        switch store.route {
                        case "history": HistoryView(store:store)
                        case "journal": JournalView(store:store)
                        case "settings": SettingsView(store:store)
                        default:
                            HSplitView {
                                TodayView(store:store).frame(minWidth:340,maxWidth:.infinity)
                                if store.inspectorVisible { InspectorView(store:store).frame(minWidth:310,idealWidth:350,maxWidth:430) }
                            }
                        }
                        Divider()
                        HStack {
                            Text(store.persistenceLabel).foregroundStyle(store.saves.failure == nil ? Color.secondary : Color.red)
                            if store.hasUnsavedChanges {Button("未保存内容 · \(store.pendingDrafts.count)") {store.presentDrafts()}}
                            if store.saves.failure != nil {Button("重试保存") {store.saves.retry()}}
                            if !store.notice.isEmpty && !store.saves.hasPendingWrites {Text(store.notice).foregroundStyle(.secondary)}
                            if store.canUndo { Button("撤销状态修改") { store.undo() }.buttonStyle(.plain) }
                            Spacer()
                            Text("本地工作空间").foregroundStyle(.tertiary)
                        }.font(.caption).padding(.horizontal,20).padding(.vertical,9).background(Design.panel)
                    }
                }
                .toolbar {
                    ToolbarItem(placement:.navigation) { Text("刻白 / 个人工作空间").foregroundStyle(.secondary).font(.caption) }
                    ToolbarItemGroup(placement:.primaryAction) {
                        Button { store.route = "today"; store.inspector = "review"; store.inspectorVisible = true } label: { Label("今日回顾",systemImage:"sparkles") }
                        Button { store.inspectorVisible.toggle() } label: { Label("详情",systemImage:"sidebar.right") }
                    }
                }
            }
        }
        .frame(minWidth:780,minHeight:580)
        .background(Design.canvas)
        .tint(Design.accent)
        .disabled(store.isRestoring || store.isTerminating)
        .onAppear {store.showWindow = {openWindow(id:"workspace")}}
        .preferredColorScheme(appearance == "system" ? nil : appearance == "dark" ? .dark : .light)
        .sheet(isPresented:$store.showDrafts,onDismiss:store.performQueuedExport) {DraftsView(store:store)}
        .alert("刻白",isPresented:Binding(get:{store.error != nil && !store.showDrafts},set:{if !$0 {store.error=nil}})) { Button("好") {store.error=nil} } message: { Text(store.error ?? "") }
        .onReceive(NotificationCenter.default.publisher(for:.dayLogOpenWindow)) { _ in openWindow(id:"workspace") }
    }
    private func nav(_ title: String,_ icon: String,route: String) -> some View {
        Button { store.route = route } label: {
            VStack(spacing:5) { Image(systemName:icon).font(.system(size:18)); Text(title).font(.system(size:10)) }
                .frame(width:46,height:49).foregroundStyle(store.route == route ? Design.accent : .secondary)
                .background(store.route == route ? Design.selected : .clear,in:RoundedRectangle(cornerRadius:9))
        }.buttonStyle(.plain).accessibilityLabel(title)
    }
}

struct TodayView: View {
    @Bindable var store: AppStore



    @FocusState private var focusedDraft: DraftID?
    var tasks: [(PlanItem,WorkTask)] { (store.today?.plans ?? []).compactMap { plan in store.state.task(plan.taskID).map { (plan,$0) } } }
    var pending: [WorkTask] { store.state.tasks.filter { task in task.status != .done && !tasks.contains { $0.1.id == task.id } } }
    var body: some View {
        ScrollViewReader { proxy in
        ScrollView {
            VStack(alignment:.leading,spacing:22) {
                HStack(alignment:.top) {
                    VStack(alignment:.leading,spacing:7) {
                        Label("今天",systemImage:"sun.max").font(.system(size:29,weight:.medium)).labelStyle(.titleAndIcon)
                        Text(store.todayID).font(.caption).foregroundStyle(.secondary)
                    }
                    Spacer()
                    Text("\(tasks.filter {$0.1.status == .done}.count) / \(tasks.count) 完成").font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                }
                HStack {
                    Image(systemName:"scope").foregroundStyle(Design.accent)
                    Text("今日重点").font(.caption).foregroundStyle(.secondary)
                    TextField("今天最重要的一件事",text:Binding(get:{store.focusDraft ?? store.today?.focus ?? ""},set:{store.focusDraft=$0})).textFieldStyle(.plain).focused($focusedDraft,equals:.focus).id(DraftID.focus).onSubmit(saveFocus)
                    Button("保存",action:saveFocus).font(.caption).buttonStyle(.plain)
                }.padding(12).background(Design.focus,in:RoundedRectangle(cornerRadius:10))
                VStack(spacing:18) {
                    taskGroup("进行中",items:tasks.filter {$0.1.status == .doing})
                    taskGroup("接下来",items:tasks.filter {$0.1.status == .todo && $0.0.section == .day})
                    taskGroup("收尾时",items:tasks.filter {$0.1.status == .todo && $0.0.section == .closing})
                    taskGroup("已完成",items:tasks.filter {$0.1.status == .done})
                    if tasks.isEmpty { ContentUnavailableView("记录今天的第一件事",systemImage:"checklist",description:Text("任务和工作记录保存在这台 Mac。")) }
                }
                HStack {
                    TextField("添加待办，回车确认…",text:$store.newTaskDraft).textFieldStyle(.plain).focused($focusedDraft,equals:.newTask).id(DraftID.newTask).onSubmit(add)
                    Button("添加",action:add).buttonStyle(.plain).disabled(store.newTaskDraft.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty)
                }.padding(12).background(Design.panel,in:RoundedRectangle(cornerRadius:7))
                if !store.menuDraft.isEmpty {
                    HStack {
                        TextField("菜单栏未提交待办",text:$store.menuDraft).focused($focusedDraft,equals:.menuTask).id(DraftID.menuTask)
                        Button("添加菜单栏待办") {_ = store.saveDrafts([.menuTask])}
                    }.padding(12).background(Design.panel,in:RoundedRectangle(cornerRadius:7))
                }
                if !pending.isEmpty {
                    DisclosureGroup("待安排 · \(pending.count)") {
                        ForEach(pending) { task in
                            HStack { Text(task.title).lineLimit(2); Spacer(); Button("加入今天") { _ = store.commit { try $0.carry(task.id,to:store.todayID) } }.font(.caption) }.padding(.vertical,5)
                        }
                    }.font(.caption).foregroundStyle(.secondary)
                }
                Divider()
                HStack { Text("工作记录").fontWeight(.medium); Spacer(); Text("TODAY").font(.caption2.monospaced()).foregroundStyle(.tertiary) }
                ForEach(store.state.entries.filter {$0.dayID == store.todayID && $0.kind != .personal}.reversed()) { entry in
                    HStack(alignment:.top,spacing:13) {
                        Text(entry.time,style:.time).font(.system(size:10,design:.monospaced)).foregroundStyle(.secondary).frame(width:44,alignment:.leading)
                        VStack(alignment:.leading,spacing:4) {
                            if let id = entry.taskID, let task = store.state.task(id) { Text(task.title).font(.caption).foregroundStyle(Design.accent) }
                            if entry.kind == .summary {MarkdownText(source:entry.body,collapsible:true)} else {Text(entry.body).font(.system(size:12)).textSelection(.enabled)}
                        }; Spacer(minLength:0)
                    }
                }
                HStack {
                    TextField("刚刚有什么进展？",text:$store.workNoteDraft).textFieldStyle(.plain).focused($focusedDraft,equals:.workNote).id(DraftID.workNote).onSubmit(addNote)
                    Button("记下",action:addNote).buttonStyle(.plain)
                }.padding(12).background(Design.panel,in:RoundedRectangle(cornerRadius:7))
            }.padding(25)
        }
        .background(Design.canvas)
        .onAppear {focusedDraft = .newTask}
        .task(id:store.draftNavigation?.id) {
            guard let target=store.draftNavigation?.target else {return}
            switch target {
            case .newTask, .menuTask, .focus, .workNote: focusedDraft=target; proxy.scrollTo(target,anchor:.center)
            default: break
            }
        }


        .onReceive(NotificationCenter.default.publisher(for:Notification.Name("DayLogQuickAdd"))) { _ in focusedDraft = .newTask }
        }
    }
    @ViewBuilder private func taskGroup(_ title: String,items: [(PlanItem,WorkTask)]) -> some View {
        if !items.isEmpty {
            VStack(alignment:.leading,spacing:5) {
                HStack { Text(title); Text("\(items.count)").monospacedDigit() }.font(.caption).foregroundStyle(.secondary)
                ForEach(items,id:\.1.id) { plan,task in
                    HStack(spacing:10) {
                        Button { store.changeStatus(task,to:task.status == .done ? task.lastOpenStatus : .done) } label: {
                            Image(systemName:task.status == .done ? "checkmark.square.fill" : "square").foregroundStyle(task.status == .done ? Design.success : Color.secondary)
                        }.buttonStyle(.plain).accessibilityLabel("完成或撤销 \(task.title)")
                        Button { store.select(task.id) } label: {
                            VStack(alignment:.leading,spacing:5) {
                                Text(task.title).strikethrough(task.status == .done).foregroundStyle(task.status == .done ? .secondary : .primary).frame(maxWidth:.infinity,alignment:.leading)
                                if store.hasTaskDraft(task.id) {Text("有未保存内容").font(.caption2).foregroundStyle(Design.accent)}
                                if task.status != .done && !task.steps.isEmpty { Text("\(task.steps.filter(\.done).count)/\(task.steps.count) 步骤").font(.caption2).foregroundStyle(.secondary) }
                            }
                        }.buttonStyle(.plain)
                    }.padding(11).background(store.selectedTaskID == task.id ? Design.selected : .clear,in:RoundedRectangle(cornerRadius:7))
                }
            }
        }
    }
    private func add() { if store.addTask(store.newTaskDraft) { store.newTaskDraft = ""; focusedDraft = .newTask } }
    private func addNote() { if store.append(store.workNoteDraft) { store.workNoteDraft = "" } }
    private func saveFocus() { if store.commit({ state in if let i = state.days.firstIndex(where:{$0.id == store.todayID}) { state.days[i].focus = store.focusDraft ?? state.days[i].focus } }) {store.focusDraft=nil} }
}

struct MenuBarView: View {
    @Bindable var store: AppStore
    @Environment(\.openWindow) private var openWindow
    var body: some View {
        VStack(alignment:.leading,spacing:15) {
            HStack { Text("今日待办").font(.headline); Spacer(); Text(store.todayID).font(.caption).foregroundStyle(.secondary) }
            TextField("添加一件事…",text:$store.menuDraft).onSubmit { if store.addTask(store.menuDraft) {store.menuDraft=""} }
            ScrollView {
                VStack(alignment:.leading,spacing:12) {
                    ForEach(store.today?.plans ?? []) { plan in
                        if let task = store.state.task(plan.taskID) {
                            HStack { Button {store.changeStatus(task,to:task.status == .done ? task.lastOpenStatus : .done)} label: {Image(systemName:task.status == .done ? "checkmark.square.fill" : "square")}.buttonStyle(.plain); Text(task.title).strikethrough(task.status == .done); Spacer() }
                        }
                    }
                }
            }.frame(maxHeight:300)
            Text(store.persistenceLabel).font(.caption).foregroundStyle(.secondary)
            if store.saves.failure != nil {Button("重试保存") {store.saves.retry()}}
            if let error = store.error { Text(error).font(.caption).foregroundStyle(.red) }
            Divider()
            HStack { Button("打开工作日记") { openWindow(id:"workspace"); NSApp.activate(ignoringOtherApps:true) }; Spacer(); Button("退出") { NSApp.terminate(nil) } }
        }.padding(20).frame(width:360).background(Design.canvas).modifier(BrandAppearance()).disabled(store.isLoading || store.isRestoring || store.isTerminating).onAppear {store.refreshDay()}
        .onReceive(NotificationCenter.default.publisher(for:.dayLogOpenWindow)) { _ in openWindow(id:"workspace") }
    }
}
