import * as React from "react"
import SignatureCanvas from "react-signature-canvas"
import { Button } from "@/components/ui/button"
import { Eraser, Pen } from "lucide-react"

export const CANVAS_ENABLED = true

interface CanvasInputProps {
  onImageReady: (blob: Blob) => void
}

type DrawMode = "pen" | "eraser"

export default function CanvasInput({ onImageReady }: CanvasInputProps) {
  const canvasRef = React.useRef<SignatureCanvas>(null)
  const [penWidth, setPenWidth] = React.useState(4)
  const [mode, setMode] = React.useState<DrawMode>("pen")

  const effectiveWidth = mode === "eraser" ? penWidth * 3 : penWidth
  const penColor = mode === "eraser" ? "white" : "black"

  const cursorSize = effectiveWidth + 8
  const cursorSvg = `<svg xmlns='http://www.w3.org/2000/svg' width='${cursorSize}' height='${cursorSize}'><circle cx='${cursorSize/2}' cy='${cursorSize/2}' r='${effectiveWidth/2}' fill='${mode === "eraser" ? "rgba(200,200,200,0.7)" : "rgba(0,0,0,0.5)"}' stroke='${mode === "eraser" ? "#999" : "#333"}' stroke-width='1.5'/></svg>`
  const cursorUrl = `url("data:image/svg+xml,${encodeURIComponent(cursorSvg)}") ${Math.floor(cursorSize/2)} ${Math.floor(cursorSize/2)}, crosshair`

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
      {/* 도구 선택 */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1 border rounded-lg p-1">
          <button
            onClick={() => setMode("pen")}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-colors ${
              mode === "pen"
                ? "bg-primary text-primary-foreground"
                : "hover:bg-accent text-muted-foreground"
            }`}
          >
            <Pen className="h-3 w-3" /> 펜
          </button>
          <button
            onClick={() => setMode("eraser")}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded text-xs font-medium transition-colors ${
              mode === "eraser"
                ? "bg-zinc-200 dark:bg-zinc-700 text-foreground"
                : "hover:bg-accent text-muted-foreground"
            }`}
          >
            <Eraser className="h-3 w-3" /> 지우개
          </button>
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-xs text-muted-foreground">굵기:</span>
          {[2, 4, 6, 8].map((w) => (
            <button
              key={w}
              onClick={() => setPenWidth(w)}
              title={`굵기 ${w}`}
              className={`rounded-lg border flex items-center justify-center transition-colors ${
                penWidth === w
                  ? "bg-primary text-primary-foreground border-primary"
                  : "bg-background border-input hover:bg-accent"
              }`}
              style={{ width: 28, height: 28 }}
            >
              <span
                className="rounded-full block"
                style={{
                  width: Math.min(w * 2.5, 20),
                  height: Math.min(w * 2.5, 20),
                  backgroundColor: penWidth === w ? "currentColor" : "#666",
                }}
              />
            </button>
          ))}
        </div>
      </div>

      {/* 캔버스 */}
      <div
        className="border rounded-2xl overflow-hidden bg-white"
        style={{ cursor: cursorUrl }}
      >
        <SignatureCanvas
          ref={canvasRef}
          penColor={penColor}
          minWidth={effectiveWidth}
          maxWidth={effectiveWidth}
          backgroundColor="white"
          canvasProps={{ width: 600, height: 300, className: "w-full", style: { cursor: "inherit" } }}
        />
      </div>

      {/* 액션 버튼 */}
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
