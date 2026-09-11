import Foundation
import IOKit
import IOKit.pwr_mgt

/// Kernel power-management message identifiers.
///
/// These are `#define`d as macro expressions in `IOMessage.h`, so the Swift
/// importer drops them. The values are `iokit_common_msg(n)`, i.e.
/// `0xE0000000 | n`.
private enum PowerMessage {
    static let canSystemSleep: UInt32 = 0xE000_0270
    static let systemWillSleep: UInt32 = 0xE000_0280
    static let systemWillNotSleep: UInt32 = 0xE000_0290
    static let systemWillPowerOn: UInt32 = 0xE000_0320
    static let systemHasPoweredOn: UInt32 = 0xE000_0300
}

/// Watches system sleep and wake, and — crucially — holds the sleep open
/// long enough for an animation to actually be seen.
///
/// The lid switch does not give any advance warning: by the time anything in
/// user space hears about it, the machine is already on its way down. The one
/// lever that exists is `kIOMessageSystemWillSleep`, which stalls the sleep
/// until every registered client calls `IOAllowPowerChange`. That window is
/// the entire reason this effect is possible.
final class PowerMonitor {

    /// Called with a completion the caller must invoke to release the sleep.
    var onWillSleep: ((@escaping () -> Void) -> Void)?
    var onDidWake: (() -> Void)?

    private var rootPort: io_connect_t = 0
    private var notificationPort: IONotificationPortRef?
    private var notifier: io_object_t = 0
    private var pendingSleepArgument: UnsafeMutableRawPointer?
    private var deferralWatchdog: DispatchWorkItem?

    /// Upper bound on the deferral, independent of what the animation does.
    /// If the fade ever hangs, the machine still sleeps.
    var maxDeferral: TimeInterval = 3.0

    func start() -> Bool {
        let context = Unmanaged.passUnretained(self).toOpaque()
        rootPort = IORegisterForSystemPower(
            context,
            &notificationPort,
            { context, _, messageType, messageArgument in
                guard let context else { return }
                let monitor = Unmanaged<PowerMonitor>
                    .fromOpaque(context).takeUnretainedValue()
                monitor.handle(messageType: messageType, argument: messageArgument)
            },
            &notifier)

        guard rootPort != 0, let notificationPort else {
            NSLog("[LidFade] IORegisterForSystemPower failed")
            return false
        }

        CFRunLoopAddSource(
            CFRunLoopGetMain(),
            IONotificationPortGetRunLoopSource(notificationPort).takeUnretainedValue(),
            .commonModes)
        return true
    }

    func stop() {
        guard rootPort != 0 else { return }
        if let notificationPort {
            CFRunLoopRemoveSource(
                CFRunLoopGetMain(),
                IONotificationPortGetRunLoopSource(notificationPort).takeUnretainedValue(),
                .commonModes)
            IODeregisterForSystemPower(&notifier)
            IOServiceClose(rootPort)
            IONotificationPortDestroy(notificationPort)
        }
        rootPort = 0
        notificationPort = nil
    }

    // MARK: - Dispatch

    private func handle(messageType: UInt32, argument: UnsafeMutableRawPointer?) {
        switch messageType {
        case PowerMessage.canSystemSleep:
            // Never veto. Vetoing here is what makes a Mac refuse to sleep in
            // a bag, and the deferral we need comes from the next message.
            IOAllowPowerChange(rootPort, Int(bitPattern: argument))

        case PowerMessage.systemWillSleep:
            beginDeferredSleep(argument: argument)

        case PowerMessage.systemHasPoweredOn:
            cancelDeferral()
            onDidWake?()

        case PowerMessage.systemWillNotSleep, PowerMessage.systemWillPowerOn:
            cancelDeferral()

        default:
            break
        }
    }

    private func beginDeferredSleep(argument: UnsafeMutableRawPointer?) {
        // A second WillSleep before the first was released should not strand
        // the older token; release it immediately and take the new one.
        if pendingSleepArgument != nil { releaseSleep() }
        pendingSleepArgument = argument

        let watchdog = DispatchWorkItem { [weak self] in
            NSLog("[LidFade] fade did not finish in time; releasing sleep")
            self?.releaseSleep()
        }
        deferralWatchdog = watchdog
        DispatchQueue.main.asyncAfter(deadline: .now() + maxDeferral, execute: watchdog)

        guard let onWillSleep else {
            releaseSleep()
            return
        }
        onWillSleep { [weak self] in self?.releaseSleep() }
    }

    private func cancelDeferral() {
        deferralWatchdog?.cancel()
        deferralWatchdog = nil
        pendingSleepArgument = nil
    }

    /// Idempotent: the animation completion and the watchdog race, and
    /// calling `IOAllowPowerChange` twice for one token is a kernel panic
    /// risk, not a no-op.
    private func releaseSleep() {
        guard let argument = pendingSleepArgument else { return }
        pendingSleepArgument = nil
        deferralWatchdog?.cancel()
        deferralWatchdog = nil
        IOAllowPowerChange(rootPort, Int(bitPattern: argument))
    }
}
