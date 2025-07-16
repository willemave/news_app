//
//  ContentListView.swift
//  newsly
//
//  Created by Assistant on 7/8/25.
//

import SwiftUI

struct ContentListView: View {
    @StateObject private var viewModel = ContentListViewModel()
    @State private var showingFilters = false
    
    var body: some View {
        NavigationView {
            ZStack {
                VStack(spacing: 0) {
                    if viewModel.isLoading && viewModel.contents.isEmpty {
                        LoadingView()
                    } else if let error = viewModel.errorMessage, viewModel.contents.isEmpty {
                        ErrorView(message: error) {
                            Task { await viewModel.loadContent() }
                        }
                    } else {
                        // Content List
                        if viewModel.contents.isEmpty {
                            VStack(spacing: 16) {
                                Spacer()
                                Image(systemName: "doc.text.magnifyingglass")
                                    .font(.largeTitle)
                                    .foregroundColor(.secondary)
                                Text("No content found matching your filters.")
                                    .foregroundColor(.secondary)
                                Spacer()
                            }
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                        } else {
                            List {
                                ForEach(viewModel.contents) { content in
                                    NavigationLink(destination: ContentDetailView(contentId: content.id)) {
                                        ContentCard(content: content) {
                                            await viewModel.markAsRead(content.id)
                                        }
                                    }
                                    .buttonStyle(PlainButtonStyle())
                                    .listRowInsets(EdgeInsets(top: 6, leading: 16, bottom: 6, trailing: 16))
                                    .listRowSeparator(.hidden)
                                    .listRowBackground(Color.clear)
                                    .swipeActions(edge: .leading, allowsFullSwipe: true) {
                                        if !content.isRead {
                                            Button {
                                                Task {
                                                    await viewModel.markAsRead(content.id)
                                                }
                                            } label: {
                                                Label("Mark as Read", systemImage: "checkmark.circle.fill")
                                            }
                                            .tint(.green)
                                        }
                                    }
                                }
                            }
                            .listStyle(.plain)
                            .padding(.top, 20) // Add top padding since we removed the navigation bar
                            .refreshable {
                                await viewModel.refresh()
                            }
                        }
                    }
                }
                .navigationBarHidden(true)
                .task {
                    await viewModel.loadContent()
                }
                
                // Floating menu button
                VStack {
                    HStack {
                        Button(action: {
                            showingFilters.toggle()
                        }) {
                            Image(systemName: "line.3.horizontal.decrease.circle.fill")
                                .font(.system(size: 44))
                                .foregroundColor(.accentColor)
                                .background(Circle().fill(Color(UIColor.systemBackground)))
                                .shadow(radius: 4)
                        }
                        .padding()
                        Spacer()
                    }
                    Spacer()
                }
            }
            .sheet(isPresented: $showingFilters) {
                FilterSheet(
                    selectedContentType: $viewModel.selectedContentType,
                    selectedDate: $viewModel.selectedDate,
                    selectedReadFilter: $viewModel.selectedReadFilter,
                    isPresented: $showingFilters, contentTypes: viewModel.contentTypes,
                    availableDates: viewModel.availableDates
                )
            }
        }
    }
}
