import AppKit
import CoreGraphics
import QuartzCore

/// Owns the overlay windows and runs the close/open animations.
final class FadeController {

    private var settings: Settings
    private let backlight = Backlight()
    private var windows: [OverlayWindow] = []
    private var completionTimer: DispatchWorkItem?
    private(set) var isAnimating = false

    init(settings: Settings) {
        self.settings = settings
    }

    func update(settings: Settings) {
        self.settings = settings
    }

    // MARK: - Permissions

    /// Cinematic style needs Screen Recording access to capture the frame it
    /// dissolves. Checked without prompting; the menu bar item is where the
    /// user is asked, because a prompt fired at lid-close time would appear
    /// on a screen that is already going dark.
    var canCapture: Bool { CGPreflightScreenCaptureAccess() }

    @discardableResult
    func requestCaptureAccess() -> Bool { CGRequestScreenCaptureAccess() }

    private var effectiveStyle: Settings.Style {
        (settings.style == .cinematic && canCapture) ? .cinematic : .classic
    }

    // MARK: - Close

    /// Runs the fade-out and calls `completion` when the last frame has been
    /// presented. The caller uses that to release the deferred sleep, so this
    /// must always fire — including on every early-return path below.
    func fadeOut(completion: @escaping () -> Void) {
        guard settings.enabled else { return completion() }
        teardown()
        isAnimating = true

        let curve = TimingCurve.make(from: settings)
        let screens = targetScreens()
        guard !screens.isEmpty else {
            isAnimating = false
            return completion()
        }

        // Capture, build and show inside one transaction. If the overlay
        // appears even one frame before the snapshot is in place, the user
        // sees a black flash, which is worse than no effect at all.
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        for screen in screens {
            let snapshot = effectiveStyle == .cinematic ? capture(screen: screen) : nil
            let window = OverlayWindow(screen: screen, settings: settings, snapshot: snapshot)
            window.setFrame(screen.frame, display: false)
            window.prepare(direction: .fadeOut)
            window.orderFrontRegardless()
            windows.append(window)
        }
        CATransaction.commit()

        for window in windows {
            window.animate(
                direction: .fadeOut, curve: curve, duration: settings.closeDuration)
        }

        if settings.rampBacklight, backlight.isAvailable,
           let display = builtInDisplayID() {
            backlight.ramp(
                display: display,
                to: 0,
                duration: settings.closeDuration,
                curve: curve,
                rememberStart: true)
        }

        // Core Animation completion blocks are not reliable while the system
        // is tearing down for sleep, so the release is driven by a timer with
        // a small margin for the final frame to reach the panel.
        let work = DispatchWorkItem { [weak self] in
            self?.isAnimating = false
            completion()
        }
        completionTimer = work
        DispatchQueue.main.asyncAfter(
            deadline: .now() + settings.closeDuration + 0.05, execute: work)
    }

    // MARK: - Open

    /// Plays the close animation backwards on wake. The overlay is already on
    /// screen from the close, so there is nothing to capture and no flash to
    /// avoid — the machine wakes up looking dark and resolves into the desktop.
    func fadeIn() {
        guard settings.enabled, !windows.isEmpty else {
            teardown()
            return
        }
        isAnimating = true
        let curve = TimingCurve.make(from: settings)

        if settings.rampBacklight, backlight.isAvailable,
           let display = builtInDisplayID() {
            backlight.restore(display: display)
        }

        for window in windows {
            window.animate(
                direction: .fadeIn, curve: curve, duration: settings.openDuration)
        }

        let work = DispatchWorkItem { [weak self] in
            self?.teardown()
        }
        completionTimer = work
        DispatchQueue.main.asyncAfter(
            deadline: .now() + settings.openDuration + 0.05, execute: work)
    }

    /// Runs the whole close/open cycle on demand, for the menu bar Preview.
    func preview() {
        fadeOut { [weak self] in
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
                self?.fadeIn()
            }
        }
    }

    // MARK: - Teardown

    func teardown() {
        completionTimer?.cancel()
        completionTimer = nil
        backlight.cancel()
        if let display = builtInDisplayID() { backlight.restore(display: display) }
        for window in windows {
            window.orderOut(nil)
            window.close()
        }
        windows.removeAll()
        isAnimating = false
    }

    // MARK: - Screens

    private func targetScreens() -> [NSScreen] {
        guard settings.builtInDisplayOnly else { return NSScreen.screens }
        let builtIn = NSScreen.screens.filter { isBuiltIn($0) }
        // A machine with no internal panel, or one whose panel has already
        // been dropped from the display list, still gets the effect on
        // whatever it does have rather than silently doing nothing.
        return builtIn.isEmpty ? NSScreen.screens : builtIn
    }

    private func isBuiltIn(_ screen: NSScreen) -> Bool {
        guard let id = displayID(of: screen) else { return false }
        return CGDisplayIsBuiltin(id) != 0
    }

    private func displayID(of screen: NSScreen) -> CGDirectDisplayID? {
        // The dictionary stores an NSNumber; bridging it straight to
        // CGDirectDisplayID silently fails, so go through NSNumber.
        let number = screen.deviceDescription[
            NSDeviceDescriptionKey("NSScreenNumber")
        ] as? NSNumber
        return number?.uint32Value
    }

    private func builtInDisplayID() -> CGDirectDisplayID? {
        NSScreen.screens.compactMap(displayID(of:)).first { CGDisplayIsBuiltin($0) != 0 }
    }

    private func capture(screen: NSScreen) -> CGImage? {
        guard let id = displayID(of: screen) else { return nil }
        return CGDisplayCreateImage(id)
    }
}
