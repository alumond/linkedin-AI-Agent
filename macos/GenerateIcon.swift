import AppKit

let directory = URL(fileURLWithPath: CommandLine.arguments[1])
try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
for size in [16, 32, 64, 128, 256, 512, 1024] {
    let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size,
                                 bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
                                 isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
    let transform = AffineTransform(scale: CGFloat(size) / 1024)
    (transform as NSAffineTransform).concat()
    NSColor(calibratedRed: 0.055, green: 0.23, blue: 0.19, alpha: 1).setFill()
    NSBezierPath(roundedRect: NSRect(x: 42, y: 42, width: 940, height: 940), xRadius: 205, yRadius: 205).fill()
    NSColor(calibratedRed: 0.29, green: 0.47, blue: 0.36, alpha: 1).setFill()
    NSBezierPath(roundedRect: NSRect(x: 235, y: 234, width: 570, height: 620), xRadius: 55, yRadius: 55).fill()
    NSColor(calibratedRed: 0.98, green: 0.97, blue: 0.89, alpha: 1).setFill()
    NSBezierPath(roundedRect: NSRect(x: 180, y: 290, width: 565, height: 580), xRadius: 55, yRadius: 55).fill()
    NSColor(calibratedRed: 0.075, green: 0.29, blue: 0.24, alpha: 1).setFill()
    for (y, width) in [(720, 330), (620, 330), (520, 235)] {
        NSBezierPath(roundedRect: NSRect(x: 265, y: y, width: width, height: 35), xRadius: 17, yRadius: 17).fill()
    }
    NSColor(calibratedRed: 0.88, green: 0.68, blue: 0.32, alpha: 1).setFill()
    NSBezierPath(ovalIn: NSRect(x: 562, y: 170, width: 285, height: 285)).fill()
    NSColor(calibratedRed: 0.055, green: 0.23, blue: 0.19, alpha: 1).setStroke()
    let check = NSBezierPath()
    check.move(to: NSPoint(x: 630, y: 309))
    check.line(to: NSPoint(x: 682, y: 257))
    check.line(to: NSPoint(x: 778, y: 368))
    check.lineWidth = 29
    check.lineCapStyle = .round
    check.lineJoinStyle = .round
    check.stroke()
    NSGraphicsContext.restoreGraphicsState()
    let data = bitmap.representation(using: .png, properties: [:])!
    let standardSizes = [16, 32, 128, 256, 512]
    if standardSizes.contains(size) { try data.write(to: directory.appendingPathComponent("icon_\(size)x\(size).png")) }
    if standardSizes.contains(size / 2) { try data.write(to: directory.appendingPathComponent("icon_\(size / 2)x\(size / 2)@2x.png")) }
}
