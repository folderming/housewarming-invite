import AppKit
import ServiceManagement

final class AppDelegate: NSObject, NSApplicationDelegate {

    private var settings = Settings.load()
    private lazy var controller = FadeController(settings: settings)
    private let power = PowerMonitor()
    private var statusItem: NSStatusItem?
    private var configWatcher: DispatchSourceFileSystemObject?
    private var wakeHandled = false

    /// The panel is not lit the instant the kernel says the machine is awake.
    /// Starting the reveal too early throws away the first frames of the
    /// animation on a display that cannot show them yet.
    private static let wakeSettleDelay: TimeInterval = 0.18

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)

        buildStatusItem()
        watchConfigFile()

        power.maxDeferral = settings.maxSleepDeferral
        power.onWillSleep = { [weak self] release in
            self?.handleWillSleep(release: release)
        }
        power.onDidWake = { [weak self] in
            self?.handleDidWake()
        }
        if !power.start() {
            presentFatal(
                "Power notifications unavailable",
                detail: "LidFade could not register with IOKit power management, "
                    + "so it cannot detect the lid closing.")
        }

        // Belt and braces: if the IOKit wake message is ever missed, the
        // overlay would stay up over a live desktop. This guarantees it comes
        // down.
        NSWorkspace.shared.notificationCenter.addObserver(
            forName: NSWorkspace.didWakeNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            self?.handleDidWake()
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        controller.teardown()
        power.stop()
    }

    // MARK: - Power events

    private func handleWillSleep(release: @escaping () -> Void) {
        wakeHandled = false
        guard settings.enabled else { return release() }

        if settings.trigger == .lidOnly, !Clamshell.isClosed() {
            return release()
        }
        controller.fadeOut(completion: release)
    }

    private func handleDidWake() {
        guard !wakeHandled else { return }
        wakeHandled = true
        DispatchQueue.main.asyncAfter(deadline: .now() + Self.wakeSettleDelay) {
            [weak self] in self?.controller.fadeIn()
        }
    }

    // MARK: - Settings

    private func reloadSettings() {
        settings = Settings.load()
        controller.update(settings: settings)
        power.maxDeferral = settings.maxSleepDeferral
        refreshMenu()
    }

    private func mutate(_ change: (inout Settings) -> Void) {
        change(&settings)
        settings = settings.validated()
        try? settings.save()
        controller.update(settings: settings)
        power.maxDeferral = settings.maxSleepDeferral
        refreshMenu()
    }

    /// Picks up edits made by hand or by the curve-fitting tool without a
    /// restart. Re-armed after every event because atomic writes replace the
    /// inode the old descriptor points at.
    private func watchConfigFile() {
        configWatcher?.cancel()
        let path = Settings.fileURL.path
        guard FileManager.default.fileExists(atPath: path) else { return }
        let descriptor = open(path, O_EVTONLY)
        guard descriptor >= 0 else { return }

        let source = DispatchSource.makeFileSystemObjectSource(
            fileDescriptor: descriptor,
            eventMask: [.write, .rename, .delete],
            queue: .main)
        source.setEventHandler { [weak self] in
            self?.reloadSettings()
            self?.watchConfigFile()
        }
        source.setCancelHandler { close(descriptor) }
        configWatcher = source
        source.resume()
    }

    // MARK: - Menu

    private func buildStatusItem() {
        let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        item.button?.image = NSImage(
            systemSymbolName: "laptopcomputer", accessibilityDescription: "LidFade")
        item.button?.image?.isTemplate = true
        item.menu = NSMenu()
        statusItem = item
        refreshMenu()
    }

    private func refreshMenu() {
        guard let menu = statusItem?.menu else { return }
        menu.removeAllItems()

        let toggle = NSMenuItem(
            title: settings.enabled ? "Effect is on" : "Effect is off",
            action: #selector(toggleEnabled), keyEquivalent: "")
        toggle.target = self
        toggle.state = settings.enabled ? .on : .off
        menu.addItem(toggle)

        menu.addItem(.separator())

        for style in [Settings.Style.cinematic, .classic] {
            let entry = NSMenuItem(
                title: style == .cinematic ? "Cinematic" : "Classic",
                action: #selector(selectStyle(_:)), keyEquivalent: "")
            entry.target = self
            entry.representedObject = style.rawValue
            entry.state = settings.style == style ? .on : .off
            menu.addItem(entry)
        }

        if settings.style == .cinematic, !controller.canCapture {
            let warning = NSMenuItem(
                title: "Grant Screen Recording access…",
                action: #selector(requestCapture), keyEquivalent: "")
            warning.target = self
            menu.addItem(warning)
        }

        menu.addItem(.separator())

        let preview = NSMenuItem(
            title: "Preview effect", action: #selector(runPreview), keyEquivalent: "p")
        preview.target = self
        menu.addItem(preview)

        let login = NSMenuItem(
            title: "Open at login", action: #selector(toggleLoginItem), keyEquivalent: "")
        login.target = self
        login.state = SMAppService.mainApp.status == .enabled ? .on : .off
        menu.addItem(login)

        let reveal = NSMenuItem(
            title: "Reveal config file", action: #selector(revealConfig), keyEquivalent: "")
        reveal.target = self
        menu.addItem(reveal)

        menu.addItem(.separator())
        let quit = NSMenuItem(
            title: "Quit LidFade", action: #selector(NSApplication.terminate(_:)),
            keyEquivalent: "q")
        menu.addItem(quit)
    }

    @objc private func toggleEnabled() {
        mutate { $0.enabled.toggle() }
    }

    @objc private func selectStyle(_ sender: NSMenuItem) {
        guard let raw = sender.representedObject as? String,
              let style = Settings.Style(rawValue: raw) else { return }
        if style == .cinematic, !controller.canCapture {
            controller.requestCaptureAccess()
        }
        mutate { $0.style = style }
    }

    @objc private func requestCapture() {
        controller.requestCaptureAccess()
        refreshMenu()
    }

    @objc private func runPreview() {
        controller.preview()
    }

    @objc private func toggleLoginItem() {
        do {
            if SMAppService.mainApp.status == .enabled {
                try SMAppService.mainApp.unregister()
            } else {
                try SMAppService.mainApp.register()
            }
        } catch {
            NSLog("[LidFade] login item change failed: \(error.localizedDescription)")
        }
        refreshMenu()
    }

    @objc private func revealConfig() {
        try? FileManager.default.createDirectory(
            at: Settings.directory, withIntermediateDirectories: true)
        if !FileManager.default.fileExists(atPath: Settings.fileURL.path) {
            try? settings.save()
            watchConfigFile()
        }
        NSWorkspace.shared.activateFileViewerSelecting([Settings.fileURL])
    }

    private func presentFatal(_ message: String, detail: String) {
        let alert = NSAlert()
        alert.messageText = message
        alert.informativeText = detail
        alert.alertStyle = .critical
        alert.runModal()
    }
}
