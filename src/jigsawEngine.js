(function(){
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
    let best = { cols: pieceCount, rows: 1, score: Infinity };
    for (let rows = 1; rows <= Math.sqrt(pieceCount); rows++) {
      if (pieceCount % rows !== 0) continue;
      const cols = pieceCount / rows;
      const aspect = cols / rows;
      const score = Math.abs(aspect - 1.5);
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

  function edgePath(side, type, x, y, w, h, tab, neck, variance){
    const v1 = variance * 0.5;
    if(side === 'top'){
      if(type === 0) return `L ${x+w} ${y}`;
      const dir = type === 1 ? -1 : 1;
      return [
        `L ${x + w*0.28} ${y}`,
        `C ${x + w*(0.36-v1)} ${y}, ${x + w*(0.40-v1)} ${y + dir*tab*0.18}, ${x + w*(0.42-v1)} ${y + dir*tab*0.35}`,
        `C ${x + w*(0.46-v1)} ${y + dir*tab*0.92}, ${x + w*(0.54+v1)} ${y + dir*tab*0.92}, ${x + w*(0.58+v1)} ${y + dir*tab*0.35}`,
        `C ${x + w*(0.60+v1)} ${y + dir*tab*0.18}, ${x + w*(0.64+v1)} ${y}, ${x + w*0.72} ${y}`,
        `L ${x + w} ${y}`
      ].join(' ');
    }
    if(side === 'right'){
      if(type === 0) return `L ${x} ${y+h}`;
      const dir = type === 1 ? 1 : -1;
      return [
        `L ${x} ${y + h*0.28}`,
        `C ${x} ${y + h*(0.36-v1)}, ${x + dir*tab*0.18} ${y + h*(0.40-v1)}, ${x + dir*tab*0.35} ${y + h*(0.42-v1)}`,
        `C ${x + dir*tab*0.92} ${y + h*(0.46-v1)}, ${x + dir*tab*0.92} ${y + h*(0.54+v1)}, ${x + dir*tab*0.35} ${y + h*(0.58+v1)}`,
        `C ${x + dir*tab*0.18} ${y + h*(0.60+v1)}, ${x} ${y + h*(0.64+v1)}, ${x} ${y + h*0.72}`,
        `L ${x} ${y + h}`
      ].join(' ');
    }
    if(side === 'bottom'){
      if(type === 0) return `L ${x-w} ${y}`;
      const dir = type === 1 ? 1 : -1;
      return [
        `L ${x - w*0.28} ${y}`,
        `C ${x - w*(0.36-v1)} ${y}, ${x - w*(0.40-v1)} ${y + dir*tab*0.18}, ${x - w*(0.42-v1)} ${y + dir*tab*0.35}`,
        `C ${x - w*(0.46-v1)} ${y + dir*tab*0.92}, ${x - w*(0.54+v1)} ${y + dir*tab*0.92}, ${x - w*(0.58+v1)} ${y + dir*tab*0.35}`,
        `C ${x - w*(0.60+v1)} ${y + dir*tab*0.18}, ${x - w*(0.64+v1)} ${y}, ${x - w*0.72} ${y}`,
        `L ${x - w} ${y}`
      ].join(' ');
    }
    if(type === 0) return `L ${x} ${y-h}`;
    const dir = type === 1 ? -1 : 1;
    return [
      `L ${x} ${y - h*0.28}`,
      `C ${x} ${y - h*(0.36-v1)}, ${x + dir*tab*0.18} ${y - h*(0.40-v1)}, ${x + dir*tab*0.35} ${y - h*(0.42-v1)}`,
      `C ${x + dir*tab*0.92} ${y - h*(0.46-v1)}, ${x + dir*tab*0.92} ${y - h*(0.54+v1)}, ${x + dir*tab*0.35} ${y - h*(0.58+v1)}`,
      `C ${x + dir*tab*0.18} ${y - h*(0.60+v1)}, ${x} ${y - h*(0.64+v1)}, ${x} ${y - h*0.72}`,
      `L ${x} ${y - h}`
    ].join(' ');
  }

  function createPiecePath(tileW, tileH, pad, edges, rng){
    const x = pad, y = pad;
    const w = tileW, h = tileH;
    const tab = Math.max(10, Math.round(Math.min(tileW, tileH) * 0.22));
    const variance = 0.16 + rng()*0.08;
    const path = [
      `M ${x} ${y}`,
      edgePath('top', edges.top, x, y, w, h, tab, tab*0.45, variance),
      edgePath('right', edges.right, x+w, y, w, h, tab, tab*0.45, variance),
      edgePath('bottom', edges.bottom, x+w, y+h, w, h, tab, tab*0.45, variance),
      edgePath('left', edges.left, x, y+h, w, h, tab, tab*0.45, variance),
      'Z'
    ].join(' ');
    return { path, tab, outerW: tileW + pad*2, outerH: tileH + pad*2 };
  }

  function svgForPiece(spec){
    const clipId = `clip-${spec.id}`;
    const imgId = `img-${spec.id}`;
    return `
      <svg class="piece-svg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${spec.outerW} ${spec.outerH}" width="${spec.outerW}" height="${spec.outerH}" aria-hidden="true">
        <defs>
          <clipPath id="${clipId}"><path d="${spec.path}"/></clipPath>
          <filter id="shadow-${spec.id}" x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="0" dy="1.4" stdDeviation="1.8" flood-color="rgba(0,0,0,0.28)"/>
          </filter>
        </defs>
        <path d="${spec.path}" fill="#ffffff" stroke="rgba(0,0,0,0.18)" stroke-width="1.25" filter="url(#shadow-${spec.id})"/>
        <image id="${imgId}" href="${spec.imageSrc}" x="${spec.imageX}" y="${spec.imageY}" width="${spec.fullW}" height="${spec.fullH}" preserveAspectRatio="none" clip-path="url(#${clipId})"/>
        <path d="${spec.path}" fill="none" stroke="rgba(255,255,255,0.35)" stroke-width="0.8"/>
      </svg>`;
  }

  function buildLayout(opts){
    const pieceCount = Number(opts.pieceCount || 9);
    const puzzleId = String(opts.puzzleId || 'puzzle');
    const boardWidthBase = Number(opts.maxWidth || 760);
    const grid = calculateGrid(pieceCount);
    const cols = grid.cols, rows = grid.rows;
    const tileW = Math.max(56, Math.floor(boardWidthBase / cols));
    const tileH = Math.max(56, Math.floor(tileW * 0.78));
    const seed = hashString(`${puzzleId}-${pieceCount}`);
    const rng = seeded(seed);
    const edgeMap = generateEdgeMap(rows, cols, rng);
    const pad = Math.round(Math.min(tileW, tileH) * 0.24);
    const fullW = tileW * cols;
    const fullH = tileH * rows;

    const pieces = edgeMap.slice(0, pieceCount).map(edge => {
      const localRng = seeded(seed + edge.index * 7919);
      const p = createPiecePath(tileW, tileH, pad, edge, localRng);
      const spec = {
        id: `${puzzleId}-${edge.index}`,
        index: edge.index,
        row: edge.row,
        col: edge.col,
        top: edge.top,
        right: edge.right,
        bottom: edge.bottom,
        left: edge.left,
        tileW,
        tileH,
        pad,
        path: p.path,
        outerW: p.outerW,
        outerH: p.outerH,
        boardX: edge.col * tileW,
        boardY: edge.row * tileH,
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
})();
