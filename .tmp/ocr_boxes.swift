import Foundation
import Vision
import AppKit

let imagePath = "/Users/willem/Development/news_app/.tmp/axe-eval-login-screen.png"
let url = URL(fileURLWithPath: imagePath)
let image = NSImage(contentsOf: url)!
let size = image.size
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
let handler = VNImageRequestHandler(url: url)
try handler.perform([request])
for obs in request.results ?? [] {
    guard let top = obs.topCandidates(1).first else { continue }
    let box = obs.boundingBox
    let x = box.origin.x * size.width
    let y = (1 - box.origin.y - box.size.height) * size.height
    let w = box.size.width * size.width
    let h = box.size.height * size.height
    print("\(top.string)\t\(Int(x)),\(Int(y)),\(Int(w)),\(Int(h))")
}
