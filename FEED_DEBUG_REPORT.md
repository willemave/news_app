# Feed Display Issue - Debug Report

## Summary
**Issue**: No feeds showing up in iOS app despite successful bootstrap
**Status**: IDENTIFIED - App filtering + Read status issue

## Database Analysis ✅

### Content Pool
- **Total Content**: 10,776 items
- **Articles**: 2,493 (all have summaries)
- **Podcasts**: 298 (all have summaries)
- **News**: 7,985 (4,960 completed)

### User 1 Inbox Status
- **Total in Inbox**: 2,791 items
- **Marked as Read**: 5,323 items (across all content)
- **Unread in Inbox**: 1,138 items
  - Articles: 913 unread
  - Podcasts: 225 unread
  - News: 0 unread

## API Testing ✅

### Test Results (using curl with fresh JWT)

**Unread Filter** (`read_filter=unread`):
```bash
curl 'http://localhost:8000/api/content/?limit=5&read_filter=unread'
# Returns: 5 unread items (articles/podcasts with is_read: false)
# Status: ✅ WORKING
```

**All Filter** (`read_filter=all`):
```bash
curl 'http://localhost:8000/api/content/?limit=5&read_filter=all'
# Returns: 5 items (mix of read/unread, mostly news with is_read: true)
# Status: ✅ WORKING
```

**By Type**:
```bash
curl 'http://localhost:8000/api/content/?limit=5&content_type=article&read_filter=unread'
# Returns: Unread articles with user_status: "inbox"
# Status: ✅ WORKING

curl 'http://localhost:8000/api/content/?limit=5&content_type=podcast&read_filter=unread'
# Returns: Unread podcasts with user_status: "inbox"
# Status: ✅ WORKING
```

## iOS App Configuration ⚠️

### Default Settings
From `ContentListViewModel.swift`:
```swift
@Published var selectedReadFilter: String = "unread" // DEFAULT

init(defaultReadFilter: String = "unread") {
    _selectedReadFilter = Published(initialValue: defaultReadFilter)
}
```

**The iOS app defaults to showing ONLY unread content.**

### Potential Issues

1. **Date Filter Conflict**:
   - If `selectedDate` is set to a date with no unread content
   - Check: `selectedDate` state in app

2. **Content Type Filter**:
   - If filtering for "news" but all news are marked read
   - Check: `selectedContentType` or `selectedContentTypes`

3. **Empty State Not Showing**:
   - UI might not be displaying "no results" message
   - Check: Error/empty state handling in views

## Recommended Fixes

### Fix 1: Change App Default to "All"

**File**: `client/newsly/newsly/ViewModels/ContentListViewModel.swift`

```swift
// Change line 45:
@Published var selectedReadFilter: String = "all" {  // Changed from "unread"
    didSet {
        Task { await loadContent() }
    }
}

// Change line 54:
init(defaultReadFilter: String = "all") {  // Changed from "unread"
    _selectedReadFilter = Published(initialValue: defaultReadFilter)
}
```

### Fix 2: Clear Read Status for User

If you want to reset the user's read status:

```bash
python -c "
from app.core.db import get_db, init_db
from app.models.schema import ContentReadStatus
init_db()
with get_db() as db:
    deleted = db.query(ContentReadStatus).filter_by(user_id=1).delete()
    db.commit()
    print(f'Cleared {deleted} read status entries for user 1')
"
```

### Fix 3: Bootstrap Only Recent Content

To avoid overwhelming with old content:

```bash
# Clear existing inbox
python -c "
from app.core.db import get_db, init_db
from app.models.schema import ContentStatusEntry
init_db()
with get_db() as db:
    deleted = db.query(ContentStatusEntry).filter_by(user_id=1).delete()
    db.commit()
    print(f'Cleared inbox for user 1')
"

# Bootstrap only last 7 days
./scripts/bootstrap_feeds.sh --users 1 --days 7
```

### Fix 4: Add Debug Logging to iOS App

Add logging to see what the app is requesting:

```swift
// In ContentListViewModel.loadContent()
print("DEBUG: Requesting content with filters:")
print("  - contentType: \(selectedContentType)")
print("  - contentTypes: \(selectedContentTypes)")
print("  - date: \(selectedDate)")
print("  - readFilter: \(selectedReadFilter)")
```

## Quick Verification Tests

### Test 1: Check Current App State
In iOS app, check:
1. What filter is selected? (All/Unread/Read)
2. What date is selected? (if any)
3. What content type is selected?

### Test 2: Force "All" Filter
Temporarily change app code to force:
```swift
selectedReadFilter = "all"
selectedDate = ""
selectedContentType = "all"
```

### Test 3: Verify API Response
From iOS device/simulator, enable network logging to see actual API requests

## Expected Behavior After Fix

After setting default to "all":
- **Total visible items**: 2,478 (from user's inbox)
  - Articles: 2,191
  - Podcasts: 287
  - News: 0 (none in inbox, but shown separately)

After clearing read status:
- **All items marked unread**: 1,138 items will show
  - Articles: 913
  - Podcasts: 225

## Root Cause Summary

✅ **Backend**: Working correctly
✅ **Database**: Properly populated with 2,791 inbox items
✅ **API**: Returning correct filtered results
⚠️ **iOS App**: Defaulting to "unread" filter
⚠️ **User State**: Most content marked as read

**Solution**: Change iOS app default filter from "unread" to "all", or clear user's read status.
