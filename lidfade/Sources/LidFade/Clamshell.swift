import Foundation
import IOKit

/// Reads the lid (Hall sensor) state that `IOPMrootDomain` publishes.
///
/// macOS exposes the lid as a binary open/closed flag and nothing more. There
/// is no hinge angle anywhere in user space, which is why this effect can be
/// driven by the *transition* but never by how far the lid has travelled.
enum Clamshell {

    /// `true` when the lid is shut. Desktops have no such property and
    /// report `false`, which is the answer we want there anyway.
    static func isClosed() -> Bool {
        let service = IOServiceGetMatchingService(
            kIOMainPortDefault, IOServiceMatching("IOPMrootDomain"))
        guard service != 0 else { return false }
        defer { IOObjectRelease(service) }

        guard let property = IORegistryEntryCreateCFProperty(
            service, "AppleClamshellState" as CFString, kCFAllocatorDefault, 0
        )?.takeRetainedValue() else { return false }

        return (property as? Bool) ?? false
    }

    /// `true` on a machine that has a lid at all.
    static var hasLid: Bool {
        let service = IOServiceGetMatchingService(
            kIOMainPortDefault, IOServiceMatching("IOPMrootDomain"))
        guard service != 0 else { return false }
        defer { IOObjectRelease(service) }
        return IORegistryEntryCreateCFProperty(
            service, "AppleClamshellState" as CFString, kCFAllocatorDefault, 0
        )?.takeRetainedValue() != nil
    }
}
