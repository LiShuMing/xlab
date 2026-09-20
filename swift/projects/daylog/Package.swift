// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "DayLog",
    platforms: [.macOS(.v14)],
    products: [.executable(name: "DayLog", targets: ["DayLog"])],
    targets: [
        .target(name: "DayLogCore", path: "DayLog/Core"),
        .executableTarget(name: "DayLog", dependencies: ["DayLogCore"], path: "DayLog", exclude: ["Core", "README.md", "Resources"]),
        .executableTarget(name: "DayLogChecks", dependencies: ["DayLogCore"], path: "DayLogTests", exclude: ["README.md"])
    ]
)
