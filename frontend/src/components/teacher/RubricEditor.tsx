import type { RubricSchema, RubricStep } from "@/api/problems"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Plus, Trash2 } from "lucide-react"

interface RubricEditorProps {
  value: RubricSchema
  onChange: (rubric: RubricSchema) => void
}

export default function RubricEditor({ value, onChange }: RubricEditorProps) {
  function updateStep(index: number, updated: Partial<RubricStep>) {
    const steps = value.steps.map((s, i) => (i === index ? { ...s, ...updated } : s))
    const total = steps.reduce((sum, s) => sum + (s.score || 0), 0)
    onChange({ steps, total_score: total })
  }

  function addStep() {
    const step = value.steps.length + 1
    const steps = [...value.steps, { step, description: "", score: 1 }]
    const total = steps.reduce((sum, s) => sum + (s.score || 0), 0)
    onChange({ steps, total_score: total })
  }

  function removeStep(index: number) {
    const steps = value.steps
      .filter((_, i) => i !== index)
      .map((s, i) => ({ ...s, step: i + 1 }))
    const total = steps.reduce((sum, s) => sum + (s.score || 0), 0)
    onChange({ steps, total_score: total })
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium">채점 기준 (루브릭)</label>
        <span className="text-xs text-muted-foreground">총점: {value.total_score}점</span>
      </div>
      {value.steps.map((step, i) => (
        <div key={i} className="flex gap-2 items-start">
          <span className="flex-shrink-0 w-6 h-8 flex items-center justify-center text-xs font-semibold text-muted-foreground">
            {step.step}
          </span>
          <Input
            placeholder="단계 설명"
            value={step.description}
            onChange={(e) => updateStep(i, { description: e.target.value })}
            className="flex-1"
          />
          <Input
            type="number"
            min={0}
            max={100}
            value={step.score}
            onChange={(e) => updateStep(i, { score: Number(e.target.value) })}
            className="w-20"
          />
          <span className="text-xs text-muted-foreground h-10 flex items-center">점</span>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={() => removeStep(i)}
            className="flex-shrink-0"
          >
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      ))}
      <Button type="button" variant="outline" size="sm" onClick={addStep} className="w-full">
        <Plus className="h-4 w-4 mr-1" /> 단계 추가
      </Button>
    </div>
  )
}
