// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "LidFade",
    platforms: [.macOS(.v13)],
    targets: [
        .executableTarget(
            name: "LidFade",
            path: "Sources/LidFade",
            linkerSettings: [
                .linkedFramework("AppKit"),
                .linkedFramework("IOKit"),
                .linkedFramework("QuartzCore"),
                .linkedFramework("CoreImage"),
                .linkedFramework("CoreGraphics"),
                .linkedFramework("ServiceManagement"),
            ]
        )
    ]
)
