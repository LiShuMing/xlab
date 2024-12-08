plugins {
    kotlin("jvm") version "1.9.20"
}

group = "com.starrocks.itest"
version = "1.1.0"

repositories {
    mavenCentral()
}

dependencies {

    implementation(libs.guava)
    implementation("org.springframework:spring-jdbc:5.2.8.RELEASE")
    implementation("mysql:mysql-connector-java:5.1.49")
    implementation("org.slf4j:slf4j-log4j12:1.7.21")
    implementation("log4j:log4j:1.2.16")
    implementation("org.antlr:stringtemplate:4.0.2")
    implementation("com.fasterxml.jackson.module:jackson-module-kotlin:2.11.2")
    implementation("com.fasterxml.jackson.dataformat:jackson-dataformat-yaml:2.11.2")

    implementation("org.jetbrains.kotlin:kotlin-test-junit5")
    implementation(libs.junit.jupiter.engine)
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

tasks.test {
    useJUnitPlatform()
}

kotlin {
    jvmToolchain(17)
}