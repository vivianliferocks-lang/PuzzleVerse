(function(){
  function safeId(str){
    return String(str || 'pv').replace(/[^a-zA-Z0-9_-]/g, '-');
  }

  function hashString(str){
    let h = 2166136261;
    for(let i=0;i<str.length;i++){
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return (h >>> 0) || 1;
  }

  function seeded(seed){
    let x = seed % 2147483647;
    if (x <= 0) x += 2147483646;
    return function(){
      x = x * 48271 % 2147483647;
      return x / 2147483647;
    };
  }

  function calculateGrid(pieceCount) {
    pieceCount = Math.max(4, Number(pieceCount || 4));
    let best = { cols: pieceCount, rows: 1, score: Infinity };
    for (let rows = 1; rows <= Math.sqrt(pieceCount); rows++) {
      if (pieceCount % rows !== 0) continue;
      const cols = pieceCount / rows;
      const aspect = cols / rows;
      const score = Math.abs(aspect - 1.45);
      if (score < best.score) best = { cols, rows, score };
    }
    if (best.score === Infinity) {
      const cols = Math.ceil(Math.sqrt(pieceCount));
      const rows = Math.ceil(pieceCount / cols);
      return { cols, rows, total: cols * rows };
    }
    return { cols: best.cols, rows: best.rows, total: best.cols * best.rows };
  }

  function complement(v){ return v === 1 ? -1 : v === -1 ? 1 : 0; }

  function generateEdgeMap(rows, cols, rng){
    const pieces = [];
    for(let r=0;r<rows;r++){
      for(let c=0;c<cols;c++){
        const idx = r * cols + c;
        const top = r === 0 ? 0 : complement(pieces[(r-1)*cols + c].bottom);
        const left = c === 0 ? 0 : complement(pieces[idx - 1].right);
        const right = c === cols - 1 ? 0 : (rng() > 0.5 ? 1 : -1);
        const bottom = r === rows - 1 ? 0 : (rng() > 0.5 ? 1 : -1);
        pieces.push({ index: idx, row: r, col: c, top, right, bottom, left });
      }
    }
    return pieces;
  }

  function topEdge(type, x, y, w, tab){
    if(type === 0) return `L ${x+w} ${y}`;
    const d = type === 1 ? -1 : 1;
    return [
      `L ${x+w*.28} ${y}`,
      `C ${x+w*.34} ${y} ${x+w*.36} ${y+d*tab*.20} ${x+w*.41} ${y+d*tab*.28}`,
      `C ${x+w*.48} ${y+d*tab*.92} ${x+w*.52} ${y+d*tab*.92} ${x+w*.59} ${y+d*tab*.28}`,
      `C ${x+w*.64} ${y+d*tab*.20} ${x+w*.66} ${y} ${x+w*.72} ${y}`,
      `L ${x+w} ${y}`
    ].join(' ');
  }

  function rightEdge(type, x, y, h, tab){
    if(type === 0) return `L ${x} ${y+h}`;
    const d = type === 1 ? 1 : -1;
    return [
      `L ${x} ${y+h*.28}`,
      `C ${x} ${y+h*.34} ${x+d*tab*.20} ${y+h*.36} ${x+d*tab*.28} ${y+h*.41}`,
      `C ${x+d*tab*.92} ${y+h*.48} ${x+d*tab*.92} ${y+h*.52} ${x+d*tab*.28} ${y+h*.59}`,
      `C ${x+d*tab*.20} ${y+h*.64} ${x} ${y+h*.66} ${x} ${y+h*.72}`,
      `L ${x} ${y+h}`
    ].join(' ');
  }

  function bottomEdge(type, x, y, w, tab){
    if(type === 0) return `L ${x-w} ${y}`;
    const d = type === 1 ? 1 : -1;
    return [
      `L ${x-w*.28} ${y}`,
      `C ${x-w*.34} ${y} ${x-w*.36} ${y+d*tab*.20} ${x-w*.41} ${y+d*tab*.28}`,
      `C ${x-w*.48} ${y+d*tab*.92} ${x-w*.52} ${y+d*tab*.92} ${x-w*.59} ${y+d*tab*.28}`,
      `C ${x-w*.64} ${y+d*tab*.20} ${x-w*.66} ${y} ${x-w*.72} ${y}`,
      `L ${x-w} ${y}`
    ].join(' ');
  }

  function leftEdge(type, x, y, h, tab){
    if(type === 0) return `L ${x} ${y-h}`;
    const d = type === 1 ? -1 : 1;
    return [
      `L ${x} ${y-h*.28}`,
      `C ${x} ${y-h*.34} ${x+d*tab*.20} ${y-h*.36} ${x+d*tab*.28} ${y-h*.41}`,
      `C ${x+d*tab*.92} ${y-h*.48} ${x+d*tab*.92} ${y-h*.52} ${x+d*tab*.28} ${y-h*.59}`,
      `C ${x+d*tab*.20} ${y-h*.64} ${x} ${y-h*.66} ${x} ${y-h*.72}`,
      `L ${x} ${y-h}`
    ].join(' ');
  }

  function createPiecePath(tileW, tileH, pad, edges){
    const x = pad, y = pad;
    const w = tileW, h = tileH;
    const tab = Math.max(12, Math.round(Math.min(tileW, tileH) * 0.22));
    const path = [
      `M ${x} ${y}`,
      topEdge(edges.top, x, y, w, tab),
      rightEdge(edges.right, x+w, y, h, tab),
      bottomEdge(edges.bottom, x+w, y+h, w, tab),
      leftEdge(edges.left, x, y+h, h, tab),
      'Z'
    ].join(' ');
    return { path, tab, outerW: tileW + pad*2, outerH: tileH + pad*2 };
  }

  function svgForPiece(spec){
    const idBase = safeId(spec.id);
    const clipId = `clip-${idBase}`;
    const patternId = `pattern-${idBase}`;
    const escapedImage = String(spec.imageSrc).replace(/&/g, '&amp;').replace(/"/g, '&quot;');
    return `
      <svg class="piece-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${spec.outerW} ${spec.outerH}" width="${spec.outerW}" height="${spec.outerH}">
        <defs>
          <clipPath id="${clipId}" clipPathUnits="userSpaceOnUse"><path d="${spec.path}"/></clipPath>
          <pattern id="${patternId}" patternUnits="userSpaceOnUse" x="${spec.imageX}" y="${spec.imageY}" width="${spec.fullW}" height="${spec.fullH}">
            <image href="${escapedImage}" x="0" y="0" width="${spec.fullW}" height="${spec.fullH}" preserveAspectRatio="none"/>
          </pattern>
        </defs>
        <path d="${spec.path}" fill="#eef3ff" stroke="rgba(30,42,90,0.24)" stroke-width="1.3"/>
        <path d="${spec.path}" fill="url(#${patternId})" stroke="rgba(25,31,70,0.35)" stroke-width="1.3"/>
        <path d="${spec.path}" fill="none" stroke="rgba(255,255,255,0.6)" stroke-width="0.75"/>
      </svg>`;
  }

  function buildLayout(opts){
    const pieceCount = Number(opts.pieceCount || 9);
    const puzzleId = safeId(opts.puzzleId || 'puzzle');
    const boardWidthBase = Number(opts.maxWidth || 760);
    const grid = calculateGrid(pieceCount);
    const cols = grid.cols, rows = grid.rows;
    const tileW = Math.max(64, Math.floor(boardWidthBase / cols));
    const tileH = Math.max(58, Math.floor(tileW * 0.78));
    const seed = hashString(`${puzzleId}-${pieceCount}`);
    const rng = seeded(seed);
    const edgeMap = generateEdgeMap(rows, cols, rng);
    const pad = Math.round(Math.min(tileW, tileH) * 0.25);
    const fullW = tileW * cols;
    const fullH = tileH * rows;

    const pieces = edgeMap.slice(0, pieceCount).map(edge => {
      const p = createPiecePath(tileW, tileH, pad, edge);
      const spec = {
        id: `${puzzleId}-${edge.index}`,
        index: edge.index,
        row: edge.row,
        col: edge.col,
        tileW,
        tileH,
        pad,
        path: p.path,
        outerW: p.outerW,
        outerH: p.outerH,
        snapX: edge.col * tileW,
        snapY: edge.row * tileH,
        imageSrc: opts.imageSrc,
        imageX: pad - edge.col * tileW,
        imageY: pad - edge.row * tileH,
        fullW,
        fullH
      };
      spec.svg = svgForPiece(spec);
      return spec;
    });

    return {
      seed, cols, rows, tileW, tileH, pad,
      boardWidth: fullW + pad * 2,
      boardHeight: fullH + pad * 2,
      fullW, fullH,
      pieces
    };
  }

  window.PVJigsaw = { buildLayout, calculateGrid, hashString };
  console.log('PuzzleVerse jigsaw engine loaded');
})();