import Foundation

/// User-tunable parameters, persisted as JSON at
/// ~/Library/Application Support/LidFade/config.json
struct Settings: Codable, Equatable {

    enum Style: String, Codable {
        /// Black veil fades in over the live screen. No permissions required.
        case classic
        /// Frozen screenshot dissolves while blurring and scaling down.
        /// Requires Screen Recording permission.
        case cinematic
    }

    enum Trigger: String, Codable {
        /// Only when the Hall sensor reports the lid as closed.
        case lidOnly
        /// Any system sleep, including the Apple menu and idle sleep.
        case anySleep
    }

    var enabled: Bool = true
    var style: Style = .cinematic
    var trigger: Trigger = .lidOnly

    /// Seconds. The reference curve is time-normalized, so this is the only
    /// knob that changes pacing.
    var closeDuration: Double = 0.42
    var openDuration: Double = 0.52

    /// Peak Gaussian blur in points at the end of the close animation.
    var blurRadius: Double = 26
    /// Scale factor the frozen screen shrinks to as it dissolves.
    var endScale: Double = 0.965
    /// Colour the screen resolves to. Apple-style is pure black.
    var tintHex: String = "#000000"

    /// Ramp the built-in display's backlight along the same curve. This is
    /// what makes the effect read as a hardware fade rather than an overlay.
    /// Uses a private framework, so it is off for App Store builds.
    var rampBacklight: Bool = true

    /// Hard ceiling on how long we hold off the actual sleep. The kernel
    /// allows roughly 30s; staying well under that keeps the machine honest.
    var maxSleepDeferral: Double = 3.0

    /// Which displays get the overlay. Built-in only is the sane default,
    /// because closing the lid does not darken an external panel.
    var builtInDisplayOnly: Bool = true

    /// Cubic-bezier control points (x1, y1, x2, y2) used when `lut` is nil.
    var bezier: [Double] = [0.32, 0.00, 0.12, 1.00]

    /// Uniformly-sampled progress table measured from a reference recording.
    /// When present it wins over `bezier`, and this is the only way to get
    /// frame-exact parity with another product's animation.
    var lut: [Double]? = nil

    // MARK: - Persistence

    static var directory: URL {
        FileManager.default
            .homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Application Support/LidFade", isDirectory: true)
    }

    static var fileURL: URL { directory.appendingPathComponent("config.json") }

    static func load() -> Settings {
        guard let data = try? Data(contentsOf: fileURL) else { return Settings() }
        let decoder = JSONDecoder()
        guard let decoded = try? decoder.decode(Settings.self, from: data) else {
            NSLog("[LidFade] config.json is malformed; falling back to defaults")
            return Settings()
        }
        return decoded.validated()
    }

    func save() throws {
        try FileManager.default.createDirectory(
            at: Settings.directory, withIntermediateDirectories: true)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        try encoder.encode(self).write(to: Settings.fileURL, options: .atomic)
    }

    /// Clamps anything a hand-edited config file could get wrong. A zero
    /// duration or a 4000pt blur would otherwise wedge the animation while
    /// sleep is deferred, which is the one place a bad value really hurts.
    func validated() -> Settings {
        var s = self
        s.closeDuration = min(max(closeDuration, 0.05), 5.0)
        s.openDuration = min(max(openDuration, 0.05), 5.0)
        s.blurRadius = min(max(blurRadius, 0), 200)
        s.endScale = min(max(endScale, 0.5), 1.5)
        s.maxSleepDeferral = min(max(maxSleepDeferral, s.closeDuration + 0.2), 20.0)
        if s.bezier.count != 4 { s.bezier = [0.32, 0.00, 0.12, 1.00] }
        if let table = s.lut, table.count < 2 { s.lut = nil }
        return s
    }

    var tintColor: CGColor {
        let hex = tintHex.trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        guard hex.count == 6, let value = UInt32(hex, radix: 16) else {
            return CGColor(red: 0, green: 0, blue: 0, alpha: 1)
        }
        return CGColor(
            red: CGFloat((value >> 16) & 0xFF) / 255.0,
            green: CGFloat((value >> 8) & 0xFF) / 255.0,
            blue: CGFloat(value & 0xFF) / 255.0,
            alpha: 1)
    }
}
