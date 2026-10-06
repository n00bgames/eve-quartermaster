/** Pixel-preserving vertical screenshot composition. No OCR or generated pixels. */
export type GridCrop = { x: number; y: number; width: number; height: number };
export type PixelCrop = GridCrop;
export const fullGridCrop: GridCrop = { x: 0, y: 0, width: 100, height: 100 };
export const gridMaxBytes = 10 * 1024 * 1024;
export const gridMaxPixels = 64_000_000;
const maxDimension = 32767;

export function pixelCrop(width: number, height: number, crop: GridCrop): PixelCrop {
  if (![width, height, crop.x, crop.y, crop.width, crop.height].every(Number.isFinite)
    || width < 1 || height < 1 || crop.x < 0 || crop.y < 0 || crop.x >= 100 || crop.y >= 100
    || crop.width <= 0 || crop.height <= 0 || crop.width > 100 || crop.height > 100) {
    throw new Error("Select a non-empty grid area in every screenshot.");
  }
  const x = Math.min(width - 1, Math.round(width * crop.x / 100));
  const y = Math.min(height - 1, Math.round(height * crop.y / 100));
  return { x, y, width: Math.min(width - x, Math.max(1, Math.round(width * crop.width / 100))),
    height: Math.min(height - y, Math.max(1, Math.round(height * crop.height / 100))) };
}

export function stitchLayout(parts: { width: number; height: number; overlap: number | null }[]) {
  if (!parts.length) throw new Error("Add at least one screenshot.");
  const width = parts[0].width;
  let height = 0;
  const placements = parts.map((part, index) => {
    if (!Number.isInteger(part.width) || !Number.isInteger(part.height) || part.width < 1 || part.height < 1) {
      throw new Error("Select a non-empty grid area in every screenshot.");
    }
    if (part.width !== width) throw new Error("Cropped grids must have the same pixel width. Adjust the side crops; images are never resized.");
    const overlap = index === 0 ? 0 : part.overlap;
    if (overlap == null) throw new Error(`Set or detect the overlap for screenshot ${index + 1}. Use 0 only for adjoining captures with no repeated rows.`);
    if (!Number.isInteger(overlap) || overlap < 0 || overlap > Math.min(parts[index - 1]?.height ?? 0, part.height)) {
      throw new Error(`Screenshot ${index + 1} has an invalid overlap.`);
    }
    // Preserve the earlier screenshot's overlap, then append only new source pixels.
    const placement = { sourceY: overlap, y: height, height: part.height - overlap };
    height += placement.height;
    return placement;
  });
  if (width > maxDimension || height > maxDimension || width * height > gridMaxPixels) {
    throw new Error("Combined grid exceeds 64 megapixels or 32,767 pixels on one side. Crop away more of the surrounding UI or capture with more grid columns.");
  }
  return { width, height, placements };
}

export type RowSignature = { width: number; height: number; samples: number; values: Float32Array };

/** Keep native vertical coordinates but sample horizontal contrast, emphasizing codes over flat UI. */
export function rowSignature(pixels: { width: number; height: number; data: Uint8ClampedArray }): RowSignature {
  const samples = Math.min(256, pixels.width - 1);
  const stride = Math.max(1, Math.floor((pixels.width - 1) / samples));
  const values = new Float32Array(pixels.height * samples);
  const grey = (x: number, y: number) => {
    const p = (y * pixels.width + x) * 4;
    return (pixels.data[p] + pixels.data[p + 1] + pixels.data[p + 2]) / 3;
  };
  for (let y = 0; y < pixels.height; y++) {
    for (let s = 0; s < samples; s++) {
      const x = Math.floor(s * (pixels.width - 1) / samples);
      values[y * samples + s] = grey(Math.min(pixels.width - 1, x + stride), y) - grey(x, y);
    }
  }
  return { width: pixels.width, height: pixels.height, samples, values };
}

export function detectGridOverlap(previous: RowSignature, next: RowSignature): number | null {
  if (previous.width !== next.width || previous.samples !== next.samples || next.samples < 8) return null;
  const minimum = 16, maximum = Math.min(previous.height, next.height);
  if (maximum < minimum) return null;
  const scores: { overlap: number; error: number; signal: number }[] = [];
  for (let overlap = minimum; overlap <= maximum; overlap++) {
    let error = 0, signal = 0, count = 0;
    // All rows for short overlaps; bounded vertical sampling for long captures.
    const step = Math.max(1, Math.floor(overlap / 96));
    for (let y = 0; y < overlap; y += step) {
      const a = (previous.height - overlap + y) * previous.samples, b = y * next.samples;
      for (let s = 0; s < next.samples; s++) {
        const av = previous.values[a + s], bv = next.values[b + s];
        error += Math.abs(av - bv); signal += Math.abs(av) + Math.abs(bv); count++;
      }
    }
    scores.push({ overlap, error: error / count, signal: signal / (count * 2) });
  }
  // Flat gaps and repeated generic tile backgrounds cannot establish an alignment.
  const candidates = scores.filter((s) => s.signal >= 2 && s.error <= Math.min(3, s.signal * .25)).sort((a, b) => a.error - b.error);
  const best = candidates[0];
  if (!best) return null;
  const competitor = scores.filter((s) => s.signal >= 2 && Math.abs(s.overlap - best.overlap) > 3).sort((a, b) => a.error - b.error)[0];
  if (competitor && competitor.error <= best.error + Math.max(.6, best.signal * .15)) return null;
  return best.overlap;
}

export async function pngBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob((value) => value ? resolve(value) : reject(new Error("Unable to encode the grid. Try smaller crops.")), "image/png"));
  if (blob.size > gridMaxBytes) throw new Error("Combined PNG exceeds 10 MB. Crop away more of the surrounding UI.");
  return blob;
}
