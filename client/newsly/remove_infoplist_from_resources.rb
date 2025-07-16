#!/usr/bin/env ruby

# This script removes Info.plist from Copy Bundle Resources build phase
# You may need to install xcodeproj gem first: gem install xcodeproj

begin
  require 'xcodeproj'
rescue LoadError
  puts "Installing xcodeproj gem..."
  system("gem install xcodeproj")
  require 'xcodeproj'
end

project_path = 'newsly.xcodeproj'
project = Xcodeproj::Project.open(project_path)

project.targets.each do |target|
  if target.name == 'newsly'
    puts "Processing target: #{target.name}"
    
    # Find the Copy Bundle Resources build phase
    resources_phase = target.resources_build_phase
    
    if resources_phase
      # Remove Info.plist from resources
      resources_phase.files.delete_if do |file|
        if file.display_name&.include?('Info.plist')
          puts "Removing #{file.display_name} from Copy Bundle Resources"
          true
        else
          false
        end
      end
    end
  end
end

# Save the project
project.save
puts "Project saved successfully!"
puts "Now try building the project again."