import SwiftUI

/// Zicou Nuit dessiné en natif (Canvas), d'après app/static/pet/skin.js et tools/icon/zicou-icon.svg : boule à facettes
/// violet nuit (mêmes facettes que le navigateur : même tirage mulberry32, même graine), casque à oreillettes et deux
/// antennes à LED de la couleur de l'humeur, grands yeux, petites jambes, gros pieds caoutchouc. Bébé, ado, adulte, œuf ;
/// variantes « étoile » (étincelles dorées) et « rebelle » (casque de travers, facettes roses), shiny (chrome).
/// Accessoires dessinés ici : les tenues d'origine et les facettes colorées ; les autres sont ignorés (jamais faux).
/// Coordonnées : le dessin de base de skin.js, en 400 × 400.
struct ZicouFigure: View, Equatable {
    let dancer: ZicouDancer
    var size: CGFloat = 96
    static let zoom: CGFloat = 1.12

    var body: some View {
        Canvas { context, canvas in
            context.scaleBy(x: canvas.width / 400, y: canvas.height / 400)
            // Zicou n'occupe que le bas du dessin de skin.js (400 × 400) : un peu plus grand, posé sur le sol.
            context.translateBy(x: 200, y: 384)
            context.scaleBy(x: Self.zoom, y: Self.zoom)
            context.translateBy(x: -200, y: -384)
            if dancer.stage == .egg {
                ZicouPainter.egg(&context, shiny: dancer.shiny)
            } else {
                ZicouPainter.creature(&context, dancer)
            }
        }
        .frame(width: size, height: size)
        .accessibilityHidden(true)
    }
}

enum ZicouPalette {
    struct Palette { let base: [Color]; let tiles: [Color]; let accents: [(Color, Double)] }

    static func hex(_ v: UInt32) -> Color {
        Color(red: Double((v >> 16) & 0xff) / 255, green: Double((v >> 8) & 0xff) / 255, blue: Double(v & 0xff) / 255)
    }

    static let ink = hex(0x1b1030), chalk = hex(0xf5f0ff), neon = hex(0xff4f9a), amber = hex(0xffb547), cyan = hex(0x5ee7ff)
    static let violet = hex(0x8f6bff), blush = hex(0xff7aa8), gold = hex(0xffd24d), green = hex(0x8be36b), lilac = hex(0xddd5f7)
    static let band = hex(0x1f1650), rubber = hex(0x3a2e78), rubberHi = hex(0x6d55f0), cup = hex(0x120d28), halo = hex(0xefe9ff)

    static let nuit = Palette(base: [hex(0x5a3fd0), hex(0x2d1d86), hex(0x160d4a)],
                              tiles: [hex(0xb9a6ff), hex(0x8f6bff), hex(0xd9ceff), hex(0x6d55f0)],
                              accents: [(cyan, 0.12), (neon, 0.22), (amber, 0.26)])
    static let wildAccents: [(Color, Double)] = [(neon, 0.3), (hex(0xff8cc2), 0.45), (cyan, 0.5), (amber, 0.54)]
    static let chrome = Palette(base: [hex(0xf4f6ff), hex(0x9aa3c2), hex(0x3b4058)],
                                tiles: [hex(0xffffff), hex(0xdfe4f5), hex(0xb9c1dc), hex(0x8f98b8)],
                                accents: [(cyan, 0.1), (hex(0xffc4e6), 0.2), (amber, 0.24)])
    /// Facettes colorées (emplacement « facets », app/static/pet/acc-b.js).
    static let facets: [String: Palette] = [
        "facettes-miroir": Palette(base: [hex(0xf2f4ff), hex(0xa6abc8), hex(0x4b4f6b)],
                                   tiles: [hex(0xffffff), hex(0xe3e6f5), hex(0xc3c8de), hex(0x9aa0bd)],
                                   accents: [(hex(0xff9be0), 0.08), (hex(0x9be8ff), 0.16)]),
        "facettes-or": Palette(base: [hex(0xfff2b8), hex(0xe2a93a), hex(0x7a4e10)],
                               tiles: [hex(0xffe27a), hex(0xffd24d), hex(0xf2b632), hex(0xfff6c4)],
                               accents: [(hex(0xffffff), 0.14), (hex(0xff9b3d), 0.22)]),
        "facettes-squelette": Palette(base: [hex(0x3a3550), hex(0x1a1626), hex(0x07060c)],
                                      tiles: [hex(0x211d30), hex(0x2d283f), hex(0x15121f), hex(0x3a3550)],
                                      accents: [(hex(0x8be36b), 0.16), (hex(0xd6ffb8), 0.24)]),
        "m-montagne": Palette(base: [hex(0xf2fbff), hex(0x7fc8e8), hex(0x1f4f7a)],
                              tiles: [hex(0xd7f3ff), hex(0xa8e1f7), hex(0xffffff), hex(0x7fc8e8)],
                              accents: [(hex(0xffc4f0), 0.08), (hex(0xc4b5ff), 0.16), (hex(0xffffff), 0.3)]),
    ]

    /// Couleur d'humeur : anneaux des oreillettes et LED des antennes (PetSkin.moodColor).
    static func mood(_ emotion: String) -> Color {
        switch emotion {
        case "egg": return hex(0xb9a6ff)
        case "party": return neon
        case "hungry": return amber
        case "tired": return hex(0x8f7bd8)
        case "sad": return hex(0x7aa2ff)
        case "sick": return green
        case "sleep": return hex(0x6b5bb8)
        default: return cyan
        }
    }

    static func glow(_ emotion: String) -> Double {
        ["party": 1.25, "hungry": 0.8, "tired": 0.45, "sleep": 0.4, "sad": 0.6, "sick": 0.55][emotion] ?? 1
    }
}

/// Pseudo-aléatoire stable de skin.js (mulberry32) : la même boule a toujours les mêmes facettes.
struct Mulberry32 {
    private var seed: UInt32
    init(_ seed: UInt32) { self.seed = seed }

    mutating func next() -> Double {
        seed = seed &+ 0x6d2b79f5
        var t = (seed ^ (seed >> 15)) &* (1 | seed)
        t = (t &+ ((t ^ (t >> 7)) &* (61 | t))) ^ t
        return Double(t ^ (t >> 14)) / 4_294_967_296
    }
}

enum ZicouPainter {
    typealias P = ZicouPalette
    static let bodyRadius: CGFloat = 114
    static let legs: CGFloat = 22
    static let dim: Set<String> = ["tired", "sleep", "sad", "sick"]

    // MARK: Outils

    static func pt(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: x, y: y) }

    static func circle(_ c: inout GraphicsContext, _ x: CGFloat, _ y: CGFloat, _ r: CGFloat, _ fill: Color,
                       stroke: Color? = nil, width: CGFloat = 0, opacity: Double = 1) {
        let path = Path(ellipseIn: CGRect(x: x - r, y: y - r, width: 2 * r, height: 2 * r))
        c.fill(path, with: .color(fill.opacity(opacity)))
        if let stroke { c.stroke(path, with: .color(stroke.opacity(opacity)), lineWidth: width) }
    }

    static func line(_ c: inout GraphicsContext, _ path: Path, _ color: Color, _ width: CGFloat, opacity: Double = 1) {
        c.stroke(path, with: .color(color.opacity(opacity)), style: StrokeStyle(lineWidth: width, lineCap: .round, lineJoin: .round))
    }

    /// Trait cerné d'encre (bras, jambes, tiges d'antenne).
    static func limb(_ c: inout GraphicsContext, _ path: Path, _ color: Color, _ width: CGFloat) {
        line(&c, path, P.ink, width + 8)
        line(&c, path, color, width)
    }

    static func sparkle(_ c: inout GraphicsContext, _ x: CGFloat, _ y: CGFloat, _ r: CGFloat, _ color: Color, opacity: Double = 1) {
        let q = r * 0.18
        var p = Path()
        p.move(to: pt(x, y - r))
        p.addQuadCurve(to: pt(x + r, y), control: pt(x + q, y - q))
        p.addQuadCurve(to: pt(x, y + r), control: pt(x + q, y + q))
        p.addQuadCurve(to: pt(x - r, y), control: pt(x - q, y + q))
        p.addQuadCurve(to: pt(x, y - r), control: pt(x - q, y - q))
        c.fill(p, with: .color(color.opacity(opacity)))
    }

    // MARK: Boule à facettes (projection latitude / longitude, lumière en haut à gauche)

    static func ball(_ c: inout GraphicsContext, cx: CGFloat, cy: CGFloat, r: CGFloat, glow: Double, bands: Int,
                     palette: P.Palette, seed: UInt32, outline: CGFloat, twinkle: Bool) {
        let disc = Path(ellipseIn: CGRect(x: cx - r, y: cy - r, width: 2 * r, height: 2 * r))
        let box = CGRect(x: cx - r, y: cy - r, width: 2 * r, height: 2 * r)
        c.fill(disc, with: .radialGradient(Gradient(stops: [.init(color: palette.base[0], location: 0),
                                                            .init(color: palette.base[1], location: 0.6),
                                                            .init(color: palette.base[2], location: 1)]),
                                           center: pt(box.minX + box.width * 0.38, box.minY + box.height * 0.32),
                                           startRadius: 0, endRadius: box.width * 0.75))
        var inner = c
        inner.clip(to: disc)
        var rand = Mulberry32(seed)
        let half = Double.pi / 2, step = Double.pi / Double(bands)
        func at(_ u: Double, _ v: Double) -> CGPoint { pt(cx + r * CGFloat(sin(u) * cos(v)), cy + r * CGFloat(sin(v))) }
        for i in 0..<bands {
            for j in 0..<bands {
                let u0 = -half + Double(i) * step, u1 = u0 + step, v0 = -half + Double(j) * step, v1 = v0 + step
                let raw = [at(u0, v0), at(u1, v0), at(u1, v1), at(u0, v1)]
                let mx = raw.map(\.x).reduce(0, +) / 4, my = raw.map(\.y).reduce(0, +) / 4
                let pts = raw.map { pt(mx + ($0.x - mx) * 0.8, my + ($0.y - my) * 0.8) }
                let nx = Double((mx - cx) / r), ny = Double((my - cy) / r), nz = max(0, 1 - nx * nx - ny * ny).squareRoot()
                let light = max(0.12, -0.45 * nx - 0.55 * ny + 0.7 * nz)
                let roll = rand.next(), pick = rand.next()
                let accent = palette.accents.first { roll < $0.1 }
                if twinkle && accent != nil { _ = rand.next() }   // même tirage que le scintillement de skin.js
                let color = accent?.0 ?? palette.tiles[min(palette.tiles.count - 1, Int(pick * Double(palette.tiles.count)))]
                var tile = Path()
                tile.addLines(pts)
                tile.closeSubpath()
                inner.fill(tile, with: .color(color.opacity(min(1, light * glow))))
            }
        }
        inner.fill(disc, with: .radialGradient(Gradient(stops: [.init(color: .clear, location: 0.55),
                                                                .init(color: P.hex(0x0b0624).opacity(0.65), location: 1)]),
                                               center: pt(box.minX + box.width * 0.4, box.minY + box.height * 0.35),
                                               startRadius: 0, endRadius: box.width * 0.7))
        var shine = inner
        shine.translateBy(x: cx - r * 0.38, y: cy - r * 0.45)
        shine.rotate(by: .degrees(-30))
        shine.fill(Path(ellipseIn: CGRect(x: -r * 0.26, y: -r * 0.15, width: r * 0.52, height: r * 0.3)),
                   with: .color(.white.opacity(0.35 * glow)))
        if outline > 0 { c.stroke(disc, with: .color(P.ink), lineWidth: outline) }
        if glow > 0.6 && r > 40 { sparkle(&c, cx - r * 0.42, cy - r * 0.5, r * 0.2, .white, opacity: 0.95) }
    }

    // MARK: Œuf facetté à mini-casque

    static func egg(_ c: inout GraphicsContext, shiny: Bool) {
        var s = c
        s.scaleBy(x: 2, y: 2)   // l'œuf de skin.js est dessiné en 200 × 200
        s.fill(Path(ellipseIn: CGRect(x: 65, y: 175, width: 70, height: 10)), with: .color(.black.opacity(0.35)))
        var shell = Path()
        shell.move(to: pt(100, 59))
        shell.addCurve(to: pt(144, 128), control1: pt(128, 59), control2: pt(144, 104))
        shell.addCurve(to: pt(100, 174), control1: pt(144, 156), control2: pt(125, 174))
        shell.addCurve(to: pt(56, 128), control1: pt(75, 174), control2: pt(56, 156))
        shell.addCurve(to: pt(100, 59), control1: pt(56, 104), control2: pt(72, 59))
        shell.closeSubpath()
        let palette = shiny ? P.chrome : P.nuit
        s.fill(shell, with: .color(palette.base[1]))
        var inside = c
        inside.scaleBy(x: 2, y: 2)
        inside.clip(to: shell)
        inside.scaleBy(x: 0.5, y: 0.5)
        ball(&inside, cx: 200, cy: 238, r: 150, glow: 1, bands: 9, palette: palette, seed: 5, outline: 0, twinkle: true)
        var shineLine = Path()
        shineLine.move(to: pt(75, 85))
        shineLine.addQuadCurve(to: pt(71, 115), control: pt(70, 100))
        line(&s, shineLine, .white, 5, opacity: 0.45)
        var crack = Path()
        crack.addLines([pt(84, 98), pt(91, 105), pt(86, 111), pt(95, 116), pt(92, 123)])
        line(&s, crack, P.ink, 2.25)
        s.stroke(shell, with: .color(P.ink), lineWidth: 3)
        var band = Path()
        band.move(to: pt(58, 103))
        band.addCurve(to: pt(142, 103), control1: pt(56, 31), control2: pt(144, 31))
        line(&s, band, P.ink, 11)
        line(&s, band, P.band, 6.5)
        for x in [CGFloat(57), 143] {
            let cup = Path(roundedRect: CGRect(x: x - 8.5, y: 93, width: 17, height: 32), cornerRadius: 8)
            s.fill(cup, with: .color(P.band))
            s.stroke(cup, with: .color(P.ink), lineWidth: 2.5)
            circle(&s, x, 109, 4.5, P.cup, stroke: P.mood("egg"), width: 2)
        }
    }

    // MARK: Zicou

    struct Geometry { let cx: CGFloat, cy: CGFloat, r: CGFloat }

    static func geometry(_ stage: ZicouDancer.Stage) -> Geometry {
        let k: CGFloat = stage == .baby ? 0.6 : stage == .teen ? 0.8 : 1
        let r = bodyRadius * k
        let legLength: CGFloat = stage == .baby ? 0 : legs * (stage == .teen ? 0.55 : 1)
        let shoe: CGFloat = stage == .baby ? 18 : 24
        return Geometry(cx: 200, cy: 372 - shoe - legLength - r + 8, r: r)
    }

    static func creature(_ c: inout GraphicsContext, _ z: ZicouDancer) {
        let g = geometry(z.stage), cx = g.cx, cy = g.cy, r = g.r
        let emotion = z.emotion, mood = P.mood(emotion), glow = P.glow(emotion)
        var palette = z.shiny ? P.chrome : (z.acc["facets"].flatMap { P.facets[$0] } ?? P.nuit)
        if z.shiny, let custom = z.acc["facets"].flatMap({ P.facets[$0] }) { palette = custom }
        if z.variant == .wild { palette = P.Palette(base: palette.base, tiles: palette.tiles, accents: P.wildAccents + palette.accents) }
        let s = r / 100 * (z.stage == .baby ? 1.55 : 1.4) * 1.18
        let gap = r * 0.36, ey = cy + r * 0.02

        c.fill(Path(ellipseIn: CGRect(x: 200 - r * 0.9, y: 368, width: r * 1.8, height: 20)), with: .color(.black.opacity(0.35)))
        if z.variant == .star {
            sparkle(&c, cx - r - 20, cy - r * 0.6, 14, P.gold)
            sparkle(&c, cx + r + 24, cy - r * 0.2, 11, P.gold)
            sparkle(&c, cx + r * 0.8, cy + r + 10, 9, P.gold)
        }
        if z.shiny {
            sparkle(&c, cx - r - 6, cy + r * 0.3, 9, .white, opacity: 0.9)
            sparkle(&c, cx + r + 8, cy - r * 0.9, 7, P.cyan, opacity: 0.9)
        }
        if z.acc["back"] == "cape" { ZicouOutfits.cape(&c, cx: cx, cy: cy, r: r) }
        if z.stage != .baby {
            for d in [CGFloat(-1), 1] {
                var leg = Path()
                leg.move(to: pt(cx + d * 26, cy + r - 10))
                leg.addLine(to: pt(cx + d * 30, 350))
                limb(&c, leg, P.lilac, 12)
            }
        }
        shoes(&c, cx: cx, baby: z.stage == .baby)
        arms(&c, cx: cx, cy: cy, r: r, emotion: emotion, stage: z.stage)
        ball(&c, cx: cx, cy: cy, r: r, glow: glow, bands: z.stage == .adult ? 8 : 6, palette: palette, seed: 21,
             outline: z.stage == .baby ? 5 : 6, twinkle: true)
        if z.shiny {
            let disc = Path(ellipseIn: CGRect(x: cx - r + 3, y: cy - r + 3, width: 2 * r - 6, height: 2 * r - 6))
            c.fill(disc, with: .linearGradient(Gradient(colors: [P.hex(0xffc4e6).opacity(0.35), P.hex(0xbff0ff).opacity(0), P.hex(0xfff0b8).opacity(0.35)]),
                                               startPoint: pt(cx - r, cy - r), endPoint: pt(cx + r, cy + r)))
        }
        if emotion == "sick" { circle(&c, cx, cy, r - 3, P.green, opacity: 0.28) }
        let head = z.acc["head"]
        if let head, ZicouOutfits.under.contains(head) { ZicouOutfits.head(&c, head, cx: cx, cy: cy, r: r) }
        var hs = c
        if z.variant == .wild {
            hs.translateBy(x: cx, y: cy)
            hs.rotate(by: .degrees(-12))
            hs.translateBy(x: -cx, y: -cy)
        }
        headset(&hs, cx: cx, cy: cy, r: r, mood: mood, dimmed: dim.contains(emotion), gold: head == "casque")
        ZicouFace.draw(&c, cx: cx, ey: ey, gap: gap, s: s, emotion: emotion)
        if z.acc["eyes"] == "lunettes" { ZicouOutfits.glasses(&c, cx: cx, ey: ey, gap: gap, s: s) }
        if let neck = z.acc["neck"] { ZicouOutfits.neck(&c, neck, cx: cx, cy: cy, r: r) }
        if let head, !ZicouOutfits.under.contains(head) { ZicouOutfits.head(&c, head, cx: cx, cy: cy, r: r) }
        if emotion == "sleep" || emotion == "tired" { zzz(&c, x: min(300, cx + r * 0.75), y: max(92, cy - r * 1.15)) }
    }

    /// Casque fin à oreillettes et deux antennes à LED (doré à paillettes avec la tenue « Casque de DJ »).
    static func headset(_ c: inout GraphicsContext, cx: CGFloat, cy: CGFloat, r: CGFloat, mood: Color, dimmed: Bool, gold: Bool) {
        let band = gold ? P.gold : P.band, cupFill = gold ? P.gold : P.band, stem = gold ? P.hex(0xfff3c4) : P.lilac
        let ring = dimmed ? 0.45 : 1
        let y0 = cy - r * 0.08, w = r * (gold ? 0.2 : 0.14)
        var arc = Path()
        arc.move(to: pt(cx - r * 0.98, y0))
        arc.addCurve(to: pt(cx + r * 0.98, y0), control1: pt(cx - r, cy - r * 1.28), control2: pt(cx + r, cy - r * 1.28))
        line(&c, arc, P.ink, w + 9)
        line(&c, arc, band, w)
        if gold {
            for (i, t) in [0.12, 0.26, 0.4, 0.5, 0.6, 0.74, 0.88].enumerated() {
                let x = cx + CGFloat(t - 0.5) * 2 * r * 0.98, y = cy - r * 0.98 + CGFloat(pow((t - 0.5) * 2, 2)) * r * 0.86
                circle(&c, x, y, w * 0.18, [Color.white, P.neon, P.cyan][i % 3])
            }
        }
        let cw = r * 0.42, ch = r * 0.78
        for d in [CGFloat(-1), 1] {
            let x = cx + d * r * 1.04, tx = cx + d * r * 0.92, ty = cy - r * 1.42
            var antenna = Path()
            antenna.move(to: pt(x, cy - ch / 2))
            antenna.addLine(to: pt(tx, ty))
            line(&c, antenna, P.ink, 9)
            line(&c, antenna, stem, 3.5)
            circle(&c, tx, ty, r * 0.1, P.ink)
            var glowing = c
            glowing.addFilter(.shadow(color: mood.opacity(0.9 * ring), radius: 6))
            circle(&glowing, tx, ty, r * 0.075, mood, opacity: ring)
            let cup = Path(roundedRect: CGRect(x: x - cw / 2, y: cy - ch / 2, width: cw, height: ch), cornerRadius: cw * 0.45)
            c.fill(cup, with: .color(cupFill))
            c.stroke(cup, with: .color(P.ink), lineWidth: 5)
            circle(&c, x, cy, r * 0.15, P.cup)
            glowing.stroke(Path(ellipseIn: CGRect(x: x - r * 0.15, y: cy - r * 0.15, width: r * 0.3, height: r * 0.3)),
                           with: .color(mood.opacity(ring)), lineWidth: r > 70 ? 6 : 4)
        }
    }

    static func shoes(_ c: inout GraphicsContext, cx: CGFloat, baby: Bool) {
        for d in [CGFloat(-1), 1] {
            let x = cx + d * 30
            if baby {
                let foot = Path(ellipseIn: CGRect(x: x - 20, y: 354, width: 40, height: 20))
                c.fill(foot, with: .color(P.rubber))
                c.stroke(foot, with: .color(P.ink), lineWidth: 4)
            } else {
                let shoe = Path(roundedRect: CGRect(x: x - 26, y: 348, width: 52, height: 24), cornerRadius: 12)
                c.fill(shoe, with: .color(P.rubber))
                c.stroke(shoe, with: .color(P.ink), lineWidth: 4)
                c.fill(Path(roundedRect: CGRect(x: x - 18, y: 352, width: 20, height: 6), cornerRadius: 3), with: .color(P.rubberHi))
            }
        }
    }

    /// Bras (pas chez le bébé) : levés en fête, un bras levé pour l'adulte content, tombants s'il est fatigué.
    static func arms(_ c: inout GraphicsContext, cx: CGFloat, cy: CGFloat, r: CGFloat, emotion: String, stage: ZicouDancer.Stage) {
        guard stage != .baby else { return }
        let w: CGFloat = stage == .adult ? 12 : 10
        let hero = emotion == "happy" && stage == .adult
        for d in [CGFloat(-1), 1] {
            let x0 = cx + d * r * 0.78, y0 = cy + r * 0.5
            let up = emotion == "party" || (hero && d == 1)
            let low = dim.contains(emotion)
            let x1 = cx + d * (up ? r + 34 : low ? r + 8 : r + 26), y1 = up ? cy - r * 0.55 : low ? cy + r * 1.15 : cy + r
            var arm = Path()
            arm.move(to: pt(x0, y0))
            arm.addQuadCurve(to: pt(x1, y1), control: pt(cx + d * (r + 26), (y0 + y1) / 2 + 10))
            limb(&c, arm, P.lilac, w)
            circle(&c, x1, y1, w * 0.8, P.lilac, stroke: P.ink, width: 4)
        }
    }

    static func zzz(_ c: inout GraphicsContext, x: CGFloat, y: CGFloat) {
        for (i, k) in [CGFloat(0.7), 1, 1.35].enumerated() {
            let w = 14 * k, zx = x + CGFloat(i) * 20, zy = y - CGFloat(i) * 24
            var z = Path()
            z.addLines([pt(zx, zy), pt(zx + w, zy), pt(zx, zy + w * 1.1), pt(zx + w, zy + w * 1.1)])
            line(&c, z, P.chalk, 4.5)
        }
    }
}
