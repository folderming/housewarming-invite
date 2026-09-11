import Foundation
import CoreGraphics

/// Ramps the built-in panel's backlight along the shared timing curve.
///
/// This is the part that sells the illusion. An overlay can only paint black
/// pixels; the panel is still lit behind them, so a pure overlay fade always
/// ends on a faint grey glow instead of true darkness. Pulling the backlight
/// down on the same curve is what makes it read as the display itself going
/// out.
///
/// `DisplayServices` is a private framework. It is resolved at runtime and
/// every failure degrades to a no-op, so a build with the ramp disabled or a
/// future macOS that moves the symbol still works — it just looks less good.
/// A Mac App Store build must ship with `rampBacklight` off.
final class Backlight {

    private typealias SetBrightness = @convention(c) (UInt32, Float) -> Int32
    private typealias GetBrightness = @convention(c) (UInt32, UnsafeMutablePointer<Float>) -> Int32

    private var handle: UnsafeMutableRawPointer?
    private var setBrightness: SetBrightness?
    private var getBrightness: GetBrightness?

    private var timer: DispatchSourceTimer?
    /// Brightness before we touched it, so wake can restore exactly.
    private(set) var restoreLevel: Float?

    var isAvailable: Bool { setBrightness != nil && getBrightness != nil }

    init() {
        let path = "/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices"
        guard let handle = dlopen(path, RTLD_LAZY) else {
            NSLog("[LidFade] DisplayServices unavailable; backlight ramp disabled")
            return
        }
        self.handle = handle
        if let symbol = dlsym(handle, "DisplayServicesSetBrightness") {
            setBrightness = unsafeBitCast(symbol, to: SetBrightness.self)
        }
        if let symbol = dlsym(handle, "DisplayServicesGetBrightness") {
            getBrightness = unsafeBitCast(symbol, to: GetBrightness.self)
        }
        if !isAvailable {
            NSLog("[LidFade] DisplayServices symbols missing; backlight ramp disabled")
        }
    }

    func currentLevel(display: CGDirectDisplayID) -> Float? {
        guard let getBrightness else { return nil }
        var level: Float = 0
        guard getBrightness(display, &level) == 0 else { return nil }
        return level
    }

    /// Drives brightness from its current value to `target` over `duration`,
    /// following `curve`. Runs on its own timer because the backlight is not a
    /// Core Animation property.
    func ramp(
        display: CGDirectDisplayID,
        to target: Float,
        duration: TimeInterval,
        curve: TimingCurve,
        rememberStart: Bool,
        completion: (() -> Void)? = nil
    ) {
        guard let setBrightness, let start = currentLevel(display: display) else {
            completion?()
            return
        }
        if rememberStart { restoreLevel = start }

        timer?.cancel()
        let began = CFAbsoluteTimeGetCurrent()
        let interval = 1.0 / 120.0
        let source = DispatchSource.makeTimerSource(queue: .main)
        source.schedule(deadline: .now(), repeating: interval)
        source.setEventHandler { [weak self] in
            let elapsed = CFAbsoluteTimeGetCurrent() - began
            let normalised = min(elapsed / duration, 1.0)
            let progress = Float(curve.progress(at: normalised))
            _ = setBrightness(display, start + (target - start) * progress)
            if normalised >= 1.0 {
                self?.timer?.cancel()
                self?.timer = nil
                completion?()
            }
        }
        timer = source
        source.resume()
    }

    /// Snaps back to the remembered level. Used on wake, before the fade-in
    /// starts, so the overlay has something to reveal.
    func restore(display: CGDirectDisplayID) {
        timer?.cancel()
        timer = nil
        guard let setBrightness, let level = restoreLevel else { return }
        _ = setBrightness(display, level)
        restoreLevel = nil
    }

    func cancel() {
        timer?.cancel()
        timer = nil
    }

    deinit {
        timer?.cancel()
        if let handle { dlclose(handle) }
    }
}
