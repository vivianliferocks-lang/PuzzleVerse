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

  function calculateGrid(pieceCount, aspectRatio) {
    pieceCount = Math.max(4, Number(pieceCount || 4));
    aspectRatio = Number(aspectRatio || 1.45);
    let best = { cols: pieceCount, rows: 1, total: pieceCount, score: Infinity };

    for (let rows = 1; rows <= Math.ceil(Math.sqrt(pieceCount)) + 10; rows++) {
      const cols = Math.ceil(pieceCount / rows);
      const total = rows * cols;
      const fillPenalty = (total - pieceCount) * 0.42;
      const gridAspect = cols / rows;
      const score = Math.abs(gridAspect - aspectRatio) + fillPenalty;
      if (score < best.score) best = { cols, rows, total, score };
    }
    return best;
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

  function edgeTop(type, x, y, w, t, rng){
    if(type === 0) return `L ${x+w} ${y}`;
    const d = type === 1 ? -1 : 1;
    const a = 0.30 + rng()*0.035;
    const b = 0.38 + rng()*0.018;
    const c = 0.50 + (rng()-0.5)*0.035;
    const e = 0.62 + rng()*0.018;
    const f = 0.70 - rng()*0.035;
    return [
      `L ${x+w*a} ${y}`,
      `C ${x+w*(a+0.03)} ${y} ${x+w*(b-0.025)} ${y+d*t*0.10} ${x+w*b} ${y+d*t*0.24}`,
      `C ${x+w*(b+0.02)} ${y+d*t*0.48} ${x+w*(c-0.14)} ${y+d*t*0.86} ${x+w*c} ${y+d*t*0.88}`,
      `C ${x+w*(c+0.14)} ${y+d*t*0.86} ${x+w*(e-0.02)} ${y+d*t*0.48} ${x+w*e} ${y+d*t*0.24}`,
      `C ${x+w*(e+0.025)} ${y+d*t*0.10} ${x+w*(f-0.03)} ${y} ${x+w*f} ${y}`,
      `L ${x+w} ${y}`
    ].join(' ');
  }

  function edgeRight(type, x, y, h, t, rng){
    if(type === 0) return `L ${x} ${y+h}`;
    const d = type === 1 ? 1 : -1;
    const a = 0.30 + rng()*0.035;
    const b = 0.38 + rng()*0.018;
    const c = 0.50 + (rng()-0.5)*0.035;
    const e = 0.62 + rng()*0.018;
    const f = 0.70 - rng()*0.035;
    return [
      `L ${x} ${y+h*a}`,
      `C ${x} ${y+h*(a+0.03)} ${x+d*t*0.10} ${y+h*(b-0.025)} ${x+d*t*0.24} ${y+h*b}`,
      `C ${x+d*t*0.48} ${y+h*(b+0.02)} ${x+d*t*0.86} ${y+h*(c-0.14)} ${x+d*t*0.88} ${y+h*c}`,
      `C ${x+d*t*0.86} ${y+h*(c+0.14)} ${x+d*t*0.48} ${y+h*(e-0.02)} ${x+d*t*0.24} ${y+h*e}`,
      `C ${x+d*t*0.10} ${y+h*(e+0.025)} ${x} ${y+h*(f-0.03)} ${x} ${y+h*f}`,
      `L ${x} ${y+h}`
    ].join(' ');
  }

  function edgeBottom(type, x, y, w, t, rng){
    if(type === 0) return `L ${x-w} ${y}`;
    const d = type === 1 ? 1 : -1;
    const a = 0.30 + rng()*0.035;
    const b = 0.38 + rng()*0.018;
    const c = 0.50 + (rng()-0.5)*0.035;
    const e = 0.62 + rng()*0.018;
    const f = 0.70 - rng()*0.035;
    return [
      `L ${x-w*a} ${y}`,
      `C ${x-w*(a+0.03)} ${y} ${x-w*(b-0.025)} ${y+d*t*0.10} ${x-w*b} ${y+d*t*0.24}`,
      `C ${x-w*(b+0.02)} ${y+d*t*0.48} ${x-w*(c-0.14)} ${y+d*t*0.86} ${x-w*c} ${y+d*t*0.88}`,
      `C ${x-w*(c+0.14)} ${y+d*t*0.86} ${x-w*(e-0.02)} ${y+d*t*0.48} ${x-w*e} ${y+d*t*0.24}`,
      `C ${x-w*(e+0.025)} ${y+d*t*0.10} ${x-w*(f-0.03)} ${y} ${x-w*f} ${y}`,
      `L ${x-w} ${y}`
    ].join(' ');
  }

  function edgeLeft(type, x, y, h, t, rng){
    if(type === 0) return `L ${x} ${y-h}`;
    const d = type === 1 ? -1 : 1;
    const a = 0.30 + rng()*0.035;
    const b = 0.38 + rng()*0.018;
    const c = 0.50 + (rng()-0.5)*0.035;
    const e = 0.62 + rng()*0.018;
    const f = 0.70 - rng()*0.035;
    return [
      `L ${x} ${y-h*a}`,
      `C ${x} ${y-h*(a+0.03)} ${x+d*t*0.10} ${y-h*(b-0.025)} ${x+d*t*0.24} ${y-h*b}`,
      `C ${x+d*t*0.48} ${y-h*(b+0.02)} ${x+d*t*0.86} ${y-h*(c-0.14)} ${x+d*t*0.88} ${y-h*c}`,
      `C ${x+d*t*0.86} ${y-h*(c+0.14)} ${x+d*t*0.48} ${y-h*(e-0.02)} ${x+d*t*0.24} ${y-h*e}`,
      `C ${x+d*t*0.10} ${y-h*(e+0.025)} ${x} ${y-h*(f-0.03)} ${x} ${y-h*f}`,
      `L ${x} ${y-h}`
    ].join(' ');
  }

  function createPiecePath(tileW, tileH, pad, edges, rng){
    const x = pad, y = pad;
    const w = tileW, h = tileH;
    const tab = Math.max(12, Math.round(Math.min(tileW, tileH) * 0.28));
    const path = [
      `M ${x} ${y}`,
      edgeTop(edges.top, x, y, w, tab, rng),
      edgeRight(edges.right, x+w, y, h, tab, rng),
      edgeBottom(edges.bottom, x+w, y+h, w, tab, rng),
      edgeLeft(edges.left, x, y+h, h, tab, rng),
      'Z'
    ].join(' ');
    return { path, outerW: tileW + pad*2, outerH: tileH + pad*2 };
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
        <path d="${spec.path}" fill="#eef3ff" stroke="rgba(30,42,90,0.18)" stroke-width="1.2"/>
        <path d="${spec.path}" fill="url(#${patternId})" stroke="rgba(18,28,65,0.42)" stroke-width="1.25"/>
        <path d="${spec.path}" fill="none" stroke="rgba(255,255,255,0.68)" stroke-width="0.75"/>
      </svg>`;
  }

  function buildLayout(opts){
    const pieceCount = Number(opts.pieceCount || 9);
    const puzzleId = safeId(opts.puzzleId || 'puzzle');
    const naturalW = Math.max(1, Number(opts.naturalWidth || 1600));
    const naturalH = Math.max(1, Number(opts.naturalHeight || 1000));
    const imageAspect = naturalW / naturalH;

    const maxW = Number(opts.maxWidth || 780);
    const maxH = Number(opts.maxHeight || 560);

    let fullW = maxW;
    let fullH = fullW / imageAspect;
    if (fullH > maxH) {
      fullH = maxH;
      fullW = fullH * imageAspect;
    }

    fullW = Math.max(260, Math.round(fullW));
    fullH = Math.max(180, Math.round(fullH));

    const grid = calculateGrid(pieceCount, imageAspect);
    const cols = grid.cols;
    const rows = grid.rows;
    const tileW = fullW / cols;
    const tileH = fullH / rows;

    const seed = hashString(`${puzzleId}-${pieceCount}`);
    const rng = seeded(seed);
    const edgeMap = generateEdgeMap(rows, cols, rng);
    const pad = Math.round(Math.min(tileW, tileH) * 0.30);

    const pieces = edgeMap.slice(0, pieceCount).map(edge => {
      const localRng = seeded(seed + edge.index * 8191);
      const p = createPiecePath(tileW, tileH, pad, edge, localRng);
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
  console.log('PuzzleVerse jigsaw engine V1.2 loaded');
})();