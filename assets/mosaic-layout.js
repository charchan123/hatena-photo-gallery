(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.DetailMosaicLayout = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const MOSAIC_GAP = 10;
  const MAX_CROP_RATIO = 0.12;
  const SINGLE_MAX_WIDTH = 380;

  function finiteRatio(value) {
    const ratio = Number(value);
    return Number.isFinite(ratio) && ratio > 0 ? ratio : 1;
  }

  function balancedColumns(ratios, count, nominalWidth) {
    const columns = Array.from({ length: count }, () => ({ items: [], height: 0 }));
    ratios.forEach((ratio, index) => {
      const column = columns.reduce((best, candidate) => (
        candidate.height < best.height ? candidate : best
      ), columns[0]);
      column.items.push({ index, ratio });
      column.height += nominalWidth / ratio + (column.items.length > 1 ? MOSAIC_GAP : 0);
    });
    return columns;
  }

  /*
   * Pure layout calculation. Column widths are solved together after balanced
   * masonry partitioning. This keeps every image at its natural ratio (zero
   * crop in the normal path), while fixed gaps and every column bottom match.
   */
  function computeMosaicLayout(imageRatios, containerWidth, requestedColumns, gap, options) {
    const ratios = imageRatios.map(finiteRatio);
    const fixedGap = Number.isFinite(gap) && gap >= 0 ? gap : MOSAIC_GAP;
    const cropLimit = options?.maxCropRatio ?? MAX_CROP_RATIO;
    if (!ratios.length) return { columns: [], items: [], width: 0, height: 0, gap: fixedGap, maxBottomError: 0 };

    if (ratios.length === 1) {
      const width = Math.min(Math.max(1, containerWidth), options?.singleMaxWidth ?? SINGLE_MAX_WIDTH);
      return {
        columns: [{ width, items: [0], bottom: width / ratios[0] }],
        items: [{ index: 0, column: 0, top: 0, width, height: width / ratios[0], cropRatio: 0,
          corners: ["tl", "tr", "bl", "br"] }],
        width, height: width / ratios[0], gap: fixedGap, cropLimit, maxBottomError: 0,
      };
    }

    const columnCount = Math.max(1, Math.min(ratios.length, Math.floor(requestedColumns) || 1));
    const availableWidth = Math.max(columnCount, containerWidth - fixedGap * (columnCount - 1));
    const nominalWidth = availableWidth / columnCount;
    const groups = balancedColumns(ratios, columnCount, nominalWidth);
    const coefficients = groups.map(column => column.items.reduce((sum, item) => sum + 1 / item.ratio, 0));
    const verticalGaps = groups.map(column => fixedGap * Math.max(0, column.items.length - 1));
    const reciprocalSum = coefficients.reduce((sum, value) => sum + 1 / value, 0);
    const gapCorrection = verticalGaps.reduce((sum, value, index) => sum + value / coefficients[index], 0);
    const targetHeight = (availableWidth + gapCorrection) / reciprocalSum;
    const widths = coefficients.map((coefficient, index) => (targetHeight - verticalGaps[index]) / coefficient);

    const items = [];
    groups.forEach((column, columnIndex) => {
      let top = 0;
      column.items.forEach((item, itemIndex) => {
        const height = widths[columnIndex] / item.ratio;
        items.push({
          index: item.index, column: columnIndex, top, width: widths[columnIndex], height,
          cropRatio: 0, corners: [],
        });
        top += height + (itemIndex < column.items.length - 1 ? fixedGap : 0);
      });
    });
    items.sort((a, b) => a.index - b.index);

    const firstColumn = items.filter(item => item.column === 0);
    const lastColumn = items.filter(item => item.column === columnCount - 1);
    firstColumn[0].corners.push("tl");
    firstColumn[firstColumn.length - 1].corners.push("bl");
    lastColumn[0].corners.push("tr");
    lastColumn[lastColumn.length - 1].corners.push("br");

    const columns = groups.map((column, index) => ({
      width: widths[index], items: column.items.map(item => item.index), bottom: targetHeight,
    }));
    return {
      columns, items, width: containerWidth, height: targetHeight, gap: fixedGap,
      cropLimit, maxBottomError: Math.max(...columns.map(column => Math.abs(column.bottom - targetHeight))),
    };
  }

  return { MOSAIC_GAP, MAX_CROP_RATIO, SINGLE_MAX_WIDTH, computeMosaicLayout };
});
