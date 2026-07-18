// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "Rpt2",
    platforms: [
        .iOS(.v14),
        .macOS(.v12),
    ],
    products: [
        .library(name: "Rpt2", targets: ["Rpt2"]),
    ],
    targets: [
        .target(
            name: "Rpt2",
            dependencies: [],
            path: "Sources/Rpt2"
        ),
        .testTarget(
            name: "Rpt2Tests",
            dependencies: ["Rpt2"],
            path: "Tests/Rpt2Tests"
        ),
    ]
)
