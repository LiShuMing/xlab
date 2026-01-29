# Java Lab (java)

## Overview
Java laboratory for enterprise applications, Android development, and object-oriented design patterns.

## Build System
- **Build Tool**: Gradle (primary), Maven (some projects)
- **JDK**: Modern Java versions (check `build.gradle`)
- **Test Tool**: JUnit 5, TestNG
- **IDE**: IntelliJ IDEA (`.idea/` directory present)

## Project Structure
```
java/
├── hello/           # Hello world / learning
└── (projects)       # Various Java projects
```

## Key Concepts
- **OOP**: Classes, inheritance, polymorphism, encapsulation
- **Generics**: Type-safe containers and methods
- **Collections**: `List`, `Set`, `Map` hierarchies
- **Streams**: Functional-style data processing
- **Concurrency**: `ExecutorService`, `CompletableFuture`
- **JVM**: Memory model, garbage collection

## Coding Conventions
- Use standard Java naming conventions
- Classes: `PascalCase`
- Methods/variables: `camelCase`
- Constants: `SCREAMING_SNAKE_CASE`
- Prefer interfaces over concrete implementations
- Use `try-with-resources` for auto-closeable resources
- Annotations: `@Override`, `@FunctionalInterface`
- Record classes for immutable data

## AI Vibe Coding Tips
- Use `var` for local variable type inference (Java 10+)
- Prefer `List.of()`, `Set.of()`, `Map.of()` for immutability
- Use `Optional` to represent nullable values
- Stream API: avoid stateful lambdas
- Parallel streams for CPU-intensive operations
- Use `java.time` API (not `Date`, `Calendar`)
- Dependency injection for testability
- Consider `Lombok` for boilerplate reduction
- Profile with VisualVM or Java Mission Control
