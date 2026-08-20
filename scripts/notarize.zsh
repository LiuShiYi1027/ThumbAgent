#!/bin/zsh

# 公证 dmg 并装订票据。需要 notarytool keychain profile（默认 thumbagent-notary）。
# 用法: scripts/notarize.zsh <path-to.dmg>

set -eu
setopt pipe_fail

readonly SCRIPT_NAME="${0:t}"
readonly NOTARY_PROFILE="${THUMBAGENT_NOTARY_PROFILE:-thumbagent-notary}"

if [[ $# -ne 1 ]]; then
  print "usage: ${SCRIPT_NAME} <path-to.dmg>" >&2
  exit 2
fi

readonly DMG_PATH="${1:A}"
if [[ ! -f "${DMG_PATH}" ]]; then
  print "dmg not found: ${DMG_PATH}" >&2
  exit 1
fi

if ! xcrun notarytool history --keychain-profile "${NOTARY_PROFILE}" >/dev/null 2>&1; then
  print "notarytool keychain profile '${NOTARY_PROFILE}' not available." >&2
  print "create it with one of:" >&2
  print "  xcrun notarytool store-credentials ${NOTARY_PROFILE} --apple-id <apple-id> --team-id JRDVQ57V39" >&2
  print "  xcrun notarytool store-credentials ${NOTARY_PROFILE} --key <AuthKey.p8> --key-id <key-id> --issuer <issuer-id>" >&2
  exit 1
fi

print "==> submitting ${DMG_PATH:t} for notarization (profile: ${NOTARY_PROFILE})"
xcrun notarytool submit "${DMG_PATH}" --keychain-profile "${NOTARY_PROFILE}" --wait

print "==> stapling ticket"
xcrun stapler staple "${DMG_PATH}"

print "==> verifying Gatekeeper assessment"
spctl -a -vv --type install "${DMG_PATH}"

print "==> notarization complete: ${DMG_PATH}"
