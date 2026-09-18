---
name: flutter-content-rendering
description: "Show HTML/links/PDFs in Flutter — viewers, clickable URLs."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [flutter, rendering, html, pdf]
    category: software-development
tags: flutter, dart, html, links, webview, pdf, url-launcher, rendering
---


# Flutter Content Rendering (HTML, links, PDFs, local files)

Package-level quirks for rendering dynamic content in Flutter apps (task
descriptions, attachment viewers, rich text). Verified against the Vikunja
Flutter app on Flutter 3.44.8 / Dart 3.12 / webview_flutter 4.13.

## Clickable links inside rendered HTML

`flutter_widget_from_html`'s `HtmlWidget`:
- Does **NOT** auto-linkify bare `https://` / `www.` URLs — they render as inert text.
- `<a href>` tags are only tappable when `onTapUrl` is supplied.
- `onTapUrl` signature: `FutureOr<bool> Function(String url)?` — return true = handled.

Recipe (works for plain text or HTML strings):
1. Linkify first: wrap bare URLs in `<a href>` (regex below), skipping URLs already inside an href attribute.
2. `HtmlWidget(linkifyHtml(desc), onTapUrl: (url) => launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication))` — `url_launcher`, already available in most apps.
3. **AndroidManifest**: add a `<queries>` block (VIEW intent, `http` + `https` schemes) for Android 11+ package visibility, or browser launch can fail silently.

Copy-paste linkify (mind the raw-string trap — see below):

```dart
final RegExp _bareUrlPattern = RegExp(
  r'(?<![="])((?:https?://|www\.)[^\s<>]+)',
  caseSensitive: false,
);
final RegExp _trailingJunk = RegExp(r'[.,;:!?…)"' r"']+$");

String linkifyHtml(String input) => input.replaceAllMapped(_bareUrlPattern, (m) {
  var url = m.group(1)!.replaceAll(_trailingJunk, '');
  if (url.isEmpty) return m.group(0)!;
  final href = url.startsWith('http') ? url : 'https://$url';
  return '<a href="$href">$url</a>';
});
```

## WebView (webview_flutter 4.x)

- `loadFile()`: pass `'file://$path'`. The 4.x Android impl hands the string
  straight to `loadUrl` (no prefix added); the legacy impl prefixes `file://`
  itself. The explicit prefix works for both, and the plugin sets
  `setAllowFileAccess(true)` for you.
- `setDomStorageEnabled` was REMOVED from the API — DOM storage is always on
  (AndroidWebViewController ctor enables it).
- Pinch zoom is ON by default (ctor: `setBuiltInZoomControls(true)`,
  `setDisplayZoomControls(false)`) — no code needed.
- CDN-script pages (Tailwind etc.): `setJavaScriptMode(JavaScriptMode.unrestricted)`.
- Loading UX: `NavigationDelegate(onPageStarted/onPageFinished)` + spinner;
  WebView stays blank until the first frame.
- HTML in a WebView renders CSS/JS/RTL exactly like a browser; a plain
  `HtmlWidget` view strips styles — choose per use case.

## PDFs (flutter_pdfview)

- Android native `PdfRenderer` → handles Hebrew/RTL PDFs and generated docs well.
- Needs a real local file path (app-private dirs like applicationSupport work).
- Default view: `PDFView(filePath: path, autoSpacing: true, pageFling: false)`;
  errors surface via `onError` / `onPageError`.

## Local file download + cache (background_downloader)

- Cache pattern: build the `DownloadTask` (same URL/headers as the download),
  call `task.filePath()` — returns `Future<String>` (**non-nullable**) — then
  `File(path).existsSync()` to skip re-downloads.
- Open a cached local file in an external app:
  `FileDownloader().openFile(filePath: path, mimeType: mime)` (exposes via
  content URI; plain `url_launcher` `Uri.file` does NOT work on Android 7+ for
  app-private files).

## Dart raw strings — no escapes

- In a raw string (`r'...'`), backslash escaping does NOT exist: `r'...\'...'`
  terminates at the quote → parse error (this is NOT a regex bug).
- Include both quote types in one regex by concatenating adjacent raw literals
  with alternating quotes: `r'[.,;:!?…)"' r"']+$"`.
- The analyzer lint `prefer_adjacent_string_concatenation` demands adjacent
  literals (no `+` operator).

## Verification

- `flutter analyze` must reach zero errors in touched files.
- After any multi-line edit: `dart format <file>` — it FAILS loudly on
  unbalanced braces, making it the fastest corruption detector.