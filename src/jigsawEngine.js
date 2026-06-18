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
    const s = 0.34 + (rng()-0.5)*0.04;
    const e = 0.66 + (rng()-0.5)*0.04;
    const c = 0.50 + (rng()-0.5)*0.035;
    const r = t * (0.88 + rng()*0.10);
    return [
      `L ${x+w*s} ${y}`,
      `C ${x+w*(s+0.035)} ${y} ${x+w*(s+0.055)} ${y+d*r*0.20} ${x+w*(s+0.085)} ${y+d*r*0.30}`,
      `C ${x+w*(s+0.13)} ${y+d*r*0.50} ${x+w*(c-0.15)} ${y+d*r*0.92} ${x+w*c} ${y+d*r*0.94}`,
      `C ${x+w*(c+0.15)} ${y+d*r*0.92} ${x+w*(e-0.13)} ${y+d*r*0.50} ${x+w*(e-0.085)} ${y+d*r*0.30}`,
      `C ${x+w*(e-0.055)} ${y+d*r*0.20} ${x+w*(e-0.035)} ${y} ${x+w*e} ${y}`,
      `L ${x+w} ${y}`
    ].join(' ');
  }

  function edgeRight(type, x, y, h, t, rng){
    if(type === 0) return `L ${x} ${y+h}`;
    const d = type === 1 ? 1 : -1;
    const s = 0.34 + (rng()-0.5)*0.04;
    const e = 0.66 + (rng()-0.5)*0.04;
    const c = 0.50 + (rng()-0.5)*0.035;
    const r = t * (0.88 + rng()*0.10);
    return [
      `L ${x} ${y+h*s}`,
      `C ${x} ${y+h*(s+0.035)} ${x+d*r*0.20} ${y+h*(s+0.055)} ${x+d*r*0.30} ${y+h*(s+0.085)}`,
      `C ${x+d*r*0.50} ${y+h*(s+0.13)} ${x+d*r*0.92} ${y+h*(c-0.15)} ${x+d*r*0.94} ${y+h*c}`,
      `C ${x+d*r*0.92} ${y+h*(c+0.15)} ${x+d*r*0.50} ${y+h*(e-0.13)} ${x+d*r*0.30} ${y+h*(e-0.085)}`,
      `C ${x+d*r*0.20} ${y+h*(e-0.055)} ${x} ${y+h*(e-0.035)} ${x} ${y+h*e}`,
      `L ${x} ${y+h}`
    ].join(' ');
  }

  function edgeBottom(type, x, y, w, t, rng){
    if(type === 0) return `L ${x-w} ${y}`;
    const d = type === 1 ? 1 : -1;
    const s = 0.34 + (rng()-0.5)*0.04;
    const e = 0.66 + (rng()-0.5)*0.04;
    const c = 0.50 + (rng()-0.5)*0.035;
    const r = t * (0.88 + rng()*0.10);
    return [
      `L ${x-w*s} ${y}`,
      `C ${x-w*(s+0.035)} ${y} ${x-w*(s+0.055)} ${y+d*r*0.20} ${x-w*(s+0.085)} ${y+d*r*0.30}`,
      `C ${x-w*(s+0.13)} ${y+d*r*0.50} ${x-w*(c-0.15)} ${y+d*r*0.92} ${x-w*c} ${y+d*r*0.94}`,
      `C ${x-w*(c+0.15)} ${y+d*r*0.92} ${x-w*(e-0.13)} ${y+d*r*0.50} ${x-w*(e-0.085)} ${y+d*r*0.30}`,
      `C ${x-w*(e-0.055)} ${y+d*r*0.20} ${x-w*(e-0.035)} ${y} ${x-w*e} ${y}`,
      `L ${x-w} ${y}`
    ].join(' ');
  }

  function edgeLeft(type, x, y, h, t, rng){
    if(type === 0) return `L ${x} ${y-h}`;
    const d = type === 1 ? -1 : 1;
    const s = 0.34 + (rng()-0.5)*0.04;
    const e = 0.66 + (rng()-0.5)*0.04;
    const c = 0.50 + (rng()-0.5)*0.035;
    const r = t * (0.88 + rng()*0.10);
    return [
      `L ${x} ${y-h*s}`,
      `C ${x} ${y-h*(s+0.035)} ${x+d*r*0.20} ${y-h*(s+0.055)} ${x+d*r*0.30} ${y-h*(s+0.085)}`,
      `C ${x+d*r*0.50} ${y-h*(s+0.13)} ${x+d*r*0.92} ${y-h*(c-0.15)} ${x+d*r*0.94} ${y-h*c}`,
      `C ${x+d*r*0.92} ${y-h*(c+0.15)} ${x+d*r*0.50} ${y-h*(e-0.13)} ${x+d*r*0.30} ${y-h*(e-0.085)}`,
      `C ${x+d*r*0.20} ${y-h*(e-0.055)} ${x} ${y-h*(e-0.035)} ${x} ${y-h*e}`,
      `L ${x} ${y-h}`
    ].join(' ');
  }

  function createPiecePath(tileW, tileH, pad, edges, rng){
    const x = pad, y = pad;
    const w = tileW, h = tileH;
    const tab = Math.max(14, Math.round(Math.min(tileW, tileH) * 0.26));
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

  function escapeImage(src){
    return String(src).replace(/&/g, '&amp;').replace(/"/g, '&quot;');
  }

  function svgForPiece(spec){
    const idBase = safeId(spec.id);
    const clipId = `clip-${idBase}`;
    const patternId = `pattern-${idBase}`;
    const escapedImage = escapeImage(spec.imageSrc);
    return `
      <svg class="piece-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${spec.outerW} ${spec.outerH}" width="${spec.outerW}" height="${spec.outerH}">
        <defs>
          <clipPath id="${clipId}" clipPathUnits="userSpaceOnUse"><path d="${spec.path}"/></clipPath>
          <pattern id="${patternId}" patternUnits="userSpaceOnUse" x="${spec.imageX}" y="${spec.imageY}" width="${spec.fullW}" height="${spec.fullH}">
            <image href="${escapedImage}" x="0" y="0" width="${spec.fullW}" height="${spec.fullH}" preserveAspectRatio="none"/>
          </pattern>
        </defs>
        <path d="${spec.path}" fill="#eef3ff" stroke="rgba(30,42,90,0.18)" stroke-width="1.1"/>
        <path d="${spec.path}" fill="url(#${patternId})" stroke="rgba(18,28,65,0.46)" stroke-width="1.35"/>
        <path d="${spec.path}" fill="none" stroke="rgba(255,255,255,0.72)" stroke-width="0.75"/>
      </svg>`;
  }

  function slotSvgForPiece(spec){
    return `
      <svg class="slot-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${spec.outerW} ${spec.outerH}" width="${spec.outerW}" height="${spec.outerH}">
        <path d="${spec.path}" fill="rgba(255,255,255,0.04)" stroke="rgba(78,96,150,0.28)" stroke-width="1.1" stroke-dasharray="5 5"/>
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

    let fullW = Number(opts.displayWidth || 0);
    let fullH = Number(opts.displayHeight || 0);

    if (!(fullW > 0 && fullH > 0)) {
      const scale = Math.min(maxW / naturalW, maxH / naturalH, 1);
      fullW = Math.round(naturalW * scale);
      fullH = Math.round(naturalH * scale);
    }

    fullW = Math.max(220, Math.round(fullW));
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
      spec.slotSvg = slotSvgForPiece(spec);
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
  console.log('PuzzleVerse classic jigsaw engine V1.3 loaded');
})();