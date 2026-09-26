import AppKit
import WebKit

// A local review window. Publishing remains behind the existing approval API.
final class StudioApp: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate {
    private let studioURL = URL(string: "http://127.0.0.1:8765/")!
    private var window: NSWindow!
    private var webView: WKWebView!
    private var loadingView: NSView!
    private var statusLabel: NSTextField!
    private var spinner: NSProgressIndicator!
    private var retryButton: NSButton!
    private var connecting = false
    private var attempts = 0

    func applicationDidFinishLaunching(_ notification: Notification) {
        makeMenu()
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1280, height: 860),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "LinkedIn Studio"
        window.minSize = NSSize(width: 940, height: 660)
        window.isReleasedWhenClosed = false
        window.center()
        window.setFrameAutosaveName("LinkedInStudioReviewWindow")

        let root = NSView()
        window.contentView = root
        webView = WKWebView(frame: .zero)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsMagnification = true
        webView.translatesAutoresizingMaskIntoConstraints = false
        root.addSubview(webView)
        NSLayoutConstraint.activate([
            webView.leadingAnchor.constraint(equalTo: root.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: root.trailingAnchor),
            webView.topAnchor.constraint(equalTo: root.topAnchor),
            webView.bottomAnchor.constraint(equalTo: root.bottomAnchor)
        ])

        loadingView = NSView()
        loadingView.wantsLayer = true
        loadingView.layer?.backgroundColor = NSColor(calibratedRed: 0.965, green: 0.97, blue: 0.95, alpha: 1).cgColor
        loadingView.translatesAutoresizingMaskIntoConstraints = false
        root.addSubview(loadingView)
        NSLayoutConstraint.activate([
            loadingView.leadingAnchor.constraint(equalTo: root.leadingAnchor),
            loadingView.trailingAnchor.constraint(equalTo: root.trailingAnchor),
            loadingView.topAnchor.constraint(equalTo: root.topAnchor),
            loadingView.bottomAnchor.constraint(equalTo: root.bottomAnchor)
        ])
        let title = NSTextField(labelWithString: "LinkedIn Studio")
        title.font = .systemFont(ofSize: 30, weight: .semibold)
        title.textColor = NSColor(calibratedRed: 0.1, green: 0.24, blue: 0.19, alpha: 1)
        statusLabel = NSTextField(wrappingLabelWithString: "Opening your review desk…")
        statusLabel.alignment = .center
        statusLabel.textColor = .darkGray
        statusLabel.font = .systemFont(ofSize: 15)
        spinner = NSProgressIndicator()
        spinner.style = .spinning
        spinner.controlSize = .regular
        retryButton = NSButton(title: "Try again", target: self, action: #selector(refresh))
        retryButton.bezelStyle = .rounded
        retryButton.isHidden = true
        let stack = NSStackView(views: [title, statusLabel, spinner, retryButton])
        stack.orientation = .vertical
        stack.alignment = .centerX
        stack.spacing = 20
        stack.translatesAutoresizingMaskIntoConstraints = false
        loadingView.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.centerXAnchor.constraint(equalTo: loadingView.centerXAnchor),
            stack.centerYAnchor.constraint(equalTo: loadingView.centerYAnchor),
            stack.widthAnchor.constraint(equalToConstant: 540)
        ])
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        connect()
    }

    private func makeMenu() {
        let menu = NSMenu()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "About LinkedIn Studio", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Hide LinkedIn Studio", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(withTitle: "Quit LinkedIn Studio", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let appItem = NSMenuItem()
        appItem.submenu = appMenu
        menu.addItem(appItem)
        let edit = NSMenu(title: "Edit")
        for (name, action, key) in [("Undo", "undo:", "z"), ("Cut", "cut:", "x"), ("Copy", "copy:", "c"), ("Paste", "paste:", "v"), ("Select All", "selectAll:", "a")] {
            edit.addItem(withTitle: name, action: Selector(action), keyEquivalent: key)
        }
        let editItem = NSMenuItem(title: "Edit", action: nil, keyEquivalent: "")
        editItem.submenu = edit
        menu.addItem(editItem)
        let view = NSMenu(title: "View")
        view.addItem(withTitle: "Refresh review desk", action: #selector(refresh), keyEquivalent: "r").target = self
        view.addItem(withTitle: "Open in browser", action: #selector(openInBrowser), keyEquivalent: "").target = self
        let viewItem = NSMenuItem(title: "View", action: nil, keyEquivalent: "")
        viewItem.submenu = view
        menu.addItem(viewItem)
        NSApp.mainMenu = menu
    }

    @objc private func openInBrowser() { NSWorkspace.shared.open(studioURL) }
    @objc private func refresh() { if !connecting { connect() } }

    private func connect() {
        connecting = true
        attempts = 0
        loadingView.isHidden = false
        statusLabel.stringValue = "Opening your review desk…"
        retryButton.isHidden = true
        spinner.startAnimation(nil)
        checkService()
    }

    private func startInstalledService() {
        DispatchQueue.global(qos: .utility).async {
            let domain = "gui/\(getuid())"
            func launchctl(_ arguments: [String]) -> Int32 {
                let process = Process()
                process.executableURL = URL(fileURLWithPath: "/bin/launchctl")
                process.arguments = arguments
                process.standardOutput = FileHandle.nullDevice
                process.standardError = FileHandle.nullDevice
                do { try process.run(); process.waitUntilExit(); return process.terminationStatus }
                catch { return -1 }
            }
            if launchctl(["kickstart", "\(domain)/com.almond.linkedin-review"]) != 0 {
                let plist = FileManager.default.homeDirectoryForCurrentUser
                    .appendingPathComponent("Library/LaunchAgents/com.almond.linkedin-review.plist").path
                _ = launchctl(["bootstrap", domain, plist])
            }
        }
    }

    private func checkService() {
        var request = URLRequest(url: studioURL, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 2)
        request.httpMethod = "GET"
        URLSession.shared.dataTask(with: request) { data, response, _ in
            let ready = (response as? HTTPURLResponse)?.statusCode == 200
                && String(data: data ?? Data(), encoding: .utf8)?.contains("LinkedIn Studio") == true
            DispatchQueue.main.async {
                if ready {
                    self.statusLabel.stringValue = "Loading your post and image…"
                    self.webView.load(URLRequest(url: self.studioURL))
                } else if self.attempts < 20 {
                    if self.attempts == 0 { self.startInstalledService() }
                    self.attempts += 1
                    self.statusLabel.stringValue = "Starting your local review desk…"
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1) { self.checkService() }
                } else {
                    self.showConnectionError()
                }
            }
        }.resume()
    }

    private func showConnectionError() {
        connecting = false
        loadingView.isHidden = false
        spinner.stopAnimation(nil)
        retryButton.isHidden = false
        statusLabel.stringValue = "The review desk could not start. Choose Try again. If this continues, reinstall LinkedIn Studio from the project."
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        connecting = false
        spinner.stopAnimation(nil)
        loadingView.isHidden = true
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { showConnectionError() }
    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { showConnectionError() }

    private func isLocal(_ url: URL) -> Bool {
        url.scheme == "http" && url.host == "127.0.0.1" && url.port == 8765
    }
    private func openExternal(_ url: URL) {
        if ["https", "http"].contains(url.scheme ?? "") { NSWorkspace.shared.open(url) }
    }
    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        if isLocal(url) { decisionHandler(.allow); return }
        if navigationAction.navigationType == .linkActivated { openExternal(url) }
        decisionHandler(.cancel)
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = navigationAction.request.url {
            if isLocal(url) { webView.load(URLRequest(url: url)) }
            else { openExternal(url) }
        }
        return nil
    }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window.makeKeyAndOrderFront(nil)
        return true
    }
}

let app = NSApplication.shared
let delegate = StudioApp()
app.setActivationPolicy(.regular)
app.delegate = delegate
app.run()
