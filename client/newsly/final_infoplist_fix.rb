#!/usr/bin/env ruby

# Final comprehensive fix for Info.plist duplicate issue

begin
  require 'xcodeproj'
rescue LoadError
  puts "Installing xcodeproj gem..."
  system("gem install xcodeproj")
  require 'xcodeproj'
end

project_path = 'newsly.xcodeproj'
pbxproj_path = File.join(project_path, 'project.pbxproj')

# Read the raw project file
content = File.read(pbxproj_path)

# Fix 1: Update the exceptions to properly exclude Info.plist
# The format should just be the filename, not a reference
updated_content = content.gsub(
  /exceptions = \(\s*E6CB700B2E1DBAD7001AB7F2 \/\* Info\.plist \*\/,?\s*\);/m,
  'exceptions = (
				"Info.plist",
			);'
)

# If that didn't work, try another pattern
if updated_content == content
  updated_content = content.gsub(
    /E6CB700B2E1DBAD7001AB7F2 \/\* newsly \*\/ = \{[^}]*\};/m
  ) do |match|
    if match.include?('exceptions = (')
      # Already has exceptions, add Info.plist
      match.gsub(/exceptions = \(\s*\);/, 'exceptions = (
				"Info.plist",
			);')
    else
      # No exceptions section, add it
      match.gsub(/isa = PBXFileSystemSynchronizedRootGroup;/, 'isa = PBXFileSystemSynchronizedRootGroup;
			exceptions = (
				"Info.plist",
			);')
    end
  end
end

# Write the updated content
File.write(pbxproj_path, updated_content)

puts "Fixed exceptions format in project file"
puts "The Info.plist should now be properly excluded from the synchronized group"
puts "Please clean and rebuild the project"