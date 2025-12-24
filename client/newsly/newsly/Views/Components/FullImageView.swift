//
//  FullImageView.swift
//  newsly
//
//  Created by Assistant on 12/20/25.
//

import SwiftUI

struct FullImageView: View {
    let imageURL: URL
    let thumbnailURL: URL?
    @Binding var isPresented: Bool
    @State private var scale: CGFloat = 1.0
    @State private var lastScale: CGFloat = 1.0

    init(imageURL: URL, thumbnailURL: URL? = nil, isPresented: Binding<Bool>) {
        self.imageURL = imageURL
        self.thumbnailURL = thumbnailURL
        self._isPresented = isPresented
    }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            CachedAsyncImage(
                url: imageURL,
                thumbnailUrl: thumbnailURL
            ) { image in
                image
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .scaleEffect(scale)
                    .gesture(
                        MagnificationGesture()
                            .onChanged { value in
                                scale = lastScale * value
                            }
                            .onEnded { _ in
                                lastScale = scale
                                // Snap back if too small
                                if scale < 1.0 {
                                    withAnimation {
                                        scale = 1.0
                                        lastScale = 1.0
                                    }
                                }
                            }
                    )
                    .onTapGesture(count: 2) {
                        withAnimation {
                            if scale > 1.0 {
                                scale = 1.0
                                lastScale = 1.0
                            } else {
                                scale = 2.0
                                lastScale = 2.0
                            }
                        }
                    }
            } placeholder: {
                ProgressView()
                    .tint(.white)
            }

            // Close button
            VStack {
                HStack {
                    Spacer()
                    Button {
                        isPresented = false
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .font(.title)
                            .foregroundColor(.white.opacity(0.8))
                            .padding()
                    }
                }
                Spacer()
            }
        }
        .onTapGesture {
            isPresented = false
        }
    }
}
