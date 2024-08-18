plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "0.5.0"
}

rootProject.name = "xlab"

include("xlab-framework")
include("xlab-itest")
include("xlab-benchmark")
include("xlab-groovy")
