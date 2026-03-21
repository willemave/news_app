import Foundation
import Vision
import AppKit

let url = URL(fileURLWithPath: "/Users/willem/Development/news_app/.tmp/axe-eval-login-screen.png")
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
let handler = try VNImageRequestHandler(url: url)
try handler.perform([request])
for obs in request.results ?? [] {
    guard let top = obs.topCandidates(1).first else { continue }
    print(top.string)
}
