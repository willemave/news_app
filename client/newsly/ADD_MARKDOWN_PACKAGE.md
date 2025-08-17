# Adding MarkdownUI Package to Newsly

To render markdown content properly in the iOS app, you need to add the MarkdownUI package dependency:

## Steps to Add MarkdownUI:

1. Open `newsly.xcodeproj` in Xcode

2. In Xcode, go to **File → Add Package Dependencies...**

3. In the search field, enter:
   ```
   https://github.com/gonzalezreal/swift-markdown-ui
   ```

4. Click **Add Package**

5. Select version rule: **Up to Next Major Version**
   - From: **2.0.2**

6. Click **Add Package**

7. When prompted, add **MarkdownUI** to the **newsly** target

8. Click **Add Package** to finish

The package will be downloaded and integrated into your project. After this is complete, the code changes in ContentDetailView.swift will work properly to render markdown content.

## Verification

After adding the package, you should see:
- A "Package Dependencies" section in your project navigator
- "swift-markdown-ui" listed under Package Dependencies
- The ability to import MarkdownUI in Swift files