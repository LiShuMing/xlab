# BUILD
cc_binary(
    name = "calculator",
    srcs = ["main.cc"],
    deps = [
        "//:math_util",
        "@fmt//:fmt",
    ],
    copts = ["-std=c++17"],
)

cc_library(
    name = "math_util",
    srcs = ["math_util.cc"],
    hdrs = ["math_util.h"],
    visibility = ["//visibility:public"],
    copts = ["-std=c++17"],
)
