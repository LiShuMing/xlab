import Foundation

public enum LLMError: Error, LocalizedError, Equatable {
    case config(String), http(Int), transport, timeout, invalidResponse
    public var errorDescription: String? {
        switch self {
        case .config(let message): message
        case .http(let code): "模型服务返回 HTTP \(code)。请检查地址、凭据与模型配置。"
        case .transport: "无法连接模型服务，请检查网络或配置。"
        case .timeout: "模型请求超时，请稍后重试。"
        case .invalidResponse: "服务响应不符合 Chat Completions 协议。"
        }
    }
}
public struct LLMConfig: Sendable, CustomStringConvertible {
    public var baseURL: URL
    public var apiKey: String
    public var model: String
    public var timeout: TimeInterval
    public var description: String { "LLMConfig([redacted])" }
    public static let keys: Set<String> = ["LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "LLM_TIMEOUT"]
    public init(values: [String:String]) throws {
        for key in Self.keys where values[key]?.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty != false { throw LLMError.config("缺少配置：\(key)") }
        let base = values["LLM_BASE_URL"]!.trimmingCharacters(in:.whitespacesAndNewlines)
        guard let url = URL(string:base), url.scheme == "https", url.host != nil,
              url.user == nil, url.password == nil, url.query == nil, url.fragment == nil,
              !url.path.hasSuffix("/chat/completions"), !url.path.hasSuffix("/responses") else { throw LLMError.config("LLM_BASE_URL 应为不含认证信息的 HTTPS API 根地址") }
        let key = values["LLM_API_KEY"]!
        guard !key.contains("\n"), !key.contains("\r") else { throw LLMError.config("LLM_API_KEY 包含非法换行") }
        guard let timeout = Double(values["LLM_TIMEOUT"]!), timeout.isFinite, (1...600).contains(timeout) else { throw LLMError.config("LLM_TIMEOUT 应为 1–600 秒") }
        self.baseURL = url; self.apiKey = key; self.model = values["LLM_MODEL"]!.trimmingCharacters(in:.whitespacesAndNewlines); self.timeout = timeout
    }
    public var endpoint: URL { baseURL.appendingPathComponent("chat/completions") }
}
public enum DotEnv {
    public static func parse(_ text: String) throws -> [String:String] {
        var result: [String:String] = [:]
        let text = text.hasPrefix("\u{feff}") ? String(text.dropFirst()) : text
        for (index, rawLine) in text.components(separatedBy:.newlines).enumerated() {
            var line = rawLine.trimmingCharacters(in:.whitespaces)
            if line.hasPrefix("export ") { line = String(line.dropFirst(7)).trimmingCharacters(in:.whitespaces) }
            guard !line.isEmpty, !line.hasPrefix("#"), let eq = line.firstIndex(of:"=") else { continue }
            let key = String(line[..<eq]).trimmingCharacters(in:.whitespaces)
            guard LLMConfig.keys.contains(key) else { continue }
            func invalid() -> LLMError { .config("配置第 \(index+1) 行（\(key)）格式无效") }
            guard result[key] == nil else { throw LLMError.config("重复配置：\(key)") }
            let raw = String(line[line.index(after:eq)...]).trimmingCharacters(in:.whitespaces)
            var value = ""
            if let quote = raw.first, quote == "\"" || quote == "'" {
                var cursor = raw.index(after:raw.startIndex), closed = false
                while cursor < raw.endIndex {
                    let char = raw[cursor]; cursor = raw.index(after:cursor)
                    if char == quote { closed = true; break }
                    if quote == "\"", char == "\\" {
                        guard cursor < raw.endIndex else { throw invalid() }
                        let next = raw[cursor]; cursor = raw.index(after:cursor)
                        switch next { case "\\": value.append("\\"); case "\"": value.append("\""); case "n": value.append("\n"); case "t": value.append("\t"); case "r": value.append("\r"); default: throw invalid() }
                    } else { value.append(char) }
                }
                guard closed else { throw invalid() }
                let tail = raw[cursor...].trimmingCharacters(in:.whitespaces)
                guard tail.isEmpty || tail.hasPrefix("#") else { throw invalid() }
            } else {
                var previous: Character?
                for char in raw {
                    if char == "#" && (previous?.isWhitespace ?? true) { break }
                    value.append(char); previous = char
                }
                value = value.trimmingCharacters(in:.whitespaces)
            }
            guard !value.contains("${"), !value.contains("$("), !value.contains("`") else { throw invalid() }
            result[key] = value
        }
        return result
    }
    public static func loadDefault(environment: [String:String] = ProcessInfo.processInfo.environment, home: URL = FileManager.default.homeDirectoryForCurrentUser) throws -> LLMConfig {
        let provided = environment.filter { LLMConfig.keys.contains($0.key) }
        if !provided.isEmpty { return try LLMConfig(values:provided) }
        let file = home.appendingPathComponent(".env")
        guard let data = try? Data(contentsOf:file), let text = String(data:data,encoding:.utf8) else { throw LLMError.config("未能读取 ~/.env，请在设置中导入配置文件") }
        return try LLMConfig(values:parse(text))
    }
}

private final class NoRedirect: NSObject, URLSessionTaskDelegate, Sendable {
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest, completionHandler: @escaping @Sendable (URLRequest?) -> Void) { completionHandler(nil) }
}
public enum LLMClient {
    public static func generate(config: LLMConfig, system: String, prompt: String, test: Bool = false) async throws -> String {
        struct Message: Encodable { let role: String; let content: String }
        struct Body: Encodable { let model: String; let messages: [Message]; let stream: Bool; let max_tokens: Int? }
        var request = URLRequest(url:config.endpoint)
        request.httpMethod = "POST"
        request.setValue("Bearer \(config.apiKey)", forHTTPHeaderField:"Authorization")
        request.setValue("application/json", forHTTPHeaderField:"Content-Type")
        request.httpBody = try JSONEncoder().encode(Body(model:config.model, messages:[Message(role:"system",content:system),Message(role:"user",content:prompt)],stream:false,max_tokens:test ? 16 : nil))
        let sessionConfig = URLSessionConfiguration.ephemeral
        sessionConfig.timeoutIntervalForRequest = config.timeout; sessionConfig.timeoutIntervalForResource = config.timeout
        sessionConfig.httpCookieStorage = nil; sessionConfig.urlCache = nil
        let session = URLSession(configuration:sessionConfig,delegate:NoRedirect(),delegateQueue:nil)
        let preparedRequest = request
        defer { session.invalidateAndCancel() }
        do {
            return try await withThrowingTaskGroup(of:String.self) { group in
                group.addTask {
                    let (data,response) = try await session.data(for:preparedRequest)
                    guard let response = response as? HTTPURLResponse else { throw LLMError.invalidResponse }
                    guard (200..<300).contains(response.statusCode) else { throw LLMError.http(response.statusCode) }
                    guard data.count <= 4_000_000 else { throw LLMError.invalidResponse }
                    struct Response: Decodable { struct Choice: Decodable { struct Message: Decodable { let content: String? }; let message: Message }; let choices: [Choice] }
                    guard let decoded = try? JSONDecoder().decode(Response.self,from:data), let content = decoded.choices.first?.message.content, !content.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty else { throw LLMError.invalidResponse }
                    return content
                }
                group.addTask { try await Task.sleep(for:.seconds(config.timeout)); throw LLMError.timeout }
                defer { group.cancelAll() }
                guard let result = try await group.next() else { throw LLMError.invalidResponse }
                return result
            }
        } catch is CancellationError { throw CancellationError() }
        catch let error as LLMError { throw error }
        catch let error as URLError {
            if error.code == .cancelled { throw CancellationError() }
            throw error.code == .timedOut ? LLMError.timeout : LLMError.transport
        } catch { throw LLMError.transport }
    }
}
