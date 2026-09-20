import SwiftUI
import AppKit

extension Notification.Name { static let dayLogOpenWindow = Notification.Name("DayLogOpenWindow") }

/// Bright brand surfaces; saturated colors are reserved for actionable details.
enum Design {
    private static func adaptive(_ light: UInt32, _ dark: UInt32) -> Color {
        Color(nsColor: NSColor(name: nil) { appearance in
            let hex = appearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua ? dark : light
            return NSColor(srgbRed: Double((hex >> 16) & 255) / 255,
                           green: Double((hex >> 8) & 255) / 255,
                           blue: Double(hex & 255) / 255, alpha: 1)
        })
    }
    static let accent = adaptive(0x2464C5, 0x91BEFF)
    static let sky = adaptive(0x5499F3, 0x84B5FA)
    static let apricot = adaptive(0xFFBD8A, 0xEDB489)
    static let canvas = adaptive(0xF5F8FD, 0x171F2C)
    static let panel = adaptive(0xFFFFFF, 0x222D3D)
    static let sidebar = adaptive(0xECF3FF, 0x1C293C)
    static let selected = adaptive(0xDCEBFF, 0x283F61)
    static let focus = adaptive(0xFFF2E5, 0x352D2A)
    static let line = adaptive(0xD9E3F0, 0x3B4A60)
    static let success = adaptive(0x20745A, 0x7CD5AD)
}

/// A simplified K retains the three folded planes without raster detail.
struct KebaiFacet: Shape {
    let index: Int
    func path(in rect: CGRect) -> Path {
        let points: [[CGPoint]] = [
            [.init(x:0.12,y:0.23), .init(x:0.37,y:0.08), .init(x:0.37,y:0.78), .init(x:0.12,y:0.93)],
            [.init(x:0.43,y:0.29), .init(x:0.88,y:0.09), .init(x:0.88,y:0.33), .init(x:0.43,y:0.53)],
            [.init(x:0.43,y:0.59), .init(x:0.88,y:0.83), .init(x:0.88,y:0.98), .init(x:0.43,y:0.75)]
        ]
        return Path { path in
            let polygon = points[index].map {CGPoint(x:rect.minX+$0.x*rect.width,y:rect.minY+$0.y*rect.height)}
            let radius = min(rect.width,rect.height) * 0.025
            func toward(_ a: CGPoint, _ b: CGPoint) -> CGPoint {
                let distance = hypot(b.x-a.x,b.y-a.y)
                let scale = min(radius / max(distance,0.001),0.3)
                return CGPoint(x:a.x+(b.x-a.x)*scale,y:a.y+(b.y-a.y)*scale)
            }
            for i in polygon.indices {
                let corner=polygon[i]
                let start=toward(corner,polygon[(i+polygon.count-1)%polygon.count])
                let end=toward(corner,polygon[(i+1)%polygon.count])
                if i == 0 {path.move(to:start)} else {path.addLine(to:start)}
                path.addQuadCurve(to:end,control:corner)
            }
            path.closeSubpath()
        }
    }
}

/// Deterministic production artwork from the same paths as the UI mark.
/// Pure SwiftUI drawing provides clean alpha at every exported AppIcon size.
struct KebaiAppIcon: View {
    var body: some View {
        GeometryReader { geometry in
            let side=min(geometry.size.width,geometry.size.height)
            ZStack {
                RoundedRectangle(cornerRadius:side*0.19,style:.continuous)
                    .fill(LinearGradient(colors:[Color(red:0.91,green:0.97,blue:1),.white,Color(red:1,green:0.96,blue:0.90)],startPoint:.topLeading,endPoint:.bottomTrailing))
                    .overlay(RoundedRectangle(cornerRadius:side*0.19,style:.continuous).strokeBorder(.white.opacity(0.9),lineWidth:side*0.003))
                    .shadow(color:Color(red:0.29,green:0.45,blue:0.64).opacity(0.15),radius:side*0.012,y:side*0.008)
                ZStack {
                    KebaiFacet(index:0).fill(LinearGradient(colors:[Color(red:0.40,green:0.69,blue:1),Color(red:0.19,green:0.46,blue:0.87)],startPoint:.topLeading,endPoint:.bottomTrailing))
                    KebaiFacet(index:1).fill(LinearGradient(colors:[Color(red:0.56,green:0.79,blue:1),Color(red:0.28,green:0.57,blue:0.93)],startPoint:.topLeading,endPoint:.bottomTrailing))
                    KebaiFacet(index:2).fill(LinearGradient(colors:[Color(red:1,green:0.85,blue:0.66),Color(red:1,green:0.65,blue:0.42)],startPoint:.topLeading,endPoint:.bottomTrailing))
                    ForEach(0..<3,id:\.self) { index in
                        KebaiFacet(index:index).stroke(.white.opacity(0.55),lineWidth:side*0.002)
                    }
                }.padding(side*0.12)
                    .shadow(color:Color(red:0.22,green:0.34,blue:0.52).opacity(0.19),radius:side*0.009,y:side*0.008)
            }.padding(side*0.065)
        }
    }
}

struct KebaiMark: View {
    var monochrome = false
    var body: some View {
        ZStack {
            KebaiFacet(index:0).fill(monochrome ? Color.primary : Design.accent)
            KebaiFacet(index:1).fill(monochrome ? Color.primary : Design.sky)
            KebaiFacet(index:2).fill(monochrome ? Color.primary : Design.apricot)
        }.accessibilityHidden(true)
    }
}

struct KebaiBadge: View {
    var body: some View {
        KebaiMark().padding(7).frame(width:36,height:36)
            .background(Design.panel,in:RoundedRectangle(cornerRadius:11))
            .overlay(RoundedRectangle(cornerRadius:11).stroke(Design.line,lineWidth:0.5))
            .accessibilityLabel("刻白")
    }
}

struct BrandAppearance: ViewModifier {
    @AppStorage("appearance") private var appearance = "system"
    func body(content: Content) -> some View {
        content.tint(Design.accent)
            .preferredColorScheme(appearance == "system" ? nil : appearance == "dark" ? .dark : .light)
    }
}
