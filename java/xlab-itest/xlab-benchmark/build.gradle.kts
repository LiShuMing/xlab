plugins {
    kotlin("jvm") version "1.9.20"
}

group = "org.example"
version = "unspecified"

repositories {
    mavenCentral()
}

dependencies {
    implementation(project(":xlab-framework"))

    implementation(libs.guava)
    implementation("mysql:mysql-connector-java:5.1.49")
    implementation("org.slf4j:slf4j-log4j12:1.7.21")
    implementation("log4j:log4j:1.2.16")
    implementation("org.antlr:stringtemplate:4.0.2")

    testImplementation("org.jetbrains.kotlin:kotlin-test-junit5")
    testImplementation(libs.junit.jupiter.engine)
    testImplementation("org.jetbrains.kotlin:kotlin-test")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
    testImplementation("org.junit.jupiter:junit-jupiter-params:5.3.2")
    testImplementation("com.carrotsearch:junit-benchmarks:0.7.2")
}

tasks.test {
    useJUnitPlatform()
}
kotlin {
    jvmToolchain(17)
}