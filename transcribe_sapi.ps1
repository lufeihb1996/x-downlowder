Add-Type -AssemblyName System.Speech

$audioFile = "d:\worksace\demo\x-downloader\temp_audio.wav"
if (-not (Test-Path $audioFile)) {
    Write-Host "Audio file not found"
    exit 1
}

$culture = New-Object System.Globalization.CultureInfo("zh-CN")
$engine = New-Object System.Speech.Recognition.SpeechRecognitionEngine($culture)
$dictationGrammar = New-Object System.Speech.Recognition.DictationGrammar
$engine.LoadGrammar($dictationGrammar)
$engine.SetInputToWaveFile($audioFile)

Write-Host "========== Start Windows Native Speech Recognition =========="

$results = @()
while ($true) {
    $result = $engine.Recognize()
    if ($null -eq $result) { break }
    
    $start = $result.Audio.AudioPosition.TotalSeconds
    $duration = $result.Audio.Duration.TotalSeconds
    $end = $start + $duration
    $text = $result.Text
    
    Write-Host ("[{0:N2}s -> {1:N2}s] {2}" -f $start, $end, $text)
    $results += [PSCustomObject]@{
        Start = $start
        End = $end
        Text = $text
    }
}

$results | ConvertTo-Json | Out-File -Encoding utf8 "sapi_result.json"
Write-Host "Done! Saved to sapi_result.json"
