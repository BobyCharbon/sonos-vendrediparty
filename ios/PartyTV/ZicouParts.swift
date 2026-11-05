import SwiftUI

/// Visage de Zicou selon l'humeur (skin.js : eye, brows, mouth, face), en coordonnées 400 × 400.
enum ZicouFace {
    typealias P = ZicouPalette
    private static func pt(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: x, y: y) }

    static func draw(_ c: inout GraphicsContext, cx: CGFloat, ey: CGFloat, gap: CGFloat, s: CGFloat, emotion: String) {
        let kind = ["happy": "open", "party": "happy", "hungry": "plead", "tired": "tired", "sleep": "sleep",
                    "sad": "open", "sick": "spiral"][emotion] ?? "open"
        eye(&c, cx - gap, ey, s, kind)
        eye(&c, cx + gap, ey, s, kind)
        brows(&c, cx: cx, ey: ey, gap: gap, s: s, emotion: emotion)
        if ["happy", "party", "hungry"].contains(emotion) {
            for d in [CGFloat(-1), 1] {
                c.fill(Path(ellipseIn: CGRect(x: cx + d * (gap + 12 * s) - 8 * s, y: ey + 20 * s - 5 * s, width: 16 * s, height: 10 * s)),
                       with: .color(P.blush.opacity(0.65)))
            }
        }
        let mouthKind = ["happy": "smile", "party": "grin", "hungry": "o", "tired": "wavy", "sick": "wavy", "sleep": "small",
                         "sad": "frown"][emotion] ?? "smile"
        mouth(&c, cx, ey + 30 * s, s, mouthKind)
        if emotion == "sad" {   // larme
            var tear = Path()
            let x = cx + gap + 8 * s, y = ey + 14 * s
            tear.move(to: pt(x, y))
            tear.addQuadCurve(to: pt(x, y + 14 * s), control: pt(x + 5 * s, y + 10 * s))
            tear.addQuadCurve(to: pt(x, y), control: pt(x - 5 * s, y + 10 * s))
            c.fill(tear, with: .color(P.cyan))
        }
    }

    static func eye(_ c: inout GraphicsContext, _ x: CGFloat, _ y: CGFloat, _ s: CGFloat, _ kind: String) {
        let sw = 3.5 * s
        switch kind {
        case "open", "plead":
            let white = Path(ellipseIn: CGRect(x: x - 13 * s, y: y - 15 * s, width: 26 * s, height: 30 * s))
            c.fill(white, with: .color(.white))
            c.stroke(white, with: .color(P.ink), lineWidth: sw)
            let py = y + 2 * s, pr = (kind == "plead" ? 9 : 7) * s
            ZicouPainter.circle(&c, x, py, pr, P.ink)
            ZicouPainter.circle(&c, x - 3 * s, py - 4 * s, 3 * s, .white)
            if kind == "plead" { ZicouPainter.circle(&c, x + 3 * s, py + 3 * s, 1.6 * s, .white) }
        case "happy":
            var p = Path()
            p.move(to: pt(x - 11 * s, y + 4 * s))
            p.addQuadCurve(to: pt(x + 11 * s, y + 4 * s), control: pt(x, y - 13 * s))
            ZicouPainter.line(&c, p, P.ink, 5 * s)
        case "sleep":
            var p = Path()
            p.move(to: pt(x - 11 * s, y))
            p.addQuadCurve(to: pt(x + 11 * s, y), control: pt(x, y + 10 * s))
            ZicouPainter.line(&c, p, P.ink, 5 * s)
        case "tired":
            var lid = Path()
            lid.addArc(center: pt(x, y), radius: 13 * s, startAngle: .degrees(0), endAngle: .degrees(180), clockwise: false)
            lid.closeSubpath()
            c.fill(lid, with: .color(.white))
            c.stroke(lid, with: .color(P.ink), lineWidth: sw)
            var pupil = Path()
            pupil.addArc(center: pt(x, y), radius: 5.5 * s, startAngle: .degrees(0), endAngle: .degrees(180), clockwise: false)
            c.fill(pupil, with: .color(P.ink))
            var bar = Path()
            bar.move(to: pt(x - 15 * s, y - s))
            bar.addLine(to: pt(x + 15 * s, y + 1.5 * s))
            ZicouPainter.line(&c, bar, P.ink, 5 * s)
        default:   // spirale (malade)
            for rr in [1.5, 4.5, 7.5] as [CGFloat] {
                c.stroke(Path(ellipseIn: CGRect(x: x - rr * s, y: y - rr * s, width: 2 * rr * s, height: 2 * rr * s)),
                         with: .color(P.ink), lineWidth: 2.5 * s)
            }
        }
    }

    static func brows(_ c: inout GraphicsContext, cx: CGFloat, ey: CGFloat, gap: CGFloat, s: CGFloat, emotion: String) {
        guard ["happy", "party", "hungry", "sad", "sick", "tired"].contains(emotion) else { return }
        let y = ey - 25 * s
        for d in [CGFloat(-1), 1] {
            let xi = cx + d * (gap - 11 * s), xo = cx + d * (gap + 11 * s), xm = (xi + xo) / 2
            var p = Path()
            switch emotion {
            case "happy", "party":
                let lift: CGFloat = emotion == "party" ? 9 : 6
                p.move(to: pt(xi, y))
                p.addQuadCurve(to: pt(xo, y + s), control: pt(xm, y - lift * s))
            case "hungry", "sad":
                p.move(to: pt(xi, y - 5 * s))
                p.addQuadCurve(to: pt(xo, y + 3 * s), control: pt(xm, y - 3 * s))
            default:
                p.move(to: pt(xi, y + 4 * s))
                p.addLine(to: pt(xo, y + 4 * s))
            }
            ZicouPainter.line(&c, p, P.ink, 4.5 * s)
        }
    }

    /// Bouche cerclée d'un liseré clair (lisible sur les facettes sombres).
    static func mouth(_ c: inout GraphicsContext, _ x: CGFloat, _ y: CGFloat, _ s: CGFloat, _ kind: String) {
        func halo(_ p: Path, _ w: CGFloat) {
            ZicouPainter.line(&c, p, P.halo, w + 7 * s)
            ZicouPainter.line(&c, p, P.ink, w)
        }
        var p = Path()
        switch kind {
        case "smile":
            p.move(to: pt(x - 13 * s, y))
            p.addQuadCurve(to: pt(x + 13 * s, y), control: pt(x, y + 13 * s))
            halo(p, 5 * s)
        case "wavy":
            p.move(to: pt(x - 12 * s, y + 2 * s))
            p.addQuadCurve(to: pt(x, y + 2 * s), control: pt(x - 6 * s, y - 3 * s))
            p.addQuadCurve(to: pt(x + 12 * s, y + 2 * s), control: pt(x + 6 * s, y + 7 * s))
            halo(p, 4.5 * s)
        case "frown":
            p.move(to: pt(x - 12 * s, y + 8 * s))
            p.addQuadCurve(to: pt(x + 12 * s, y + 8 * s), control: pt(x, y - 4 * s))
            halo(p, 4.5 * s)
        case "grin":
            p.move(to: pt(x - 18 * s, y))
            p.addQuadCurve(to: pt(x + 18 * s, y), control: pt(x, y + 32 * s))
            p.closeSubpath()
            c.fill(p, with: .color(P.halo))
            c.stroke(p, with: .color(P.halo), style: StrokeStyle(lineWidth: 11 * s, lineJoin: .round))
            c.fill(p, with: .color(P.ink))
            c.stroke(p, with: .color(P.ink), style: StrokeStyle(lineWidth: 4 * s, lineJoin: .round))
            c.fill(Path(ellipseIn: CGRect(x: x - 7 * s, y: y + 6 * s, width: 14 * s, height: 8 * s)), with: .color(P.blush))
        default:   // « o » (faim) ou petite bouche (sommeil)
            let small = kind == "small"
            let ry: CGFloat = small ? 6 : 9, rx: CGFloat = small ? 5 : 7, oy: CGFloat = small ? 3 : 4
            c.fill(Path(ellipseIn: CGRect(x: x - (rx + 3.5) * s, y: y + oy * s - (ry + 3.5) * s, width: 2 * (rx + 3.5) * s, height: 2 * (ry + 3.5) * s)),
                   with: .color(P.halo))
            c.fill(Path(ellipseIn: CGRect(x: x - rx * s, y: y + oy * s - ry * s, width: 2 * rx * s, height: 2 * ry * s)), with: .color(P.ink))
        }
    }
}

/// Tenues d'origine de Zicou (app/static/pet/skin.js OUTFITS), dessinées depuis les mêmes points d'ancrage.
enum ZicouOutfits {
    typealias P = ZicouPalette
    /// Coiffes posées SOUS l'arceau du casque.
    static let under: Set<String> = ["casquette", "bonnet"]
    private static func pt(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: x, y: y) }

    static func outlined(_ c: inout GraphicsContext, _ p: Path, _ fill: Color, _ width: CGFloat = 5) {
        c.fill(p, with: .color(fill))
        c.stroke(p, with: .color(P.ink), style: StrokeStyle(lineWidth: width, lineJoin: .round))
    }

    static func head(_ c: inout GraphicsContext, _ id: String, cx: CGFloat, cy: CGFloat, r: CGFloat) {
        let x = cx, y = cy - r   // sommet de la boule
        switch id {
        case "couronne":
            let w = r * 0.3, top = cy - r * 0.98 - r * 0.07 - 8
            var p = Path()
            p.addLines([pt(x - w, top), pt(x - w, top - w * 0.9), pt(x - w / 2, top - w * 0.4), pt(x, top - w * 1.15),
                        pt(x + w / 2, top - w * 0.4), pt(x + w, top - w * 0.9), pt(x + w, top)])
            p.closeSubpath()
            outlined(&c, p, P.gold, 4.5)
            ZicouPainter.circle(&c, x, top - w * 0.35, w * 0.16, P.neon)
        case "chapeau":
            let hx = x - r * 0.42, hy = y + r * 0.16, h = r * 0.7
            var hat = c
            hat.translateBy(x: hx, y: hy)
            hat.rotate(by: .degrees(-18))
            var p = Path()
            p.addLines([pt(-h * 0.33, 0), pt(0, -h), pt(h * 0.33, 0)])
            p.closeSubpath()
            outlined(&hat, p, P.neon, 4.5)
            ZicouPainter.circle(&hat, -5, -h * 0.35, 4, P.amber)
            ZicouPainter.circle(&hat, 4, -h * 0.6, 4, P.cyan)
            ZicouPainter.circle(&hat, 0, -h, 8, P.amber, stroke: P.ink, width: 3.5)
        case "casquette":
            var p = Path()
            p.move(to: pt(x - r * 0.74, y + r * 0.42))
            p.addQuadCurve(to: pt(x + r * 0.74, y + r * 0.42), control: pt(x, y - r * 0.32))
            p.closeSubpath()
            outlined(&c, p, P.cyan)
            var visor = Path()
            visor.addRoundedRect(in: CGRect(x: x + r * 0.3, y: y + r * 0.4, width: r * 0.8, height: 8), cornerSize: CGSize(width: 4, height: 4))
            outlined(&c, visor, P.hex(0x38bcd8))
        case "bonnet":
            var p = Path()
            p.move(to: pt(x - r * 0.78, y + r * 0.5))
            p.addQuadCurve(to: pt(x, y - r * 0.28), control: pt(x - r * 0.8, y - r * 0.26))
            p.addQuadCurve(to: pt(x + r * 0.78, y + r * 0.5), control: pt(x + r * 0.8, y - r * 0.26))
            p.closeSubpath()
            outlined(&c, p, P.cyan)
            var rim = Path()
            rim.move(to: pt(x - r * 0.8, y + r * 0.42))
            rim.addQuadCurve(to: pt(x + r * 0.8, y + r * 0.42), control: pt(x, y + r * 0.2))
            ZicouPainter.line(&c, rim, P.chalk, r * 0.14)
            ZicouPainter.circle(&c, x, y - r * 0.3, r * 0.16, P.neon, stroke: P.ink, width: 4)
        case "aureole":
            let top = cy - r * 0.98 - r * 0.07 - 8 - 18
            c.stroke(Path(ellipseIn: CGRect(x: x - r * 0.45, y: top - r * 0.11, width: r * 0.9, height: r * 0.22)),
                     with: .color(P.gold), lineWidth: 6)
        default:
            break   // « casque » : le casque doré (ZicouPainter.headset) ; autres coiffes : pas encore dessinées sur la télé
        }
    }

    static func glasses(_ c: inout GraphicsContext, cx: CGFloat, ey: CGFloat, gap: CGFloat, s: CGFloat) {
        let w = 13 * s * 1.45, h = 15 * s * 0.9
        for x in [cx - gap, cx + gap] {
            let lens = Path(roundedRect: CGRect(x: x - w, y: ey - h, width: 2 * w, height: 2 * h), cornerRadius: h * 0.75)
            outlined(&c, lens, P.hex(0x120a26), 4)
            var glint = Path()
            glint.move(to: pt(x - w * 0.6, ey - h * 0.45))
            glint.addLine(to: pt(x - w * 0.1, ey - h * 0.45))
            ZicouPainter.line(&c, glint, P.cyan, 4)
        }
        var bridge = Path()
        bridge.move(to: pt(cx - gap + w, ey - h * 0.3))
        bridge.addLine(to: pt(cx + gap - w, ey - h * 0.3))
        c.stroke(bridge, with: .color(P.ink), lineWidth: 5)
    }

    static func neck(_ c: inout GraphicsContext, _ id: String, cx: CGFloat, cy: CGFloat, r: CGFloat) {
        switch id {
        case "noeud":
            let k = r / 57, y = cy + r * 0.92 + 2
            var bow = c
            bow.translateBy(x: cx, y: y)
            bow.scaleBy(x: k, y: k)
            var p = Path()
            p.addLines([pt(0, 0), pt(-13, -7), pt(-13, 7)])
            p.closeSubpath()
            p.addLines([pt(0, 0), pt(13, -7), pt(13, 7)])
            p.closeSubpath()
            outlined(&bow, p, P.neon, 2)
            ZicouPainter.circle(&bow, 0, 0, 4, P.amber, stroke: P.ink, width: 2)
        case "boa":
            for i in 0..<13 {
                let t = Double.pi * (0.1 + 0.8 * Double(i) / 12)
                let px = cx - CGFloat(cos(t)) * r * 0.95, py = cy + CGFloat(sin(t)) * r * 0.9
                ZicouPainter.circle(&c, px, py, r * 0.11, [P.cyan, P.neon, P.amber][i % 3], stroke: P.ink, width: 3)
            }
        case "echarpe":
            let by = cy + r * 0.72, w = r * 0.86
            var p = Path()
            p.move(to: pt(cx - w, by - r * 0.08))
            p.addQuadCurve(to: pt(cx + w, by - r * 0.08), control: pt(cx, by + r * 0.26))
            p.addLine(to: pt(cx + w * 0.92, by + r * 0.14))
            p.addQuadCurve(to: pt(cx - w * 0.92, by + r * 0.14), control: pt(cx, by + r * 0.46))
            p.closeSubpath()
            outlined(&c, p, P.neon, 4)
        default:
            break
        }
    }

    static func cape(_ c: inout GraphicsContext, cx: CGFloat, cy: CGFloat, r: CGFloat) {
        let ground: CGFloat = 378
        var p = Path()
        p.move(to: pt(cx - r * 0.7, cy - r * 0.2))
        p.addQuadCurve(to: pt(cx - r * 1.2, ground - 8), control: pt(cx - r * 1.5, ground - 16))
        p.addLine(to: pt(cx + r * 1.2, ground - 8))
        p.addQuadCurve(to: pt(cx + r * 0.7, cy - r * 0.2), control: pt(cx + r * 1.5, ground - 16))
        p.closeSubpath()
        outlined(&c, p, P.hex(0xe0315f))
    }
}
