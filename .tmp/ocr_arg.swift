import Foundation
import Vision
import AppKit

let path = CommandLine.arguments.dropFirst().first ?? "/Users/willem/Development/news_app/.tmp/axe-password-focus.png"
let url = URL(fileURLWithPath: path)
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
let handler = VNImageRequestHandler(url: url)
try handler.perform([request])
for obs in request.results ?? [] {
    guard let top = obs.topCandidates(1).first else { continue }
    print(top.string)
}
