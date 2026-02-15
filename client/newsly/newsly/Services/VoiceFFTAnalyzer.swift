//
//  VoiceFFTAnalyzer.swift
//  newsly
//

import Accelerate
import Foundation

enum VoiceFFTAnalyzer {
    private static let targetFrameCount = 512

    static func normalizedEnergy(fromPCM16 pcmData: Data) -> Float {
        let sampleCount = pcmData.count / MemoryLayout<Int16>.size
        guard sampleCount >= 32 else { return 0 }

        let powerOfTwoCount = min(targetFrameCount, highestPowerOfTwo(sampleCount))
        guard powerOfTwoCount >= 32 else { return 0 }

        var samples = [Float](repeating: 0, count: powerOfTwoCount)
        pcmData.withUnsafeBytes { rawBuffer in
            guard let int16Buffer = rawBuffer.bindMemory(to: Int16.self).baseAddress else { return }
            for idx in 0..<powerOfTwoCount {
                samples[idx] = Float(int16Buffer[idx]) / Float(Int16.max)
            }
        }

        var window = [Float](repeating: 0, count: powerOfTwoCount)
        vDSP_hann_window(&window, vDSP_Length(powerOfTwoCount), Int32(vDSP_HANN_NORM))
        vDSP_vmul(samples, 1, window, 1, &samples, 1, vDSP_Length(powerOfTwoCount))

        let log2n = vDSP_Length(log2(Float(powerOfTwoCount)))
        guard let fftSetup = vDSP_create_fftsetup(log2n, FFTRadix(kFFTRadix2)) else {
            return 0
        }
        defer { vDSP_destroy_fftsetup(fftSetup) }

        var real = [Float](repeating: 0, count: powerOfTwoCount / 2)
        var imag = [Float](repeating: 0, count: powerOfTwoCount / 2)
        real.withUnsafeMutableBufferPointer { realPtr in
            imag.withUnsafeMutableBufferPointer { imagPtr in
                var splitComplex = DSPSplitComplex(realp: realPtr.baseAddress!, imagp: imagPtr.baseAddress!)
                samples.withUnsafeBufferPointer { samplePtr in
                    samplePtr.baseAddress!.withMemoryRebound(to: DSPComplex.self, capacity: powerOfTwoCount / 2) { complexPtr in
                        vDSP_ctoz(complexPtr, 2, &splitComplex, 1, vDSP_Length(powerOfTwoCount / 2))
                    }
                }
                vDSP_fft_zrip(fftSetup, &splitComplex, 1, log2n, FFTDirection(FFT_FORWARD))
            }
        }

        let interestingBins = max(4, min(32, real.count / 3))
        guard interestingBins > 0 else { return 0 }
        var sumPower: Float = 0
        var count: Float = 0
        for idx in 1..<interestingBins {
            let power = (real[idx] * real[idx]) + (imag[idx] * imag[idx])
            sumPower += power
            count += 1
        }
        guard count > 0 else { return 0 }
        let meanPower = sumPower / count
        let normalized = min(1, max(0, sqrt(meanPower) * 6))
        return normalized
    }

    private static func highestPowerOfTwo(_ value: Int) -> Int {
        var n = 1
        while n * 2 <= value {
            n *= 2
        }
        return n
    }
}
