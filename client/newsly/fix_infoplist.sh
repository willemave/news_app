#!/bin/bash

# This script fixes the Info.plist duplicate error by removing it from Copy Bundle Resources

echo "Fixing Info.plist duplicate error..."

# Create an AppleScript to remove Info.plist from Copy Bundle Resources
osascript <<EOF
tell application "Xcode"
    open "/Users/willem/Development/news_app/client/newsly/newsly.xcodeproj"
    delay 2
    
    tell project "newsly"
        tell target "newsly"
            tell build phase "Copy Bundle Resources"
                set resourceFiles to build files
                repeat with aFile in resourceFiles
                    if name of aFile contains "Info.plist" then
                        delete aFile
                        log "Removed Info.plist from Copy Bundle Resources"
                    end if
                end repeat
            end build phase
        end tell
    end tell
end tell
EOF

echo "Fix completed. Please try building the project again."