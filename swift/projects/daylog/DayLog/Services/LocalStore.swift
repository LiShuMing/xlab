import Foundation
import CoreData
import DayLogCore

protocol WorkspaceStorage: Sendable {
    func load() async throws -> Workspace
    func save(_ state: Workspace) async throws
}

/// Owns encoding, validation and SQLite I/O away from MainActor. The Core Data
/// model is unchanged, so existing v1 documents need no migration or rewrite.
actor LocalStore: WorkspaceStorage {
    private let inMemory: Bool
    private let directory: URL?
    private var context: NSManagedObjectContext?

    init(inMemory: Bool = false, directory: URL? = nil) {
        self.inMemory = inMemory; self.directory = directory
    }
    private func open() throws -> NSManagedObjectContext {
        if let context { return context }
        let model = NSManagedObjectModel()
        let entity = NSEntityDescription(); entity.name = "WorkspaceDocument"; entity.managedObjectClassName = "NSManagedObject"
        let key = NSAttributeDescription(); key.name = "key"; key.attributeType = .stringAttributeType; key.isOptional = false
        let payload = NSAttributeDescription(); payload.name = "payload"; payload.attributeType = .binaryDataAttributeType; payload.isOptional = false
        entity.properties = [key,payload]; entity.uniquenessConstraints = [["key"]]; model.entities = [entity]
        let coordinator = NSPersistentStoreCoordinator(managedObjectModel:model)
        var url: URL?
        if !inMemory {
            let folder = try directory ?? FileManager.default.url(for:.applicationSupportDirectory,in:.userDomainMask,appropriateFor:nil,create:true).appendingPathComponent("DayLog",isDirectory:true)
            try FileManager.default.createDirectory(at:folder,withIntermediateDirectories:true)
            url = folder.appendingPathComponent("DayLog.sqlite")
        }
        try coordinator.addPersistentStore(ofType:inMemory ? NSInMemoryStoreType : NSSQLiteStoreType,configurationName:nil,at:url,options:[NSMigratePersistentStoresAutomaticallyOption:true,NSInferMappingModelAutomaticallyOption:true])
        let context = NSManagedObjectContext(concurrencyType:.privateQueueConcurrencyType)
        context.persistentStoreCoordinator = coordinator
        self.context = context
        return context
    }
    func load() throws -> Workspace {
        let context = try open()
        let data: Data? = try context.performAndWait {
            guard let record = try context.fetch(NSFetchRequest<NSManagedObject>(entityName:"WorkspaceDocument")).first else { return nil }
            guard let data = record.value(forKey:"payload") as? Data else {throw DomainError.invalid("Missing workspace payload")}
            return data
        }
        guard let data else { return Workspace() }
        return try Workspace.decode(data)
    }
    func save(_ state: Workspace) throws {
        try state.validate()
        let data = try state.encoded(pretty:false)
        let context = try open()
        try context.performAndWait {
            do {
                let record = try context.fetch(NSFetchRequest<NSManagedObject>(entityName:"WorkspaceDocument")).first ?? NSEntityDescription.insertNewObject(forEntityName:"WorkspaceDocument",into:context)
                record.setValue("workspace-v1",forKey:"key"); record.setValue(data,forKey:"payload")
                try context.save()
            } catch {context.rollback(); throw error}
        }
    }
}
