import * as React from "react"
import SignatureCanvas from "react-signature-canvas"
import { Button } from "@/components/ui/button"

export const CANVAS_ENABLED = true

interface CanvasInputProps {
  onImageReady: (blob: Blob) => void
}

export default function CanvasInput({ onImageReady }: CanvasInputProps) {
  const canvasRef = React.useRef<SignatureCanvas>(null)
  const [penWidth, setPenWidth] = React.useState(4)

  function handleClear() {
    canvasRef.current?.clear()
  }

  function handleDone() {
    const canvas = canvasRef.current
    if (!canvas || canvas.isEmpty()) return
    const dataUrl = canvas.toDataURL("image/png")
    fetch(dataUrl)
      .then((r) => r.blob())
      .then((blob) => onImageReady(blob))
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">선 굵기:</span>
        {[2, 4, 6].map((w) => (
          <button
            key={w}
            onClick={() => setPenWidth(w)}
            className={`w-8 h-8 rounded-lg border flex items-center justify-center text-xs font-medium transition-colors ${
              penWidth === w
                ? "bg-primary text-primary-foreground border-primary"
                : "bg-background border-input hover:bg-accent"
            }`}
          >
            {w}
          </button>
        ))}
      </div>
      <div className="border rounded-2xl overflow-hidden bg-white">
        <SignatureCanvas
          ref={canvasRef}
          penColor="black"
          minWidth={penWidth}
          maxWidth={penWidth}
          backgroundColor="white"
          canvasProps={{ width: 600, height: 300, className: "w-full" }}
        />
      </div>
      <div className="flex gap-2">
        <Button variant="outline" onClick={handleClear} className="flex-1">
          초기화
        </Button>
        <Button onClick={handleDone} className="flex-1">
          완료
        </Button>
      </div>
    </div>
  )
}
