plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "0.5.0"
}

rootProject.name = "xlab"

include("framework")
include("itest")
include("benchmark")
include("xlab-groovy")
