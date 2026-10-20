/* Authoritative Sichuan blood-battle kong display, in EACH player's
 * own clockwise frame. Majiang's '+'/'='/'-' shorthand is unsuitable here:
 * those signs were previously chosen from the seat, not the actual payer.
 * Only publicly settled claims and a public one-face concealed-kong
 * disclosure are allowed; never inspect wall or opponents' private hands.
 */
const TILE=/^[mps][1-9]$/;
const KONGS=new Set(["an_gang","bu_gang","ming_gang"]);

export function calledTilePosition(owner,source){
  if(!Number.isInteger(owner)||owner<0||owner>3)throw new TypeError("invalid owner");
  if(source===null||source===undefined)return "unknown";
  if(!Number.isInteger(source)||source<0||source>3||source===owner)
    throw new TypeError("invalid kong claimant source");
  const relative=(source-owner+4)%4;
  return relative===3?"left":relative===1?"right":"opposite";
}

export function kongLayout(meld,owner){
  if(!meld||!KONGS.has(meld.kind))throw new TypeError("not a kong");
  const position=meld.kind==="ming_gang"
    ?calledTilePosition(owner,meld.source):"self";
  if(meld.kind==="an_gang"){
    const visible=meld.revealed===true && TILE.test(meld.tile||"");
    return {kind:"an_gang",position,slots:Array.from({length:4},(_,i)=>({
      tile:visible&&i===3?meld.tile:null,orientation:"upright",
      stacked:false,role:visible&&i===3?"public-face":"back",
    }))};
  }
  if(!TILE.test(meld.tile||""))throw new TypeError("untrusted open kong tile");
  const slots=Array.from({length:3},()=>({
    tile:meld.tile,orientation:"upright",stacked:false,role:"owned",
  }));
  const fourth={tile:meld.tile,orientation:"sideways",stacked:false,
    role:meld.kind==="ming_gang"?"claimed":"supplement"};
  if(meld.kind==="bu_gang"){
    // A self-drawn fourth tile rests horizontally ON TOP of the central
    // upright tile; the underlying original peng remains three uprights.
    slots[1]={...slots[1],overlay:{...fourth,stacked:true}};
  }else{
    // Layout from the caller's OWN visual left to right. An opposite
    // player's claimed fourth tile sits between upright tiles.
    const insertion=position==="left"?0:position==="right"?3:2;
    slots.splice(insertion,0,fourth);
  }
  return {kind:meld.kind,position,slots};
}

function image(value,role,doc){
  const img=doc.createElement("img");
  img.className="pai";
  img.src="/classic/img/"+(value||"pai")+".gif";
  img.dataset.pai=value||"_";
  img.alt=value?role==="claimed"?"点杠牌":role==="supplement"?"自摸补杠牌":
    "公开麻将牌":"盖住的暗杠牌";
  img.draggable=false;
  return img;
}

export function renderKongMeld(node,meld,owner){
  const layout=kongLayout(meld,owner),doc=node.ownerDocument;
  const group=doc.createElement("div");
  group.className="mahtrain-kong";
  group.dataset.kongType=layout.kind;
  group.dataset.claimPosition=layout.position;
  for(const spec of layout.slots){
    const holder=doc.createElement("span");
    holder.className="mahtrain-kong-slot"+
      (spec.orientation==="sideways"?" mahtrain-kong-sideways":"");
    holder.dataset.orientation=spec.orientation;
    holder.dataset.role=spec.role;
    holder.append(image(spec.tile,spec.role,doc));
    if(spec.overlay){
      const overlay=doc.createElement("span");
      overlay.className="mahtrain-kong-overlay";
      overlay.dataset.orientation="sideways";
      overlay.dataset.role=spec.overlay.role;
      overlay.append(image(spec.overlay.tile,spec.overlay.role,doc));
      holder.append(overlay);
    }
    group.append(holder);
  }
  node.classList.add("mahtrain-kong-mianzi");
  node.replaceChildren(group);
  return group;
}
