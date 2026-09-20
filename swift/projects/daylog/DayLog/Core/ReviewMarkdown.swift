import Foundation

/// A deliberately small reading format: paragraphs, headings, lists and code.
/// No HTML/web view, remote images or executable content are involved.
public struct ReviewMarkdownBlock: Equatable, Sendable {
    public enum Kind: Equatable, Sendable {case paragraph, heading(Int), item(String), code}
    public var kind: Kind
    public var text: String
}
public enum ReviewMarkdown {
    public static func blocks(_ source: String) -> [ReviewMarkdownBlock] {
        var result: [ReviewMarkdownBlock] = [], pending: [String] = []
        var inCode=false
        func flush(_ kind: ReviewMarkdownBlock.Kind = .paragraph) {
            if !pending.isEmpty {result.append(.init(kind:kind,text:pending.joined(separator:"\n"))); pending=[]}
        }
        for raw in source.components(separatedBy:.newlines) {
            let line=raw.trimmingCharacters(in:.whitespaces)
            if line.hasPrefix("```") {flush(inCode ? .code : .paragraph); inCode.toggle(); continue}
            if inCode {pending.append(raw); continue}
            if line.isEmpty {flush(); continue}
            let hashes=line.prefix(while:{$0 == "#"}).count
            if (1...6).contains(hashes), line.dropFirst(hashes).hasPrefix(" ") {
                flush(); result.append(.init(kind:.heading(hashes),text:String(line.dropFirst(hashes+1)))); continue
            }
            if ["- ","* ","+ "].contains(where:line.hasPrefix) {
                flush(); result.append(.init(kind:.item("•"),text:String(line.dropFirst(2)))); continue
            }
            let digits=line.prefix(while:{$0.isNumber})
            if !digits.isEmpty, line.dropFirst(digits.count).hasPrefix(". ") {
                flush(); result.append(.init(kind:.item(String(digits)+"."),text:String(line.dropFirst(digits.count+2)))); continue
            }
            pending.append(raw)
        }
        flush(inCode ? .code : .paragraph)
        return result
    }
    public static func inline(_ source: String) -> AttributedString {
        var result=(try? AttributedString(markdown:source,options:.init(interpretedSyntax:.inlineOnlyPreservingWhitespace))) ?? AttributedString(source)
        // Render link labels as text; model output cannot open file/custom URLs.
        for run in result.runs where run.link != nil {result[run.range].link=nil}
        return result
    }
}
