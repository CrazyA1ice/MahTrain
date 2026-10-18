// ============================================================
// scene.mjs — 桌子 / 牌墙 / 骰子 / 灯光 / 尘埃
// ============================================================
import * as THREE from 'three';
import * as CANNON from './physics.ts';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { TileFactory } from './tile-factory.ts';
import { Tex } from './tex.ts';
import { world, matGround, matDice } from './physics.ts';
import { sceneRefs } from './state/scene-refs.ts';
import { CFG, SPACING, LAYER_Y, MY_SEAT, pivotRotYForSeat } from './constants.ts';
// 方案2: showDiceResult 已迁至 animation/dice-anims.ts, 此处仅 re-export 保持调用方兼容
import { showDiceResult } from './animation/dice-anims.ts';

const _tmpQ = new THREE.Quaternion();

function setCam(dist: any, polarDeg: any, aziDeg: any) {
  const p = (polarDeg * Math.PI) / 180,
    a = (aziDeg * Math.PI) / 180;
  sceneRefs.camera!.position.set(
    dist * Math.sin(p) * Math.cos(a),
    dist * Math.cos(p),
    dist * Math.sin(p) * Math.sin(a)
  );
}

// buildTable 拆为 buildTableMesh + buildTablePhysics, 共享 tableLayout() 配置
// 原函数 153 行, 拆分后职责单一, 易于独立修改视觉或物理
function tableLayout() {
  const { outerSize, holeSize, feltHeight, woodHeight, rimWidth } = CFG.table;
  const { trayBottomY, glassY } = CFG.dice;
  const halfOuter = outerSize / 2,
    halfHole = holeSize / 2;
  const feltWidth = (outerSize - holeSize - 2 * rimWidth) / 2;
  const feltY = feltHeight / 2,
    frameY = woodHeight / 2,
    frameThickness = rimWidth;
  const trayDepth = 0.6;
  const trayBottomCenterY = trayBottomY - trayDepth / 2;
  const wallH = glassY - trayBottomY,
    wallCenterY = trayBottomY + wallH / 2,
    wallThick = 0.15;
  return {
    outerSize,
    holeSize,
    feltHeight,
    woodHeight,
    rimWidth,
    trayBottomY,
    glassY,
    halfOuter,
    halfHole,
    feltWidth,
    feltY,
    frameY,
    frameThickness,
    trayDepth,
    trayBottomCenterY,
    wallH,
    wallCenterY,
    wallThick,
  };
}

// 渲染几何: 桌面 + 骰子盘 + 桌腿 (Three.js Mesh)
function buildTableMesh(layout: any, materials: any) {
  const {
    outerSize,
    holeSize,
    woodHeight,
    feltHeight,
    halfOuter,
    halfHole,
    feltWidth,
    feltY,
    frameY,
    frameThickness,
    trayBottomY: _trayBottomY,
    glassY,
    trayBottomCenterY,
    wallH,
    wallCenterY,
    wallThick,
  } = layout;
  const { woodMat, feltMat, trayMat, glassMat, goldMat } = materials;
  const g = new THREE.Group();

  // 桌框改用圆角盒 (倒角木框, 比直角更精致); 半径小于最短边一半
  const frameRadius = 0.09;
  for (const sz of [1, -1]) {
    const m = new THREE.Mesh(new RoundedBoxGeometry(outerSize, woodHeight, frameThickness, 3, frameRadius), woodMat);
    m.position.set(0, frameY, sz * (halfOuter - frameThickness / 2));
    m.castShadow = true;
    m.receiveShadow = true;
    g.add(m);
  }
  for (const sx of [1, -1]) {
    const m = new THREE.Mesh(
      new RoundedBoxGeometry(frameThickness, woodHeight, outerSize - 2 * frameThickness, 3, frameRadius),
      woodMat
    );
    m.position.set(sx * (halfOuter - frameThickness / 2), frameY, 0);
    m.castShadow = true;
    m.receiveShadow = true;
    g.add(m);
  }
  for (const sz of [1, -1]) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(outerSize - 2 * frameThickness, feltHeight, feltWidth), feltMat);
    m.position.set(0, feltY, sz * (halfHole + feltWidth / 2));
    m.receiveShadow = true;
    g.add(m);
  }
  for (const sx of [1, -1]) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(feltWidth, feltHeight, holeSize), feltMat);
    m.position.set(sx * (halfHole + feltWidth / 2), feltY, 0);
    m.receiveShadow = true;
    g.add(m);
  }

  // 骰子盘
  const trayBottom = new THREE.Mesh(new THREE.BoxGeometry(holeSize, layout.trayDepth, holeSize), trayMat);
  trayBottom.position.set(0, trayBottomCenterY, 0);
  g.add(trayBottom);

  for (const sz of [1, -1]) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(holeSize, wallH, wallThick), trayMat);
    m.position.set(0, wallCenterY, sz * (halfHole - wallThick / 2));
    g.add(m);
  }
  for (const sx of [1, -1]) {
    const m = new THREE.Mesh(new THREE.BoxGeometry(wallThick, wallH, holeSize - 2 * wallThick), trayMat);
    m.position.set(sx * (halfHole - wallThick / 2), wallCenterY, 0);
    g.add(m);
  }
  const glass = new THREE.Mesh(new THREE.BoxGeometry(holeSize, 0.05, holeSize), glassMat);
  glass.position.set(0, glassY, 0);
  g.add(glass);

  // 金边镶饰 (点缀高光, 提升桌面档次)
  const inlayY = feltHeight + 0.02;
  // 矩形金边工具: 在 ±half 处围一圈细金条
  const goldRing = (half: number, w: number, h: number) => {
    for (const sz of [1, -1]) {
      const m = new THREE.Mesh(new THREE.BoxGeometry(half * 2 + w, h, w), goldMat);
      m.position.set(0, inlayY, sz * half);
      m.castShadow = true;
      g.add(m);
    }
    for (const sx of [1, -1]) {
      const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, half * 2 - w), goldMat);
      m.position.set(sx * half, inlayY, 0);
      m.castShadow = true;
      g.add(m);
    }
  };
  // 骰盘洞口金边
  goldRing(halfHole + 0.07, 0.14, 0.06);
  // 台面外圈金边 (绒布与木框交界处, 框住整个牌桌)
  goldRing(halfOuter - frameThickness - 0.1, 0.14, 0.05);

  const legSize = 0.8,
    legH = 4,
    legOff = outerSize / 2 - 1.5;
  for (let i = 0; i < 4; i++) {
    const sx = i & 1 ? 1 : -1,
      sz = i & 2 ? 1 : -1;
    const leg = new THREE.Mesh(new RoundedBoxGeometry(legSize, legH, legSize, 3, 0.1), woodMat);
    leg.position.set(sx * legOff, -legH / 2 + 0.2, sz * legOff);
    leg.castShadow = true;
    g.add(leg);
  }
  sceneRefs.seatPivot!.add(g);
}

// 物理体: 台面 + 围栏 + 骰子盘壁 + 地面 (CANNON.Body)
function buildTablePhysics(layout: any) {
  const {
    outerSize,
    holeSize,
    feltHeight,
    halfOuter,
    halfHole,
    feltWidth,
    frameThickness,
    trayBottomCenterY,
    glassY,
    trayDepth,
    wallH,
    wallCenterY,
    wallThick,
  } = layout;
  // 物理地面 (台面 + 围栏)
  const phyH = 0.5,
    phyY = feltHeight - phyH / 2;
  for (const sz of [1, -1]) {
    const body = new CANNON.Body({ mass: 0, material: matGround });
    body.addShape(new CANNON.Box(new CANNON.Vec3((outerSize - 2 * frameThickness) / 2, phyH / 2, feltWidth / 2)));
    body.position.set(0, phyY, sz * (halfHole + feltWidth / 2));
    world.addBody(body);
  }
  for (const sx of [1, -1]) {
    const body = new CANNON.Body({ mass: 0, material: matGround });
    body.addShape(new CANNON.Box(new CANNON.Vec3(feltWidth / 2, phyH / 2, holeSize / 2)));
    body.position.set(sx * (halfHole + feltWidth / 2), phyY, 0);
    world.addBody(body);
  }
  const rimH = 0.4,
    rimY = feltHeight + rimH / 2;
  for (const sz of [1, -1]) {
    const body = new CANNON.Body({ mass: 0, material: matGround });
    body.addShape(new CANNON.Box(new CANNON.Vec3(outerSize / 2, rimH / 2, frameThickness / 2)));
    body.position.set(0, rimY, sz * (halfOuter - frameThickness / 2));
    world.addBody(body);
  }
  for (const sx of [1, -1]) {
    const body = new CANNON.Body({ mass: 0, material: matGround });
    body.addShape(new CANNON.Box(new CANNON.Vec3(frameThickness / 2, rimH / 2, (outerSize - 2 * frameThickness) / 2)));
    body.position.set(sx * (halfOuter - frameThickness / 2), rimY, 0);
    world.addBody(body);
  }
  const trayPhyBody = new CANNON.Body({ mass: 0, material: matGround });
  trayPhyBody.addShape(new CANNON.Box(new CANNON.Vec3(holeSize / 2, trayDepth / 2, holeSize / 2)));
  trayPhyBody.position.set(0, trayBottomCenterY, 0);
  world.addBody(trayPhyBody);
  const tWallH = wallH,
    tWallY = wallCenterY,
    tWallT = wallThick;
  for (const sz of [1, -1]) {
    const b = new CANNON.Body({ mass: 0, material: matGround });
    b!.addShape(new CANNON.Box(new CANNON.Vec3(halfHole, tWallH / 2, tWallT / 2)));
    b!.position.set(0, tWallY, sz * (halfHole - tWallT / 2));
    world.addBody(b);
  }
  for (const sx of [1, -1]) {
    const b = new CANNON.Body({ mass: 0, material: matGround });
    b!.addShape(new CANNON.Box(new CANNON.Vec3(tWallT / 2, tWallH / 2, halfHole)));
    b!.position.set(sx * (halfHole - tWallT / 2), tWallY, 0);
    world.addBody(b);
  }
  const ceil = new CANNON.Body({ mass: 0, material: matGround });
  ceil.addShape(new CANNON.Box(new CANNON.Vec3(halfHole, 0.05, halfHole)));
  ceil.position.set(0, glassY - 0.05, 0);
  world.addBody(ceil);
  const fb = new CANNON.Body({ mass: 0, material: matGround });
  fb!.addShape(new CANNON.Plane());
  fb!.quaternion.setFromAxisAngle(new CANNON.Vec3(1, 0, 0), -Math.PI / 2);
  fb!.position.set(0, -4, 0);
  world.addBody(fb);
}

// 兼容入口: 同时构建 mesh + physics
function buildTable() {
  const layout = tableLayout();
  // 木框: 深色胡桃木纹 + 清漆罩光 (clearcoat), 高档漆面质感
  const woodTex = Tex.makeWood();
  woodTex.repeat.set(2, 2);
  const woodMat = new THREE.MeshPhysicalMaterial({
    map: woodTex,
    color: '#7a4a26',
    roughness: 0.38,
    metalness: 0.12,
    clearcoat: 0.7,
    clearcoatRoughness: 0.28,
  });
  // 台面绒布: 沉稳的赌桌绿 + 细噪点织物纹
  const feltTex = Tex.makeFelt();
  feltTex.repeat.set(6, 6);
  const feltMat = new THREE.MeshStandardMaterial({
    map: feltTex,
    color: '#2c8c54',
    roughness: 0.95,
    metalness: 0.0,
  });
  const trayMat = new THREE.MeshStandardMaterial({ color: '#1c1c1c', roughness: 0.7, metalness: 0.15 });
  const glassMat = new THREE.MeshStandardMaterial({
    color: '#ffffff',
    transparent: true,
    opacity: 0.18,
    roughness: 0.08,
    metalness: 0.6,
  });
  // 金边镶饰: 抛光黄铜质感
  const goldMat = new THREE.MeshStandardMaterial({
    color: '#d4af37',
    roughness: 0.28,
    metalness: 0.9,
    emissive: '#3a2c08',
  });
  buildTableMesh(layout, { woodMat, feltMat, trayMat, glassMat, goldMat });
  buildTablePhysics(layout);
  return { feltMat };
}

function buildDice() {
  const size = CFG.dice.size;
  // 圆角骰子 (真实骰子倒角), 与物理体 (仍为直角 Box) 尺寸一致, 不影响点数判定
  const geo = new RoundedBoxGeometry(size, size, size, 4, size * 0.14);
  const halfExtents = new CANNON.Vec3(size / 2, size / 2, size / 2);
  const startY = CFG.dice.trayBottomY + size / 2 + 0.02;
  const { diceMeshes, diceBodies } = sceneRefs;
  // 共享 6 个骰子面材质 (两个骰子的相同点数面复用同一纹理, 节省 6×65KB = 390KB GPU 内存)
  const sharedDiceMats = [1, 2, 3, 4, 5, 6].map(
    (n: any) => new THREE.MeshStandardMaterial({ map: Tex.makeDiceFace(n), roughness: 0.3, metalness: 0.04 })
  );
  for (let i = 0; i < 2; i++) {
    const mesh = new THREE.Mesh(geo, sharedDiceMats);
    mesh.castShadow = true;
    sceneRefs.seatPivot!.add(mesh);
    diceMeshes.push(mesh);
    const body = new CANNON.Body({
      mass: 0,
      type: CANNON.Body.KINEMATIC,
      shape: new CANNON.Box(halfExtents),
      material: matDice,
      position: new CANNON.Vec3(-0.55 + i * 1.1, startY, 0),
    });
    world.addBody(body);
    diceBodies.push(body);
  }
}

// 方案2: showDiceResult 已迁至 animation/dice-anims.ts (52 行)
// 此处仅通过顶部 import + 底部 export 保持调用方 (handlers/dice-deal.ts) 兼容.

// ============ 牌墙 ============
function makeDeck() {
  const d: any[] = [];
  for (let i = 1; i <= 9; i++) d.push(['wan', i]);
  for (let i = 1; i <= 9; i++) d.push(['tong', i]);
  for (let i = 1; i <= 9; i++) d.push(['tiao', i]);
  ['東', '南', '西', '北'].forEach((c: any) => d.push(['feng', c]));
  ['中', '發', '白'].forEach((c: any) => d.push(['feng', c]));
  return d;
}

function buildWalls() {
  sceneRefs.wallTiles.length = 0;
  sceneRefs.wallBack.length = 0;
  sceneRefs.wallCursor = 0;
  sceneRefs.wallBackCursor = 0;
  const { offset, perSide, layers } = CFG.wall;
  // .2 修复: 重建前先清理旧 wallGroup (如果存在), 避免新旧 wallGroup 叠加
  // 原问题: buildWalls 直接 sceneRefs.wallGroup! = new THREE.Group() 赋值,
  //         旧的 wallGroup (可能是 finalizeAnimatedWall 创建的残缺牌墙) 仍留在 scene 中
  //         导致刷新后看到两个牌墙叠加
  if (sceneRefs.wallGroup! && sceneRefs.wallGroup!.parent) {
    sceneRefs.wallGroup!.parent.remove(sceneRefs.wallGroup);
  }
  const deck = makeDeck(),
    all: any[] = [];
  for (const [t, v] of deck) for (let k = 0; k < 4; k++) all.push([t as any, v as any]);
  for (let i = all.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [all[i], all[j]] = [all[j], all[i]];
  }
  // sides 顺序与 seat 顺序一致 (南=0, 西=1, 北=2, 东=3)
  // 原顺序 [南, 东, 北, 西] 是逆时针, 导致发牌方向错误
  // 新顺序 [南, 西, 北, 东] 是顺时针, 发完当前牌墙后从左边相邻牌墙继续
  // 物理: 顺时针在牌桌上 = 南→西→北→东 (从俯视图看是顺时针)
  const sides = [
    { pos: [0, 0, offset], rotY: 0 }, // 南 (seat 0)
    { pos: [-offset, 0, 0], rotY: -Math.PI / 2 }, // 西 (seat 1)
    { pos: [0, 0, -offset], rotY: Math.PI }, // 北 (seat 2)
    { pos: [offset, 0, 0], rotY: Math.PI / 2 }, // 东 (seat 3)
  ];
  let idx = 0;
  sceneRefs.wallGroup! = new THREE.Group();
  sceneRefs.seatPivot!.add(sceneRefs.wallGroup);
  const grid = sides.map(() => [[], []]);
  sides.forEach((side: any, si: any) => {
    for (let layer = 0; layer < layers; layer++) {
      for (let i = 0; i < perSide; i++) {
        const [type, value] = all[idx % all.length];
        idx++;
        const mesh = TileFactory.create(type, value);
        const localX = (i - (perSide - 1) / 2) * SPACING;
        const cos = Math.cos(side.rotY),
          sin = Math.sin(side.rotY);
        mesh.position.set(side.pos[0] + localX * cos, LAYER_Y[layer], side.pos[2] - localX * sin);
        mesh.rotation.set(0, side.rotY, 0, 'YXZ');
        mesh.rotateX(Math.PI / 2);
        sceneRefs.wallGroup!.add(mesh);
        (grid as any)[si][layer][i] = mesh;
      }
    }
  });
  // wallTiles 列顺序从右到左 (原从左到右)
  // 每个牌墙发牌时从右端开始, 向左推进, 发完后从左边相邻牌墙的右端继续
  // 物理: 玩家面前的牌墙, 右端 = 该玩家视角的右侧
  const top = layers - 1,
    bot = 0;
  for (let si = 0; si < sides.length; si++) {
    // 从右到左: c 从 perSide-1 递减到 0, 每两列一组
    for (let c = perSide - 1 - (perSide % 2 ? 0 : 1); c >= 0; c -= 2) {
      const c0 = c - 1;
      // 当前列 c: top, bot
      if (grid[si][top][c]) sceneRefs.wallTiles.push(grid[si][top][c]);
      if (grid[si][bot][c]) sceneRefs.wallTiles.push(grid[si][bot][c]);
      // 前一列 c0 (c 的左边): top, bot
      if (c0 >= 0 && grid[si][top][c0]) sceneRefs.wallTiles.push(grid[si][top][c0]);
      if (c0 >= 0 && grid[si][bot][c0]) sceneRefs.wallTiles.push(grid[si][bot][c0]);
    }
  }
  // wallBack 列顺序从左到右 (与 wallTiles 相反, 牌尾从左端开始)
  sceneRefs.wallBack.length = 0;
  for (let si = sides.length - 1; si >= 0; si--) {
    for (let c = 0; c < perSide; c += 2) {
      if (grid[si][top][c]) sceneRefs.wallBack.push(grid[si][top][c]);
      if (grid[si][bot][c]) sceneRefs.wallBack.push(grid[si][bot][c]);
      if (grid[si][top][c + 1]) sceneRefs.wallBack.push(grid[si][top][c + 1]);
      if (grid[si][bot][c + 1]) sceneRefs.wallBack.push(grid[si][bot][c + 1]);
    }
  }
  sceneRefs.wallCursor = 0;
  sceneRefs.wallBackCursor = 0;
}

function takeWallPos(mesh: any) {
  const p = { x: mesh.position.x, y: mesh.position.y, z: mesh.position.z };
  mesh.userData._taken = true;
  // 从父节点移除 (不一定是 wallGroup, 再来一局动画后可能挂在 seatPivot)
  if (mesh.parent) mesh.parent.remove(mesh);
  return p;
}

// popWallTile: 取牌墙下一张 (正常发牌/摸牌用)
function popWallTile() {
  while (
    sceneRefs.wallCursor < sceneRefs.wallTiles.length &&
    sceneRefs.wallTiles[sceneRefs.wallCursor]?.userData?._taken
  )
    sceneRefs.wallCursor++;
  const mesh = sceneRefs.wallTiles[sceneRefs.wallCursor++];
  if (!mesh || (mesh as any).userData?._taken) return { x: 0, y: LAYER_Y[0] + 1, z: 0 };
  return takeWallPos(mesh);
}

//   数人: 从庄家自己开始, 顺时针 (庄家→左边→对面→右边) 数 diceSum 个人
//         1=庄家, 2=顺时针下家(左), 3=对面, 4=顺时针上家(右), 5=庄家...
//         数到的人用其面前的牌墙发牌
//   数列: 从那个人面前牌墙的右端往左数 diceMin 列 (每列上下2张), 跳过的列变牌尾
//         从第 diceMin+1 列开始发牌
//   实现: 后 wallTiles 已是从右到左, 所以不再需要反转目标面
//         只需跳过 diceMin*2 张标记 _taken
//   注意: 每局开始时 wallCursor 已被 doResetBoard 重置为 0, 这里重新设置
//   重排 wallTiles, 让目标面排到最前面, 后续面按顺时针跟在后面
//         这样 wallCursor 从 0 开始即可正确跨面
function setWallStart(dealerSeat: any, diceSum: any, diceMin: any) {
  const tilesPerSide = CFG.wall.perSide * CFG.wall.layers; // 17*2 = 34
  // 数人: 第 diceSum 个人 = (dealerSeat + diceSum - 1) % 4
  const targetSeat = (dealerSeat + diceSum - 1) % 4;
  const startSide = targetSeat; // seat 与面索引一致
  const sideStart = startSide * tilesPerSide;
  const sideEnd = sideStart + tilesPerSide;

  // wallTiles 已是从右到左, 不再需要反转目标面
  // 跳过 diceMin 列 (diceMin*2 张), 标记为 _taken 变牌尾
  // (跳过的是目标面右端的 diceMin 列, 即 wallTiles 中该面的前 diceMin*2 张)
  const skipTiles = diceMin * 2;
  let actualSkip = 0;
  for (let i = sideStart; i < sideStart + skipTiles && i < sideEnd; i++) {
    if (sceneRefs.wallTiles[i] && !sceneRefs.wallTiles[i].userData._taken) {
      sceneRefs.wallTiles[i].userData._taken = true;
      actualSkip++;
    }
  }

  // 重排 wallTiles, 让目标面排到最前面, 后续面按顺时针跟在后面
  // 这样 wallCursor 从 skipTiles 开始, 发完目标面后自然进入下一个面
  if (startSide > 0) {
    const newWallTiles: any[] = [];
    const newWallBack: any[] = [];
    // wallTiles: 按 side 顺序重排, 起始面为 startSide
    for (let si = 0; si < 4; si++) {
      const srcSide = (startSide + si) % 4;
      const srcStart = srcSide * tilesPerSide;
      for (let i = 0; i < tilesPerSide; i++) {
        newWallTiles.push(sceneRefs.wallTiles[srcStart + i]);
      }
    }
    // wallBack: 按 side 逆序重排 (杠后摸牌从牌尾开始)
    const wallBackPerSide = sceneRefs.wallBack.length / 4;
    for (let si = 0; si < 4; si++) {
      const srcSide = (startSide + 3 - si) % 4;
      const srcStart = srcSide * wallBackPerSide;
      for (let i = 0; i < wallBackPerSide; i++) {
        newWallBack.push(sceneRefs.wallBack[srcStart + i]);
      }
    }
    for (let i = 0; i < sceneRefs.wallTiles.length; i++) {
      sceneRefs.wallTiles[i] = newWallTiles[i];
    }
    for (let i = 0; i < sceneRefs.wallBack.length; i++) {
      sceneRefs.wallBack[i] = newWallBack[i];
    }
  }

  // 发牌起点 = 跳过的张数 (此时 wallTiles 已重排, 目标面在最前)
  sceneRefs.wallCursor = skipTiles;

  console.log(
    `[wall] 摸牌规则: 庄家seat=${dealerSeat} 点数和=${diceSum} 最小=${diceMin} → 数到seat=${targetSeat}(面${startSide}) 跳过${actualSkip}张+wallTiles重排(起始面${startSide}), wallCursor=${sceneRefs.wallCursor}`
  );
}

// 按原版规则取牌顺序 (相对于跳牌开始时的 wallCursor):
//   wallTiles 顺序: [top0, bot0, top1, bot1, top2, bot2, ...]
//   跳牌5张顺序: top0(庄), top2(庄), bot0(闲1), top1(闲2), bot1(闲3)
//   即 offset: [0, 4, 1, 2, 3]
let _jumpDealOffsets: any = null;
let _jumpDealIndex = 0;
let _jumpDealBaseCursor = 0;

function startJumpDeal() {
  _jumpDealOffsets = [0, 4, 1, 2, 3];
  _jumpDealIndex = 0;
  // 跳牌起始位置: 跳过已取的, 找第一个未取的位置
  _jumpDealBaseCursor = sceneRefs.wallCursor;
  while (_jumpDealBaseCursor < sceneRefs.wallTiles.length && sceneRefs.wallTiles[_jumpDealBaseCursor]?.userData?._taken)
    _jumpDealBaseCursor++;
}

function popWallTileJumpDeal() {
  if (!_jumpDealOffsets || _jumpDealIndex >= _jumpDealOffsets.length) {
    return popWallTile(); // 跳牌阶段已结束, 用普通取牌
  }
  // 用 startJumpDeal 时缓存的 baseCursor, 5张都基于同一个起点
  const offset = _jumpDealOffsets[_jumpDealIndex];
  const idx = _jumpDealBaseCursor + offset;
  _jumpDealIndex++;

  if (_jumpDealIndex >= _jumpDealOffsets.length) {
    _jumpDealOffsets = null; // 跳牌阶段结束
  }

  if (idx >= sceneRefs.wallTiles.length || !sceneRefs.wallTiles[idx] || sceneRefs.wallTiles[idx].userData?._taken) {
    return popWallTile(); // fallback
  }

  return takeWallPos(sceneRefs.wallTiles[idx]);
}

function popWallTileBack() {
  while (
    sceneRefs.wallBackCursor < sceneRefs.wallBack.length &&
    (sceneRefs.wallBack[sceneRefs.wallBackCursor] as any)?.userData?._taken
  )
    sceneRefs.wallBackCursor++;
  const mesh = sceneRefs.wallBack[sceneRefs.wallBackCursor++];
  if (!mesh || (mesh as any).userData?._taken) return { x: 0, y: LAYER_Y[0] + 1, z: 0 };
  return takeWallPos(mesh);
}

// ============ 灯光 / 环境场景 ============
function buildLights() {
  // 柔和补光: 避免暗部死黑, 又不过曝 (配合 IBL 环境反射)
  const amb = new THREE.AmbientLight('#7d6c4c', 0.62);
  const hemi = new THREE.HemisphereLight('#fff4dd', '#5c4c36', 0.72);
  const key = new THREE.DirectionalLight('#ffe6bc', 1.55);
  key.position.set(6, 14, 4);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  key.shadow.camera.left = -12;
  key.shadow.camera.right = 12;
  key.shadow.camera.top = 12;
  key.shadow.camera.bottom = -12;
  key.shadow.camera.near = 1;
  key.shadow.camera.far = 40;
  key.shadow.bias = -0.0005;
  key.shadow.radius = 4;
  const fill = new THREE.PointLight('#ffb27a', 0.5, 34, 2);
  fill.position.set(-7, 5, -5);
  const rim = new THREE.PointLight('#8fd0b4', 0.4, 34, 2);
  rim.position.set(7, 4, 7);
  // 桌面顶部聚光: 让牌桌成为视觉焦点 (强度降低, 避免牌面过曝)
  const spot = new THREE.SpotLight('#fff3da', 1.7, 32, Math.PI * 0.34, 0.5, 1.3);
  spot.position.set(0, 12, 0);
  spot.target.position.set(0, 0, 0);
  sceneRefs.scene!.add(amb, hemi, key, fill, rim, spot, spot.target);
  return { key, fill, rim, spot, amb };
}

// 环境场景: 木地板 + 暖色房间墙面 + 渐变天幕 + IBL 环境光
// 取代原本纯黑背景, 营造温暖的麻将茶室氛围
function buildEnvironment() {
  const scene = sceneRefs.scene!;
  // 暖色渐变天幕 (替代纯黑背景)
  scene.background = Tex.makeBackground();
  // 基于图像的环境光 (RoomEnvironment): 柔和补光 + 材质反射, 消除死黑暗部
  const pmrem = new THREE.PMREMGenerator(sceneRefs.renderer!);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.5; // 降低 IBL 强度, 避免牌面/绒布过曝
  pmrem.dispose();

  const env = new THREE.Group();
  const floorY = -3.85; // 桌腿底部约 -3.8, 地板紧贴其下
  const roomHalf = 70,
    wallDist = 58,
    wallH = 46;

  // 木地板
  const floorTex = Tex.makeFloor();
  floorTex.repeat.set(8, 8);
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(roomHalf * 2, roomHalf * 2),
    new THREE.MeshStandardMaterial({ map: floorTex, color: '#8a5f38', roughness: 0.75, metalness: 0.04 })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = floorY;
  floor.receiveShadow = true;
  env.add(floor);

  // 四面墙 (暖色灰泥), 法线朝内
  const wallMat = new THREE.MeshStandardMaterial({
    color: '#8d7658',
    roughness: 0.9,
    metalness: 0.0,
    side: THREE.DoubleSide,
  });
  const wallGeo = new THREE.PlaneGeometry(roomHalf * 2, wallH);
  const mkWall = (x: number, z: number, ry: number) => {
    const w = new THREE.Mesh(wallGeo, wallMat);
    w.position.set(x, floorY + wallH / 2, z);
    w.rotation.y = ry;
    env.add(w);
  };
  mkWall(0, -wallDist, 0);
  mkWall(0, wallDist, Math.PI);
  mkWall(-wallDist, 0, Math.PI / 2);
  mkWall(wallDist, 0, -Math.PI / 2);

  // 顶棚 (暖色, 遮住上方天幕硬边)
  const ceil = new THREE.Mesh(
    new THREE.PlaneGeometry(roomHalf * 2, roomHalf * 2),
    new THREE.MeshStandardMaterial({ color: '#493c2d', roughness: 1.0 })
  );
  ceil.rotation.x = Math.PI / 2;
  ceil.position.y = floorY + wallH;
  env.add(ceil);

  scene.add(env);
  return env;
}

// 初始化整个 Three.js 场景
function initScene() {
  const t0 = performance.now();
  const app = document.getElementById('app') as any;
  sceneRefs.scene = new THREE.Scene();
  // 背景与环境场景在 buildEnvironment() 中设置 (暖色天幕 + 房间, 不再是纯黑 + 浓雾)
  sceneRefs.camera = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 0.1, 200);
  setCam(26, 50, 42);
  const tRenderer = performance.now();
  // M-11 修复: 移动端渲染降级 (降低 antialias/pixelRatio/shadow 提升 FPS)
  const isMobile = typeof navigator !== 'undefined' &&
    /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini/i.test(navigator.userAgent.toLowerCase());
  sceneRefs.renderer! = new THREE.WebGLRenderer({
    antialias: !isMobile,  // 移动端关闭抗锯齿 (GPU 开销大)
    powerPreference: isMobile ? 'low-power' : 'high-performance',
  });
  sceneRefs.renderer!.setSize(innerWidth, innerHeight);
  // 移动端限制 pixelRatio 为 1 (避免高 DPI 屏幕 GPU 过载), 桌面端允许 2
  sceneRefs.renderer!.setPixelRatio(isMobile ? 1 : Math.min(devicePixelRatio, 2));
  // 移动端关闭阴影 (GPU 开销大), 桌面端启用 PCFSoftShadowMap
  sceneRefs.renderer!.shadowMap.enabled = !isMobile;
  sceneRefs.renderer!.shadowMap.type = THREE.PCFSoftShadowMap;
  sceneRefs.renderer!.outputColorSpace = THREE.SRGBColorSpace;
  sceneRefs.renderer!.toneMapping = THREE.ACESFilmicToneMapping;
  sceneRefs.renderer!.toneMappingExposure = 0.98;
  app.appendChild(sceneRefs.renderer!.domElement);
  console.log(`[perf] WebGLRenderer init: ${(performance.now() - tRenderer).toFixed(1)}ms${isMobile ? ' (移动端降级)' : ''}`);

  // L-03 修复: sceneRefs.controls 已强类型化为 OrbitControls, 直接赋值与方法调用
  const controls = new OrbitControls(sceneRefs.camera, sceneRefs.renderer!.domElement);
  sceneRefs.controls = controls;
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.minDistance = 12;
  controls.maxDistance = 42;
  controls.maxPolarAngle = Math.PI * 0.49;
  controls.target.set(0, 1.0, 0);
  controls.mouseButtons = {
    LEFT: THREE.MOUSE.ROTATE,
    MIDDLE: THREE.MOUSE.DOLLY,
    RIGHT: null,
  };

  // 监听 controls 交互, 设置 dirty 标记, 主循环仅在交互后 500ms 内调用 update
  controls.addEventListener('start', () => {
    sceneRefs._controlsDirty = true;
    sceneRefs._controlsIdle = 0;
  });
  controls.addEventListener('change', () => {
    sceneRefs._controlsDirty = true;
    sceneRefs._controlsIdle = 0;
  });

  sceneRefs.seatPivot! = new THREE.Group();
  sceneRefs.scene!.add(sceneRefs.seatPivot);

  const tTileFactory = performance.now();
  TileFactory.init();
  console.log(`[perf] TileFactory.init: ${(performance.now() - tTileFactory).toFixed(1)}ms`);

  const tTable = performance.now();
  sceneRefs.table = buildTable();
  console.log(`[perf] buildTable: ${(performance.now() - tTable).toFixed(1)}ms`);

  const tDice = performance.now();
  buildDice();
  console.log(`[perf] buildDice: ${(performance.now() - tDice).toFixed(1)}ms`);

  const tWalls = performance.now();
  buildWalls();
  console.log(
    `[perf] buildWalls: ${(performance.now() - tWalls).toFixed(1)}ms (${CFG.wall.perSide * CFG.wall.layers * 4} mesh)`
  );

  const tLights = performance.now();
  sceneRefs.lights! = buildLights();
  console.log(`[perf] buildLights: ${(performance.now() - tLights).toFixed(1)}ms`);

  const tEnv = performance.now();
  buildEnvironment();
  console.log(`[perf] buildEnvironment: ${(performance.now() - tEnv).toFixed(1)}ms`);

  // 应用座位视角
  sceneRefs.seatPivot!.rotation.y = pivotRotYForSeat(MY_SEAT);

  // Three.js 默认懒编译: 首次 render 时为每个 material 编译 shader + 上传纹理到 GPU,
  // 一次性触发导致首帧 render=232ms。
  // 策略: 在 initScene 阶段 (主循环尚未启动, perf 不计帧) 做一次真正的 render(),
  // 把 shader 编译 + 纹理上传开销移到这里。用户感知为 "loader 多停留 200ms",
  // 而非 "进游戏后卡一下"。compile() 单独不够 — 它不渲染, 纹理不上传。
  const tCompile = performance.now();
  try {
    sceneRefs.renderer!.compile(sceneRefs.scene, sceneRefs.camera);
    // 真正渲染一次到屏幕 (触发纹理上传), 但此时主循环未启动, 不会被 perf 计为慢帧
    sceneRefs.renderer!.render(sceneRefs.scene, sceneRefs.camera);
  } catch (e: any) {
    console.warn('[perf] 预渲染失败 (非致命):', e.message);
  }
  console.log(`[perf] compile + 预渲染 (shader 编译 + 纹理上传): ${(performance.now() - tCompile).toFixed(1)}ms`);

  console.log(`[perf] initScene total: ${(performance.now() - t0).toFixed(1)}ms`);
}

export {
  initScene,
  setCam,
  buildTable,
  buildDice,
  buildWalls,
  buildLights,
  buildEnvironment,
  showDiceResult,
  popWallTile,
  popWallTileJumpDeal,
  popWallTileBack,
  startJumpDeal,
  setWallStart,
  makeDeck,
};
