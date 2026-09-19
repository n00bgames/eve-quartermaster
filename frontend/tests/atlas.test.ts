import test from "node:test";
import assert from "node:assert/strict";
import {activityValue,lpCovered,securityColor} from "../src/features/navigation/atlasTypes.ts";

test("missing telemetry and wormholes remain unknown; sparse successful feeds imply zero",()=>{
  const feed={data:{},observed_at:null,expires_at:"",stale:false,error:null};
  assert.equal(activityValue(null,1,"ship_kills"),null);
  assert.equal(activityValue({kills:feed,jumps:feed},1,"ship_kills"),0);
  assert.equal(activityValue({kills:feed,jumps:feed},1,"ship_jumps",true),null);
});
test("unknown LP is distinct from zero and sufficient LP",()=>{
  const offer={offer_id:1,type_id:1,name:"Reward",quantity:1,lp_cost:100,isk_cost:1000,required_items:[]};
  assert.equal(lpCovered(offer,null),null);assert.equal(lpCovered(offer,0),false);assert.equal(lpCovered(offer,100),true);
});
test("security colors agree with routing at rounded highsec boundary",()=>{
  assert.equal(securityColor(.45),securityColor(1));assert.notEqual(securityColor(.449),securityColor(.45));
  assert.notEqual(securityColor(null),securityColor(0));
});
