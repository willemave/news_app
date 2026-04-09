package api

import (
	"fmt"
	"time"

	"github.com/go-faster/jx"
)

var naiveDateTimeLayouts = []string{
	"2006-01-02T15:04:05.999999999",
	"2006-01-02T15:04:05.999999",
	"2006-01-02T15:04:05",
}

// decodeFlexibleDateTime accepts RFC3339 timestamps and the naive ISO-like
// timestamps currently returned by the local backend for some endpoints.
func decodeFlexibleDateTime(d *jx.Decoder) (time.Time, error) {
	raw, err := d.Str()
	if err != nil {
		return time.Time{}, err
	}

	if parsed, err := time.Parse(time.RFC3339Nano, raw); err == nil {
		return parsed, nil
	}

	var lastErr error
	for _, layout := range naiveDateTimeLayouts {
		if parsed, err := time.ParseInLocation(layout, raw, time.UTC); err == nil {
			return parsed.UTC(), nil
		} else {
			lastErr = err
		}
	}

	return time.Time{}, fmt.Errorf("parse datetime %q: %w", raw, lastErr)
}
