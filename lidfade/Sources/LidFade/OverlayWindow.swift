import AppKit
import QuartzCore
import CoreImage

/// A borderless, click-through window that covers one screen and hosts the
/// animation.
///
/// It sits at `CGShieldingWindowLevel()`, above the menu bar, the Dock and
/// full-screen apps. It deliberately does not cover the login window or the
/// lock screen, which live above every window level available to an
/// application — and should, because a fade must never be able to obscure
/// authentication UI.
final class OverlayWindow: NSWindow {

    private let tintLayer = CALayer()
    private let snapshotLayer = CALayer()
    private let settings: Settings

    /// Name used to address the blur in animation key paths.
    private static let blurFilterName = "lidFadeBlur"

    init(screen: NSScreen, settings: Settings, snapshot: CGImage?) {
        self.settings = settings
        super.init(
            contentRect: screen.frame,
            styleMask: .borderless,
            backing: .buffered,
            defer: false)

        isReleasedWhenClosed = false
        level = NSWindow.Level(rawValue: Int(CGShieldingWindowLevel()))
        backgroundColor = .clear
        isOpaque = false
        hasShadow = false
        ignoresMouseEvents = true
        isMovable = false
        animationBehavior = .none
        // Keep the overlay out of screenshots and screen shares; a recording
        // of the fade should show the app being used, not a black rectangle.
        sharingType = .none
        collectionBehavior = [
            .canJoinAllSpaces, .stationary, .fullScreenAuxiliary, .ignoresCycle,
        ]

        let host = NSView(frame: NSRect(origin: .zero, size: screen.frame.size))
        host.wantsLayer = true
        host.layer?.backgroundColor = CGColor(red: 0, green: 0, blue: 0, alpha: 0)
        contentView = host

        guard let root = host.layer else { return }
        root.masksToBounds = true

        tintLayer.frame = root.bounds
        tintLayer.backgroundColor = settings.tintColor
        tintLayer.autoresizingMask = [.layerWidthSizable, .layerHeightSizable]
        root.addSublayer(tintLayer)

        if let snapshot {
            snapshotLayer.frame = root.bounds
            snapshotLayer.contents = snapshot
            snapshotLayer.contentsGravity = .resize
            snapshotLayer.masksToBounds = false
            snapshotLayer.filters = OverlayWindow.makeFilters()
            root.addSublayer(snapshotLayer)
        }
    }

    override var canBecomeKey: Bool { false }
    override var canBecomeMain: Bool { false }

    /// `CIAffineClamp` before the blur is not optional. Without it Core Image
    /// treats everything outside the image as transparent and the Gaussian
    /// pulls that in, so the screen edges darken a frame before the rest —
    /// a vignette that instantly reads as "overlay", not "display off".
    private static func makeFilters() -> [CIFilter] {
        var filters: [CIFilter] = []
        if let clamp = CIFilter(name: "CIAffineClamp") {
            clamp.setValue(NSAffineTransform(), forKey: "inputTransform")
            clamp.name = "lidFadeClamp"
            filters.append(clamp)
        }
        if let blur = CIFilter(name: "CIGaussianBlur") {
            blur.setValue(0.0, forKey: kCIInputRadiusKey)
            blur.name = blurFilterName
            filters.append(blur)
        }
        return filters
    }

    /// Writes the resting blur value onto the filter itself. `filters` holds
    /// copies, so the array has to be reassigned for the change to stick.
    private func setBlurRadius(_ radius: Double) {
        guard let filters = snapshotLayer.filters as? [CIFilter] else { return }
        for filter in filters where filter.name == OverlayWindow.blurFilterName {
            filter.setValue(radius, forKey: kCIInputRadiusKey)
        }
        snapshotLayer.filters = filters
    }

    // MARK: - Animation

    enum Direction {
        /// Screen resolves to the tint colour.
        case fadeOut
        /// Screen emerges from the tint colour.
        case fadeIn
    }

    /// Installs the whole animation as explicit keyframe tables.
    ///
    /// Nothing here uses `CAMediaTimingFunction`. Every property is sampled
    /// from one `TimingCurve`, which is what allows a curve measured from a
    /// reference recording to be reproduced frame for frame instead of
    /// approximated by the nearest bezier.
    func animate(direction: Direction, curve: TimingCurve, duration: TimeInterval) {
        let effective = direction == .fadeOut ? curve : curve.reversed
        let hasSnapshot = snapshotLayer.contents != nil

        CATransaction.begin()
        CATransaction.setDisableActions(true)

        if hasSnapshot {
            add(
                keyPath: "opacity",
                to: snapshotLayer,
                values: effective.values { 1 - $0 },
                curve: effective,
                duration: duration)
            add(
                keyPath: "transform.scale",
                to: snapshotLayer,
                values: effective.values { 1 + (self.settings.endScale - 1) * $0 },
                curve: effective,
                duration: duration)
            let blurValues = effective.values { self.settings.blurRadius * $0 }
            add(
                keyPath: "filters.\(OverlayWindow.blurFilterName).inputRadius",
                to: snapshotLayer,
                values: blurValues,
                curve: effective,
                duration: duration,
                // Setting the model value through the filter key path is not
                // reliable, so the filter object is updated directly instead.
                finalize: { [weak self] in
                    self?.setBlurRadius(blurValues.last?.doubleValue ?? 0)
                })
            // The tint is the backdrop the snapshot dissolves into, so it is
            // opaque throughout. Fading it in alongside would double-dip and
            // make the midpoint visibly darker than the reference.
            tintLayer.opacity = 1
        } else {
            add(
                keyPath: "opacity",
                to: tintLayer,
                values: effective.values { $0 },
                curve: effective,
                duration: duration)
        }

        CATransaction.commit()
    }

    private func add(
        keyPath: String,
        to layer: CALayer,
        values: [NSNumber],
        curve: TimingCurve,
        duration: TimeInterval,
        finalize: (() -> Void)? = nil
    ) {
        let animation = CAKeyframeAnimation(keyPath: keyPath)
        animation.values = values
        animation.keyTimes = curve.keyTimes
        animation.calculationMode = .linear
        animation.duration = duration
        animation.fillMode = .forwards
        animation.isRemovedOnCompletion = false
        if let finalize {
            finalize()
        } else {
            layer.setValue(values.last, forKeyPath: keyPath)
        }
        layer.add(animation, forKey: keyPath)
    }

    /// Puts the layers in their pre-roll state so the window can be shown
    /// without a flash before the animation starts.
    func prepare(direction: Direction) {
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        let hasSnapshot = snapshotLayer.contents != nil
        switch direction {
        case .fadeOut:
            tintLayer.opacity = hasSnapshot ? 1 : 0
            snapshotLayer.opacity = 1
        case .fadeIn:
            tintLayer.opacity = 1
            snapshotLayer.opacity = hasSnapshot ? 0 : 1
        }
        CATransaction.commit()
    }
}
