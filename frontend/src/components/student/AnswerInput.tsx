import * as React from "react"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import CanvasInput, { CANVAS_ENABLED } from "./CanvasInput"
import {
  fetchPrototypeSampleImageFile,
  getPrototypeProblemSampleImages,
  type PrototypeSampleImageItem,
} from "@/api/submissions"
import { apiOrigin } from "@/api/client"
import { Upload, Camera, PenLine, Images } from "lucide-react"

interface AnswerInputProps {
  onFileReady: (file: File) => void
  schoolLevel?: string | null
  domain?: string | null
}

const SAMPLE_IMAGE_ENABLED = String(import.meta.env.VITE_ENABLE_SAMPLE_IMAGE_INPUT ?? "false").toLowerCase() === "true"

export default function AnswerInput({ onFileReady, schoolLevel, domain }: AnswerInputProps) {
  const [preview, setPreview] = React.useState<string | null>(null)
  const [samples, setSamples] = React.useState<PrototypeSampleImageItem[]>([])
  const [sampleEnabledByServer, setSampleEnabledByServer] = React.useState(false)
  const [sampleLoading, setSampleLoading] = React.useState(false)
  const [sampleError, setSampleError] = React.useState("")

  React.useEffect(() => {
    if (!SAMPLE_IMAGE_ENABLED || !schoolLevel || !domain) return
    setSampleLoading(true)
    setSampleError("")
    getPrototypeProblemSampleImages(schoolLevel, domain)
      .then((res) => {
        setSampleEnabledByServer(res.enabled)
        setSamples(res.samples ?? [])
      })
      .catch((e: unknown) => setSampleError(e instanceof Error ? e.message : "샘플 이미지 조회 실패"))
      .finally(() => setSampleLoading(false))
  }, [schoolLevel, domain])

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

  async function handleSamplePick(sample: PrototypeSampleImageItem) {
    try {
      const file = await fetchPrototypeSampleImageFile(sample)
      handleFileChange(file)
    } catch (e) {
      setSampleError(e instanceof Error ? e.message : "샘플 이미지 선택 실패")
    }
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
        {SAMPLE_IMAGE_ENABLED && (
          <TabsTrigger value="samples" className="flex-1 gap-1">
            <Images className="h-4 w-4" /> 샘플
          </TabsTrigger>
        )}
      </TabsList>

      <TabsContent value="upload">
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          className="rounded-lg border-2 border-dashed border-gray-200 bg-gray-50 p-8 text-center cursor-pointer hover:bg-gray-100 transition-colors"
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
            <img src={preview} alt="미리보기" className="max-h-64 mx-auto rounded-lg object-contain" />
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
          <label className="block rounded-lg border-2 border-dashed border-gray-200 bg-gray-50 p-8 text-center cursor-pointer hover:bg-gray-100 transition-colors">
            <input
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={(e) => handleFileChange(e.target.files?.[0] ?? null)}
            />
            {preview ? (
              <img src={preview} alt="카메라 미리보기" className="max-h-64 mx-auto rounded-lg object-contain" />
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

      {SAMPLE_IMAGE_ENABLED && (
        <TabsContent value="samples">
          <div className="space-y-3">
            {sampleLoading ? (
              <p className="text-sm text-muted-foreground">샘플 이미지를 불러오는 중...</p>
            ) : !sampleEnabledByServer ? (
              <p className="text-sm text-muted-foreground">현재 샘플 이미지 기능이 비활성화되어 있습니다.</p>
            ) : samples.length === 0 ? (
              <p className="text-sm text-muted-foreground">현재 선택한 학교급/도메인에 샘플 이미지가 없습니다.</p>
            ) : (
              <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
                {samples.map((sample) => (
                  <button
                    key={sample.sample_id}
                    type="button"
                    onClick={() => { void handleSamplePick(sample) }}
                    className="overflow-hidden rounded-lg border border-gray-200 bg-white hover:border-primary/60"
                  >
                    <img
                      src={`${apiOrigin()}${sample.content_url}`}
                      alt={sample.filename}
                      className="h-28 w-full object-cover"
                    />
                    <div className="flex items-center justify-between gap-1 px-2 py-1">
                      <p className="truncate text-[11px] text-muted-foreground">{sample.filename}</p>
                      {sample.is_answer && (
                        <span className="shrink-0 rounded bg-green-100 px-1.5 py-0.5 text-[10px] font-semibold text-green-700">
                          정답 이미지
                        </span>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            )}
            {sampleError && <p className="text-xs text-destructive">{sampleError}</p>}
            {preview && (
              <div className="rounded-lg border border-gray-200 bg-gray-50 p-2">
                <p className="mb-1 text-xs text-muted-foreground">선택된 샘플</p>
                <img src={preview} alt="선택된 샘플" className="max-h-56 rounded-lg object-contain" />
              </div>
            )}
          </div>
        </TabsContent>
      )}
    </Tabs>
  )
}
