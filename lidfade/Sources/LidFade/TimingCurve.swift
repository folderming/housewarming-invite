import Foundation

/// A time-normalised progress curve, sampled at uniform time steps.
///
/// Every animated property in the fade is driven from one shared curve so the
/// opacity, the blur, the scale and the backlight ramp stay locked together.
/// Core Animation's own timing functions are not used, because a keyframe
/// table is the only representation that can reproduce a *measured* curve
/// exactly rather than approximately.
struct TimingCurve {

    /// progress[i] for time i / (count - 1), both in 0...1.
    let samples: [Double]

    static let sampleCount = 121

    // MARK: - Construction

    init(samples: [Double]) {
        precondition(samples.count >= 2)
        self.samples = samples
    }

    /// Resamples an arbitrary-length measured table onto the standard grid.
    static func fromMeasured(_ table: [Double]) -> TimingCurve {
        guard table.count >= 2 else { return .bezier([0.32, 0, 0.12, 1]) }
        var out = [Double](repeating: 0, count: sampleCount)
        for i in 0..<sampleCount {
            let position = Double(i) / Double(sampleCount - 1) * Double(table.count - 1)
            let low = Int(position.rounded(.down))
            let high = min(low + 1, table.count - 1)
            let fraction = position - Double(low)
            out[i] = table[low] + (table[high] - table[low]) * fraction
        }
        return TimingCurve(samples: out)
    }

    /// Samples a CSS/Core Animation style cubic bezier with endpoints pinned
    /// at (0,0) and (1,1).
    static func bezier(_ points: [Double]) -> TimingCurve {
        let p = points.count == 4 ? points : [0.32, 0, 0.12, 1]
        var out = [Double](repeating: 0, count: sampleCount)
        for i in 0..<sampleCount {
            let x = Double(i) / Double(sampleCount - 1)
            out[i] = bezierValue(x: x, x1: p[0], y1: p[1], x2: p[2], y2: p[3])
        }
        return TimingCurve(samples: out)
    }

    static func make(from settings: Settings) -> TimingCurve {
        if let table = settings.lut { return .fromMeasured(table) }
        return .bezier(settings.bezier)
    }

    // MARK: - Use

    /// Uniform key times matching `samples`, for CAKeyframeAnimation.
    var keyTimes: [NSNumber] {
        (0..<samples.count).map {
            NSNumber(value: Double($0) / Double(samples.count - 1))
        }
    }

    /// Maps the normalised progress through `transform` to produce the value
    /// table for one animated property.
    func values(_ transform: (Double) -> Double) -> [NSNumber] {
        samples.map { NSNumber(value: transform($0)) }
    }

    /// Progress at an arbitrary point in normalised time, for the backlight
    /// ramp which is driven by a timer rather than by Core Animation.
    func progress(at time: Double) -> Double {
        let clamped = min(max(time, 0), 1)
        let position = clamped * Double(samples.count - 1)
        let low = Int(position.rounded(.down))
        let high = min(low + 1, samples.count - 1)
        let fraction = position - Double(low)
        return samples[low] + (samples[high] - samples[low]) * fraction
    }

    /// The same curve played backwards, used for the fade-in on wake.
    var reversed: TimingCurve {
        TimingCurve(samples: samples.reversed().map { 1 - $0 })
    }

    // MARK: - Bezier solver

    private static func bezierValue(
        x: Double, x1: Double, y1: Double, x2: Double, y2: Double
    ) -> Double {
        if x <= 0 { return 0 }
        if x >= 1 { return 1 }
        let t = solveForT(x: x, x1: x1, x2: x2)
        return cubic(t, y1, y2)
    }

    private static func cubic(_ t: Double, _ a: Double, _ b: Double) -> Double {
        let inverse = 1 - t
        return 3 * inverse * inverse * t * a + 3 * inverse * t * t * b + t * t * t
    }

    private static func cubicDerivative(_ t: Double, _ a: Double, _ b: Double) -> Double {
        let inverse = 1 - t
        return 3 * inverse * inverse * a
            + 6 * inverse * t * (b - a)
            + 3 * t * t * (1 - b)
    }

    /// Newton-Raphson with a bisection fallback. The fallback matters: control
    /// points outside 0...1, which real measured curves routinely produce,
    /// give the bezier a near-zero derivative where Newton stalls.
    private static func solveForT(x: Double, x1: Double, x2: Double) -> Double {
        var t = x
        for _ in 0..<8 {
            let error = cubic(t, x1, x2) - x
            if abs(error) < 1e-7 { return t }
            let derivative = cubicDerivative(t, x1, x2)
            if abs(derivative) < 1e-7 { break }
            t -= error / derivative
        }
        var low = 0.0
        var high = 1.0
        t = x
        for _ in 0..<40 {
            let value = cubic(t, x1, x2)
            if abs(value - x) < 1e-7 { return t }
            if value > x { high = t } else { low = t }
            t = (low + high) / 2
        }
        return t
    }
}
