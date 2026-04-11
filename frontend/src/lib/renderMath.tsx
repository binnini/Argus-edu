import * as React from "react"
import { InlineMath, BlockMath } from "react-katex"
import "katex/dist/katex.min.css"

/**
 * $...$ 와 $$...$$ 구문을 KaTeX로 렌더링한다.
 * 나머지는 평문으로 출력.
 */
export function renderMath(text: string): React.ReactNode {
  if (!text) return null
  const parts = text.split(/(\$\$[\s\S]+?\$\$|\$[^$]+?\$)/g)
  return parts.map((part, i) => {
    if (part.startsWith("$$") && part.endsWith("$$")) {
      try {
        return <BlockMath key={i} math={part.slice(2, -2)} />
      } catch {
        return <span key={i}>{part}</span>
      }
    }
    if (part.startsWith("$") && part.endsWith("$")) {
      try {
        return <InlineMath key={i} math={part.slice(1, -1)} />
      } catch {
        return <span key={i}>{part}</span>
      }
    }
    return <span key={i}>{part}</span>
  })
}
