#!/bin/zsh

# 本机发布构建：构建 + 签名验证；若 notarytool keychain profile 可用则提示公证。
# 用法: scripts/release-local.zsh [--notarize]

set -eu
setopt pipe_fail

readonly SCRIPT_NAME="${0:t}"
readonly PROJECT_ROOT="${0:A:h:h}"
readonly DESKTOP_DIR="${PROJECT_ROOT}/apps/desktop"
readonly BUNDLE_DIR="${DESKTOP_DIR}/src-tauri/target/release/bundle"
readonly APP_PATH="${BUNDLE_DIR}/macos/ThumbAgent.app"
readonly EXPECTED_TEAM_ID="JRDVQ57V39"
readonly NOTARY_PROFILE="${THUMBAGENT_NOTARY_PROFILE:-thumbagent-notary}"

DO_NOTARIZE=false
for arg in "$@"; do
  case "${arg}" in
    --notarize) DO_NOTARIZE=true ;;
    -h|--help)
      print "usage: ${SCRIPT_NAME} [--notarize]"
      exit 0
      ;;
    *) print "unknown argument: ${arg}" >&2; exit 2 ;;
  esac
done

print "==> building signed bundle"
cd "${DESKTOP_DIR}"
npm run tauri build

print "==> verifying app signature"
codesign -vvv --deep --strict "${APP_PATH}"

readonly TEAM_ID="$(codesign -dv --verbose=4 "${APP_PATH}" 2>&1 | awk -F= '/^TeamIdentifier=/{print $2}')"
if [[ "${TEAM_ID}" != "${EXPECTED_TEAM_ID}" ]]; then
  print "unexpected TeamIdentifier: ${TEAM_ID} (expected ${EXPECTED_TEAM_ID})" >&2
  exit 1
fi
if ! codesign -dv --verbose=4 "${APP_PATH}" 2>&1 | grep -q 'flags=0x10000(runtime)'; then
  print "hardened runtime flag missing on ${APP_PATH}" >&2
  exit 1
fi
print "    TeamIdentifier=${TEAM_ID}, hardened runtime enabled"

readonly DMG_PATH="$(ls "${BUNDLE_DIR}"/dmg/*.dmg(N) | head -1)"
if [[ -z "${DMG_PATH}" ]]; then
  print "no dmg found under ${BUNDLE_DIR}/dmg" >&2
  exit 1
fi
print "==> verifying dmg signature: ${DMG_PATH:t}"
codesign -vvv --deep --strict "${DMG_PATH}"

print "==> signature verification passed"

if [[ "${DO_NOTARIZE}" == true ]]; then
  exec "${PROJECT_ROOT}/scripts/notarize.zsh" "${DMG_PATH}"
fi

if xcrun notarytool history --keychain-profile "${NOTARY_PROFILE}" >/dev/null 2>&1; then
  print "==> notary profile '${NOTARY_PROFILE}' available; run:"
  print "      scripts/notarize.zsh '${DMG_PATH}'"
else
  print "==> notarization skipped: no notarytool keychain profile '${NOTARY_PROFILE}'"
  print "    set it up with one of:"
  print "      xcrun notarytool store-credentials ${NOTARY_PROFILE} --apple-id <apple-id> --team-id ${EXPECTED_TEAM_ID}"
  print "      xcrun notarytool store-credentials ${NOTARY_PROFILE} --key <AuthKey.p8> --key-id <key-id> --issuer <issuer-id>"
fi
