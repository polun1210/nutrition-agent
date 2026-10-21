import { useState } from "react";

const EXPIRED_TEXT = "照片已超過保存期限";

interface PhotoThumbsProps {
  name: string;
  photoIds?: number[];
}

/** 產品名稱旁的照片縮圖；照片只有本人拿得到（cookie 驗證），所以直接用 <img>。 */
export default function PhotoThumbs({ name, photoIds }: PhotoThumbsProps) {
  if (!photoIds || photoIds.length === 0) return null;
  return (
    <span className="thumbs">
      {photoIds.map((id, i) => (
        <Thumb key={id} id={id} alt={`${name} 的標示照片 ${i + 1}`} />
      ))}
    </span>
  );
}

/** 載入失敗（過期的 410、物件已刪的 404 等）就換成替代文字，不留破圖。 */
function Thumb({ id, alt }: { id: number; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <span role="img" aria-label={alt} className="thumb thumb-missing">
        {EXPIRED_TEXT}
      </span>
    );
  }
  return <img src={`/api/photos/${id}`} alt={alt} className="thumb" onError={() => setFailed(true)} />;
}
