---
name: flutter-android-build
description: Build Flutter APKs and modify Glance widgets.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [flutter, android, build, apk]
    category: software-development
---


# Flutter Android Build

Build Flutter APKs and modify Glance-based home screen widgets.

## Version Bumping

Update both pubspec.yaml and android/local.properties. Both must match.

## Dart Pitfall

substringAfter() does not exist in Dart. Use .split("x").last instead.
