import Foundation
import Security
import DayLogCore

@MainActor enum ConfigStore {
    private static let service = "app.daylog.llm"
    private static let account = "active-profile"
    // Store the complete imported profile together in Keychain so URL/key cannot be mixed.
    static func imported() throws -> LLMConfig? {
        let query: [String:Any] = [kSecClass as String:kSecClassGenericPassword,kSecAttrService as String:service,kSecAttrAccount as String:account,kSecReturnData as String:true,kSecMatchLimit as String:kSecMatchLimitOne]
        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary,&result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = result as? Data, let values = try? JSONDecoder().decode([String:String].self,from:data) else { throw LLMError.config("无法读取 Keychain 配置") }
        return try LLMConfig(values:values)
    }
    static func save(text: String) throws -> LLMConfig {
        let values = try DotEnv.parse(text), config = try LLMConfig(values:values)
        let data = try JSONEncoder().encode(values)
        let query: [String:Any] = [kSecClass as String:kSecClassGenericPassword,kSecAttrService as String:service,kSecAttrAccount as String:account]
        let update = SecItemUpdate(query as CFDictionary,[kSecValueData as String:data] as CFDictionary)
        if update == errSecItemNotFound {
            var insert = query; insert[kSecValueData as String] = data; insert[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
            guard SecItemAdd(insert as CFDictionary,nil) == errSecSuccess else { throw LLMError.config("无法保存到 Keychain") }
        } else if update != errSecSuccess { throw LLMError.config("无法更新 Keychain") }
        return config
    }
    static func remove() throws {
        let status = SecItemDelete([kSecClass as String:kSecClassGenericPassword,kSecAttrService as String:service,kSecAttrAccount as String:account] as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else { throw LLMError.config("无法删除应用配置") }
    }
}
