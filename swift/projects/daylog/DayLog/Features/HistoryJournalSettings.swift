import SwiftUI
import ServiceManagement
import DayLogCore

struct HistoryView: View {
    @Bindable var store: AppStore
    var selected: WorkDay? { store.state.days.first {$0.id == store.historyDayID} ?? store.state.days.sorted {$0.id > $1.id}.first }
    var body: some View {
        HSplitView {
            List(store.state.days.sorted {$0.id > $1.id}) { day in
                Button {store.historyDayID=day.id} label: {
                    VStack(alignment:.leading,spacing:5) {Text(day.id).fontWeight(.medium); Text(day.focus.isEmpty ? "\(day.plans.count) 件事" : day.focus).font(.caption).foregroundStyle(.secondary).lineLimit(1)}.padding(.vertical,8).frame(maxWidth:.infinity,alignment:.leading)
                }.buttonStyle(.plain).listRowBackground(selected?.id == day.id ? Design.selected : .clear)
            }.scrollContentBackground(.hidden).background(Design.sidebar).frame(minWidth:180,idealWidth:210,maxWidth:260)
            ScrollView {
                if let day = selected {
                    VStack(alignment:.leading,spacing:22) {
                        HStack { Text(day.id).font(.title); Spacer(); Text(day.closed ? "当日快照" : "今天 · 更新中").font(.caption).foregroundStyle(.secondary) }
                        if !day.focus.isEmpty {Label(day.focus,systemImage:"scope").foregroundStyle(Design.accent)}
                        Text("当日计划").font(.headline)
                        ForEach(day.plans) { plan in
                            if let task = store.state.displayedTask(plan,day:day) {
                                VStack(alignment:.leading,spacing:7) {
                                    HStack {Image(systemName:task.status == .done ? "checkmark.square" : "square"); Text(task.title); Spacer(); Text(task.status.label).font(.caption).foregroundStyle(.secondary)}
                                    if !task.notes.isEmpty {Text(task.notes).font(.caption).foregroundStyle(.secondary)}
                                }
                            }
                        }
                        Divider(); Text("工作记录").font(.headline)
                        ForEach(store.state.entries.filter {$0.dayID == day.id && $0.kind != .personal}) { entry in
                            VStack(alignment:.leading,spacing:5) {Text(entry.time,style:.time).font(.caption).foregroundStyle(.secondary); if entry.kind == .summary {MarkdownText(source:entry.body,collapsible:true)} else {Text(entry.body).textSelection(.enabled)}}
                        }
                        if day.closed {Text("历史任务状态保留在当日结束时，后续修改不会覆盖这个快照。").font(.caption).foregroundStyle(.tertiary)}
                    }.padding(30).frame(maxWidth:.infinity,alignment:.leading)
                }
            }.frame(minWidth:400,maxWidth:.infinity).background(Design.canvas)
        }
    }
}

struct JournalView: View {
    @Bindable var store: AppStore
    @FocusState private var editing: Bool
    var body: some View {
        ScrollView {
            VStack(alignment:.leading,spacing:23) {
                Text("留给自己的一页").font(.system(size:28,weight:.medium))
                Text("私人日记独立保存，不进入工作回顾的模型上下文。").foregroundStyle(.secondary).font(.caption)
                TextEditor(text:$store.journalDraft).focused($editing).font(.body).scrollContentBackground(.hidden).frame(minHeight:150).padding(10).background(Design.panel,in:RoundedRectangle(cornerRadius:9))
                HStack {Text("\(store.journalDraft.count) 字").font(.caption).foregroundStyle(.secondary); Spacer(); Button("保存日记") {if store.append(store.journalDraft,kind:.personal) {store.journalDraft=""}}.buttonStyle(.borderedProminent).disabled(store.journalDraft.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty)}
                Divider()
                ForEach(store.state.entries.filter {$0.kind == .personal}.reversed()) { entry in
                    VStack(alignment:.leading,spacing:10) {Text(entry.time.formatted(date:.abbreviated,time:.shortened)).font(.caption).foregroundStyle(.secondary); Text(entry.body).textSelection(.enabled).lineSpacing(5)}.padding(.vertical,8)
                }
            }.padding(36).frame(maxWidth:760)
        }.frame(maxWidth:.infinity).background(Design.canvas)
        .task(id:store.draftNavigation?.id) {if store.draftNavigation?.target == .journal {editing=true}}
    }
}

struct SettingsView: View {
    @Bindable var store: AppStore
    @AppStorage("appearance") private var appearance = "system"
    @FocusState private var focusedDraft: DraftID?
    @State private var loginEnabled = SMAppService.mainApp.status == .enabled
    var body: some View {
        Form {
            Section("外观") {
                Picker("色彩",selection:$appearance) {Text("跟随系统").tag("system"); Text("浅色").tag("light"); Text("深色").tag("dark")}
                Text("晴白 · 云白、清透蓝与浅杏色").font(.caption).foregroundStyle(.secondary)
            }
            Section("模型服务") {
                LabeledContent("配置来源",value:store.configSource)
                Text(store.configStatus).font(.caption).foregroundStyle(.secondary)
                HStack {
                    Button("重新读取",action:store.reloadConfig)
                    Button("导入 .env…",action:store.importConfig)
                    Button("测试连接",action:store.testConnection).disabled(store.config == nil || store.llmBusy)
                    if store.llmBusy {ProgressView().controlSize(.small); Button("取消",action:store.cancelRequest)}
                }
                Text("使用 LLM_BASE_URL、LLM_API_KEY、LLM_MODEL、LLM_TIMEOUT。测试只发送固定问候；导入配置保存在 macOS Keychain。").font(.caption).foregroundStyle(.secondary)
                if store.configSource == "应用 Keychain 配置" {
                    Button("移除导入配置，使用 ~/.env") {
                        do {try ConfigStore.remove(); store.reloadConfig()} catch {store.error="无法移除 Keychain 配置"}
                    }.font(.caption)
                }
            }
            Section("工作日提醒") {
                Toggle("开启本机通知",isOn:Binding(get:{store.state.reminders.enabled},set:{store.enableReminders($0)}))
                HStack {
                    Text("开始工作").fixedSize(); TextField("09:30",text:Binding(get:{store.morningDraft ?? store.state.reminders.morning},set:{store.morningDraft=$0})).focused($focusedDraft,equals:.reminderTimes).labelsHidden().textFieldStyle(.roundedBorder).frame(width:74)
                    Text("下班回顾").fixedSize(); TextField("18:00",text:Binding(get:{store.eveningDraft ?? store.state.reminders.evening},set:{store.eveningDraft=$0})).labelsHidden().textFieldStyle(.roundedBorder).frame(width:74)
                    Button("保存时间") {_ = store.saveDrafts([.reminderTimes])}.disabled(!store.pendingDrafts.contains {$0.id == .reminderTimes})
                }
                HStack {
                    ForEach([2,3,4,5,6,7,1],id:\.self) { weekday in
                        Toggle([1:"日",2:"一",3:"二",4:"三",5:"四",6:"五",7:"六"][weekday]!,isOn:Binding(get:{store.state.reminders.weekdays.contains(weekday)},set:{ enabled in
                            if store.commit({ value in value.reminders.weekdays.removeAll {$0 == weekday}; if enabled {value.reminders.weekdays.append(weekday)} }) {Task {await store.syncReminders()}}
                        })).toggleStyle(.button)
                    }
                }
                HStack {
                    TextField("例外日期",text:$store.exceptionDateDraft,prompt:Text("例外日期 yyyy-MM-dd")).labelsHidden().textFieldStyle(.roundedBorder).focused($focusedDraft,equals:.reminderException)
                    Picker("",selection:$store.exceptionWorkdayDraft) {Text("工作日").tag(true); Text("休息日").tag(false)}.labelsHidden().frame(width:100)
                    Button("添加") {_ = store.saveDrafts([.reminderException])}
                }
                ForEach(store.state.reminders.overrides.keys.sorted(),id:\.self) { day in
                    HStack {Text(day); Text(store.state.reminders.overrides[day] == true ? "工作日" : "休息日").foregroundStyle(.secondary); Spacer(); Button("移除") {if store.commit({$0.reminders.overrides.removeValue(forKey:day)}) {Task {await store.syncReminders()}}}}
                }
                Text(store.reminderStatus).font(.caption).foregroundStyle(.secondary)
                Text("按工作空间时区 \(store.state.timeZoneID) 排期未来 14 天；应用启动、唤醒和跨日时补齐。").font(.caption).foregroundStyle(.secondary)
                Button("打开系统通知设置") {if let url=URL(string:"x-apple.systempreferences:com.apple.Notifications-Settings.extension") {NSWorkspace.shared.open(url)}}
            }
            Section("启动与数据") {
                Toggle("登录时启动",isOn:Binding(get:{loginEnabled},set:{ enabled in
                    do {if enabled {try SMAppService.mainApp.register()} else {try SMAppService.mainApp.unregister()}; loginEnabled=SMAppService.mainApp.status == .enabled; if enabled && !loginEnabled {store.notice="请在系统登录项设置中批准刻白"}}
                    catch {store.error="无法修改登录项。请将应用放入 Applications 后重试。"}
                }))
                HStack {Button("导出工作 Markdown…") {store.export(json:false)}; Button("完整 JSON 备份…") {store.export(json:true)}; Button("恢复备份…",action:store.restore)}
                Text("完整备份包含个人日记。模型凭据不进入备份。关闭窗口后，菜单栏入口继续运行。").font(.caption).foregroundStyle(.secondary)
            }
        }.formStyle(.grouped).scrollContentBackground(.hidden).background(Design.canvas).modifier(BrandAppearance()).disabled(store.isLoading || store.isRestoring || store.isTerminating).task(id:store.draftNavigation?.id) {
            if let target=store.draftNavigation?.target, target == .reminderTimes || target == .reminderException {focusedDraft=target}
        }
    }
}
