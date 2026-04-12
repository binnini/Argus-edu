import * as React from "react"
import SignatureCanvas from "react-signature-canvas"
import { Button } from "@/components/ui/button"
import { Eraser, Pen } from "lucide-react"

export const CANVAS_ENABLED = true

interface CanvasInputProps {
  onImageReady: (blob: Blob) => void
}

type DrawMode = "pen" | "eraser"

const CANVAS_HEIGHT = 480

export default function CanvasInput({ onImageReady }: CanvasInputProps) {
  const canvasRef = React.useRef<SignatureCanvas>(null)
  const wrapperRef = React.useRef<HTMLDivElement>(null)
  const [penWidth, setPenWidth] = React.useState(4)
  const [mode, setMode] = React.useState<DrawMode>("pen")
  const [canvasWidth, setCanvasWidth] = React.useState(800)

  // 컨테이너 너비에 맞게 캔버스 내부 해상도 동기화 (포인터 오프셋 방지)
  React.useEffect(() => {
    if (!wrapperRef.current) return

    const observer = new ResizeObserver((entries) => {
      const width = Math.floor(entries[0].contentRect.width)
      if (width > 0 && width !== canvasWidth) {
        // 크기 변경 시 캔버스 초기화 후 재조정
        canvasRef.current?.clear()
        setCanvasWidth(width)
      }
    })
    observer.observe(wrapperRef.current)
    // 초기 너비 설정
    setCanvasWidth(Math.floor(wrapperRef.current.getBoundingClientRect().width) || 800)

    return () => observer.disconnect()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const effectiveWidth = mode === "eraser" ? penWidth * 3 : penWidth
  const penColor = mode === "eraser" ? "white" : "black"

  // 커서 SVG — 정확히 그리는 위치가 원의 중심이 되도록 hotspot 설정
  const cursorSize = effectiveWidth + 8
  const half = Math.floor(cursorSize / 2)
  const cursorSvg = `<svg xmlns='http://www.w3.org/2000/svg' width='${cursorSize}' height='${cursorSize}'><circle cx='${half}' cy='${half}' r='${effectiveWidth / 2}' fill='${mode === "eraser" ? "rgba(200,200,200,0.7)" : "rgba(0,0,0,0.5)"}' stroke='${mode === "eraser" ? "#999" : "#333"}' stroke-width='1.5'/></svg>`
  const cursorUrl = `url("data:image/svg+xml,${encodeURIComponent(cursorSvg)}") ${half} ${half}, crosshair`

  function handleClear() {
    canvasRef.current?.clear()
  }

  function handleDone() {
    const canvas = canvasRef.current
    if (!canvas || canvas.isEmpty()) return

    // 내부 canvas 요소를 직접 참조해 흰 배경 위에 합성 후 export
    // (ResizeObserver 리사이즈 후 backgroundColor 재적용이 누락되는 경우를 방어)
    const sigCanvas = canvas.getCanvas()
    const exportCanvas = document.createElement("canvas")
    exportCanvas.width = sigCanvas.width
    exportCanvas.height = sigCanvas.height
    const ctx = exportCanvas.getContext("2d")!
    ctx.fillStyle = "white"
    ctx.fillRect(0, 0, exportCanvas.width, exportCanvas.height)
    ctx.drawImage(sigCanvas, 0, 0)
    exportCanvas.toBlob((blob) => {
      if (blob) onImageReady(blob)
    }, "image/png")
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

      {/* 캔버스 — wrapper 너비와 내부 해상도를 일치시켜 포인터 오프셋 제거 */}
      <div
        ref={wrapperRef}
        className="border rounded-2xl overflow-hidden bg-white"
        style={{ cursor: cursorUrl }}
      >
        <SignatureCanvas
          ref={canvasRef}
          penColor={penColor}
          minWidth={effectiveWidth}
          maxWidth={effectiveWidth}
          backgroundColor="white"
          canvasProps={{
            width: canvasWidth,
            height: CANVAS_HEIGHT,
            style: { display: "block", width: "100%", height: CANVAS_HEIGHT, cursor: "inherit" },
          }}
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
