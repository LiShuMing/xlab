#!/usr/bin/env bash
set -euo pipefail
DAYLOG_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$DAYLOG_ROOT"

# Respect explicit selection, then the active developer directory. A single
# installed Xcode is unambiguous even when xcode-select still points to CLT.
if [[ -z "${DEVELOPER_DIR:-}" ]]; then
    DAYLOG_DEVELOPER="$(xcode-select -p 2>/dev/null || true)"
    if [[ ! -x "$DAYLOG_DEVELOPER/usr/bin/xcodebuild" ]]; then
        shopt -s nullglob
        DAYLOG_XCODES=(/Applications/Xcode*.app/Contents/Developer)
        shopt -u nullglob
        if [[ ${#DAYLOG_XCODES[@]} -ne 1 ]]; then
            echo '请用 DEVELOPER_DIR 指定完整 Xcode 的 Contents/Developer 路径。' >&2
            exit 1
        fi
        DAYLOG_DEVELOPER="${DAYLOG_XCODES[0]}"
    fi
    export DEVELOPER_DIR="$DAYLOG_DEVELOPER"
fi
if [[ ! -x "$DEVELOPER_DIR/usr/bin/xcodebuild" ]]; then
    echo 'DEVELOPER_DIR 未指向完整 Xcode。' >&2
    exit 1
fi

DAYLOG_ACTION="${1:-open}"
if [[ "$DAYLOG_ACTION" == generate ]]; then
    if ! command -v xcodegen >/dev/null; then
        echo '重新生成工程需要 XcodeGen：brew install xcodegen' >&2
        exit 1
    fi
    exec xcodegen generate
fi
if [[ "$DAYLOG_ACTION" == open ]]; then
    exec open -a "${DEVELOPER_DIR%/Contents/Developer}" DayLog.xcodeproj
fi
if [[ "$DAYLOG_ACTION" == render ]]; then
    DAYLOG_RENDER_DIR="${2:-$DAYLOG_ROOT/build/qa/appearance}"
    xcodebuild -project DayLog.xcodeproj -target KebaiAppearanceChecks -configuration Debug \
        "CONFIGURATION_BUILD_DIR=$DAYLOG_ROOT/build/Appearance" build
    exec "$DAYLOG_ROOT/build/Appearance/KebaiAppearanceChecks" "$DAYLOG_RENDER_DIR"
fi
case "$DAYLOG_ACTION" in
    build|test|run|release) ;;
    *) echo '用法: ./scripts/xcode.sh [open|build|test|run|release|generate|render [目录]]' >&2; exit 2 ;;
esac
DAYLOG_CONFIGURATION=Debug
[[ "$DAYLOG_ACTION" != release ]] || DAYLOG_CONFIGURATION=Release
DAYLOG_BUILD_ACTION=build
[[ "$DAYLOG_ACTION" != test ]] || DAYLOG_BUILD_ACTION=test
DAYLOG_ARGS=(-project DayLog.xcodeproj -scheme DayLog -configuration "$DAYLOG_CONFIGURATION"
    -destination "platform=macOS,arch=$(uname -m)" -derivedDataPath build/Xcode)
if [[ "$DAYLOG_ACTION" == test ]]; then
    mkdir -p build/qa
    DAYLOG_RESULT="$(mktemp -d "$DAYLOG_ROOT/build/qa/xcode-test.XXXXXX")/Results.xcresult"
    DAYLOG_ARGS+=(-resultBundlePath "$DAYLOG_RESULT")
fi
xcodebuild "${DAYLOG_ARGS[@]}" "$DAYLOG_BUILD_ACTION"
if [[ "$DAYLOG_ACTION" == run ]]; then
    open "$DAYLOG_ROOT/build/Xcode/Build/Products/Debug/DayLog.app"
fi
