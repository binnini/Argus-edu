import * as React from "react"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import CanvasInput, { CANVAS_ENABLED } from "./CanvasInput"
import { Upload, Camera, PenLine } from "lucide-react"

interface AnswerInputProps {
  onFileReady: (file: File) => void
}

export default function AnswerInput({ onFileReady }: AnswerInputProps) {
  const [preview, setPreview] = React.useState<string | null>(null)

  function handleFileChange(file: File | null) {
    if (!file) return
    const url = URL.createObjectURL(file)
    setPreview(url)
    onFileReady(file)
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file) handleFileChange(file)
  }

  function handleCanvasBlob(blob: Blob) {
    const file = new File([blob], "canvas_drawing.png", { type: "image/png" })
    handleFileChange(file)
  }

  return (
    <Tabs defaultValue="upload">
      <TabsList className="w-full">
        <TabsTrigger value="upload" className="flex-1 gap-1">
          <Upload className="h-4 w-4" /> 이미지 업로드
        </TabsTrigger>
        <TabsTrigger value="camera" className="flex-1 gap-1">
          <Camera className="h-4 w-4" /> 카메라
        </TabsTrigger>
        {CANVAS_ENABLED && (
          <TabsTrigger value="canvas" className="flex-1 gap-1">
            <PenLine className="h-4 w-4" /> 직접 그리기
          </TabsTrigger>
        )}
      </TabsList>

      <TabsContent value="upload">
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          className="border-2 border-dashed border-border rounded-2xl p-8 text-center cursor-pointer hover:bg-accent/50 transition-colors"
          onClick={() => document.getElementById("file-upload")?.click()}
        >
          <input
            id="file-upload"
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
          />
          {preview ? (
            <img src={preview} alt="미리보기" className="max-h-64 mx-auto rounded-xl object-contain" />
          ) : (
            <div className="space-y-2">
              <Upload className="h-10 w-10 mx-auto text-muted-foreground" />
              <p className="text-sm text-muted-foreground">파일을 드래그하거나 클릭해서 선택</p>
              <p className="text-xs text-muted-foreground">JPEG, PNG, WEBP 지원</p>
            </div>
          )}
        </div>
      </TabsContent>

      <TabsContent value="camera">
        <div className="space-y-4">
          <label className="block border-2 border-dashed border-border rounded-2xl p-8 text-center cursor-pointer hover:bg-accent/50 transition-colors">
            <input
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
            />
            {preview ? (
              <img src={preview} alt="카메라 미리보기" className="max-h-64 mx-auto rounded-xl object-contain" />
            ) : (
              <div className="space-y-2">
                <Camera className="h-10 w-10 mx-auto text-muted-foreground" />
                <p className="text-sm text-muted-foreground">클릭해서 카메라로 촬영</p>
              </div>
            )}
          </label>
        </div>
      </TabsContent>

      {CANVAS_ENABLED && (
        <TabsContent value="canvas">
          <CanvasInput onImageReady={handleCanvasBlob} />
        </TabsContent>
      )}
    </Tabs>
  )
}
