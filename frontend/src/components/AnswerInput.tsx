import { useState, useRef } from "react";

export type InputMode = "text" | "image";

interface AnswerInputProps {
  onSubmitText: (answer: string) => void;
  onSubmitImage: (file: File) => void;
  disabled: boolean;
}

export default function AnswerInput({ onSubmitText, onSubmitImage, disabled }: AnswerInputProps) {
  const [mode, setMode] = useState<InputMode>("text");
  const [textAnswer, setTextAnswer] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleImageChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = (ev) => setImagePreview(ev.target?.result as string);
    reader.readAsDataURL(file);
  }

  function handleSubmit() {
    if (disabled) return;
    if (mode === "text") {
      if (!textAnswer.trim()) return;
      onSubmitText(textAnswer.trim());
    } else {
      if (!imageFile) return;
      onSubmitImage(imageFile);
    }
  }

  const canSubmit =
    !disabled && (mode === "text" ? textAnswer.trim().length > 0 : imageFile !== null);

  return (
    <div style={styles.wrapper}>
      {/* 탭 */}
      <div style={styles.tabs}>
        <button
          style={{ ...styles.tab, ...(mode === "text" ? styles.activeTab : {}) }}
          onClick={() => setMode("text")}
          disabled={disabled}
        >
          텍스트 입력
        </button>
        <button
          style={{ ...styles.tab, ...(mode === "image" ? styles.activeTab : {}) }}
          onClick={() => setMode("image")}
          disabled={disabled}
        >
          손글씨 이미지 업로드
        </button>
      </div>

      {/* 텍스트 입력 */}
      {mode === "text" && (
        <textarea
          style={styles.textarea}
          placeholder="풀이 과정과 답을 입력하세요..."
          value={textAnswer}
          onChange={(e) => setTextAnswer(e.target.value)}
          rows={6}
          disabled={disabled}
        />
      )}

      {/* 이미지 업로드 */}
      {mode === "image" && (
        <div style={styles.imageZone}>
          <input
            type="file"
            ref={fileInputRef}
            accept="image/jpeg,image/png,image/webp"
            onChange={handleImageChange}
            style={{ display: "none" }}
            disabled={disabled}
          />
          {imagePreview ? (
            <div>
              <img src={imagePreview} alt="업로드된 손글씨" style={styles.preview} />
              <button
                style={styles.changeBtn}
                onClick={() => {
                  setImageFile(null);
                  setImagePreview(null);
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
                disabled={disabled}
              >
                다시 선택
              </button>
            </div>
          ) : (
            <div
              style={styles.dropZone}
              onClick={() => fileInputRef.current?.click()}
            >
              <p>📷 손글씨 풀이 이미지를 선택하세요</p>
              <p style={{ fontSize: "0.85rem", color: "#666" }}>
                JPEG / PNG / WEBP, 최대 10MB
              </p>
            </div>
          )}
        </div>
      )}

      <button style={styles.submitBtn} onClick={handleSubmit} disabled={!canSubmit}>
        {disabled ? "제출 중..." : "답변 제출"}
      </button>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: { marginTop: "1rem" },
  tabs: { display: "flex", gap: "0.5rem", marginBottom: "0.75rem" },
  tab: {
    padding: "0.5rem 1.25rem",
    border: "1px solid #ccc",
    borderRadius: 6,
    background: "white",
    cursor: "pointer",
    fontSize: "0.9rem",
  },
  activeTab: {
    background: "#2563eb",
    color: "white",
    borderColor: "#2563eb",
  },
  textarea: {
    width: "100%",
    padding: "0.75rem",
    fontSize: "1rem",
    borderRadius: 8,
    border: "1px solid #ccc",
    boxSizing: "border-box",
    resize: "vertical",
  },
  imageZone: { minHeight: 160 },
  dropZone: {
    border: "2px dashed #ccc",
    borderRadius: 8,
    padding: "2rem",
    textAlign: "center",
    cursor: "pointer",
    background: "#fafafa",
  },
  preview: {
    maxWidth: "100%",
    maxHeight: 300,
    borderRadius: 8,
    border: "1px solid #e0e0e0",
    display: "block",
    marginBottom: "0.5rem",
  },
  changeBtn: {
    padding: "0.4rem 1rem",
    border: "1px solid #ccc",
    borderRadius: 6,
    background: "white",
    cursor: "pointer",
    fontSize: "0.85rem",
  },
  submitBtn: {
    marginTop: "1rem",
    padding: "0.75rem 2rem",
    background: "#2563eb",
    color: "white",
    border: "none",
    borderRadius: 8,
    fontSize: "1rem",
    cursor: "pointer",
    width: "100%",
  },
};
