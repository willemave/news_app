#!/usr/bin/env ruby

# This script adds Info.plist to the exceptions in the file system synchronized group
# to prevent it from being copied as a resource when it's already being processed

begin
  require 'xcodeproj'
rescue LoadError
  puts "Installing xcodeproj gem..."
  system("gem install xcodeproj")
  require 'xcodeproj'
end

project_path = 'newsly.xcodeproj'
project = Xcodeproj::Project.open(project_path)

# Find the main target
main_target = project.targets.find { |t| t.name == 'newsly' }

if main_target
  puts "Found target: #{main_target.name}"
  
  # Get the build configuration
  main_target.build_configurations.each do |config|
    puts "Checking configuration: #{config.name}"
    
    # Ensure INFOPLIST_FILE is set correctly
    config.build_settings['INFOPLIST_FILE'] = 'newsly/Info.plist'
    config.build_settings['GENERATE_INFOPLIST_FILE'] = 'NO'
    
    puts "Set INFOPLIST_FILE = newsly/Info.plist"
    puts "Set GENERATE_INFOPLIST_FILE = NO"
  end
end

# Save the project
project.save
puts "Project saved successfully!"

# Now let's modify the pbxproj directly to add exceptions
pbxproj_path = File.join(project_path, 'project.pbxproj')
content = File.read(pbxproj_path)

# Add Info.plist to exceptions in the synchronized root group
if content.include?('E6CB700B2E1DBAD7001AB7F2 /* newsly */')
  # Find the newsly synchronized group and add exceptions
  updated_content = content.gsub(
    /E6CB700B2E1DBAD7001AB7F2 \/\* newsly \*\/ = \{\s*isa = PBXFileSystemSynchronizedRootGroup;\s*exceptions = \(\s*\);/m,
    <<~REPLACEMENT
    E6CB700B2E1DBAD7001AB7F2 /* newsly */ = {
    			isa = PBXFileSystemSynchronizedRootGroup;
    			exceptions = (
    				E6CB700B2E1DBAD7001AB7F2 /* Info.plist */,
    			);
    REPLACEMENT
  )
  
  if updated_content != content
    File.write(pbxproj_path, updated_content)
    puts "Added Info.plist to exceptions in synchronized root group"
  else
    puts "Could not find the pattern to update or it's already updated"
  end
end

puts "Fix completed. Now clean and rebuild the project."