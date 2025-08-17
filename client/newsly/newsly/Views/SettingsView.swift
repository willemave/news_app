//
//  SettingsView.swift
//  newsly
//
//  Created by Assistant on 7/9/25.
//

import SwiftUI

struct SettingsView: View {
    @ObservedObject private var settings = AppSettings.shared
    @State private var tempHost: String = ""
    @State private var tempPort: String = ""
    @State private var showingAlert = false
    @State private var alertMessage = ""
    
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("Server Configuration")) {
                    HStack {
                        Text("Host")
                        Spacer()
                        TextField("localhost", text: $tempHost)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                            .autocapitalization(.none)
                            .disableAutocorrection(true)
                            .frame(maxWidth: 200)
                    }
                    
                    HStack {
                        Text("Port")
                        Spacer()
                        TextField("8000", text: $tempPort)
                            .textFieldStyle(RoundedBorderTextFieldStyle())
                            .keyboardType(.numberPad)
                            .frame(maxWidth: 100)
                    }
                    
                    Toggle("Use HTTPS", isOn: $settings.useHTTPS)
                    
                    HStack {
                        Text("Current URL")
                            .foregroundColor(.secondary)
                        Spacer()
                        Text(settings.baseURL)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                
                Section(header: Text("Display Preferences")) {
                    Toggle("Show Read Articles", isOn: $settings.showReadContent)
                    Text("When enabled, both read and unread articles will be displayed")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Section {
                    Button(action: saveSettings) {
                        HStack {
                            Spacer()
                            Text("Save Settings")
                                .foregroundColor(.white)
                            Spacer()
                        }
                    }
                    .listRowBackground(Color.blue)
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.inline)
            .alert("Settings", isPresented: $showingAlert) {
                Button("OK", role: .cancel) { }
            } message: {
                Text(alertMessage)
            }
            .onAppear {
                tempHost = settings.serverHost
                tempPort = settings.serverPort
            }
        }
    }
    
    private func saveSettings() {
        // Validate port number
        if let portNumber = Int(tempPort), portNumber > 0 && portNumber <= 65535 {
            settings.serverHost = tempHost.isEmpty ? "localhost" : tempHost
            settings.serverPort = tempPort.isEmpty ? "8000" : tempPort
            alertMessage = "Settings saved successfully"
            showingAlert = true
        } else {
            alertMessage = "Invalid port number. Please enter a number between 1 and 65535."
            showingAlert = true
        }
    }
}