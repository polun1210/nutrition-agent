/** 產品名稱旁的照片縮圖；照片只有本人拿得到（cookie 驗證），所以直接用 <img>。 */
export default function PhotoThumbs({ name, photoIds }: { name: string; photoIds?: number[] }) {
  if (!photoIds || photoIds.length === 0) return null;
  return (
    <span className="thumbs">
      {photoIds.map((id, i) => (
        <img key={id} src={`/api/photos/${id}`} alt={`${name} 的標示照片 ${i + 1}`} className="thumb" />
      ))}
    </span>
  );
}
