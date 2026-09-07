---
name: flutter-android-build
description: Use when building Flutter APKs for Android or modifying Glance-based home screen widgets.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [flutter, android, build, apk, glance, widgets]
    category: software-development
---


# Flutter Android Build

## Overview

Building Flutter APKs for Android and modifying Glance-based home screen
widgets (Jetpack Glance, the Compose-style widget toolkit Android apps use
for `home_widget`-style integrations).

## When to Use

- Cutting a release/debug APK build for an Android Flutter app
- Bumping the app version ahead of a release
- Editing or debugging a Glance home screen widget shipped alongside the app
- Don't use for: iOS builds, or general Dart/UI rendering issues (see
  `flutter-content-rendering` for HTML/PDF/WebView content quirks)

## Version Bumping

Update **both** of these together — they drift independently and Android will
happily build with mismatched values, so nothing fails until a store upload
or a widget update check compares them:

- `pubspec.yaml` — the `version: X.Y.Z+N` line (`X.Y.Z` is the display
  version, `N` after the `+` is the build number / `versionCode`).
- `android/local.properties` — Flutter's Gradle plugin reads `flutter.versionName`
  / `flutter.versionCode` overrides from here if present; if the file pins a
  version it will silently take precedence over `pubspec.yaml` at build time.

If a build ships with the old version despite a `pubspec.yaml` bump, check
`local.properties` first before suspecting a Gradle cache issue.

## Build Commands

```bash
flutter clean                      # when in doubt after a version/dependency change
flutter pub get
flutter build apk --release        # single universal APK
flutter build apk --release --split-per-abi   # smaller per-ABI APKs
flutter build appbundle --release  # .aab for Play Store upload
```

- `--split-per-abi` produces `app-armeabi-v7a-release.apk`,
  `app-arm64-v8a-release.apk`, `app-x86_64-release.apk` separately under
  `build/app/outputs/flutter-apk/` — don't sideload the wrong ABI onto a test
  device.
- A release build requires a signing config (`android/key.properties` +
  matching `signingConfigs` block in `android/app/build.gradle`); without it
  Gradle falls back to the debug keystore and the APK will fail to update
  over an existing store install (signature mismatch).

## Glance Widget Pitfalls

- Glance widgets are native Kotlin/Compose code living under
  `android/app/src/main/kotlin/**/widget/`, not Dart — Flutter hot reload does
  **not** touch them. Rebuild and reinstall the APK to see widget changes.
  A pure Dart-side hot reload will make it look like your widget edit "did
  nothing."
- Widget state updates from the Dart side (e.g. via `home_widget` plugin)
  only take effect after you explicitly call the widget update trigger from
  Dart; changing shared prefs/files alone does not refresh a placed widget.
- Test widget layout changes on-device or via Android Studio's widget
  preview — the Flutter app's own UI preview tools don't render Glance
  widgets.

## Dart Pitfall

`substringAfter()` does not exist in Dart's `String` API (it's a
Kotlin/Guava-ism). Use `.split("x").last` instead, e.g.
`"foo=bar".split("=").last` → `"bar"`.

## Common Pitfalls

1. **Version mismatch between `pubspec.yaml` and `android/local.properties`.**
   See Version Bumping above — always grep both before assuming a version bug
   is a build-cache issue.
2. **Expecting hot reload to update a Glance widget.** It won't — widgets are
   native code, not Dart.
3. **Sideloading the wrong split APK.** Match the device's ABI
   (`arm64-v8a` for virtually all modern phones) or install the universal
   `app-release.apk` instead.
4. **Missing signing config on release builds.** Falls back to the debug
   keystore silently; only surfaces as a signature-mismatch failure when
   updating an existing store install.

## Verification Checklist

- [ ] `pubspec.yaml` version and `android/local.properties` (if present) agree
- [ ] `flutter build apk --release` (or `appbundle`) completes with no errors
- [ ] Release build is signed with the real keystore, not the debug fallback
- [ ] If a Glance widget was touched: APK reinstalled on-device, not just
      hot-reloaded, before judging the change
