#if DEBUG
import SwiftUI

// The preview owns an isolated store and never loads real diary data or keys.
private struct WorkspacePreview: View {
    @State private var store = AppStore(inMemory:true, demoData:true)

    var body: some View {
        WorkspaceView(store:store).frame(width:1080, height:780)
    }
}

#Preview("Kebai · Daylight · Light") {
    WorkspacePreview().environment(\.colorScheme, .light)
}

#Preview("Kebai · Daylight · Dark") {
    WorkspacePreview().environment(\.colorScheme, .dark)
}
#endif
