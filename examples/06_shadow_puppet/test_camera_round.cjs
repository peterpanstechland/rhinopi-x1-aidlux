// Run with: node --test test_camera_round.cjs
const assert = require("node:assert/strict");
const test = require("node:test");
global.window = {};
require("./web/camera-round.js");
const {CameraRound} = window;

// Joint offsets are measured in shoulder widths relative to the shoulder midpoint.
function frame({head=[0,-.7],left=[-.65,.8],right=[.65,.8],dx=0,dy=0,tilt=0}={}) {
  const aspect = 16/9;
  const span = .26;
  const points = Array(25).fill(null);
  function put(index,pair) {
    if (pair) points[index] = [.5+(pair[0]+dx)*span/aspect,.55+(pair[1]+dy)*span];
  }
  put(0,head); put(11,[-.5,-tilt/2]); put(12,[.5,tilt/2]);
  put(15,left); put(16,right);
  return {pose_points:points,pose_aspect:aspect,tracked:true};
}
function player(ids) {
  const round = new CameraRound(ids);
  let now = 0;
  return {
    status:null,
    tick(pose={},n=1) {
      for (let i=0;i<n;i++) this.status=round.update(frame(pose),now+=100);
      return this.status;
    },
    ready() {
      for(let i=0;i<25 && (!this.status || this.status.sub==="ready");i++) this.tick();
      assert.equal(this.status.sub,"play");
    },
    leaveClear() {
      assert.equal(this.status.sub,"clear");
      for (let i=0;i<25 && this.status.sub==="clear" && this.status.phase==="round";i++) this.tick();
    },
  };
}
const wide = y => ({left:[-1.5,y],right:[1.5,y]});
function playAction(p) {
  p.ready();
  const id = p.status.act_id;
  for (let i=0;i<390 && p.status.sub==="play";i++) {
    const v=p.status.challenge.visual;
    let pose={};
    switch(id) {
      case "wings": pose=wide(0); break;
      case "flap": pose=wide(i%6<3 ? .24 : -.24); break;
      case "wave": pose={left:null,right:[i%6<3?.68:1.05,-.35]}; break;
      case "lean": {
        const side=(v.gates[0]?.x ?? 110)<160 ? -1 : 1;
        pose={head:[side*.22,-.7],dx:side*.17,left:null,right:null};
        break;
      }
      case "piano": {
        const aim=((v.target_key+.5)/10-.5)*2.6;
        pose=aim<0?{left:[aim,i%3===2?.99:.77]}:{right:[aim,i%3===2?.99:.77]};
        break;
      }
      case "hands_up": pose={head:null,left:null,right:null,dy:v.obs<198 && v.obs>173 ? -.16 : 0}; break;
      case "turn": pose={head:[[0,-.24,0,.24][i%4],-.7],left:null,right:null}; break;
      case "nod": pose={head:[0,i%4<2?-.7:-.55],left:null,right:null}; break;
    }
    p.tick(pose);
  }
  assert.equal(p.status.sub,"clear",id);
  assert.equal(p.status.challenge.count,p.status.challenge.target,id);
  p.leaveClear();
}

test("each serialised action is playable on its own, and a relay carries its full result",() => {
  const ids=["wings","flap","wave","lean","piano","hands_up","turn","nod"];
  assert.deepEqual(CameraRound.ids,ids);
  const relay=player();
  ids.forEach((id,index) => {
    const solo=player([id]);
    playAction(solo);
    assert.equal(solo.status.act_id,id);
    assert.equal(solo.status.round_len,1);
    assert.equal(solo.status.phase,"summary");
    assert.equal(solo.status.cleared,1);
    playAction(relay);
    assert.equal(relay.status.results[index].id,id);
    assert.equal(relay.status.cleared,index+1);
  });
  assert.equal(relay.status.phase,"summary");
  assert.equal(relay.status.round_len,8);
  assert.equal(relay.status.round_score,3250);
});

test("still, hidden, or mismatched movements do not farm points",() => {
  const flap=player(["flap"]); flap.ready();
  for(let i=0;i<40;i++) flap.tick({left:[-1.5,i%2?.3:-.3],right:[1.5,0]});
  assert.equal(flap.status.challenge.count,0);
  for(let i=0;i<40;i++) flap.tick({...wide(0),dy:i%2?-.2:.2});
  assert.equal(flap.status.challenge.count,0,"whole-body bob is not a wingbeat");

  const wave=player(["wave"]); wave.ready();
  for(let i=0;i<40;i++) wave.tick({left:null,right:[i%2?.7:1.2,.5]});
  assert.equal(wave.status.challenge.count,0,"a lowered wrist does not wave");
  wave.tick({left:null,right:[.7,-.3]}); wave.tick({left:null,right:[1,-.3]});
  const before=wave.status.challenge.count;
  wave.tick({left:null,right:[1,-.3]},20);
  assert.equal(wave.status.challenge.count,before);
  const elapsed=wave.status.round_time;
  wave.tick({left:null,right:null},100);
  assert.equal(wave.status.challenge.tracking,false);
  assert.equal(wave.status.round_time,elapsed);
  wave.tick({left:null,right:[.5,-.3]});
  assert.equal(wave.status.challenge.count,before,"occlusion is not a swipe");

  const turn=player(["turn"]); turn.ready();
  turn.tick(); turn.tick({head:[.23,-.7]},18);
  assert.equal(turn.status.challenge.count,1);
  turn.tick({head:[-.23,-.7]},18);
  assert.equal(turn.status.challenge.count,1,"a return to center is required");
  for(let i=0;i<12;i++) turn.tick({dx:i%2?.25:-.25});
  assert.equal(turn.status.challenge.count,1,"translating both shoulders and nose is not yaw");

  const nod=player(["nod"]); nod.ready();
  for(let i=0;i<40;i++) nod.tick({dy:i%2?.16:0});
  assert.equal(nod.status.challenge.count,0);
  nod.tick({head:[0,-.5]},12);
  assert.equal(nod.status.challenge.count,0,"holding the down pose is not a complete nod");
  nod.tick({head:null},3); nod.tick();
  assert.equal(nod.status.challenge.count,0,"reacquisition alone cannot finish the nod");

  const jump=player(["hands_up"]); jump.ready();
  // An early jump lands far ahead of the obstacle. Waving arms alone cannot clear it.
  jump.tick(); jump.tick({dy:-.18}); jump.tick({},7);
  for(let i=0;i<80;i++) jump.tick(wide(i%2?.3:-.4));
  assert.equal(jump.status.challenge.count,0);
  for(let i=0;i<60;i++) jump.tick(i%3 ? {dy:-.15,tilt:.30} : {});
  assert.equal(jump.status.challenge.count,0,"tilting one shoulder does not jump");
  jump.tick({dy:-.18},65);
  const singleJump=jump.status.challenge.count;
  assert.ok(singleJump<=1);
  jump.tick({dy:-.18},55);
  assert.equal(jump.status.challenge.count,singleJump,"staying elevated cannot generate repeated jumps");
});

test("single-action timeouts are recorded without inventing cleared actions",() => {
  const p=player(["turn"]); p.ready(); p.tick({},460);
  assert.equal(p.status.phase,"summary");
  assert.equal(p.status.round_len,1);
  assert.equal(p.status.cleared,0);
  assert.equal(p.status.round_score,0);
  assert.ok(p.status.round_ended_at>0);
});
