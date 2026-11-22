import test from 'node:test';
import assert from 'node:assert/strict';
import {sortClips,configKey} from '../src/features/journey/clipStitch.ts';
import {ambienceSamples} from '../src/features/journey/spaceAmbience.ts';

test('numbered clips sort naturally, without mutating the user selection',()=>{
 const files=['part-10.mp4','part-2.mp4','part-1.mp4'].map(name=>new File([],name));
 assert.deepEqual(sortClips(files).map(f=>f.name),['part-1.mp4','part-2.mp4','part-10.mp4']);assert.equal(files[0].name,'part-10.mp4');
});
test('compatibility signatures compare descriptor bytes including typed-array slices',()=>{
 const bytes=new Uint8Array([99,1,2,99]),base={codec:'avc1',codedWidth:1920,codedHeight:1080};
 assert.equal(configKey({...base,description:bytes.subarray(1,3)}),configKey({...base,description:new Uint8Array([1,2]).buffer}));
 assert.notEqual(configKey({...base,description:new Uint8Array([1,2])}),configKey({...base,description:new Uint8Array([1,3])}));
 assert.throws(()=>configKey(null),/missing decoder/);
});
test('procedural music is deterministic, bounded, faded and generated in small chunks',()=>{
 const a=ambienceSamples(3,1600,48000,10,.15),b=ambienceSamples(3,1600,48000,10,.15);
 assert.deepEqual(a,b);assert.equal(a.byteLength,6400);assert.ok(a.every(n=>Number.isFinite(n)&&Math.abs(n)<.3));assert.ok(a.some(n=>n!==0));
 assert.equal(ambienceSamples(0,1,48000,10,.15)[0],0);assert.equal(ambienceSamples(10,1,48000,10,.15)[0],0);
 assert.ok(ambienceSamples(3,1600,48000,10,0).every(n=>n===0));
});
